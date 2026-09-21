"""轻推群文档提取 — 从 csp4.db 消息中提取在线文档/文件/链接.

按权重排序, URL 去重聚合, 自动让重要文档浮上来, 旧的沉下去.
"""

import json
import math
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
QT_DB = HOME / "Library/Application Support/Qingtui/sqlite/344548d972f44d799aeea39ae3e231ba/csp4.db"
ME = "344548d972f44d799aeea39ae3e231ba"

# ── 文档类型分类 ──
TYPE_LABELS = {
    "article": "企业号文章",
    "drive": "云盘文档",
    "excel": "Excel",
    "pdf": "PDF",
    "word": "Word",
    "markdown": "Markdown",
    "tencent_doc": "腾讯文档",
    "ones": "ONES任务",
    "oa": "OA系统",
    "minmetals": "五矿系统",
    "link": "其他链接",
    "file": "文件",
}

# 默认排除的类型 (企业号文章都是新闻, 不重要)
DEFAULT_EXCLUDE_TYPES = {"article"}

# 噪音 URL 关键词
NOISE_URLS = ["qtfile.qingtui.com", "oa.qingtui.com/sign", "oa.qingtui.cn/sign"]

# ── 权重规则 ──
# 文档类型权重: 工作相关 > 新闻 > 链接
TYPE_WEIGHTS = {
    "ones": 1.3,       # ONES任务, 最重要
    "excel": 1.2,      # Excel, 工作文档
    "drive": 1.0,      # 云盘文档
    "word": 1.0,       # Word
    "tencent_doc": 1.0, # 腾讯文档
    "minmetals": 1.1,  # 五矿系统
    "oa": 1.0,         # OA系统
    "pdf": 0.9,        # PDF, 可能是参考资料
    "markdown": 0.8,
    "file": 0.7,       # 通用文件
    "link": 0.5,       # 随手转的链接
    "article": 0.1,    # 企业号文章(默认排除, 权重最低)
}


def _classify(url: str, content_type: str = "", title: str = "") -> str | None:
    if not url:
        return None
    if any(n in url for n in NOISE_URLS):
        return None
    if "web.qingtui.com/team/servicemng/getArticle" in url:
        return "article"
    if "web.qingtui.com/drive/preview" in url:
        return "drive"
    if "docs.qq.com" in url:
        return "tencent_doc"
    if "ones.cisdigital" in url:
        return "ones"
    if "oa.qingtui.com" in url:
        return "oa"
    if "minmetals.com.cn" in url:
        return "minmetals"
    if "qtfile.qingtui.com" in url:
        if content_type:
            if "pdf" in content_type:
                return "pdf"
            if "spreadsheet" in content_type or "excel" in content_type or "xls" in content_type:
                return "excel"
            if "word" in content_type or "document" in content_type:
                return "word"
            if "markdown" in content_type:
                return "markdown"
        if title and any(title.lower().endswith(ext) for ext in [".xlsx", ".xls", ".pdf", ".doc", ".docx", ".md", ".ppt", ".pptx"]):
            return "file"
        return None
    if url.startswith("http"):
        return "link"
    return None


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


def _resolve_chat_name(chat_id: str, channels: dict) -> str:
    if chat_id in channels:
        return channels[chat_id]
    for cid, name in channels.items():
        if cid.startswith(chat_id):
            return name
    return chat_id[:12] if len(chat_id) > 12 else chat_id


def _extract_from_msg(msg: dict, chat_id: str, chat_name: str,
                      from_id: str, create_time: int) -> list[dict]:
    """从单条消息的 msg 对象提取文档."""
    docs = []
    ts_str = datetime.fromtimestamp(create_time / 1000).strftime("%Y-%m-%d %H:%M")
    date_str = ts_str[:10]

    def _make_doc(url, title, t):
        return {
            "url": url,
            "title": title,
            "type": t,
            "type_label": TYPE_LABELS.get(t, t),
            "chat_id": chat_id,
            "chat_name": chat_name,
            "from": from_id,
            "is_me": from_id == ME,
            "time": create_time,
            "time_str": ts_str,
            "date": date_str,
        }

    # 1. bodyUrl — 企业号文章
    body_url = msg.get("bodyUrl", "")
    if body_url:
        t = _classify(body_url)
        if t:
            docs.append(_make_doc(body_url, msg.get("title", "") or msg.get("body", "")[:80], t))

    # 2. url + name — 文件/云盘
    file_url = msg.get("url", "")
    file_name = msg.get("name", "")
    ct = msg.get("contentType", "")
    if file_url and file_name:
        t = _classify(file_url, ct, file_name)
        if t:
            docs.append(_make_doc(file_url, file_name, t))

    # 3. title + url/linkList — 卡片消息
    card_title = msg.get("title", "")
    card_url = msg.get("url", "")
    if card_title and not card_url:
        for link in (msg.get("linkList") or []):
            if isinstance(link, dict) and link.get("url"):
                card_url = link["url"]
                break
    if card_title and card_url:
        t = _classify(card_url, "", card_title)
        if t:
            docs.append(_make_doc(card_url, card_title, t))

    # 4. msgInfos 里的文本 URL
    for info in (msg.get("msgInfos") or []):
        if not isinstance(info, dict):
            continue
        body = info.get("body", "")
        for url in re.findall(r"https?://[^\s<>\"')]+", body):
            t = _classify(url)
            if t:
                docs.append(_make_doc(url, "", t))

    # 5. refMsg 里的引用文档
    ref_msg = msg.get("refMsg", {})
    if isinstance(ref_msg, dict):
        ref_url = ref_msg.get("url", "")
        ref_name = ref_msg.get("name", "")
        ref_ct = ref_msg.get("contentType", "")
        if ref_url and ref_name:
            t = _classify(ref_url, ref_ct, ref_name)
            if t:
                d = _make_doc(ref_url, ref_name, t)
                d["from_ref"] = True
                docs.append(d)

    return docs


