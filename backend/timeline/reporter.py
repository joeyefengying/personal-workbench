"""日报生成器 — 与 Obsidian LifeOS Pro 深度集成。

能力:
  1. 自动创建 LifeOS 项目: 扫描 git 项目/工作目录 → 在 PARA 管理/1. 项目/ 下建 README.md
     (带 tags frontmatter, 供 LifeOS 的 TaskListByTag/BulletListByTag/FileListByTag 聚合)
  2. 生成 LifeOS 兼容日报: 写入 0. 周期笔记/2026/Daily/{MM}/YYYY-MM-DD.md
     用 {{snapshot:Project}} 快照 + 事件正文 + tags 关联, 让 LifeOS 自动向上汇总周/月/年报
  3. Base 视图: 时间线总览 .base 文件

设计原则:
  - 只写 Obsidian 文件, 不触碰事件库; 幂等可重跑
  - 项目创建用"目录名 + apps.json 中文名映射"
  - 日报复用 LifeOS Daily 模板结构, 让 snapshot/ProjectListByTime 正常工作
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path.home()
# 个人笔记库根 (Obsidian vault)
VAULT_ROOT = HOME / "Downloads" / "笔记" / "笔记"
# LifeOS 目录 (从 data.json 读取, 这里用默认值兜底)
PARA_ROOT = VAULT_ROOT / "PARA 管理"
PROJECTS_DIR = PARA_ROOT / "1. 项目"
PERIODIC_DIR = PARA_ROOT / "0. 周期笔记"
DAILY_TEMPLATE_DIR = PERIODIC_DIR / "Templates"

# 数据源 -> 图标/名称 映射
SOURCE_META = {
    "files":   {"icon": "📁", "name": "文件变化"},
    "browser": {"icon": "🌐", "name": "浏览器访问"},
    "qingtui": {"icon": "💬", "name": "轻推消息"},
    "git":     {"icon": "🔧", "name": "代码提交"},
    "other":   {"icon": "📌", "name": "其他"},
}

ACTION_ICONS = {
    "add": "➕", "mod": "✏️", "del": "🗑️",
    "visit": "🔗", "发言": "💬", "提交": "🔧", "浏览": "🔗",
}


def _read_lifeos_config() -> dict:
    """读取 LifeOS 插件 data.json, 获取目录配置 (失败返回默认)."""
    config = {
        "projectsPath": "PARA 管理/1. 项目",
        "periodicNotesPath": "PARA 管理/0. 周期笔记",
        "projectsTemplateFilePath": "",
    }
    data_json = VAULT_ROOT / ".obsidian" / "plugins" / "lifeos-pro" / "data.json"
    if data_json.exists():
        try:
            cfg = json.loads(data_json.read_text(encoding="utf-8"))
            config["projectsPath"] = cfg.get("projectsPath") or config["projectsPath"]
            config["periodicNotesPath"] = cfg.get("periodicNotesPath") or config["periodicNotesPath"]
            config["projectsTemplateFilePath"] = cfg.get("projectsTemplateFilePath", "")
        except Exception:
            pass
    return config


LIFEOS_CONFIG = _read_lifeos_config()


# ---------------------------------------------------------------
# 项目名称映射 (目录名 -> 中文名)
# ---------------------------------------------------------------
def _load_apps_name_map() -> dict:
    """从 apps.json 读 目录名 -> 中文名 映射."""
    apps_json = Path(__file__).resolve().parent.parent / "apps.json"
    name_map = {}
    if apps_json.exists():
        try:
            cfg = json.loads(apps_json.read_text(encoding="utf-8"))
            for cat in cfg.get("categories", []):
                for proj in cat.get("projects", []):
                    p = Path(proj.get("path", "")).expanduser()
                    name_map[p.name] = proj.get("name", p.name)
                    for child in proj.get("children", []):
                        cp = Path(proj.get("path", "")).expanduser() / child.get("dir", "")
                        name_map[cp.name] = child.get("name", cp.name)
        except Exception:
            pass
    return name_map


APPS_NAME_MAP = _load_apps_name_map()


def project_display_name(dir_name: str) -> str:
    """目录名 -> 友好显示名 (优先 apps.json 中文名)."""
    return APPS_NAME_MAP.get(dir_name, dir_name)


# ---------------------------------------------------------------
# 项目自动创建
# ---------------------------------------------------------------
PROJECT_TEMPLATE = """---
tags: ["{tag}"]
aliases: ["#{tag}"]
---

%%设置项目截止日期，及其结果描述%%
- [ ] 截止日期 📅 {year}-xx-xx
- 结果描述

> 来源: 个人工作台时间线自动创建 · {created}

## 任务
%%根据当前文件的 Properties 的 tags 字段查询任务%%
```LifeOS
TaskListByTag
```

## 列表
%%根据当前文件的 Properties 的 tags 字段查询子弹列表%%
```LifeOS
BulletListByTag
```

