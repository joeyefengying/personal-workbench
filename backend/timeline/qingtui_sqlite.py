"""轻推 SQLite 直读 — 从 csp4.db 读取消息/会话, 不依赖 CDP 调试端口.

替代原 qingtui 模块依赖 CDP (调试端口 9222) 的方案.
数据源: ~/Library/Application Support/Qingtui/sqlite/{ME}/csp4.db
"""
import json
import re
import sqlite3
import time
from pathlib import Path

HOME = Path.home()
QT_DB = HOME / "Library/Application Support/Qingtui/sqlite/344548d972f44d799aeea39ae3e231ba/csp4.db"
ME = "344548d972f44d799aeea39ae3e231ba"

# @提及 识别 (别人点名我 / 全群通知)
MENTION_KEYWORDS = ["@张浩", "@我", "@所有人"]

# 工作群关键词 (与 weekly_collect.py 保持一致)
WORK_KEYWORDS = [
    "共享运营", "会计引擎", "财务", "低开", "低码",
    "平台组", "平台支撑", "基础框架", "流程引擎", "消息中心",
    "文件中心", "任务中心", "统一密码", "UX", "PRD",
    "测试", "联调", "部署", "发版", "攻坚",
    "主数据", "合同台账", "应付", "报账", "资产",
    "票据", "影像", "安全合规", "性能测试",
    "日报", "实施", "配置", "环境",
    "前端", "开发", "统建", "五矿", "应用架构",
    "智慧政企", "平台业务部", "核心研发",
    "财务管控", "财务组", "ACoding", "数据建模",
    "需求", "评审", "值班",
]


def db_exists() -> bool:
    return QT_DB.exists()


def _conn():
    if not db_exists():
        return None
    c = sqlite3.connect(str(QT_DB))
    c.row_factory = sqlite3.Row
    return c


def get_channels() -> dict:
    """返回 {chat_id: {name, type, member_count, ...}}"""
    c = _conn()
    if not c:
        return {}
    try:
        rows = c.execute(
            'SELECT id, name, type, member_count, "join", archived, domain_name, comment '
            "FROM channel_detail").fetchall()
        result = {}
        for r in rows:
            result[r["id"]] = {
                "name": r["name"] or "",
                "type": r["type"] or 0,
                "member_count": r["member_count"] or 0,
                "join": r["join"] or 0,
                "archived": r["archived"] or 0,
                "domain_name": r["domain_name"] or "",
                "comment": r["comment"] or "",
            }
        return result
    except Exception:
        return {}
    finally:
        c.close()


def _extract_body(content: str, body: str) -> str:
    """从消息提取纯文本. body 字段优先, 为空则解析 content JSON 的 body."""
    body = (body or "").strip()
    if body:
        return body
    content = (content or "").strip()
    if not content:
        return ""
    try:
        obj = json.loads(content)
        return str(obj.get("body", ""))
    except Exception:
        return ""


def _clean_body(body: str) -> str:
    """清理占位符和 HTML 标签."""
    body = re.sub(r'<[^>]+>', '', body)
    body = re.sub(r'\[图片\]|\[文件\]|\[协作文档\]|\[语音\]|\[视频\]|\[位置\]', '', body)
    return body.strip()


def iter_messages(start_ms: int, end_ms: int = None, mine_only: bool = True) -> list:
    """遍历所有 message 分片表, 返回 [{chat_id, from, to, ts, body, content}]"""
    c = _conn()
    if not c:
        return []
    end_ms = end_ms or (int(time.time() * 1000) + 1000)
    msgs = []
    try:
        for i in range(60):
            try:
                sql = f'SELECT msg_id, chat_id, "from", "to", create_time, body, content FROM message_{i} ' \
                      f'WHERE create_time>=? AND create_time<?'
                params = [start_ms, end_ms]
                if mine_only:
                    sql += ' AND "from"=?'
                    params.append(ME)
                sql += ' ORDER BY create_time'
                for r in c.execute(sql, params).fetchall():
                    msgs.append({
                        "msg_id": r["msg_id"],
                        "chat_id": r["chat_id"],
                        "from": r["from"],
                        "to": r["to"],
                        "ts": int(r["create_time"]),
                        "body": _clean_body(_extract_body(r["content"], r["body"])),
                        "content": r["content"] or "",
                    })
            except Exception:
                pass
    finally:
        c.close()
    return msgs


