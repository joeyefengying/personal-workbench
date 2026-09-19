"""轻推群文档提取 — 从 csp4.db 消息中提取在线文档/文件/链接.

按天聚合, 按群分类, 帮用户快速找到需要关注的群文档.
"""

import json
import re
import sqlite3
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

# 排除的文档类型 (纯图片/截图不收)
EXCLUDE_TYPES = {"file"}  # file 类型默认排除(多为截图), 但有文件名的 excel/pdf/word 保留

# 噪音 URL 关键词
NOISE_URLS = ["qtfile.qingtui.com", "oa.qingtui.com/sign", "oa.qingtui.cn/sign"]


def _classify(url: str, content_type: str = "", title: str = "") -> str | None:
    if not url:
        return None
    # 排除签到/打卡
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
        # 有 title/文件名的保留
        if title and any(title.lower().endswith(ext) for ext in [".xlsx", ".xls", ".pdf", ".doc", ".docx", ".md", ".ppt", ".pptx"]):
            return "file"
        return None  # 纯图片/截图不要
    if url.startswith("http"):
        return "link"
    return None


def _load_channels() -> dict:
    """加载群ID→群名映射 (channel_detail 群 + collaboration 应用号)."""
    if not QT_DB.exists():
        return {}
    try:
        c = sqlite3.connect(str(QT_DB))
        c.row_factory = sqlite3.Row
        channels = {}
        # 1. 群聊
        for r in c.execute("SELECT id, name FROM channel_detail").fetchall():
            channels[r["id"]] = r["name"]
        # 2. 应用号/企业号 (id 是纯数字)
        for r in c.execute("SELECT id, name FROM collaboration").fetchall():
            channels[r["id"]] = r["name"]
        c.close()
        return channels
    except Exception:
        return {}


def _resolve_chat_name(chat_id: str, channels: dict) -> str:
    """解析群名: 精确匹配 → 前缀匹配 → 截断 ID."""
    if chat_id in channels:
        return channels[chat_id]
    # chat_id 可能是截断的 (8位), collaboration.id 是 10 位
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

    # 1. bodyUrl — 企业号文章
    body_url = msg.get("bodyUrl", "")
    if body_url:
        t = _classify(body_url)
        if t:
            docs.append({
                "url": body_url,
                "title": msg.get("title", "") or msg.get("body", "")[:80],
                "type": t,
                "type_label": TYPE_LABELS.get(t, t),
                "chat_id": chat_id,
                "chat_name": chat_name,
                "from": from_id,
                "is_me": from_id == ME,
                "time": create_time,
                "time_str": ts_str,
                "date": date_str,
            })

    # 2. url + name — 文件/云盘
    file_url = msg.get("url", "")
    file_name = msg.get("name", "")
    ct = msg.get("contentType", "")
    if file_url and file_name:
        t = _classify(file_url, ct, file_name)
        if t:
            docs.append({
                "url": file_url,
                "title": file_name,
                "type": t,
                "type_label": TYPE_LABELS.get(t, t),
                "chat_id": chat_id,
                "chat_name": chat_name,
                "from": from_id,
                "is_me": from_id == ME,
                "time": create_time,
                "time_str": ts_str,
                "date": date_str,
            })

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
            docs.append({
                "url": card_url,
                "title": card_title,
                "type": t,
                "type_label": TYPE_LABELS.get(t, t),
                "chat_id": chat_id,
                "chat_name": chat_name,
                "from": from_id,
                "is_me": from_id == ME,
                "time": create_time,
                "time_str": ts_str,
                "date": date_str,
            })

    # 4. msgInfos 里的文本 URL
    for info in (msg.get("msgInfos") or []):
        if not isinstance(info, dict):
            continue
        body = info.get("body", "")
        for url in re.findall(r"https?://[^\s<>\"')]+", body):
            t = _classify(url)
            if t:
                docs.append({
                    "url": url,
                    "title": "",
                    "type": t,
                    "type_label": TYPE_LABELS.get(t, t),
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "from": from_id,
                    "is_me": from_id == ME,
                    "time": create_time,
                    "time_str": ts_str,
                    "date": date_str,
                })

    # 5. refMsg 里的引用文档 (别人转发/回复的文档)
    ref_msg = msg.get("refMsg", {})
    if isinstance(ref_msg, dict):
        ref_url = ref_msg.get("url", "")
        ref_name = ref_msg.get("name", "")
        ref_ct = ref_msg.get("contentType", "")
        if ref_url and ref_name:
            t = _classify(ref_url, ref_ct, ref_name)
            if t:
                docs.append({
                    "url": ref_url,
                    "title": ref_name,
                    "type": t,
                    "type_label": TYPE_LABELS.get(t, t),
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "from": from_id,
                    "is_me": from_id == ME,
                    "time": create_time,
                    "time_str": ts_str,
                    "date": date_str,
                    "from_ref": True,
                })

    return docs


def extract_docs(days: int = 7, chat_id: str = "",
                 doc_type: str = "", date: str = "") -> dict:
    """提取最近 N 天的群文档.

    Args:
        days: 最近多少天 (默认7)
        chat_id: 筛选指定群 (可选)
        doc_type: 筛选文档类型 (可选)
        date: 筛选某一天 YYYY-MM-DD (可选, 优先于 days)

    Returns:
        {ok, total, docs: [...], by_date: {...}, by_chat: {...}, by_type: {...}}
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

    all_docs = []
    seen_urls = set()  # 去重

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
                            dedup = f"{url}:{cid}"
                            if dedup in seen_urls:
                                continue
                            seen_urls.add(dedup)
                            all_docs.append({
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
                for d in docs:
                    dedup = f"{d['url']}:{cid}"
                    if dedup in seen_urls:
                        continue
                    seen_urls.add(dedup)
                    all_docs.append(d)

        except sqlite3.OperationalError:
            continue

    conn.close()

    # 筛选
    if doc_type:
        all_docs = [d for d in all_docs if d["type"] == doc_type]

    # 排序 (最新在前)
    all_docs.sort(key=lambda d: d["time"], reverse=True)

    # 聚合统计
    by_date = {}
    by_chat = {}
    by_type = {}
    for d in all_docs:
        by_date[d["date"]] = by_date.get(d["date"], 0) + 1
        by_chat[d["chat_name"]] = by_chat.get(d["chat_name"], 0) + 1
        by_type[d["type"]] = by_type.get(d["type"], 0) + 1

    # 按天分组
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
