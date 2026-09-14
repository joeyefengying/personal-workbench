"""周报 / 月报数据读取与 Markdown 导出(独立模块, 只读 JSON, 不依赖 timeline)."""
import json
import re
from pathlib import Path

# 数据目录: backend/performance/reports/
_REPORTS_DIR = Path(__file__).resolve().parent / "performance" / "reports"
_WEEKLY_DIR = _REPORTS_DIR / "weekly"
_MONTHLY_DIR = _REPORTS_DIR / "monthly"
_QUARTERLY_DIR = _REPORTS_DIR / "quarterly"
_YEARLY_DIR = _REPORTS_DIR / "yearly"


def _read_json(path: Path) -> dict | None:
    """读取单个 JSON 文件, 失败返回 None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _list_reports(directory: Path) -> list[dict]:
    """扫描目录下 *.json(跳过 latest.json), 返回按 label 排序的 [{label, ...meta}]. """
    items = []
    if not directory.is_dir():
        return items
    for p in sorted(directory.glob("*.json")):
        if p.stem == "latest":
            continue
        data = _read_json(p)
        if not data:
            continue
        meta = data.get("meta", {}) or {}
        if meta.get("week_label"):
            # 周报
            items.append({
                "week_label": meta["week_label"],
                "start": meta.get("start", ""),
                "end": meta.get("end", ""),
                "collected_at": meta.get("collected_at", ""),
            })
        elif meta.get("month") is not None:
            # 月报
            year = meta.get("year", "")
            month = meta.get("month", "")
            label = f"{year}-{int(month):02d}" if year != "" and month != "" else p.stem
            items.append({
                "month": label,
                "start": _month_start(data),
                "end": _month_end(data),
                "collected_at": meta.get("generated_at", ""),
            })
    return items


def _month_start(data: dict) -> str:
    """月报起始日期 = 首周 start."""
    weeks = data.get("weeks") or []
    if weeks:
        return (weeks[0].get("meta") or {}).get("start", "")
    return ""


def _month_end(data: dict) -> str:
    """月报结束日期 = 末周 end."""
    weeks = data.get("weeks") or []
    if weeks:
        return (weeks[-1].get("meta") or {}).get("end", "")
    return ""


def list_weekly_reports() -> list[dict]:
    """Returns all available weekly reports as [{week_label, start, end, collected_at}]"""
    return _list_reports(_WEEKLY_DIR)


def get_weekly_report(week_label: str) -> dict | None:
    """Returns full report data for a given week, or None if not found"""
    p = _WEEKLY_DIR / f"{week_label}.json"
    if not p.is_file():
        return None
    return _read_json(p)


def list_monthly_reports() -> list[dict]:
    """Returns all available monthly reports as [{month, start, end, collected_at}]"""
    return _list_reports(_MONTHLY_DIR)


def get_monthly_report(month: str) -> dict | None:
    """Returns full report data for a given month (format '2026-08'), or None if not found"""
    p = _MONTHLY_DIR / f"{month}.json"
    if not p.is_file():
        return None
    return _read_json(p)


# ---------------------------------------------------------------------------
# 季报 / 年报 — 从月报聚合
# ---------------------------------------------------------------------------

def _list_monthly_file_labels() -> list[str]:
    """列出 monthly 目录下所有月报 label (如 '2026-08'), 按时间排序."""
    labels = []
    if not _MONTHLY_DIR.is_dir():
        return labels
    for p in sorted(_MONTHLY_DIR.glob("*.json")):
        if p.stem == "latest":
            continue
        labels.append(p.stem)
    return labels


def _months_to_quarter(month_label: str) -> str | None:
    """'2026-08' -> '2026-Q3'; '2026-01' -> '2026-Q1'."""
    try:
        y, m = month_label.split("-")
        yr, mo = int(y), int(m)
        q = (mo - 1) // 3 + 1
        return f"{yr}-Q{q}"
    except (ValueError, AttributeError):
        return None


def list_quarterly_reports() -> list[dict]:
    """返回所有可聚合的季度: [{quarter: '2026-Q3', months: [...], month_count: int}]"""
    from collections import defaultdict
    qmap: dict[str, list[str]] = defaultdict(list)
    for label in _list_monthly_file_labels():
        q = _months_to_quarter(label)
        if q:
            qmap[q].append(label)
    return [
        {"quarter": q, "months": sorted(ms), "month_count": len(ms)}
        for q, ms in sorted(qmap.items())
    ]


def list_yearly_reports() -> list[dict]:
    """返回所有可聚合的年度: [{year: '2026', months: [...], month_count: int}]"""
    from collections import defaultdict
    ymap: dict[str, list[str]] = defaultdict(list)
    for label in _list_monthly_file_labels():
        try:
            yr = label.split("-")[0]
        except (ValueError, AttributeError):
            continue
        ymap[yr].append(label)
    return [
        {"year": yr, "months": sorted(ms), "month_count": len(ms)}
        for yr, ms in sorted(ymap.items())
    ]


def _aggregate_monthly_reports(month_labels: list[str]) -> dict | None:
    """把多个月报 JSON 聚合为一个报告 dict.

    返回 {meta, months_data: [...], summary: {total_qingtui_msgs, total_git_commits,
    total_ones_bugs, month_count, top_channels, top_projects, all_channels, all_projects},
    ai_summary, ai_summary_at}
    供季报/年报使用.
    """
    if not month_labels:
        return None
    months_data = []
    for ml in month_labels:
        data = get_monthly_report(ml)
        if data is not None:
            months_data.append(data)
    if not months_data:
        return None

    # 聚合 summary
    total_qingtui = 0
    total_git = 0
    total_ones = 0
    chan_map: dict[str, int] = {}
    proj_map: dict[str, int] = {}

    for d in months_data:
        s = d.get("summary", {}) or {}
        total_qingtui += s.get("total_qingtui_msgs", 0)
        total_git += s.get("total_git_commits", 0)
        total_ones += s.get("total_ones_bugs", 0)
        for ch in (s.get("top_channels") or []):
            name = ch.get("name", "")
            if name:
                chan_map[name] = chan_map.get(name, 0) + ch.get("count", 0)
        for pj in (s.get("top_projects") or []):
            name = pj.get("name", "")
            if name:
                proj_map[name] = proj_map.get(name, 0) + pj.get("count", 0)

    top_channels = sorted(
        [{"name": k, "count": v} for k, v in chan_map.items()],
        key=lambda x: -x["count"],
    )[:10]
    top_projects = sorted(
        [{"name": k, "count": v} for k, v in proj_map.items()],
        key=lambda x: -x["count"],
    )[:10]

    return {
        "meta": {
            "month_labels": month_labels,
            "month_count": len(month_labels),
        },
        "months_data": months_data,
        "summary": {
            "total_qingtui_msgs": total_qingtui,
            "total_git_commits": total_git,
            "total_ones_bugs": total_ones,
            "month_count": len(month_labels),
            "top_channels": top_channels,
            "top_projects": top_projects,
        },
    }


def get_quarterly_report(quarter: str) -> dict | None:
    """返回某季度的聚合报告 (含 AI 缓存).

    quarter: '2026-Q3'
    先从 quarterly/*.json 回读缓存的 ai_summary; 无则从月报聚合.
    """
    # 先尝试季度缓存 JSON
    cached_json = _read_json(_QUARTERLY_DIR / f"{quarter}.json")
    if cached_json:
        return cached_json

    # 从月报聚合
    all_q = list_quarterly_reports()
    qmap = {q["quarter"]: q["months"] for q in all_q}
    months = qmap.get(quarter, [])
    if not months:
        return None
    return _aggregate_monthly_reports(months)


def get_yearly_report(year: str) -> dict | None:
    """返回某年度的聚合报告 (含 AI 缓存).

    year: '2026'
    """
    cached_json = _read_json(_YEARLY_DIR / f"{year}.json")
    if cached_json:
        return cached_json

    all_y = list_yearly_reports()
    ymap = {y["year"]: y["months"] for y in all_y}
    months = ymap.get(year, [])
    if not months:
        return None
    return _aggregate_monthly_reports(months)


# ---------------------------------------------------------------------------
# Markdown 导出
# ---------------------------------------------------------------------------

def _fmt_date(d: str) -> str:
    """'2026-09-07' -> '9/7'."""
    if not d:
        return ""
    try:
        y, m, day = d.split("-")
        return f"{int(m)}/{int(day)}"
    except (ValueError, AttributeError):
        return d


def _overview_md(summary: dict) -> str:
    """概览表格."""
    lines = ["## 📊 概览", "", "| 指标 | 数值 |", "|------|------|"]
    rows = [
        ("轻推工作消息", summary.get("qingtui_msgs"), "条"),
        ("Git 提交", summary.get("git_commits"), "次"),
        ("活跃项目", summary.get("active_projects"), "个"),
        ("活跃群聊", summary.get("active_channels"), "个"),
        ("ONES 缺陷", summary.get("ones_bugs"), ""),
    ]
    for name, val, unit in rows:
        v = val if val is not None else 0
        lines.append(f"| {name} | {v} {unit} |".rstrip())
    return "\n".join(lines)


def _channels_md(qingtui: dict) -> str:
    """轻推消息按群聊 top5."""
    lines = ["## 💬 轻推消息", ""]
    by_channel = qingtui.get("by_channel", {}) or {}
    sorted_channels = sorted(
        by_channel.items(), key=lambda kv: kv[1].get("count", 0), reverse=True
    )[:5]
    if not sorted_channels:
        lines.append("（无）")
        return "\n".join(lines)
    for name, info in sorted_channels:
        count = info.get("count", 0)
        lines.append(f"### {name}（{count}条）")
    return "\n".join(lines)


def _git_md(git: dict) -> str:
    """Git 提交按项目, 每个项目列 top5 提交."""
    lines = ["## 🔧 Git 提交", ""]
    by_project = git.get("by_project", {}) or {}
    sorted_projects = sorted(
        by_project.items(), key=lambda kv: kv[1].get("count", 0), reverse=True
    )
    if not sorted_projects:
        lines.append("（无）")
        return "\n".join(lines)
    for proj, info in sorted_projects:
        count = info.get("count", 0)
        lines.append(f"### {proj}（{count} commits）")
        commits = info.get("commits", []) or []
        for c in commits[:5]:
            subject = (c.get("subject") or "").strip()
            author = c.get("author") or ""
            when = c.get("when") or ""
            line = f"- {subject}"
            if author or when:
                line += f"（{author} {when}）".rstrip()
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_weekly_markdown(week_label: str) -> str | None:
    """Export weekly report as Markdown string, or None if not found"""
    data = get_weekly_report(week_label)
    if data is None:
        return None
    meta = data.get("meta", {}) or {}
    start, end = meta.get("start", ""), meta.get("end", "")
    sd, ed = _fmt_date(start), _fmt_date(end)
    title = f"# 周报 {week_label}"
    if sd and ed:
        title += f"（{sd} - {ed}）"
    parts = [title, "", _overview_md(data.get("summary", {}) or {}),
             "", _channels_md(data.get("qingtui", {}) or {}),
             "", _git_md(data.get("git", {}) or {})]
    return "\n".join(parts)


def export_monthly_markdown(month: str) -> str | None:
    """Export monthly report as Markdown string, or None if not found"""
    data = get_monthly_report(month)
    if data is None:
        return None
    meta = data.get("meta", {}) or {}
    start, end = _month_start(data), _month_end(data)
    sd, ed = _fmt_date(start), _fmt_date(end)
    title = f"# 月报 {month}"
    if sd and ed:
        title += f"（{sd} - {ed}）"

    summary = data.get("summary", {}) or {}
    lines = [title, "", "## 📊 概览", "", "| 指标 | 数值 |", "|------|------|",
             f"| 轻推工作消息 | {summary.get('total_qingtui_msgs', 0)} 条 |",
             f"| Git 提交 | {summary.get('total_git_commits', 0)} 次 |",
             f"| ONES 缺陷 | {summary.get('total_ones_bugs', 0)} |",
             f"| 覆盖周数 | {len(data.get('weeks') or [])} 周 |"]

    top_channels = summary.get("top_channels") or []
    if top_channels:
        lines += ["", "## 💬 轻推消息（TOP 群聊）", ""]
        for c in top_channels[:5]:
            lines.append(f"- {c.get('name', '')}（{c.get('count', 0)}条）")

    top_projects = summary.get("top_projects") or []
    if top_projects:
        lines += ["", "## 🔧 Git 提交（TOP 项目）", ""]
        for p in top_projects[:5]:
            lines.append(f"- {p.get('name', '')}（{p.get('count', 0)} commits）")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# AI 总结 — 用 LLM 把周报/月报的原始数据提炼成"人话"总结
# ---------------------------------------------------------------------------

def _build_context_from_report(data: dict) -> str:
    """从周报/月报 JSON 提炼关键信息, 生成给 LLM 的上下文文本."""
    summary = data.get("summary", {}) or {}

    # 周报字段
    qingtui_msgs = summary.get("qingtui_msgs") or summary.get("total_qingtui_msgs", 0)
    git_commits = summary.get("git_commits") or summary.get("total_git_commits", 0)
    ones_bugs = summary.get("ones_bugs") or summary.get("total_ones_bugs", 0)

    # 渠道 TOP
    channels = []
    by_channel = (data.get("qingtui") or {}).get("by_channel", {})
    if by_channel:
        for name, info in sorted(by_channel.items(), key=lambda x: -(x[1].get("count", 0)))[:6]:
            channels.append(f"{name}({info.get('count', 0)}条)")
    else:
        for c in (summary.get("top_channels") or [])[:6]:
            channels.append(f"{c.get('name','')}({c.get('count',0)}条)")

    # 项目 TOP
    projects = []
    by_project = (data.get("git") or {}).get("by_project", {})
    if by_project:
        for name, info in sorted(by_project.items(), key=lambda x: -(x[1].get("count", 0)))[:6]:
            projects.append(f"{name}({info.get('count', 0)}次)")
    else:
        for p in (summary.get("top_projects") or [])[:6]:
            projects.append(f"{p.get('name','')}({p.get('count',0)}次)")

    # 采样几条代表性 commit subject
    commits = []
    all_commits = (data.get("git") or {}).get("all_commits", [])
    for c in all_commits[:10]:
        subject = c.get("subject", "")
        if subject and len(subject) > 5:
            commits.append(subject[:80])

    lines = []
    lines.append(f"工作消息 {qingtui_msgs} 条, Git 提交 {git_commits} 次, 缺陷 {ones_bugs} 个")
    if channels:
        lines.append("主要沟通群聊: " + ", ".join(channels))
    if projects:
        lines.append("主要投入项目: " + ", ".join(projects))
    if commits:
        lines.append("代表性提交:")
        for c in commits[:8]:
            lines.append(f"- {c}")
    return "\n".join(lines)


def summarize_weekly(week_label: str, force: bool = False) -> str | None:
    """用 LLM 生成周报总结 (约 200 字).

    优先读 JSON 缓存; 若 JSON 无缓存, 从 LifeOS 文件回读「## 工作回顾」内容;
    都无则调 LLM 生成. force=True 跳过所有缓存, 强制 LLM 生成.
    """
    data = get_weekly_report(week_label)
    if data is None:
        return None

    # 1) JSON 缓存命中 → 直接返回 (force 跳过)
    if not force:
        cached = data.get("ai_summary", "")
        if cached:
            return cached

        # 2) JSON 无缓存, 从 LifeOS 文件回读
        lifeos_summary = _read_lifeos_section("weekly", week_label)
        if lifeos_summary is not None:
            _save_ai_summary(_WEEKLY_DIR, week_label, lifeos_summary)
            return lifeos_summary

    # 3) 都没有 → 调 LLM 生成
    context = _build_context_from_report(data)
    meta = data.get("meta", {})
    start, end = meta.get("start", ""), meta.get("end", "")

    prompt = f"""你是个人工作台的周报助手。以下是本周（{start} 至 {end}）的工作数据，请生成一段中文周报总结。

要求:
1. 语气专业、简洁，可直接用于向上汇报
2. 提炼"本周主要做了什么"（按项目/主题归类，不要罗列数字）
3. 如果数据里有明显的重点工作或趋势，点出来
4. 长度控制在 150-250 字，用 1-2 段

本周数据:
{context}

请只输出周报总结正文，不要加标题或解释。"""

    from timeline.llm_summary import _api_request
    result = _api_request([
        {"role": "system", "content": "你是个人工作周报助手，擅长从工作数据中提炼简洁、可用于汇报的总结。"},
        {"role": "user", "content": prompt},
    ], max_tokens=500, temperature=0.4)

    # 如果 LLM 失败, 返回 None (前端提示降级)
    if result.startswith("[LLM"):
        return None
    summary = result.strip()

    # 持久化到 JSON — 下次直接读缓存, 不再调 LLM
    _save_ai_summary(_WEEKLY_DIR, week_label, summary)

    return summary


def summarize_monthly(month: str, force: bool = False) -> str | None:
    """用 LLM 生成月报总结 (约 300 字).

    同 summarize_weekly: JSON 缓存 → LifeOS 回读 → LLM 生成. force=True 强制 LLM 生成.
    """
    data = get_monthly_report(month)
    if data is None:
        return None

    # 1) JSON 缓存命中 (force 跳过)
    if not force:
        cached = data.get("ai_summary", "")
        if cached:
            return cached

        # 2) LifeOS 回读
        lifeos_summary = _read_lifeos_section("monthly", month)
        if lifeos_summary is not None:
            _save_ai_summary(_MONTHLY_DIR, month, lifeos_summary)
            return lifeos_summary
    context = _build_context_from_report(data)

    prompt = f"""你是个人工作台的月报助手。以下是本月（{month}）的工作数据，请生成一段中文月度总结。

要求:
1. 语气专业、简洁，可用于月度汇报
2. 提炼"本月主要完成了什么、投入在哪些方向"
3. 点出重点产出和趋势
4. 长度控制在 250-400 字，用 1-3 段

本月数据:
{context}

请只输出月报总结正文，不要加标题或解释。"""

    from timeline.llm_summary import _api_request
    result = _api_request([
        {"role": "system", "content": "你是个人工作月度总结助手，擅长从工作数据中提炼简洁、可用于汇报的总结。"},
        {"role": "user", "content": prompt},
    ], max_tokens=600, temperature=0.4)

    if result.startswith("[LLM"):
        return None
    summary = result.strip()

    # 持久化到 JSON
    _save_ai_summary(_MONTHLY_DIR, month, summary)

    return summary


def summarize_quarterly(quarter: str, force: bool = False) -> str | None:
    """用 LLM 生成季报总结 (约 400-600 字).

    缓存策略: quarterly/*.json 缓存 → LifeOS 回读 → LLM 生成.
    """
    data = get_quarterly_report(quarter)
    if data is None:
        return None

    _ensure_dir(_QUARTERLY_DIR)

    # 1) JSON 缓存命中
    if not force:
        cached = data.get("ai_summary", "")
        if cached:
            return cached

        lifeos_summary = _read_lifeos_section("quarterly", quarter)
        if lifeos_summary is not None:
            _save_ai_summary(_QUARTERLY_DIR, quarter, lifeos_summary)
            return lifeos_summary

    context = _build_context_from_report(data)
    months = data.get("meta", {}).get("month_labels", [])

    prompt = f"""你是个人工作台的季报助手。以下是本季度（{quarter}，覆盖 {', '.join(months[:6])} 等 {len(months)} 个月）的工作数据，请生成一段中文季度汇报总结。

要求:
1. 语气专业、正式，适合季度汇报（向上级或团队）
2. 提炼"本季度主要完成了什么、投入在哪些方向、有哪些关键产出"
3. 从月份维度点出趋势变化（如"前期侧重XX，后期转向YY"）
4. 点出重点产出和亮点
5. 长度控制在 400-600 字，用 2-4 段

本季度数据:
{context}

请只输出季报总结正文，不要加标题或解释。"""

    from timeline.llm_summary import _api_request
    result = _api_request([
        {"role": "system", "content": "你是个人工作季度总结助手，擅长从工作数据中提炼正式、可用于汇报的季度总结。"},
        {"role": "user", "content": prompt},
    ], max_tokens=900, temperature=0.4)

    if result.startswith("[LLM"):
        return None
    summary = result.strip()

    _save_ai_summary(_QUARTERLY_DIR, quarter, summary)

    return summary


def summarize_yearly(year: str, force: bool = False) -> str | None:
    """用 LLM 生成年报总结 (约 600-900 字).

    缓存策略: yearly/*.json 缓存 → LifeOS 回读 → LLM 生成.
    """
    data = get_yearly_report(year)
    if data is None:
        return None

    _ensure_dir(_YEARLY_DIR)

    # 1) JSON 缓存命中
    if not force:
        cached = data.get("ai_summary", "")
        if cached:
            return cached

        lifeos_summary = _read_lifeos_section("yearly", year)
        if lifeos_summary is not None:
            _save_ai_summary(_YEARLY_DIR, year, lifeos_summary)
            return lifeos_summary

    context = _build_context_from_report(data)
    months = data.get("meta", {}).get("month_labels", [])

    prompt = f"""你是个人工作台的年报助手。以下是本年度（{year}，覆盖 {', '.join(months[:12])} 共 {len(months)} 个月）的工作数据，请生成一段中文年度总结。

要求:
1. 语气正式、有大局观，适合年度汇报
2. 提炼"全年主要成果、重点方向、关键里程碑"
3. 从季度或月度维度做趋势分析（如"上半年侧重XX，下半年转向YY"）
4. 突出年度亮点和成长
5. 长度控制在 600-900 字，用 3-5 段

本年度数据:
{context}

请只输出年报总结正文，不要加标题或解释。"""

    from timeline.llm_summary import _api_request
    result = _api_request([
        {"role": "system", "content": "你是个人工作年度总结助手，擅长从工作数据中提炼正式、有大局观的年度总结。"},
        {"role": "user", "content": prompt},
    ], max_tokens=1200, temperature=0.4)

    if result.startswith("[LLM"):
        return None
    summary = result.strip()

    _save_ai_summary(_YEARLY_DIR, year, summary)

    return summary


# ---------------------------------------------------------------------------
# AI 总结持久化 — 生成一次, 写入 JSON, 下次直接读缓存
# ---------------------------------------------------------------------------

def _ensure_dir(directory: Path) -> None:
    """确保目录存在 (idempotent)."""
    directory.mkdir(parents=True, exist_ok=True)


def _save_ai_summary(directory: Path, label: str, summary: str) -> None:
    """把 AI 总结写入对应的报告 JSON 文件 (ai_summary + ai_summary_at 字段)."""
    path = directory / f"{label}.json"
    if not path.is_file():
        return
    data = _read_json(path)
    if data is None:
        return
    from datetime import datetime
    data["ai_summary"] = summary
    data["ai_summary_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _read_lifeos_section(mode: str, label: str) -> str | None:
    """从已生成的 LifeOS 文件中提取「工作回顾」章节内容, 作为 JSON 缓存的第二数据源."""
    path = _lifeos_path(mode, label)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    section = _LIFEOS_PERIODS.get(mode, {}).get("section", "工作回顾")
    pattern = re.compile(
        rf"^## {re.escape(section)}\s*\n(.*?)(?=\n## |\n```LifeOS|\n# |\n---|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        return None
    content = m.group(1).strip()
    return content if len(content) > 20 else None   # 太短视为无效


def get_cached_ai_summary(mode: str, label: str) -> dict | None:
    """读取已缓存的 AI 总结 (不调 LLM).

    mode: 'weekly' | 'monthly' | 'quarterly' | 'yearly'
    返回 {summary, at} 或 None (未生成过).
    """
    dir_map = {
        "weekly": _WEEKLY_DIR,
        "monthly": _MONTHLY_DIR,
        "quarterly": _QUARTERLY_DIR,
        "yearly": _YEARLY_DIR,
    }
    directory = dir_map.get(mode, _MONTHLY_DIR)
    data = _read_json(directory / f"{label}.json")
    if not data:
        return None
    summary = data.get("ai_summary", "")
    if not summary:
        return None
    return {"summary": summary, "at": data.get("ai_summary_at", "")}


# ---------------------------------------------------------------------------
# 日报 — 优先读 LifeOS Daily 文件, 无文件时用事件聚合兜底
# ---------------------------------------------------------------------------

_VAULT_ROOT = Path.home() / "Downloads" / "笔记" / "笔记"
_PERIODIC_ROOT = _VAULT_ROOT / "PARA 管理" / "0. 周期笔记"
_DAILY_ROOT = _PERIODIC_ROOT / "0. 周期笔记"  # 占位, 实际见下
_DAILY_ROOT = _PERIODIC_ROOT  # 0. 周期笔记 根


def _daily_file_path(date: str) -> Path:
    """LifeOS 日报文件路径: 0. 周期笔记/{year}/Daily/{MM}/{date}.md"""
    try:
        y, m, d = date.split("-")
    except ValueError:
        return _DAILY_ROOT / date
    return _DAILY_ROOT / y / "Daily" / m / f"{date}.md"


def _parse_daily_markdown(text: str) -> dict:
    """解析 LifeOS 日报 markdown, 提取关键章节.

    返回 {frontmatter, summary_stats, sections: {标题: 内容}, ai_review}
    """
    result = {
        "frontmatter": {},
        "summary_stats": "",
        "sections": {},
        "ai_review": "",
    }
    # 1) frontmatter
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if m:
        body = text[m.end():]
        fm_text = m.group(1)
        for line in fm_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                result["frontmatter"][k.strip()] = v.strip().strip('"\'')
    else:
        body = text

    # 2) summary callout (> [!summary] ...)
    m2 = re.search(r"^> \[!summary\](.*?)(?=\n## |\Z)", body, re.DOTALL)
    if m2:
        result["summary_stats"] = m2.group(1).strip()

    # 3) 按 ## 分章节
    # 用正则在每个 "## " 处切分
    parts = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m3 = re.match(r"^## (.+?)\n(.*)", p, re.DOTALL)
        if not m3:
            continue
        title = m3.group(1).strip()
        content = m3.group(2).strip()
        if "AI 今日回顾" in title or "AI 回顾" in title:
            result["ai_review"] = content
        else:
            result["sections"][title] = content

    return result


def list_daily_dates() -> list[dict]:
    """返回有日报数据的所有日期, 供日历打点.

    数据源: 1) LifeOS Daily 文件  2) timeline 事件库中有事件的日期
    返回 [{date, has_lifeos, event_count, by_source: {git, files, browser, qingtui, ...}}]
    """
    dates: dict[str, dict] = {}

    def _new_entry(d: str) -> dict:
        return {"date": d, "has_lifeos": False, "event_count": 0,
                "by_source": {"git": 0, "files": 0, "browser": 0, "qingtui": 0}}

    # 1) LifeOS Daily 文件
    if _DAILY_ROOT.is_dir():
        for y_dir in _DAILY_ROOT.glob("*/Daily"):
            for m_dir in y_dir.glob("*"):
                if not m_dir.is_dir():
                    continue
                for f in m_dir.glob("*.md"):
                    d = f.stem  # YYYY-MM-DD
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                        dates.setdefault(d, _new_entry(d))
                        dates[d]["has_lifeos"] = True

    # 2) timeline 事件库中的日期 + 按源聚合 (一次 SQL 聚合, 避免逐日 full query)
    try:
        from timeline.db import get_db
        db = get_db()
        conn = db._conn()
        # 只取最近 90 天的事件做聚合, 控制数据量
        rows = conn.execute(
            """SELECT date, source, COUNT(*) FROM events
               WHERE date >= date('now', '-90 days')
               GROUP BY date, source"""
        ).fetchall()
        for d, source, cnt in rows:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", d or ""):
                continue
            entry = dates.setdefault(d, _new_entry(d))
            if source in entry["by_source"]:
                entry["by_source"][source] += cnt
            entry["event_count"] += cnt
    except Exception:
        pass

    return sorted(dates.values(), key=lambda x: x["date"])