def _calc_weight(doc: dict, now_ms: int) -> float:
    """计算单个文档的权重分数.

    规则:
      - 基础分: 类型权重 × 10
      - 提及次数: 每被分享一次 +3 (跨群累加)
      - 跨群传播: 2群 +5, 3群 +12, 4+群 +20
      - 我发的: +2
      - 时效衰减: 今天×1.0, 1天前×0.85, 2天前×0.7, 3天前×0.55, 4天前×0.4, 5+天×0.25
    """
    # 基础分
    type_w = TYPE_WEIGHTS.get(doc["type"], 0.5)
    base = type_w * 10

    # 提及次数
    mentions = doc.get("mention_count", 1)
    mention_score = mentions * 3

    # 跨群传播
    chat_count = len(doc.get("chat_ids", []))
    spread_score = 0
    if chat_count >= 4:
        spread_score = 20
    elif chat_count >= 3:
        spread_score = 12
    elif chat_count >= 2:
        spread_score = 5

    # 我发的
    mine_score = 2 if doc.get("has_me") else 0

    # 时效衰减
    age_hours = (now_ms - doc["time"]) / (1000 * 3600)
    if age_hours < 24:
        decay = 1.0
    elif age_hours < 48:
        decay = 0.85
    elif age_hours < 72:
        decay = 0.7
    elif age_hours < 96:
        decay = 0.55
    elif age_hours < 120:
        decay = 0.4
    else:
        decay = 0.25

    raw = base + mention_score + spread_score + mine_score
    return round(raw * decay, 1)