def list_sessions_sqlite(recent_days: int = 7) -> list:
    """模拟原 list_sessions: 返回最近活跃会话 [{cid, type, name, my_replies, last_ts}]"""
    channels = get_channels()
    since = int(time.time() * 1000) - recent_days * 24 * 3600 * 1000
    msgs = iter_messages(since, mine_only=False)

    # 按 chat_id 统计我的回复数和最后活跃时间
    agg = {}
    for m in msgs:
        cid = m["chat_id"]
        if cid not in agg:
            agg[cid] = {"my_replies": 0, "last_ts": 0}
        if m["from"] == ME:
            agg[cid]["my_replies"] += 1
        if m["ts"] > agg[cid]["last_ts"]:
            agg[cid]["last_ts"] = m["ts"]

    sessions = []
    for cid, ch in channels.items():
        if not ch["join"]:
            continue
        a = agg.get(cid, {"my_replies": 0, "last_ts": 0})
        sessions.append({
            "cid": cid,
            "type": ch["type"],
            "name": ch["name"],
            "member_count": ch["member_count"],
            "my_replies": a["my_replies"],
            "last_ts": a["last_ts"],
            "is_work": any(kw in ch["name"] for kw in WORK_KEYWORDS),
        })

    # 按最近活跃排序
    sessions.sort(key=lambda s: (-s["last_ts"], -s["my_replies"]))
    return sessions


def daily_summary_sqlite(date: str = None, cids: list = None) -> dict:
    """某天的每日总结 (从 SQLite 直读). 
    返回结构对齐前端 Qingtui.vue 期望:
      {ok, date, my_total, all_total, sessions, achievement:{top_themes, highlights}}
    """
    date = date or time.strftime("%Y-%m-%d")
    import datetime
    dt = datetime.datetime.strptime(date, "%Y-%m-%d")
    start_ms = int(dt.timestamp() * 1000)
    end_ms = start_ms + 24 * 3600 * 1000

    channels = get_channels()
    msgs = iter_messages(start_ms, end_ms, mine_only=False)
    my_msgs = [m for m in msgs if m["from"] == ME]

    # 别人 @我 / @所有人的消息 (需要我关注)
    mention_msgs = []
    for m in msgs:
        if m["from"] == ME:
            continue
        body = m["body"] or ""
        if any(kw in body for kw in MENTION_KEYWORDS):
            mention_msgs.append(m)

    # 过滤会话
    if cids:
        cid_set = set(cids)
        my_msgs = [m for m in my_msgs if m["chat_id"] in cid_set]
        mention_msgs = [m for m in mention_msgs if m["chat_id"] in cid_set]
        msgs = [m for m in msgs if m["chat_id"] in cid_set]

    # 按会话分组 (我的发言 + 别人@我的), 群内分三类
    def _kind_of(m):
        """判断消息类型: mention(@我) / at_all(@所有人) / mine(我发言)."""
        if m["from"] == ME:
            return "mine"
        body = m["body"] or ""
        if "@所有人" in body:
            return "at_all"
        return "mention"

    by_session = {}  # cid -> {session, mention:[], at_all:[], mine:[]}
    def _ensure(cid):
        if cid not in by_session:
            cname = channels.get(cid, {}).get("name", cid)
            by_session[cid] = {"session": cname, "mention": [], "at_all": [], "mine": []}
        return by_session[cid]

    for m in my_msgs:
        cname = channels.get(m["chat_id"], {}).get("name", m["chat_id"])
        if not any(kw in cname for kw in WORK_KEYWORDS):
            continue
        _ensure(m["chat_id"])["mine"].append(m)

    for m in mention_msgs:
        cname = channels.get(m["chat_id"], {}).get("name", m["chat_id"])
        if not any(kw in cname for kw in WORK_KEYWORDS):
            continue
        _ensure(m["chat_id"])[_kind_of(m)].append(m)

    # 组装 groups 列表 (按群总活跃度排序)
    def _fmt(ms):
        return [{"time": time.strftime("%H:%M", time.localtime(x["ts"] / 1000)),
                 "ts": x["ts"],
                 "text": x["body"][:500],
                 "msg_id": x.get("msg_id", ""),
                 "chat_id": x["chat_id"],
                 "from": x["from"]} for x in sorted(ms, key=lambda y: y["ts"])]

    groups = []
    for cid, info in by_session.items():
        mention = _fmt(info["mention"])
        at_all = _fmt(info["at_all"])
        mine = _fmt(info["mine"])
        total = len(mention) + len(at_all) + len(mine)
        groups.append({
            "session": info["session"],
            "cid": cid,
            "total": total,
            "mention": mention,      # @我
            "at_all": at_all,        # @所有人
            "mine": mine,            # 我发言
            "mention_count": len(mention),
            "at_all_count": len(at_all),
            "mine_count": len(mine),
        })

    # 排序: 有 @我 的群优先, 其次按总消息量
    groups.sort(key=lambda g: (-g["mention_count"], -g["total"]))

    # 兼容旧字段 (平铺 highlights + sessions)
    sessions_out = [{"session": g["session"], "cid": g["cid"], "count": g["total"]} for g in groups]
    highlights = []
    for g in groups:
        for kind, label in (("mention", "mention"), ("at_all", "at_all"), ("mine", "mine")):
            for h in g[kind]:
                highlights.append({"time": h["time"], "text": h["text"],
                                   "session": g["session"], "kind": kind})

    return {
        "ok": True,
        "date": date,
        "my_total": len(my_msgs),
        "all_total": len(msgs),
        "mention_total": len(mention_msgs),
        "groups": groups,
        "group_count": len(groups),
        "sessions": sessions_out,
        "achievement": {
            "top_themes": [[s["session"], s["count"]] for s in sessions_out[:10]],
            "highlights": highlights,
        },
        "source": "sqlite",
    }