def _build_event_detail_md(date: str) -> dict:
    """从时间线 DB 查询当天事件, 生成按来源分组的 Markdown 明细.

    返回 {git_md, files_md, browser_md, qingtui_md, counts}
    """
    try:
        from timeline.db import get_db
        db = get_db()
        events, _ = db.query(date=date, limit=100000)
    except Exception:
        events = []

    from collections import defaultdict
    buckets = defaultdict(list)
    for e in events:
        buckets[e.get("source", "other")].append(e)

    def ts_hm(ts):
        import time as _t
        try:
            return _t.strftime("%H:%M", _t.localtime(ts / 1000))
        except Exception:
            return ""

    # Git
    git_lines = []
    for e in buckets.get("git", []):
        proj = e.get("target", "") or (e.get("meta") or {}).get("project", "")
        subject = (e.get("title") or "").strip()
        t = ts_hm(e.get("ts", 0))
        git_lines.append(f"- `{t}` 🔧 {subject}" + (f"（{proj}）" if proj else ""))

    # 文件
    files_lines = []
    for e in buckets.get("files", []):
        path = e.get("target", "")
        fname = path.split("/")[-1] if "/" in path else path
        action = e.get("action", "") or "修改"
        t = ts_hm(e.get("ts", 0))
        files_lines.append(f"- `{t}` {action} {fname}")

    # 浏览器
    browser_lines = []
    for e in buckets.get("browser", []):
        title = (e.get("title") or "").strip()
        t = ts_hm(e.get("ts", 0))
        browser_lines.append(f"- `{t}` 🔗 {title}")

    # 轻推
    qingtui_lines = []
    for e in buckets.get("qingtui", []):
        text = (e.get("title") or "").strip()
        session = (e.get("meta") or {}).get("session", "")
        t = ts_hm(e.get("ts", 0))
        prefix = "🔔" if e.get("category") == "mention" else "•"
        line = f"- `{t}` {prefix} {text}"
        if session:
            line += f"（{session}）"
        qingtui_lines.append(line)

    return {
        "git": "\n".join(git_lines),
        "files": "\n".join(files_lines),
        "browser": "\n".join(browser_lines),
        "qingtui": "\n".join(qingtui_lines),
        "counts": {k: len(v) for k, v in buckets.items()},
    }


