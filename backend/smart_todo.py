"""智能待办系统 — 从轻推消息中提取、评分、聚类待办项.

评分维度 (满分100):
  @提及 (30): @张浩=30, @所有人=15
  关键词 (25): 截止/尽快/确认/回复/帮忙/处理/提交/审批/评审/反馈...
  重复提 (20): 同话题多群/多天提到, count×5 max 20
  时效   (15): 24h=15, 48h=10, 72h=5, 7d=2
  学习   (10): 从确认/忽略历史中学习的模式加权

学习机制:
  confirm → 提取关键词/chat加权 +1
  ignore  → 提取关键词/chat加权 -1
  积累形成用户的「关注模式」

存储: SQLite (todo_db.sqlite3)
  todos 表: 待办项 (id, title, chat_name, score, source, status, ...)
  learning 表: 学习模式 (keyword, chat_name, weight, confirm_count, ignore_count)
"""

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
QT_DB = HOME / "Library/Application Support/Qingtui/sqlite/344548d972f44d799aeea39ae3e231ba/csp4.db"
ME = "344548d972f44d799aeea39ae3e231ba"
TODO_DB = Path(__file__).resolve().parent / "qingtui_data" / "todo_db.sqlite3"

# ── 评分关键词 ──
URGENCY_KEYWORDS = {
    # 高紧急 (每词+8)
    "截止": 8, "尽快": 8, "立即": 8, "马上": 8, "今天内": 8, "今晚": 8, "下班前": 8,
    "明天": 6, "本周": 6, "周一": 6, "周二": 6, "周三": 6, "周四": 6, "周五": 6,
    # 中等 (每词+5)
    "确认": 5, "回复": 5, "帮忙": 5, "处理": 5, "提交": 5, "审批": 5, "评审": 5,
    "反馈": 5, "检查": 5, "更新": 5, "修改": 5, "修复": 5, "完成": 5, "安排": 5,
    "对接": 5, "协调": 5, "联调": 5, "测试": 5, "部署": 5, "发版": 5, "值班": 5,
    # 低 (每词+3)
    "看看": 3, "了解": 3, "关注": 3, "注意": 3, "同步": 3, "讨论": 3, "计划": 3,
    "梳理": 3, "整理": 3, "准备": 3, "梳理": 3, "评估": 3, "核实": 3, "核对": 3,
}

# 话题聚类关键词 (用于合并同话题消息)
TOPIC_KEYWORDS = [
    "发版", "部署", " hotfix", "分支", "环境", "准出", "上线",
    "主数据", "一致性", "数据同步", "对账",
    "权限", "账号", "登录", "安全",
    "前端", "组件", "页面", "样式", "UX",
    "应付", "报账", "合同", "票据", "影像", "资产",
    "共享运营", "低开", "低码", "平台",
    "ONES", "缺陷", "bug", "测试",
    "需求", "PRD", "评审", "详设",
    "实施", "配置", "联调", "攻坚",
]