def extract_docs(days: int = 7, chat_id: str = "",
                 doc_type: str = "", date: str = "",
                 exclude_types: str = "article") -> dict:
    """提取最近 N 天的群文档, 按权重排序.

    Args:
        days: 最近多少天 (默认7)
        chat_id: 筛选指定群 (可选)
        doc_type: 筛选文档类型 (可选)
        date: 筛选某一天 YYYY-MM-DD (可选, 优先于 days)
        exclude_types: 排除的类型, 逗号分隔 (默认 "article")

    Returns:
        {ok, total, docs: [...], grouped: {...}, by_date, by_chat, by_type, type_labels}
    """
    if not QT_DB.exists():
        return {"ok": False, "error": "轻推数据库不存在"}

    channels = _load_channels()
    now_ms = int(datetime.now().timestamp() * 1000)

    if date:
        start = int(datetime.strptime(date, "%Y-%m-%d").timestamp() * 1000)
        end = start + 24 * 3600 * 1000
    else:
        end = now_ms
        start = end - days * 24 * 3600 * 1000

    # 排除类型集合
    excluded = set()
    if exclude_types:
        excluded = {t.strip() for t in exclude_types.split(",") if t.strip()}

    # 收集所有原始文档 (不去重, 保留每次提及)
    raw_docs = []

    conn = sqlite3.connect(str(QT_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    for i in range(20):
        try:
            if chat_id:
                rows = cur.execute(
                    f"SELECT chat_id, `from`, create_time, content FROM message_{i} "
                    f"WHERE create_time >= ? AND create_time < ? AND chat_id = ? "
                    f"AND content LIKE '%http%' ORDER BY create_time DESC",
                    (start, end, chat_id)
                ).fetchall()
            else:
                rows = cur.execute(
                    f"SELECT chat_id, `from`, create_time, content FROM message_{i} "
                    f"WHERE create_time >= ? AND create_time < ? "
                    f"AND content LIKE '%http%' ORDER BY create_time DESC",
                    (start, end)
                ).fetchall()

            for row in rows:
                content_str = row["content"]
                if not content_str:
                    continue
                try:
                    data = json.loads(content_str)
                except (json.JSONDecodeError, TypeError):
                    # 纯文本消息
                    for url in re.findall(r"https?://[^\s<>\"')]+", content_str):
                        t = _classify(url)
                        if t:
                            ts = row["create_time"]
                            ts_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
                            cid = row["chat_id"]
                            raw_docs.append({
                                "url": url,
                                "title": "",
                                "type": t,
                                "type_label": TYPE_LABELS.get(t, t),
                                "chat_id": cid,
                                "chat_name": _resolve_chat_name(cid, channels),
                                "from": row["from"],
                                "is_me": row["from"] == ME,
                                "time": ts,
                                "time_str": ts_str,
                                "date": ts_str[:10],
                            })
                    continue

                msg = data.get("msg", {})
                if not isinstance(msg, dict):
                    continue

                cid = row["chat_id"]
                cname = _resolve_chat_name(cid, channels)
                docs = _extract_from_msg(msg, cid, cname, row["from"], row["create_time"])
                raw_docs.extend(docs)

        except sqlite3.OperationalError:
            continue

    conn.close()

    # 按类型过滤
    if doc_type:
        raw_docs = [d for d in raw_docs if d["type"] == doc_type]

    # 排除指定类型 (默认排除企业号文章)
    if excluded:
        raw_docs = [d for d in raw_docs if d["type"] not in excluded]

    # ── URL 聚合: 相同 URL 的文档合并, 计算提及次数和跨群数 ──
    url_map = {}  # url → 聚合后的 doc

    for d in raw_docs:
        url = d["url"]
        if url not in url_map:
            # 第一次见到这个 URL
            agg = {
                "url": url,
                "title": d["title"],
                "type": d["type"],
                "type_label": d["type_label"],
                "time": d["time"],       # 最近一次提及时间
                "time_str": d["time_str"],
                "date": d["date"],
                "first_time": d["time"],  # 最早提及时间
                "first_time_str": d["time_str"],
                "chat_ids": set(),        # 来源群集合
                "chat_names": [],         # 来源群名列表
                "mention_count": 0,       # 总提及次数
                "has_me": False,          # 是否包含我发的
                "sources": [],            # 每次提及的详情
            }
            url_map[url] = agg
        else:
            agg = url_map[url]

        # 更新最近时间
        if d["time"] > agg["time"]:
            agg["time"] = d["time"]
            agg["time_str"] = d["time_str"]
            agg["date"] = d["date"]
            # 用最新的标题 (有时旧消息标题为空)
            if d["title"]:
                agg["title"] = d["title"]

        # 更新最早时间
        if d["time"] < agg["first_time"]:
            agg["first_time"] = d["time"]
            agg["first_time_str"] = d["time_str"]

        # 累加提及
        agg["mention_count"] += 1
        agg["chat_ids"].add(d["chat_id"])
        if d["chat_name"] not in agg["chat_names"]:
            agg["chat_names"].append(d["chat_name"])
        if d["is_me"]:
            agg["has_me"] = True

        # 记录来源 (最多保留 5 条)
        if len(agg["sources"]) < 5:
            agg["sources"].append({
                "chat_name": d["chat_name"],
                "time_str": d["time_str"],
                "is_me": d["is_me"],
            })

    # 计算权重并转为列表
    all_docs = []
    for url, agg in url_map.items():
        agg["chat_count"] = len(agg["chat_ids"])
        agg["weight"] = _calc_weight(agg, now_ms)
        # set → list (JSON 序列化)
        agg["chat_ids"] = sorted(agg["chat_ids"])
        all_docs.append(agg)

    # 按权重排序 (高在前), 权重相同按时间 (新在前)
    all_docs.sort(key=lambda d: (d["weight"], d["time"]), reverse=True)

    # 聚合统计
    by_date = {}
    by_chat = {}
    by_type = {}
    for d in all_docs:
        by_date[d["date"]] = by_date.get(d["date"], 0) + 1
        for cn in d["chat_names"]:
            by_chat[cn] = by_chat.get(cn, 0) + 1
        by_type[d["type"]] = by_type.get(d["type"], 0) + 1

    # 按天分组 (权重排序)
    grouped = {}
    for d in all_docs:
        grouped.setdefault(d["date"], []).append(d)

    return {
        "ok": True,
        "total": len(all_docs),
        "docs": all_docs,
        "grouped": grouped,
        "by_date": dict(sorted(by_date.items(), reverse=True)),
        "by_chat": dict(sorted(by_chat.items(), key=lambda x: -x[1])),
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "type_labels": TYPE_LABELS,
    }