## 文件
%%根据当前文件的 Properties 的 tags 字段查询文件列表%%
```LifeOS
FileListByTag
```
"""


def ensure_project(project_name: str, display_name: str | None = None) -> Path | None:
    """确保 LifeOS 项目存在, 不存在则创建. 返回项目文件路径."""
    display_name = display_name or project_display_name(project_name)
    projects_root = VAULT_ROOT / LIFEOS_CONFIG["projectsPath"]

    # 项目文件 = {display_name}.README.md, 放在 1. 项目/ 根目录下
    readme = projects_root / f"{display_name}.README.md"

    if readme.exists():
        return readme

    # 创建
    projects_root.mkdir(parents=True, exist_ok=True)
    content = PROJECT_TEMPLATE.format(
        tag=display_name,
        year=datetime.now().year,
        created=time.strftime("%Y-%m-%d %H:%M"),
    )
    readme.write_text(content, encoding="utf-8")
    return readme


def ensure_projects_from_events(daily_summary: dict) -> list[Path]:
    """根据某天事件里的项目名, 自动创建缺失的 LifeOS 项目."""
    created = []
    # git 提交里的项目名 (已经是显示名格式)
    for e in daily_summary.get("git", []):
        proj = e.get("target", "") or (e.get("meta", {}) or {}).get("project", "")
        if proj:
            # 直接以显示名创建项目目录
            p = ensure_project(proj, display_name=proj)
            if p and p not in created:
                created.append(p)
    return created


# ---------------------------------------------------------------
# LifeOS 兼容日报
# ---------------------------------------------------------------
def _lifeos_daily_dir(year: int, month: int) -> Path:
    """LifeOS 日报目录: 0. 周期笔记/2026/Daily/09/"""
    return VAULT_ROOT / LIFEOS_CONFIG["periodicNotesPath"] / str(year) / "Daily" / f"{month:02d}"


def _daily_template_text() -> str:
    """读取 LifeOS Daily 模板 (若存在), 否则用内置模板."""
    tpl = DAILY_TEMPLATE_DIR / "Daily.md"
    if tpl.exists():
        return tpl.read_text(encoding="utf-8")
    return """## 项目列表
%%项目的今日快照%%
{{snapshot:Project}}

## 日常记录
%%你的记录%%

## 习惯打卡
%%打卡不会被统计为任务%%

