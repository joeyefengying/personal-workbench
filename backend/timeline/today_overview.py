"""今日概览 — 聚合今天的事件、@提及、采集状态, 生成 Dashboard 卡片数据."""
import time
from datetime import datetime
from pathlib import Path

from .llm_summary import summarize_daily, API_KEY
from .daily_report import events_to_projects


def today_overview(date: str | None = None, db=None) -> dict:
    """返回今日概览数据, 供前端 Dashboard 使用.

    返回:
      {date, ai_one_liner, mention_count, mention_samples,
       events_by_source, active_projects, collection_runs_today, next_collection}
    """
    if not date:
        date = time.strftime("%Y-%m-%d")

    from .db import get_db
    db = db or get_db()
    events, _total = db.query(date=date, limit=100000)

    # ── ai_one_liner ──────────────────────────────────────────
    ai_one_liner = ""
    if API_KEY and events:
        by_project = events_to_projects(events)
        proj_events = {k: v for k, v in by_project.items() if k != "_global"}
        if proj_events:
            summary = summarize_daily(
                proj_events, date,
                system="你是个人工作日报助手, 擅长用一句话概括当天的工作内容。",
                user=f"用一句话总结我今天的工作（不超过50字）, 只输出这句话不要解释。\n\n日期: {date}",
                max_tokens=128,
            )
            # 如果是 fallback (以 "## 今日总结" 开头且含 > 引用模式), 丢弃
            if summary.startswith("## 今日总结") and any(">" in ln for ln in summary.splitlines()):
                summary = ""
            # 也丢弃 LLM 失败/不可用标记
            if summary.startswith("[LLM "):
                summary = ""
            ai_one_liner = summary.strip() if summary else ""

    # ── mention_count / mention_samples ───────────────────────
    mentions = [e for e in events if e.get("source") == "qingtui" and e.get("category") == "mention"]
    mention_count = len(mentions)
    mention_samples = []
    for e in mentions[:3]:
        meta = e.get("meta", {}) or {}
        session = meta.get("session", e.get("target", ""))
        ts_str = time.strftime("%H:%M", time.localtime(e["ts"] / 1000))
        mention_samples.append({
            "time": ts_str,
            "session": session,
            "text": e.get("title", ""),
        })

    # ── events_by_source ──────────────────────────────────────
    events_by_source = {}
    for e in events:
        src = e.get("source", "?")
        events_by_source[src] = events_by_source.get(src, 0) + 1

    # ── active_projects ───────────────────────────────────────
    by_project = events_to_projects(events)
    active_projects = sorted([p for p in by_project if p != "_global"])

    # ── collection_runs_today ─────────────────────────────────
    collection_runs_today = 0
    log_path = Path("/tmp/workbench-collect.log")
    if log_path.exists():
        prefix = f"[{date}"
        try:
            for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith(prefix):
                    collection_runs_today += 1
        except Exception:
            pass

    # ── next_collection ───────────────────────────────────────
    now = datetime.now()
    next_hour = (now.hour + 1) % 24
    next_collection = f"{next_hour:02d}:00"

    return {
        "date": date,
        "ai_one_liner": ai_one_liner,
        "mention_count": mention_count,
        "mention_samples": mention_samples,
        "events_by_source": events_by_source,
        "active_projects": active_projects,
        "collection_runs_today": collection_runs_today,
        "next_collection": next_collection,
    }