def get_daily_report(date: str) -> dict:
    """返回某天的日报内容.

    优先读 LifeOS Daily 文件; 无文件则用 today_overview 事件聚合兜底.
    同时附带当天事件明细 (从时间线 DB 实时查询, 不写文件).
    返回 {date, source: 'lifeos'|'events', ...}
    """
    # 事件明细 (始终附带)
    event_detail = _build_event_detail_md(date)

    path = _daily_file_path(date)
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text:
            parsed = _parse_daily_markdown(text)
            return {
                "date": date,
                "source": "lifeos",
                "path": str(path),
                "frontmatter": parsed["frontmatter"],
                "summary_stats": parsed["summary_stats"],
                "sections": parsed["sections"],
                "ai_review": parsed["ai_review"],
                "event_detail": event_detail,
            }

    # 兜底: 事件聚合
    try:
        from timeline.today_overview import today_overview
        overview = today_overview(date)
        overview["event_detail"] = event_detail
        return {"date": date, "source": "events", "overview": overview}
    except Exception as e:
        return {"date": date, "source": "none", "error": str(e), "event_detail": event_detail}


# ---------------------------------------------------------------------------
# 写入 LifeOS 周期笔记 (遵循 LifeOS 模板结构)
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = _PERIODIC_ROOT / "Templates"