## 精力分配
%%今日的项目列表，根据耗时情况，自动统计项目耗时占比%%
```LifeOS
ProjectListByTime
```
"""


def render_lifeos_daily(date: str, daily_summary: dict) -> str:
    """渲染 LifeOS 兼容日报.

    结构:
      1. frontmatter (date + tags 关联的项目)
      2. 事件正文 (按数据源分组)
      3. LifeOS 模板体 ({{snapshot:Project}} + ProjectListByTime 代码块)
    """
    by_source = daily_summary.get("by_source", {})
    total = daily_summary.get("total", 0)

    # 收集今日涉及的项目名 (用于 tags 关联)
    project_tags = set()
    for e in daily_summary.get("git", []):
        proj = e.get("target", "") or (e.get("meta", {}) or {}).get("project", "")
        if proj:
            project_tags.add(project_display_name(proj))
    # 文件事件的顶层目录也作为项目
    for e in daily_summary.get("files", []):
        path = e.get("target", "")
        # 提取 ~/Downloads/project/mine/xxx 或 cisdigital/xxx 的顶层项目名
        parts = path.replace(str(HOME) + "/", "").split("/")
        if "project" in parts:
            idx = parts.index("project")
            if idx + 1 < len(parts):
                project_tags.add(project_display_name(parts[idx + 1]))

    lines = []
    # frontmatter
    lines.append("---")
    lines.append(f"date: {date}")
    lines.append("type: daily")
    lines.append("tags:")
    for t in sorted(project_tags):
        lines.append(f'  - "{t}"')
    if not project_tags:
        lines.append("  - 时间线")
    lines.append("---")
    lines.append("")

    # 标题
    dt = datetime.strptime(date, "%Y-%m-%d")
    weekday = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][dt.weekday()]
    lines.append(f"# {date} {weekday}")
    lines.append("")

    # 事件摘要
    lines.append(f"> [!summary] 今日共记录 **{total}** 条事件")
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
        meta = SOURCE_META.get(src, SOURCE_META["other"])
        lines.append(f"> - {meta['icon']} {meta['name']}: {cnt} 条")
    lines.append("")

    # 事件正文 (按数据源)
    for src in ["git", "files", "browser", "qingtui"]:
        items = daily_summary.get(src, [])
        if not items:
            continue
        meta = SOURCE_META.get(src, SOURCE_META["other"])
        lines.append(f"## {meta['icon']} {meta['name']} ({len(items)})")
        lines.append("")
        for e in sorted(items, key=lambda x: x["ts"])[:50]:
            ts_str = time.strftime("%H:%M", time.localtime(e["ts"] / 1000))
            icon = ACTION_ICONS.get(e.get("action", ""), "•")
            title = e.get("title", "") or e.get("target", "")
            # git 事件带项目 wikilink
            if src == "git":
                proj = e.get("target", "")
                disp = project_display_name(proj)
                lines.append(f"- `{ts_str}` {icon} [[{disp}|{title}]]")
            else:
                lines.append(f"- `{ts_str}` {icon} {title}")
        lines.append("")

    # LifeOS 模板体 (正常章节)
    lines.append(_daily_template_text())

    return "\n".join(lines)


class LifeOSDailyReport:
    """LifeOS 兼容日报写入器."""

    def render(self, date: str, daily_summary: dict) -> str:
        return render_lifeos_daily(date, daily_summary)

    def write(self, date: str, daily_summary: dict) -> Path:
        dt = datetime.strptime(date, "%Y-%m-%d")
        d = _lifeos_daily_dir(dt.year, dt.month)
        d.mkdir(parents=True, exist_ok=True)
        md = self.render(date, daily_summary)
        path = d / f"{date}.md"

        # 已有 LifeOS 模板文件 → merge (只更新事件正文, 保留模板体/AI 回顾)
        if path.is_file():
            try:
                existing = path.read_text(encoding="utf-8")
            except OSError:
                existing = ""
            if existing.strip().startswith("---"):
                # 提取 frontmatter + 保留模板体章节, 用新事件正文替换中间部分
                # 简化: 保留 frontmatter, 替换 frontmatter 之后到模板体之前的内容
                import re as _re
                # 找模板体起始 (## 项目列表)
                tpl_start = existing.find("## 项目列表")
                if tpl_start == -1:
                    tpl_start = existing.find("## 习惯打卡")
                if tpl_start == -1:
                    tpl_start = existing.find("## 精力分配")

                if tpl_start != -1:
                    # 保留 frontmatter
                    fm_end = existing.find("---", 1) + 3  # 第二个 ---
                    fm = existing[:fm_end] if fm_end > 3 else ""
                    tpl_tail = existing[tpl_start:]
                    # 新正文 = frontmatter + 新事件正文 + 模板体
                    body = md[md.find("---", 1)+3:] if md.startswith("---") else md
                    # 去掉新 md 里自己的模板体 (避免重复)
                    body_tpl = body.find("## 项目列表")
                    if body_tpl == -1:
                        body_tpl = body.find("## 习惯打卡")
                    if body_tpl == -1:
                        body_tpl = body.find("## 精力分配")
                    if body_tpl != -1:
                        body = body[:body_tpl]
                    new_content = fm + body.rstrip() + "\n\n" + tpl_tail.lstrip()
                    path.write_text(new_content, encoding="utf-8")
                    return path

        # 新建或非模板文件 → 直接写
        path.write_text(md, encoding="utf-8")
        return path


def generate_daily_report(date: str, db=None) -> dict:
    """生成某天的 LifeOS 日报 + 自动创建项目."""
    from .db import get_db
    db = db or get_db()
    summary = db.daily_summary(date)

    # 自动创建缺失项目
    created_projects = ensure_projects_from_events(summary)

    reporter = LifeOSDailyReport()
    path = reporter.write(date, summary)
    return {
        "path": str(path),
        "md": path.read_text(encoding="utf-8"),
        "summary": summary,
        "created_projects": [str(p) for p in created_projects],
    }


# ---------------------------------------------------------------
# Base 视图 (obsidian-bases)
# ---------------------------------------------------------------
BASE_FILE = VAULT_ROOT / "99_系统" / "时间线总览.base"

BASE_YAML = """# 时间线总览 Base 视图
# 用 obsidian-bases 语法, 把周期笔记的日报聚合为表格视图

filters:
  and:
    - file.inFolder("PARA 管理/0. 周期笔记")
    - '/^\\d{4}-\\d{2}-\\d{2}$/.matches(file.basename)'

formulas:
  day_of_week: 'date(file.basename).format("dddd")'

properties:
  formula.day_of_week:
    displayName: "星期"
  date:
    displayName: "日期"

views:
  - type: table
    name: "每日时间线"
    order:
      - file.name
      - formula.day_of_week
"""


def generate_obsidian_base(base_file: Path = BASE_FILE) -> Path:
    """生成/更新 Obsidian Base 视图文件."""
    base_file.parent.mkdir(parents=True, exist_ok=True)
    base_file.write_text(BASE_YAML, encoding="utf-8")
    return base_file


def generate_obsidian_daily(date: str, db=None) -> dict:
    """生成日报 + 自动建项目 + Base 视图, 返回结果. (对外统一入口)"""
    result = generate_daily_report(date, db)
    base_path = generate_obsidian_base()
    result["base"] = str(base_path)
    return result