#!/usr/bin/env python3
"""
weekly_collect.py — 绩效周报自动化采集器

从三个数据源汇聚工作轨迹：
  1. 轻推聊天记录 (csp4.db) — 提取指定时间范围内的消息，按群聊/主题归类
  2. Git 提交记录 — 扫描注册在 apps.json 中的项目仓库
  3. ONES 缺陷列表 — 读取 _ones-defect-wf 目录下的缺陷数据

输出:
  - reports/weekly/W{year}W{week}.json   — 每周完整档案
  - reports/weekly/latest.json           — 最新一期
  - reports/weekly/monthly/{year}-{month}.json — 月度汇总 (自动从周报合并)

用法:
  python3 weekly_collect.py                          # 采集本周
  python3 weekly_collect.py --week 2026-W35          # 采集指定周
  python3 weekly_collect.py --monthly 2026-08         # 从周报汇总生成月报
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
PERF_DIR = Path(__file__).resolve().parent
REPORTS_DIR = PERF_DIR / "reports"
WEEKLY_DIR = REPORTS_DIR / "weekly"
MONTHLY_DIR = REPORTS_DIR / "monthly"

# ============================================================
# 轻推数据源
# ============================================================
QINGTUI_DB = HOME / "Library/Application Support/Qingtui/sqlite/344548d972f44d799aeea39ae3e231ba/csp4.db"
ME = "344548d972f44d799aeea39ae3e231ba"

# 与工作相关的群聊名称关键词 (排除闲聊群)
WORK_CHANNEL_KEYWORDS = [
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


def _get_channel_names(db_path: str) -> dict:
    """读取群聊名称映射"""
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT id, name FROM channel_detail").fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _is_work_channel(name: str) -> bool:
    """判断是否工作相关群聊"""
    for kw in WORK_CHANNEL_KEYWORDS:
        if kw in name:
            return True
    return False


def collect_qingtui(start_ms: int, end_ms: int, db_path: str = None) -> dict:
    """采集轻推聊天记录"""
    db = db_path or str(QINGTUI_DB)
    if not os.path.exists(db):
        return {"error": f"轻推数据库不存在: {db}", "messages": [], "by_channel": {}}

    channel_names = _get_channel_names(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    all_msgs = []
    for i in range(20):
        try:
            rows = conn.execute(
                f'SELECT create_time, chat_id, "to", body FROM message_{i} '
                f'WHERE "from"=? AND create_time>=? AND create_time<? '
                f'ORDER BY create_time',
                (ME, start_ms, end_ms)
            ).fetchall()
            for r in rows:
                body = r["body"] or ""
                body = re.sub(r'<[^>]+>', '', body).strip()
                body = re.sub(r'\[图片\]|\[文件\]|\[协作文档\]|\[语音\]|\[视频\]|\[位置\]', '', body).strip()
                if not body:
                    continue
                ts = datetime.fromtimestamp(r["create_time"] / 1000)
                cname = channel_names.get(r["chat_id"], r["chat_id"])
                all_msgs.append({
                    "ts": ts.strftime("%Y-%m-%d %H:%M"),
                    "date": ts.strftime("%Y-%m-%d"),
                    "channel_id": r["chat_id"],
                    "channel_name": cname,
                    "is_work": _is_work_channel(cname),
                    "to": r["to"],
                    "body": body[:500],
                })
        except Exception:
            pass
    conn.close()

    # 按群聊分组 (只保留工作相关)
    by_channel = defaultdict(list)
    for m in all_msgs:
        if m["is_work"]:
            by_channel[m["channel_name"]].append(m)

    # 每日消息数
    daily_count = Counter(m["date"] for m in all_msgs if m["is_work"])

    return {
        "total": len([m for m in all_msgs if m["is_work"]]),
        "total_all": len(all_msgs),
        "daily_count": dict(sorted(daily_count.items())),
        "by_channel": {
            name: {
                "count": len(msgs),
                "sample": [m["body"][:120] for m in msgs[:5]],
                "first_ts": msgs[0]["ts"],
                "last_ts": msgs[-1]["ts"],
            }
            for name, msgs in sorted(by_channel.items(), key=lambda x: -len(x[1]))
        },
        "all_messages": all_msgs,
    }


# ============================================================
# Git 数据源
# ============================================================
# 张浩本人的 git author 名称 (用于过滤个人提交)
MY_AUTHORS = ["张浩", "zhanghao", "Zhanghao", "zhangh333"]

# 额外需要扫描的工作项目 (即使没登记在 apps.json)
EXTRA_WORK_PROJECTS = [
    str(HOME / "Downloads/project/cisdigital/fe-minmetals-fm-fis-fs"),
    str(HOME / "Downloads/project/cisdigital/fe-minmetals-fm-fia-sla"),
    str(HOME / "Downloads/project/cisdigital/fe-minmetals-fm-packages"),
    str(HOME / "Downloads/project/cisdigital/low-code"),
    str(HOME / "Downloads/project/cisdigital/_ones-defect-wf"),
    str(HOME / "Downloads/project/cisdigital/minmetals-ui"),
    str(HOME / "Downloads/project/cisdigital/fe-minmetals-template"),
]


def collect_git(start_dt: datetime, end_dt: datetime, apps_json: str = None) -> dict:
    """采集 Git 提交记录 (只统计张浩本人的提交)"""
    apps_file = apps_json or str(PERF_DIR.parent / "apps.json")

    # 收集所有需要扫描的项目路径
    projects = {}  # path -> name
    if os.path.exists(apps_file):
        try:
            with open(apps_file, encoding="utf-8") as f:
                cfg = json.load(f)
            for cat in cfg.get("categories", []):
                for proj in cat.get("projects", []):
                    p = Path(proj.get("path", "")).expanduser()
                    projects[str(p)] = proj.get("name", str(p))
        except Exception:
            pass

    # 加入额外工作项目
    for p in EXTRA_WORK_PROJECTS:
        name = Path(p).name
        projects[p] = name

    since = start_dt.strftime("%Y-%m-%d")
    until = end_dt.strftime("%Y-%m-%d")

    all_commits = []
    for proj_path, proj_name in projects.items():
        if not (Path(proj_path) / ".git").exists():
            continue
        try:
            r = subprocess.run(
                ["git", "-C", proj_path, "log",
                 f"--since={since}", f"--until={until}",
                 "--author", "张浩",
                 "--pretty=format:%h|%ad|%an|%s",
                 "--date=format:%Y-%m-%d %H:%M"],
                capture_output=True, text=True, timeout=10
            )
            for line in r.stdout.strip().splitlines():
                if "|" not in line:
                    continue
                parts = line.split("|", 3)
                if len(parts) < 4:
                    continue
                h, when, author, subj = parts
                all_commits.append({
                    "project": proj_name,
                    "project_path": str(proj_path),
                    "hash": h,
                    "when": when,
                    "date": when[:10],
                    "author": author,
                    "subject": subj[:150],
                })
        except Exception:
            continue

    # 按项目分组
    by_project = defaultdict(list)
    for c in all_commits:
        by_project[c["project"]].append(c)

    # 项目名友好化
    FRIENDLY_NAMES = {
        "fe-minmetals-fm-fis-fs": "共享运营前端",
        "fe-minmetals-fm-fia-sla": "会计引擎SLA",
        "fe-minmetals-fm-packages": "财务组件库",
        "low-code": "低码工作台",
        "fe-minmetals-template": "财务模板工程",
        "minmetals-ui": "Minmetals UI",
        "_ones-defect-wf": "ONES缺陷修复",
        "AI 副业情报": "AI 副业情报",
        "交易策略系统 v2": "交易策略系统",
        "五矿一企一屏": "五矿一企一屏",
    }

    by_project_friendly = {}
    for name, commits in by_project.items():
        fn = FRIENDLY_NAMES.get(name, name)
        by_project_friendly[fn] = {
            "count": len(commits),
            "commits": commits,
        }

    return {
        "total": len(all_commits),
        "by_project": dict(sorted(by_project_friendly.items(), key=lambda x: -x[1]["count"])),
        "all_commits": all_commits,
    }


# ============================================================
# ONES 数据源
# ============================================================
def collect_ones(start_dt: datetime, end_dt: datetime) -> dict:
    """采集 ONES 缺陷数据"""
    ones_dir = HOME / "Downloads/project/cisdigital/_ones-defect-wf"
    bugs_file = ones_dir / "bug_notes.json"

    bugs = []
    if bugs_file.exists():
        try:
            with open(bugs_file, encoding="utf-8") as f:
                data = json.load(f)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")

            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = list(data.values()) if "bugs" not in data else data.get("bugs", [])
            else:
                items = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                created = item.get("created_at") or item.get("created") or ""
                updated = item.get("updated_at") or item.get("updated") or ""

                in_range = False
                for ts in [created, updated]:
                    if ts and isinstance(ts, str) and ts[:10] >= start_str and ts[:10] <= end_str:
                        in_range = True
                        break

                if in_range:
                    bugs.append({
                        "id": item.get("id") or item.get("bug_id", ""),
                        "title": item.get("title") or item.get("summary", ""),
                        "status": item.get("status", ""),
                        "priority": item.get("priority", ""),
                        "created_at": created,
                        "updated_at": updated,
                        "assignee": item.get("assignee", ""),
                    })
        except Exception:
            pass

    # 也读 worklist.md
    worklist_file = ones_dir / "worklist.md"
    worklist = ""
    if worklist_file.exists():
        try:
            worklist = worklist_file.read_text(encoding="utf-8")[:2000]
        except Exception:
            pass

    return {
        "total": len(bugs),
        "bugs": bugs,
        "worklist_snippet": worklist,
    }


# ============================================================
# 汇总 & 输出
# ============================================================
def collect_week(year: int, week: int) -> dict:
    """采集指定周的任务轨迹"""
    # 计算周范围 (周一~周日)
    # Python isoweek 标准
    from datetime import date
    d = date.fromisocalendar(year, week, 1)  # 周一
    start_dt = datetime(d.year, d.month, d.day, 0, 0, 0)
    end_dt = start_dt + timedelta(days=7)  # 下周一 00:00

    # 转换为毫秒时间戳 (轻推用)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    qt = collect_qingtui(start_ms, end_ms)
    git = collect_git(start_dt, end_dt)
    ones = collect_ones(start_dt, end_dt)

    return {
        "meta": {
            "year": year,
            "week": week,
            "week_label": f"{year}-W{week:02d}",
            "start": start_dt.strftime("%Y-%m-%d"),
            "end": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summary": {
            "qingtui_msgs": qt.get("total", 0),
            "git_commits": git.get("total", 0),
            "ones_bugs": ones.get("total", 0),
            "active_channels": len(qt.get("by_channel", {})),
            "active_projects": len(git.get("by_project", {})),
        },
        "qingtui": qt,
        "git": git,
        "ones": ones,
    }


def save_weekly(report: dict):
    """保存周报"""
    meta = report["meta"]
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

    # 版本文件
    fname = f"{meta['week_label']}.json"
    path = WEEKLY_DIR / fname
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # latest
    (WEEKLY_DIR / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return str(path)


def merge_to_monthly(year: int, month: int) -> dict:
    """将当月的周报合并为月报"""
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)

    week_files = sorted(WEEKLY_DIR.glob(f"{year}-W*.json"))
    month_prefix = f"{year}-{month:02d}"

    merged = {
        "meta": {
            "year": year,
            "month": month,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "weeks": [],
        "summary": {
            "total_qingtui_msgs": 0,
            "total_git_commits": 0,
            "total_ones_bugs": 0,
            "top_channels": [],
            "top_projects": [],
        },
        "monthly_narrative": "",
    }

    all_channels = Counter()
    all_projects = Counter()

    for wf in week_files:
        try:
            data = json.loads(wf.read_text(encoding="utf-8"))
            start = data.get("meta", {}).get("start", "")
            if not start.startswith(month_prefix):
                continue

            merged["weeks"].append(data)

            s = data.get("summary", {})
            merged["summary"]["total_qingtui_msgs"] += s.get("qingtui_msgs", 0)
            merged["summary"]["total_git_commits"] += s.get("git_commits", 0)
            merged["summary"]["total_ones_bugs"] += s.get("ones_bugs", 0)

            for name, info in data.get("qingtui", {}).get("by_channel", {}).items():
                all_channels[name] += info.get("count", 0)
            for name, info in data.get("git", {}).get("by_project", {}).items():
                all_projects[name] += info.get("count", 0)
        except Exception:
            continue

    merged["summary"]["top_channels"] = [
        {"name": n, "count": c} for n, c in all_channels.most_common(15)
    ]
    merged["summary"]["top_projects"] = [
        {"name": n, "count": c} for n, c in all_projects.most_common(10)
    ]

    # 生成月度叙述
    narrative_parts = []
    top_projs = all_projects.most_common(5)
    if top_projs:
        narrative_parts.append(f"本月主要投入项目: " + "、".join(n for n, _ in top_projs))
    top_chs = all_channels.most_common(5)
    if top_chs:
        narrative_parts.append(f"主要沟通群聊: " + "、".join(n for n, _ in top_chs))
    narrative_parts.append(
        f"共 {merged['summary']['total_qingtui_msgs']} 条工作消息, "
        f"{merged['summary']['total_git_commits']} 次代码提交, "
        f"{merged['summary']['total_ones_bugs']} 个缺陷"
    )
    merged["monthly_narrative"] = "；".join(narrative_parts)

    # 保存
    fname = f"{year}-{month:02d}.json"
    path = MONTHLY_DIR / fname
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    (MONTHLY_DIR / "latest.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return merged


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="绩效周报采集器")
    parser.add_argument("--week", help="指定周, 如 2026-W35")
    parser.add_argument("--monthly", help="从周报汇总月报, 如 2026-08")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.monthly:
        y, m = args.monthly.split("-")
        report = merge_to_monthly(int(y), int(m))
        if not args.quiet:
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return

    if args.week:
        y, w = args.week.split("-W")
        year, week = int(y), int(w)
    else:
        today = datetime.now()
        year, week, _ = today.isocalendar()

    report = collect_week(year, week)
    path = save_weekly(report)
    if not args.quiet:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print(f"\n💾 已保存: {path}")


if __name__ == "__main__":
    main()