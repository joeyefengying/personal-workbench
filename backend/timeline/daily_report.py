"""日报生成器 v2 — 按项目维度写 AI 总结到 LifeOS 项目 README。

能力:
  1. 事件→项目映射: 根据 source 特定规则把事件分到项目名下
  2. AI 总结: 调用 llm_summary.summarize_daily 生成每个项目的日报摘要
  3. 预览: 渲染 Markdown 预览 (不落盘)
  4. 提交: 写入各项目 README 的「## YYYY-MM-DD 日报」章节 + 独立日报文件

项目 README 结构 (merge 逻辑):
  - 已有 YAML frontmatter → 保留
  - 已有 deadline checklist → 保留
  - 已有 LifeOS 代码块 (TaskListByTag/BulletListByTag/FileListByTag) → 保留
  - 新插入: 在 deadline 块之后、第一个 LifeOS 块之前, 写入日报章节
  - 如果已有同日期日报 → 替换
"""

import re
import time
from datetime import datetime
from pathlib import Path

from .llm_summary import summarize_daily, _fallback_summary, API_KEY as LLM_API_KEY

HOME = Path.home()
VAULT_ROOT = HOME / "Downloads" / "笔记" / "笔记"
PROJECTS_DIR = VAULT_ROOT / "PARA 管理" / "1. 项目"
PERIODIC_DIR = VAULT_ROOT / "PARA 管理" / "0. 周期笔记"

# ---------------------------------------------------------------
# 事件 → 项目映射
# ---------------------------------------------------------------
# Git 事件: target 就是项目名 (apps.json 显示名), 直接使用
# 轻推事件: target/meta.session 是群名, 从群名提取项目 (关键字匹配)
# 文件事件: 从路径推断项目目录
# 浏览器事件: 不收归属到项目 (global)

QINGTUI_PROJECT_KEYWORDS = {
    "财务前端 fs":     ["财务前端", "fs", "前端组", "财务开发"],
    "低码工作台":       ["低码", "低开", "UC", "通用组件", "可视化"],
    "AI 副业情报":     ["AI", "副业", "情报", "出海"],
    "共享运营":        ["共享运营", "共享"],
    "会计引擎":        ["会计引擎"],
    "五矿统建":        ["五矿", "统建", "财务系统"],
    "平台支撑":        ["平台支撑", "平台组", "基础框架"],
    "流程引擎":        ["流程引擎"],
    "消息中心":        ["消息中心"],
    "文件中心":        ["文件中心"],
    "任务中心":        ["任务中心"],
}


def _match_project_for_qingtui(session_name: str) -> str | None:
    """根据轻推群名匹配项目名."""
    for proj, keywords in QINGTUI_PROJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in session_name:
                return proj
    return None


def _project_from_file_path(file_path: str) -> str | None:
    """从文件路径提取项目名 (匹配 observation/project/{cat}/{name} 或 cisdigital/{name}).

    使用 apps.json 中的目录名→显示名映射, 返回显示名.
    """
    h = str(HOME)
    if file_path.startswith(h):
        file_path = "~" + file_path[len(h):]

    parts = file_path.lstrip("/").split("/")

    # ~/{downloads}/project/{category}/{project_dir}/...
    if "project" in parts:
        idx = parts.index("project")
        # 跳过 project 后面的子类目 (mine/cisdigital/cisdi-work), 取项目目录名
        for j in range(idx + 1, min(len(parts), idx + 4)):
            # 找到项目根目录
            candidate = parts[j]
            # 排除通用子目录
            if candidate in ("mine", "cisdigital", "cisdi-work"):
                continue
            name = dir_name_to_project(candidate)
            if name:
                return name
            # 如果是最后一段, 返回候选
            if j == len(parts) - 1:
                return dir_name_to_project(candidate) or candidate

    # ~/{downloads}/cisdi-work/{project_dir}/...
    for seg in ["cisdi-work", "Downloads"]:
        if seg in parts:
            idx = parts.index(seg)
            if idx + 1 < len(parts):
                cand = parts[idx + 1]
                name = dir_name_to_project(cand)
                if name:
                    return name
                # 继续看下一层
                if idx + 2 < len(parts):
                    cand2 = parts[idx + 2]
                    name2 = dir_name_to_project(cand2)
                    if name2:
                        return name2

    # ~/Downloads/笔记 → 不归到项目 (归类为笔记)
    if "笔记" in parts:
        return None

    return None