def _load_chat_messages(chat_id: str) -> list:
    """加载某群全部消息 (按时间升序), 供上下文游标分页使用."""
    c = _conn()
    if not c:
        return []
    msgs = []
    try:
        for i in range(60):
            try:
                rows = c.execute(
                    f'SELECT msg_id, chat_id, "from", create_time, body, content FROM message_{i} '
                    f'WHERE chat_id=? ORDER BY create_time',
                    (chat_id,)).fetchall()
                for r in rows:
                    msgs.append({
                        "msg_id": r["msg_id"],
                        "from": r["from"],
                        "ts": int(r["create_time"]),
                        "body": _clean_body(_extract_body(r["content"], r["body"])),
                    })
            except Exception:
                pass
    finally:
        c.close()
    msgs.sort(key=lambda x: x["ts"])
    return msgs


def _fmt_msg(m: dict, is_target: bool = False) -> dict:
    return {
        "msg_id": m["msg_id"],
        "mine": m["from"] == ME,
        "time": time.strftime("%H:%M", time.localtime(m["ts"] / 1000)),
        "ts": m["ts"],
        "text": m["body"],
        "is_target": is_target,
    }


def message_context_sqlite(chat_id: str, ts: int, before: int = 20, after: int = 20) -> dict:
    """查询某条消息在会话中的上下文, 支持游标向前/向后翻页.

    chat_id: 会话 id, ts: 目标消息时间戳 (ms).
    返回目标消息前后各 before/after 条, 并给出 has_more_before/after + 游标 ts.
    """
    msgs = _load_chat_messages(chat_id)
    if not msgs:
        return {"ok": False, "messages": [], "has_more_before": False, "has_more_after": False}

    # 定位目标
    target_idx = 0
    for idx, m in enumerate(msgs):
        if m["ts"] == ts:
            target_idx = idx
            break
        if m["ts"] > ts:
            target_idx = max(0, idx - 1)
            break

    start = max(0, target_idx - before)
    end = min(len(msgs), target_idx + after + 1)
    ctx = msgs[start:end]

    return {
        "ok": True,
        "messages": [_fmt_msg(m, m["ts"] == ts) for m in ctx],
        "total": len(ctx),
        "target_ts": ts,
        "has_more_before": start > 0,
        "has_more_after": end < len(msgs),
        "before_cursor": msgs[start]["ts"] if start > 0 else None,
        "after_cursor": msgs[end - 1]["ts"] if end < len(msgs) else None,
    }


def message_context_page_sqlite(chat_id: str, cursor_ts: int, direction: str, limit: int = 30) -> dict:
    """按游标翻页: direction='before' 取 cursor_ts 之前的消息, 'after' 取之后的.

    返回消息 + has_more 标志 + 新游标.
    """
    msgs = _load_chat_messages(chat_id)
    if not msgs:
        return {"ok": False, "messages": [], "has_more_before": False, "has_more_after": False}

    if direction == "before":
        # 取 ts < cursor_ts 的最后 limit 条 (即向上翻)
        seg = [m for m in msgs if m["ts"] < cursor_ts]
        page = seg[-limit:] if seg else []
        has_more = len(seg) > limit
        new_cursor = page[0]["ts"] if page else None
        return {
            "ok": True, "messages": [_fmt_msg(m) for m in page],
            "total": len(page),
            "has_more_before": has_more, "has_more_after": False,
            "before_cursor": new_cursor, "after_cursor": None,
        }
    else:
        # 取 ts > cursor_ts 的前 limit 条 (向下翻)
        seg = [m for m in msgs if m["ts"] > cursor_ts]
        page = seg[:limit] if seg else []
        has_more = len(seg) > limit
        new_cursor = page[-1]["ts"] if page else None
        return {
            "ok": True, "messages": [_fmt_msg(m) for m in page],
            "total": len(page),
            "has_more_before": False, "has_more_after": has_more,
            "before_cursor": None, "after_cursor": new_cursor,
        }