def _conn():
    TODO_DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(TODO_DB))
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT DEFAULT '',
        chat_id TEXT DEFAULT '',
        chat_name TEXT DEFAULT '',
        msg_id TEXT DEFAULT '',
        msg_ts INTEGER DEFAULT 0,
        score INTEGER DEFAULT 0,
        score_detail TEXT DEFAULT '',
        topic TEXT DEFAULT '',
        source TEXT DEFAULT 'auto',
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT '',
        updated_at TEXT DEFAULT '',
        confirmed_at TEXT DEFAULT '',
        ignored_at TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS learning (
        keyword TEXT PRIMARY KEY,
        weight REAL DEFAULT 0,
        confirm_count INTEGER DEFAULT 0,
        ignore_count INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS learning_chat (
        chat_name TEXT PRIMARY KEY,
        weight REAL DEFAULT 0,
        confirm_count INTEGER DEFAULT 0,
        ignore_count INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT ''
    )""")
    c.commit()
    return c


def _load_channels() -> dict:
    if not QT_DB.exists():
        return {}
    try:
        c = sqlite3.connect(str(QT_DB))
        c.row_factory = sqlite3.Row
        channels = {}
        for r in c.execute("SELECT id, name FROM channel_detail").fetchall():
            channels[r["id"]] = r["name"]
        for r in c.execute("SELECT id, name FROM collaboration").fetchall():
            channels[r["id"]] = r["name"]
        c.close()
        return channels
    except Exception:
        return {}


def _resolve_name(chat_id, channels):
    if chat_id in channels:
        return channels[chat_id]
    for cid, name in channels.items():
        if cid.startswith(chat_id):
            return name
    return chat_id[:12]


def _extract_body(content_str):
    """从消息 content JSON 提取纯文本 body."""
    if not content_str:
        return "", []
    try:
        data = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        return content_str[:500], []

    msg = data.get("msg", {})
    body = data.get("body", "") or msg.get("body", "")

    # msgInfos 多条
    if msg.get("msgInfos"):
        parts = []
        for info in msg["msgInfos"]:
            if isinstance(info, dict) and info.get("body"):
                parts.append(info["body"])
        if parts:
            body = " ".join(parts)

    # @提及信息
    at_info = []
    if msg.get("at"):
        at_all = any(a.get("uid") == "all" or a.get("index") == "1-4" for a in msg.get("at", []))
        at_me = any(a.get("uid") == ME for a in msg.get("at", []))
        if at_me:
            at_info.append("@me")
        if at_all:
            at_info.append("@all")

    return body[:500], at_info


def _detect_topic(body):
    """检测消息所属话题."""
    body_lower = body.lower()
    topics = []
    for kw in TOPIC_KEYWORDS:
        if kw.lower() in body_lower:
            topics.append(kw.strip())
    return topics[0] if topics else "其他"


def _score_message(body, at_info, msg_ts, chat_name, learning_kw, learning_chat):
    """评分单条消息, 返回 (score, detail_dict)."""
    now_ms = int(time.time() * 1000)
    detail = {}

    # 1. @提及 (max 30)
    at_score = 0
    if "@me" in at_info:
        at_score = 30
    elif "@all" in at_info:
        at_score = 15
    detail["at"] = at_score

    # 2. 关键词 (max 25)
    kw_score = 0
    matched_kw = []
    for kw, weight in URGENCY_KEYWORDS.items():
        if kw in body:
            kw_score += weight
            matched_kw.append(kw)
    kw_score = min(kw_score, 25)
    detail["kw"] = kw_score
    detail["matched_kw"] = matched_kw

    # 3. 重复提 (max 20) — 在聚类阶段计算, 这里先 0
    detail["repeat"] = 0

    # 4. 时效 (max 15)
    age_hours = (now_ms - msg_ts) / 3600000
    if age_hours < 24:
        time_score = 15
    elif age_hours < 48:
        time_score = 10
    elif age_hours < 72:
        time_score = 5
    elif age_hours < 168:
        time_score = 2
    else:
        time_score = 0
    detail["time"] = time_score

    # 5. 学习权重 (max 10)
    learn_score = 0
    for kw in matched_kw:
        learn_score += learning_kw.get(kw, 0)
    learn_score += learning_chat.get(chat_name, 0)
    learn_score = max(-5, min(learn_score, 10))
    detail["learn"] = round(learn_score, 1)

    total = at_score + kw_score + 0 + time_score + learn_score
    detail["total"] = round(total)

    return total, detail


def _cluster_messages(messages, min_score=20):
    """将相关消息聚合成待办项 (按 topic + chat 聚合)."""
    clusters = {}
    for m in messages:
        topic = m["topic"]
        chat = m["chat_name"]
        key = f"{topic}@{chat}"
        if key not in clusters:
            clusters[key] = {
                "topic": topic,
                "chat_name": chat,
                "chat_id": m["chat_id"],
                "messages": [],
                "max_score": 0,
                "score_detail": {},
            }
        clusters[key]["messages"].append(m)
        if m["score"] > clusters[key]["max_score"]:
            clusters[key]["max_score"] = m["score"]
            clusters[key]["score_detail"] = m["score_detail"]

    # 重复提分: 同 cluster 内消息数 × 5, max 20
    for key, cluster in clusters.items():
        repeat = min(len(cluster["messages"]) * 5, 20)
        cluster["score_detail"]["repeat"] = repeat
        cluster["max_score"] += repeat

    # 过滤低分 + 排序
    result = []
    for cluster in clusters.values():
        if cluster["max_score"] >= min_score:
            # 取最高分消息的 body 作为标题
            best_msg = max(cluster["messages"], key=lambda m: m["score"])
            title = best_msg["body"][:120]
            result.append({
                "title": title,
                "body": best_msg["body"],
                "topic": cluster["topic"],
                "chat_name": cluster["chat_name"],
                "chat_id": cluster["chat_id"],
                "msg_id": best_msg.get("msg_id", ""),
                "msg_ts": best_msg["msg_ts"],
                "score": cluster["max_score"],
                "score_detail": cluster["score_detail"],
                "related_count": len(cluster["messages"]),
                "time_str": best_msg.get("time_str", ""),
                "source": "auto",
            })

    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def analyze_todos(days=3, min_score=20, max_results=50):
    """扫描最近 N 天消息, 评分+聚类, 返回待办列表."""
    if not QT_DB.exists():
        return {"ok": False, "error": "轻推数据库不存在"}

    channels = _load_channels()
    conn = _conn()

    # 加载学习模式
    learning_kw = {}
    for row in conn.execute("SELECT keyword, weight FROM learning").fetchall():
        learning_kw[row["keyword"]] = row["weight"]
    learning_chat = {}
    for row in conn.execute("SELECT chat_name, weight FROM learning_chat").fetchall():
        learning_chat[row["chat_name"]] = row["weight"]

    now_ms = int(time.time() * 1000)
    start = now_ms - days * 24 * 3600 * 1000

    qt_conn = sqlite3.connect(str(QT_DB))
    qt_conn.row_factory = sqlite3.Row
    qt_cur = qt_conn.cursor()

    all_msgs = []
    for i in range(20):
        try:
            rows = qt_cur.execute(
                f"SELECT msg_id, chat_id, `from`, create_time, content FROM message_{i} "
                f"WHERE create_time >= ? AND content IS NOT NULL "
                f"AND content != '' ORDER BY create_time DESC",
                (start,)
            ).fetchall()
            for row in rows:
                body, at_info = _extract_body(row["content"])
                if not body or len(body) < 5:
                    continue
                # 排除纯图片/文件消息
                if body in ("图片", "图片消息", "[图片]", "[文件]"):
                    continue
                cid = row["chat_id"]
                cname = _resolve_name(cid, channels)
                msg_ts = row["create_time"]
                ts_str = datetime.fromtimestamp(msg_ts / 1000).strftime("%Y-%m-%d %H:%M")
                score, detail = _score_message(
                    body, at_info, msg_ts, cname, learning_kw, learning_chat
                )
                topic = _detect_topic(body)
                all_msgs.append({
                    "msg_id": row["msg_id"],
                    "chat_id": cid,
                    "chat_name": cname,
                    "body": body,
                    "at_info": at_info,
                    "msg_ts": msg_ts,
                    "time_str": ts_str,
                    "score": score,
                    "score_detail": detail,
                    "topic": topic,
                })
        except sqlite3.OperationalError:
            continue

    qt_conn.close()

    # 聚类
    todos = _cluster_messages(all_msgs, min_score=min_score)
    todos = todos[:max_results]

    # 保存到 DB (替换旧的 pending auto todos, 保留用户已确认/已忽略的)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 查询已确认/已忽略的 msg_id, 这些不再重新插入
    done_msg_ids = set()
    for row in conn.execute(
        "SELECT DISTINCT msg_id FROM todos WHERE source = 'auto' AND status IN ('confirmed', 'ignored')"
    ).fetchall():
        if row["msg_id"]:
            done_msg_ids.add(row["msg_id"])
    conn.execute("DELETE FROM todos WHERE source = 'auto' AND status = 'pending'")
    skipped = 0
    for t in todos:
        if t["msg_id"] and t["msg_id"] in done_msg_ids:
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO todos (title, body, chat_id, chat_name, msg_id, msg_ts, "
            "score, score_detail, topic, source, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?)",
            (t["title"], t["body"], t["chat_id"], t["chat_name"], t["msg_id"],
             t["msg_ts"], t["score"], json.dumps(t["score_detail"], ensure_ascii=False),
             t["topic"], "auto", now_str, now_str)
        )
    conn.commit()

    # 统计
    by_topic = {}
    by_chat = {}
    for t in todos:
        by_topic[t["topic"]] = by_topic.get(t["topic"], 0) + 1
        by_chat[t["chat_name"]] = by_chat.get(t["chat_name"], 0) + 1

    result = {
        "ok": True,
        "total": len(todos),
        "todos": todos,
        "by_topic": dict(sorted(by_topic.items(), key=lambda x: -x[1])),
        "by_chat": dict(sorted(by_chat.items(), key=lambda x: -x[1])),
        "scanned_messages": len(all_msgs),
        "days": days,
    }
    conn.close()
    return result


def list_todos(status="pending", limit=50):
    """读取已存储的待办列表."""
    conn = _conn()
    if status == "all":
        rows = conn.execute(
            "SELECT * FROM todos ORDER BY score DESC, created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM todos WHERE status = ? ORDER BY score DESC, created_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()

    todos = []
    for r in rows:
        todos.append({
            "id": r["id"],
            "title": r["title"],
            "body": r["body"],
            "chat_name": r["chat_name"],
            "chat_id": r["chat_id"],
            "msg_id": r["msg_id"],
            "msg_ts": r["msg_ts"],
            "score": r["score"],
            "score_detail": json.loads(r["score_detail"]) if r["score_detail"] else {},
            "topic": r["topic"],
            "source": r["source"],
            "status": r["status"],
            "created_at": r["created_at"],
            "time_str": datetime.fromtimestamp(r["msg_ts"] / 1000).strftime("%Y-%m-%d %H:%M") if r["msg_ts"] else "",
        })
    conn.close()
    return {"ok": True, "total": len(todos), "todos": todos}


def operate_todo(todo_id, action):
    """操作待办: confirm / ignore / reopen / delete."""
    conn = _conn()
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "待办不存在"}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_map = {
        "confirm": ("confirmed", "confirmed_at"),
        "ignore": ("ignored", "ignored_at"),
        "reopen": ("pending", None),
        "delete": ("deleted", None),
    }
    if action not in status_map:
        conn.close()
        return {"ok": False, "error": f"未知操作: {action}"}

    new_status, ts_col = status_map[action]
    conn.execute(
        "UPDATE todos SET status = ?, updated_at = ?" +
        (f", {ts_col} = ?" if ts_col else "") +
        " WHERE id = ?",
        (new_status, now_str) + ((now_str,) if ts_col else ()) + (todo_id,)
    )

    # 学习机制: confirm/ignore 时提取关键词调整权重
    if action in ("confirm", "ignore"):
        body = row["body"]
        chat_name = row["chat_name"]
        detail = json.loads(row["score_detail"]) if row["score_detail"] else {}
        matched_kw = detail.get("matched_kw", [])

        delta = 1 if action == "confirm" else -1
        col = "confirm_count" if action == "confirm" else "ignore_count"

        for kw in matched_kw:
            existing = conn.execute(
                "SELECT weight, confirm_count, ignore_count FROM learning WHERE keyword = ?",
                (kw,)
            ).fetchone()
            if existing:
                new_weight = max(-5, min(existing["weight"] + delta * 0.5, 10))
                new_count = existing[col] + 1
                conn.execute(
                    "UPDATE learning SET weight = ?, {} = ?, updated_at = ? WHERE keyword = ?".format(col),
                    (new_weight, new_count, now_str, kw)
                )
            else:
                conn.execute(
                    "INSERT INTO learning (keyword, weight, {}, updated_at) VALUES (?, ?, ?, ?)".format(col),
                    (kw, delta * 0.5, 1, now_str)
                )

        # chat 权重
        if chat_name:
            existing = conn.execute(
                "SELECT weight, confirm_count, ignore_count FROM learning_chat WHERE chat_name = ?",
                (chat_name,)
            ).fetchone()
            if existing:
                new_weight = max(-5, min(existing["weight"] + delta * 0.3, 5))
                new_count = existing[col] + 1
                conn.execute(
                    "UPDATE learning_chat SET weight = ?, {} = ?, updated_at = ? WHERE chat_name = ?".format(col),
                    (new_weight, new_count, now_str, chat_name)
                )
            else:
                conn.execute(
                    "INSERT INTO learning_chat (chat_name, weight, {}, updated_at) VALUES (?, ?, ?, ?)".format(col),
                    (chat_name, delta * 0.3, 1, now_str)
                )

    conn.commit()
    conn.close()
    return {"ok": True, "action": action, "todo_id": todo_id, "new_status": new_status}


def add_manual_todo(title, chat_name="", body="", topic="手动"):
    """手动添加待办."""
    conn = _conn()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_ts = int(time.time() * 1000)
    cur = conn.execute(
        "INSERT INTO todos (title, body, chat_name, msg_ts, score, score_detail, "
        "topic, source, status, created_at, updated_at) "
        "VALUES (?,?,?,?, 100, '{\"manual\":100}', ?, 'manual', 'pending', ?, ?)",
        (title, body, chat_name, now_ts, topic, now_str, now_str)
    )
    conn.commit()
    todo_id = cur.lastrowid
    conn.close()
    return {"ok": True, "todo_id": todo_id, "title": title}


def get_learning():
    """获取学习模式 (关键词权重 + 群权重)."""
    conn = _conn()
    kw_rows = conn.execute(
        "SELECT keyword, weight, confirm_count, ignore_count FROM learning "
        "ORDER BY ABS(weight) DESC LIMIT 50"
    ).fetchall()
    chat_rows = conn.execute(
        "SELECT chat_name, weight, confirm_count, ignore_count FROM learning_chat "
        "ORDER BY ABS(weight) DESC LIMIT 30"
    ).fetchall()
    conn.close()

    return {
        "ok": True,
        "keywords": [dict(r) for r in kw_rows],
        "chats": [dict(r) for r in chat_rows],
    }