def dir_name_to_project(dir_name: str) -> str | None:
    """目录名 → 项目显示名.

    已知映射 (来自 apps.json):
      低码工作台 → low-code
      财务前端 fs → fs
      personal-workbench → personal-workbench (保持原名)
      共享运营 → 已在 QINGTUI_PROJECT_KEYWORDS
    """
    mapping = {
        "low-code": "低码工作台",
        "fs": "财务前端 fs",
        "personal-workbench": "personal-workbench",
        "workbench": "personal-workbench",
    }
    return mapping.get(dir_name, None)


def events_to_projects(events: list[dict]) -> dict[str, list[dict]]:
    """把事件列表按项目分组.

    返回: {项目名: [events, ...]}
    不归属的项目用 '_global' 作为 key.
    """
    projects: dict[str, list[dict]] = {}

    for e in events:
        src = e.get("source", "")
        target = e.get("target", "")
        meta = e.get("meta", {}) or {}
        project = None

        if src == "git":
            # target 直接是项目显示名
            project = target or meta.get("project", "")

        elif src == "qingtui":
            session = meta.get("session", target)
            project = _match_project_for_qingtui(session)

        elif src == "files":
            path = e.get("target", "")
            project = _project_from_file_path(path)

        elif src == "browser":
            # 浏览器事件不归属项目
            project = None

        if not project:
            project = "_global"

        projects.setdefault(project, []).append(e)

    return projects


# ---------------------------------------------------------------
# 预览渲染
# ---------------------------------------------------------------
def render_preview(date: str, events_by_project: dict[str, list[dict]]) -> str:
    """渲染日报预览 Markdown (不落盘).

    调用 LLM 总结, 返回完整的日报正文供前端展示.
    """
    # 分离全局事件 (浏览器等)
    proj_events = {k: v for k, v in events_by_project.items() if k != "_global"}

    if not proj_events:
        return f"# {date} 日报预览\n\n> 暂无归属项目的事件，无法生成项目日报。"

    lines = [f"# {date} 日报预览", ""]

    # AI 总结
    ai_summary = summarize_daily(proj_events, date)
    lines.append(ai_summary)

    # 事件统计附录
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📊 原始数据统计")
    for proj, evts in sorted(proj_events.items(), key=lambda x: -len(x[1])):
        # 按 source 统计
        src_counts = {}
        for e in evts:
            src = e.get("source", "?")
            src_counts[src] = src_counts.get(src, 0) + 1
        parts = [f"{src}={cnt}" for src, cnt in sorted(src_counts.items())]
        lines.append(f"- **{proj}**: {len(evts)} 条 ({', '.join(parts)})")

    return "\n".join(lines)


# ---------------------------------------------------------------
# 提交到项目 README
# ---------------------------------------------------------------
def _find_readme(project_name: str) -> Path | None:
    """查找项目 README 文件."""
    # 格式: {display_name}.README.md
    readme = PROJECTS_DIR / f"{project_name}.README.md"
    if readme.exists():
        return readme

    # 也尝试子目录
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir():
            for f in d.rglob(f"{project_name}.README.md"):
                return f
    return None