# 各周期类型的模板文件 + 章节标题 + 目录名
_LIFEOS_PERIODS = {
    "weekly":    {"dir": "Weekly",    "section": "工作回顾"},
    "monthly":   {"dir": "Monthly",   "section": "工作回顾"},
    "quarterly": {"dir": "Quarterly", "section": "季度工作回顾"},
    "yearly":    {"dir": "Yearly",    "section": "年度工作回顾"},
}


def _load_template(mode: str) -> str:
    """读取 LifeOS 周期笔记模板 (Weekly.md / Monthly.md / ...)."""
    tpl_file = _TEMPLATES_DIR / f"{mode.capitalize()}.md"
    if tpl_file.is_file():
        try:
            return tpl_file.read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


def _lifeos_path(mode: str, label: str) -> Path:
    """周期笔记路径: 0. 周期笔记/{year}/{Weekly|Monthly}/{label}.md"""
    try:
        year = label.split("-")[0]
    except Exception:
        year = "2026"
    dir_name = _LIFEOS_PERIODS.get(mode, {}).get("dir", "Weekly")
    return _PERIODIC_ROOT / year / dir_name / f"{label}.md"


def _insert_into_template(template: str, section_title: str, section_body: str) -> str:
    """把总结章节插入到模板的 '# 复盘' 标题之后."""
    m = re.search(r"^# 复盘\s*\n", template, re.MULTILINE)
    if m:
        return template[:m.end()] + f"{section_title}\n\n{section_body}\n\n" + template[m.end():]
    # 无「# 复盘」则追加在末尾
    return template.rstrip("\n") + f"\n\n# 复盘\n\n{section_title}\n\n{section_body}\n"


