#!/usr/bin/env python3
"""analyze_recent.py — 扫描 Hermes 会话历史 + git 活动 + cron 状态, 生成"近期活动分析报告".

用法:
  python3 analyze_recent.py [--days 7] [--out reports/]

每次执行生成一个带时间戳的版本文件 (reports/analysis_<ts>.json), 并更新 reports/latest.json。
报告内容:
  - 热点项目 (从会话首条用户消息提取项目关键词 + git 提交统计)
  - 热点主题 (会话消息主题词频)
  - 活跃 skill 使用 (会话中提及的 skill)
  - cron 健康 (失败任务预警)
  - 建议 (基于活跃度给"下一步做什么"建议)
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
SESSIONS_DIR = HOME / ".hermes" / "sessions"
CRON_JOBS = HOME / ".hermes" / "cron" / "jobs.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_DAYS = 7

# 项目关键词 → 项目名 (用于从会话消息里识别在聊哪个项目)
PROJECT_KEYWORDS = [
    (r"低码|low-?code|lcdp|DSEP", "低码工作台"),
    (r"ONES|缺陷|bug|defect", "ONES 缺陷修复"),
    (r"交易策略|trading|回测", "交易策略系统"),
    (r"知识库|llm-wiki|wiki|消化", "知识库/llm-wiki"),
    (r"漫剧|comic", "AI 漫剧生产线"),
    (r"面试|简历", "面试工作流"),
    (r"财务|fs-front|报销|应付", "财务系统"),
    (r"打卡|思想汇报|入党", "党务/工作日常"),
    (r"第二大脑|second-brain|日结", "Second Brain"),
    (r"GitHub|trending|日报", "GitHub Trending"),
    (r"个人工作台|workbench", "个人工作台"),
    (r"side-?hustle|副业", "AI 副业"),
]


def load_sessions(days: int) -> list:
    """加载最近 N 天的 Hermes 会话, 返回 [{id, ts, title, first_user, messages, project}]"""
    cutoff = datetime.now() - timedelta(days=days)
    sessions = []
    for f in glob.glob(str(SESSIONS_DIR / "session_*.json")):
        mtime = datetime.fromtimestamp(os.path.getmtime(f))
        if mtime < cutoff:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        sid = d.get("session_id") or os.path.basename(f).replace("session_", "").replace(".json", "")
        # 首条用户消息
        first_user = ""
        user_msgs = []
        for m in d.get("messages", []):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                c = m["content"]
                if not first_user:
                    first_user = c[:200]
                user_msgs.append(c)
        # 识别项目
        project = "其他"
        for pat, name in PROJECT_KEYWORDS:
            if re.search(pat, first_user + " ".join(user_msgs[:3]), re.I):
                project = name
                break
        sessions.append({
            "id": sid,
            "ts": mtime.strftime("%Y-%m-%d %H:%M"),
            "first_user": first_user[:150],
            "user_msgs": user_msgs,
            "project": project,
            "msg_count": d.get("message_count", len(d.get("messages", []))),
        })
    sessions.sort(key=lambda s: s["ts"], reverse=True)
    return sessions


def git_activity(days: int) -> list:
    """扫描个人项目仓库最近 N 天的 git 提交"""
    # 从工作台 apps.json 读项目列表
    apps = Path(__file__).resolve().parent / "apps.json"
    events = []
    if apps.exists():
        try:
            cfg = json.load(open(apps, encoding="utf-8"))
        except Exception:
            cfg = {"categories": []}
        for cat in cfg.get("categories", []):
            for p in cat.get("projects", []):
                path = Path(p.get("path", "")).expanduser()
                if not (path / ".git").exists():
                    continue
                try:
                    r = subprocess.run(
                        ["git", "-C", str(path), "log", "--since=%d days ago" % days,
                         "--pretty=%h|%ad|%s", "--date=format:%m-%d %H:%M"],
                        capture_output=True, text=True, timeout=8)
                    for line in r.stdout.strip().splitlines():
                        if "|" not in line:
                            continue
                        h, when, subj = line.split("|", 2)
                        events.append({"proj": p.get("name"), "when": when, "subject": subj[:70]})
                except Exception:
                    continue
    events.sort(key=lambda e: e["when"], reverse=True)
    return events[:50]


def cron_health() -> dict:
    """cron 任务健康: 返回失败任务列表"""
    bad = []
    if CRON_JOBS.exists():
        try:
            data = json.load(open(CRON_JOBS, encoding="utf-8"))
            raw = data.get("jobs", [])
            if isinstance(raw, dict):
                raw = list(raw.values())
            for j in raw:
                if str(j.get("enabled")) == "True" and j.get("last_status") == "error":
                    bad.append({
                        "name": j.get("name"),
                        "error": (j.get("last_error") or "")[:120],
                        "last_run": (j.get("last_run_at") or "")[:16],
                    })
        except Exception:
            pass
    return {"bad": bad, "count": len(bad)}


def extract_topics(sessions: list, topn: int = 12) -> list:
    """从用户消息提取高频词作为热点主题 (简单分词: 中文按词, 英文按词)"""
    # 去停用词
    stop = {"这个", "那个", "怎么", "什么", "可以", "一下", "现在", "我们", "你们", "还有",
            "一个", "那个", "就是", "不是", "没有", "为什么", "如何", "把", "在", "了", "吗", "呢",
            "the", "and", "for", "with", "from", "that", "this", "what", "how"}
    words = Counter()
    for s in sessions:
        for msg in s["user_msgs"]:
            # 中文字符 2-6 长度片段
            for tok in re.findall(r"[\u4e00-\u9fff]{2,6}", msg):
                if tok not in stop:
                    words[tok] += 1
            # 英文/数字词
            for tok in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", msg.lower()):
                if tok not in stop:
                    words[tok] += 1
    return [{"word": w, "count": c} for w, c in words.most_common(topn)]


def suggestions(projects: Counter, cron_bad: list, sessions: list) -> list:
    """基于活跃度生成"下一步做什么"建议"""
    sug = []
    top_proj = projects.most_common(3)
    for name, cnt in top_proj:
        sug.append(f"近期最活跃: {name} ({cnt} 次会话), 可考虑深入该方向")
    if cron_bad:
        sug.append(f"⚠️ {len(cron_bad)} 个定时任务运行失败: {cron_bad[0]['name']} — 建议检查脚本超时/依赖")
    # 从会话里找"正在做但可能没做完"的
    unfinished_keywords = ["导出", "拉取", "修复", "报错", "失败", "超时", "bug", "500", "待办", "还差", "没"]
    for s in sessions[:10]:
        for msg in s["user_msgs"]:
            if any(k in msg for k in unfinished_keywords):
                sug.append(f"[{s['project']}] 提到待解决事项: {msg[:60]}…")
                break
    return sug[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--out", default=str(REPORTS_DIR))
    args = ap.parse_args()

    sessions = load_sessions(args.days)
    git = git_activity(args.days)
    cron = cron_health()

    projects = Counter(s["project"] for s in sessions)
    topics = extract_topics(sessions)
    sug = suggestions(projects, cron["bad"], sessions)

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": args.days,
        "stats": {
            "sessions": len(sessions),
            "projects": len(projects),
            "git_events": len(git),
            "cron_failures": cron["count"],
        },
        "hot_projects": [{"name": n, "count": c} for n, c in projects.most_common(8)],
        "top_topics": topics,
        "recent_sessions": [{"ts": s["ts"], "project": s["project"], "first": s["first_user"]} for s in sessions[:12]],
        "git_activity": git[:30],
        "cron_issues": cron["bad"],
        "suggestions": sug,
    }

    # 版本记录: 每次执行存一个带时间戳的文件 + latest.json
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_file = out_dir / f"analysis_{ts}.json"
    version_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 版本历史 (列出所有版本文件)
    versions = sorted(out_dir.glob("analysis_*.json"), reverse=True)
    history = [{"version": v.stem.replace("analysis_", ""), "file": v.name, "time": v.stem.replace("analysis_", "")[:14]} for v in versions]

    print(json.dumps({"report": report, "version": ts, "history": history}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