def _insert_daily_section(existing_content: str, date: str, summary_md: str) -> str:
    """在 README 中插入或替换日报章节.

    插入位置: 在 frontmatter + deadline 块之后, 第一个 LifeOS 或 ## 章节之前.
    如果已有同日期日报章节, 替换其内容.
    """
    header = f"## {date} 日报"

    # 1. 已有同日期日报 → 替换
    pattern = re.compile(
        rf"(^{re.escape(header)}\s*\n.*?)(?=\n## |\n```LifeOS|\n---|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    if pattern.search(existing_content):
        return pattern.sub(
            f"{header}\n\n{summary_md.strip()}",
            existing_content,
        )

    # 2. 新增: 找到插入点
    # 在 frontmatter (---...---) 之后 + deadline checklist 之后,
    # 第一个 ## 或 ```LifeOS 之前
    lines = existing_content.splitlines()
    result = []
    in_front = False
    front_done = False
    inserted = False

    for i, line in enumerate(lines):
        result.append(line)

        # 跟踪 frontmatter
        if not front_done:
            if line.strip() == "---":
                if not in_front:
                    in_front = True
                else:
                    in_front = False
                    front_done = True
        elif not inserted:
            # frontmatter 之后, 找插入点:
            # deadline checklist 通常以 "- [ ] 截止日期" 开头
            # 之后可能跟 "- 结果描述", 然后 "> 来源:"
            # 在这些元数据行之后, 第一个 ## 或 ```LifeOS 之前插入
            # 向前看: 如果下一行是 ## 或 ```LifeOS, 在这里插入
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith("## ") or next_line.startswith("```LifeOS"):
                    result.append("")
                    result.append(header)
                    result.append("")
                    for sl in summary_md.strip().splitlines():
                        result.append(sl)
                    result.append("")
                    inserted = True

    if not inserted:
        # fallback: 追加到末尾
        result.append("")
        result.append(header)
        result.append("")
        for sl in summary_md.strip().splitlines():
            result.append(sl)
        result.append("")

    return "\n".join(result)


def commit_to_project_readme(date: str, project_name: str, summary_md: str) -> dict:
    """将日报章节写入项目 README.

    返回: {project, readme_path, action: new|replace, error?}
    """
    readme = _find_readme(project_name)
    if not readme:
        return {
            "project": project_name,
            "readme_path": "",
            "action": "skipped",
            "error": f"未找到 {project_name}.README.md; 请先「自动建项目」",
        }

    try:
        existing = readme.read_text(encoding="utf-8")
    except Exception as e:
        return {"project": project_name, "readme_path": str(readme),
                "action": "error", "error": f"读取失败: {e}"}

    new_content = _insert_daily_section(existing, date, summary_md)

    action = "new"
    if f"## {date} 日报" in existing:
        action = "replace"

    try:
        readme.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return {"project": project_name, "readme_path": str(readme),
                "action": "error", "error": f"写入失败: {e}"}

    return {"project": project_name, "readme_path": str(readme), "action": action}


# ---------------------------------------------------------------
# 提交独立日报文件
# ---------------------------------------------------------------

DAILY_AI_REVIEW_PATTERN = re.compile(
    r"(^## 🧠 AI 今日回顾\s*\n.*?)(?=\n## |\n```LifeOS|\n# |\n---|\Z)",
    re.DOTALL | re.MULTILINE,
)


def _build_ai_review_section(date: str, events_by_project: dict, project_summaries: dict[str, str] | None = None) -> str:
    """生成 AI 回顾章节内容 (Markdown).

    只包含任务摘要 — AI 生成的各项目今日总结要点.
    插入到现有 LifeOS 日报的 ## 🧠 AI 今日回顾.
    """
    lines = []
    lines.append(f"> 自动采集于 {time.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    if not project_summaries:
        lines.append("（无项目数据）")
        return "\n".join(lines)

    # 按 project_summaries 渲染每个项目的要点
    for proj, summary_md in sorted(project_summaries.items()):
        # 从 summary_md 中提取 ### {proj} 之后的要点
        m = re.search(rf"^### {re.escape(proj)}\s*\n(.*?)(?=\n### |\n## |\Z)", summary_md, re.DOTALL | re.MULTILINE)
        if not m:
            continue
        block = m.group(1).strip()
        # 去掉列表项符号前缀, 直接作为自然段落
        lines.append(f"**{proj}**")
        lines.append("")
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                stripped = stripped[2:]
            lines.append(stripped)
        lines.append("")

    if len(lines) <= 2:
        lines.append("（无项目数据）")
    return "\n".join(lines)


DAILY_TEMPLATE_PATH = PERIODIC_DIR / "Templates" / "Daily.md"


def _get_daily_base_template(date: str) -> str:
    """获取带 frontmatter 和模板内容的日报基础骨架.

    优先级: 已有 LifeOS 文件(有frontmatter) > Templates/Daily.md > 最简占位.
    如果已有文件但没有 frontmatter, 以模板为主体, 保留已有文件中的 AI 回顾.
    """
    dt = datetime.strptime(date, "%Y-%m-%d")
    daily_file = PERIODIC_DIR / str(dt.year) / "Daily" / f"{dt.month:02d}" / f"{date}.md"

    # 已有文件 → 有 frontmatter 直接用作骨架; 无 frontmatter 则只提取 AI 回顾内容
    existing_ai_review = ""
    if daily_file.is_file():
        try:
            raw = daily_file.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        if raw.strip().startswith("---"):
            return raw
        # 无 frontmatter: 提取已有 AI 回顾 (可能为空)
        m = re.search(r"(## 🧠 AI 今日回顾\s*\n.*)", raw, re.DOTALL)
        if m:
            existing_ai_review = m.group(1).strip()

    # 读模板
    if DAILY_TEMPLATE_PATH.is_file():
        try:
            tpl = DAILY_TEMPLATE_PATH.read_text(encoding="utf-8")
        except OSError:
            tpl = ""
    else:
        tpl = ""

    weekday_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    wd = weekday_names[dt.weekday()]

    body = tpl.strip() if tpl else "## 项目列表\n\n## 日常记录\n\n## 习惯打卡\n"
    skeleton = f"---\ndate: {date}\ntype: daily\ntags:\n  - 时间线\n---\n\n# {date} {wd}\n\n{body}"

    if existing_ai_review:
        skeleton += "\n\n" + existing_ai_review

    return skeleton


# 旧版生成的原始事件章节 (应被清理, 不在 LifeOS 模板内)
_LEGACY_EVENT_SECTION_HEADERS = [
    "## 🔧 代码提交",
    "## 📁 文件变化",
    "## 🌐 浏览器访问",
    "## 💬 轻推消息",
    "## 原始数据统计",
    "## 今日总结",
    "## 待关注",
]


def _strip_legacy_event_sections(text: str) -> str:
    """删除旧版日报里不属于 LifeOS 模板的原始事件章节 (保留 frontmatter + 模板章节 + AI 回顾)."""
    # 逐章节切分, 只保留 模板章节 + AI 回顾
    lines = text.splitlines()
    result: list[str] = []
    skip = False
    for line in lines:
        stripped = line.strip()
        # 遇到章节标题
        if stripped.startswith("## "):
            title = stripped
            # 旧事件章节 → 跳过
            if any(title.startswith(h) for h in _LEGACY_EVENT_SECTION_HEADERS):
                skip = True
                continue
            # 其他章节 (模板 + AI 回顾) → 保留
            skip = False
        if not skip:
            result.append(line)
    return "\n".join(result)


def commit_standalone_daily(date: str, content_md: str) -> Path | None:
    """写入独立的日报文件到 0. 周期笔记/{year}/Daily/{MM}/{date}.md

    如果已有 LifeOS 模板格式文件 (frontmatter 开头):
      1. 清除旧版原始事件章节 (## 🔧 代码提交 等)
      2. 替换/插入「## 🧠 AI 今日回顾」章节
    如果无则基于 Templates/Daily.md 新建.
    """
    dt = datetime.strptime(date, "%Y-%m-%d")
    daily_dir = PERIODIC_DIR / str(dt.year) / "Daily" / f"{dt.month:02d}"
    daily_dir.mkdir(parents=True, exist_ok=True)
    file_path = daily_dir / f"{date}.md"

    try:
        existing = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
    except OSError:
        existing = ""

    # 判断是否 LifeOS 模板格式 (frontmatter 开头)
    if existing.strip().startswith("---"):
        # 1. 清除旧事件章节
        cleaned = _strip_legacy_event_sections(existing)

        # 2. 替换或插入 ## 🧠 AI 今日回顾
        if DAILY_AI_REVIEW_PATTERN.search(cleaned):
            new_content = DAILY_AI_REVIEW_PATTERN.sub(
                "## 🧠 AI 今日回顾\n\n" + content_md.strip(),
                cleaned,
            )
        else:
            # 无 AI 回顾章节 → 插入在 ## 习惯打卡 之前
            insert_point = len(cleaned)
            for pattern_str in [r"\n## 习惯打卡", r"\n## 精力分配", r"\n## 项目列表"]:
                m = re.search(pattern_str, cleaned)
                if m:
                    insert_point = m.start()
                    break
            new_content = (
                cleaned[:insert_point].rstrip()
                + "\n\n## 🧠 AI 今日回顾\n\n"
                + content_md.strip()
                + "\n\n"
                + cleaned[insert_point:].lstrip()
            )

        try:
            file_path.write_text(new_content, encoding="utf-8")
        except OSError:
            return None
        return file_path

    # 新建: 基于 Templates/Daily.md 模板骨架 (含 frontmatter)
    skeleton = _get_daily_base_template(date)
    # skeleton 可能已含 AI 回顾 (从无frontmatter的旧文件提取) → 先替换, 避免重复
    if DAILY_AI_REVIEW_PATTERN.search(skeleton):
        new_full = DAILY_AI_REVIEW_PATTERN.sub(
            "## 🧠 AI 今日回顾\n\n" + content_md.strip(),
            skeleton,
        )
    else:
        new_full = skeleton.strip() + "\n\n## 🧠 AI 今日回顾\n\n" + content_md.strip() + "\n"
    try:
        file_path.write_text(new_full, encoding="utf-8")
        return file_path
    except OSError:
        return None


# ---------------------------------------------------------------
# 对外统一入口
# ---------------------------------------------------------------

def preview_daily_report(date: str, db=None) -> dict:
    """预览日报: 返回 AI 总结 Markdown + 项目归类.

    返回:
      {date, preview_md, projects: {name: {event_count, summary_md}},
       has_ai: bool, events_total: int}
    """
    from .db import get_db
    db = db or get_db()
    events, total = db.query(date=date, limit=100000)
    if not events:
        return {
            "date": date, "preview_md": "",
            "projects": {}, "has_ai": False, "events_total": 0,
            "error": f"{date} 暂无事件，请先采集数据",
        }

    by_project = events_to_projects(events)

    # 生成总预览
    preview_md = render_preview(date, by_project)

    # 各项目摘要 (分离全局事件)
    proj_events = {k: v for k, v in by_project.items() if k != "_global"}
    projects = {}
    for proj, evts in proj_events.items():
        # 为每个项目单独生成摘要
        single = {proj: evts}
        summary = summarize_daily(single, date)
        # 去掉外层 ## 今日总结 / ## 待关注 包装, 只取项目级内容
        projects[proj] = {
            "event_count": len(evts),
            "summary_md": summary.strip(),
        }

    return {
        "date": date,
        "preview_md": preview_md,
        "projects": projects,
        "has_ai": bool(LLM_API_KEY),
        "events_total": total,
    }


def commit_daily_report(date: str, project_summaries: dict[str, str] | None = None,
                        db=None) -> dict:
    """提交日报: 写入各项目 README + 独立日报文件.

    project_summaries: {项目名: summary_md}, 如果为空则从事件重新生成
    返回: {date, results: [{project, action, ...}], daily_path}
    """
    from .db import get_db
    db = db or get_db()
    events, total = db.query(date=date, limit=100000)

    by_project = events_to_projects(events)
    proj_events = {k: v for k, v in by_project.items() if k != "_global"}

    # 如果没有传入 summaries, 自动生成
    if not project_summaries:
        project_summaries = {}
        for proj, evts in proj_events.items():
            summary = summarize_daily({proj: evts}, date)
            project_summaries[proj] = summary.strip()

    results = []
    for proj, summary_md in sorted(project_summaries.items()):
        r = commit_to_project_readme(date, proj, summary_md)
        results.append(r)

    # 写入独立日报 (AI 回顾章节)
    ai_review_md = _build_ai_review_section(date, by_project, project_summaries)
    daily_path = commit_standalone_daily(date, ai_review_md)

    return {
        "date": date,
        "results": results,
        "daily_path": str(daily_path) if daily_path else "",
        "events_total": total,
        "projects_updated": sum(1 for r in results if r["action"] in ("new", "replace")),
    }