def write_summary_to_lifeos(mode: str, label: str) -> dict:
    """把 AI 总结写入 LifeOS 周期笔记, 遵循模板结构.

    mode: 'weekly' | 'monthly' | 'quarterly' | 'yearly'
    返回 {ok, path, action, error?}
    """
    if mode not in _LIFEOS_PERIODS:
        return {"ok": False, "error": f"不支持的周期类型: {mode}"}

    cached = get_cached_ai_summary(mode, label)
    if cached is None:
        if mode == "weekly":
            summary = summarize_weekly(label)
        elif mode == "monthly":
            summary = summarize_monthly(label)
        elif mode == "quarterly":
            summary = summarize_quarterly(label)
        else:
            summary = summarize_yearly(label)
        if summary is None:
            return {"ok": False, "error": "AI 总结生成失败"}
    else:
        summary = cached["summary"]

    section = _LIFEOS_PERIODS[mode]["section"]
    section_title = f"## {section}"
    summary_body = summary.strip()
    path = _lifeos_path(mode, label)

    # 1. 文件不存在 → 用模板创建, 总结插入「# 复盘」之后
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        template = _load_template(mode)
        if template:
            content = _insert_into_template(template, section_title, summary_body)
            content = f"# {label}\n\n" + content
        else:
            # 无模板兜底
            content = f"# {label}\n\n# 复盘\n\n{section_title}\n\n{summary_body}\n"
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(path), "action": "create"}

    # 2. 文件已存在 → 智能合并
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        return {"ok": False, "error": f"读取失败: {path}"}

    # 已有同名章节 → 替换
    pattern = re.compile(
        rf"(^{re.escape(section_title)}\s*\n.*?)(?=\n## |\n```LifeOS|\n# |\n---|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    if pattern.search(existing):
        new_content = pattern.sub(f"{section_title}\n\n{summary_body}", existing)
        action = "replace"
    else:
        # 无该章节 → 插入「# 复盘」之后
        m = re.search(r"^# 复盘\s*\n", existing, re.MULTILINE)
        if m:
            new_content = existing[:m.end()] + f"{section_title}\n\n{summary_body}\n\n" + existing[m.end():]
            action = "insert"
        else:
            new_content = existing.rstrip("\n") + f"\n\n# 复盘\n\n{section_title}\n\n{summary_body}\n"
            action = "append"

    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": f"写入失败: {e}"}

    return {"ok": True, "path": str(path), "action": action}
