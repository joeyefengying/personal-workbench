"""统一时间线模块 (LifeOS Timeline Backend)
将文件变化、浏览器历史、轻推消息等多源事件汇聚到 SQLite 事件流，
同时支持生成 Obsidian 日报/Base 视图。

数据源:
  - files  : macOS 文件系统事件 (增/删/改)
  - browser: Chrome/Safari 浏览器历史访问记录
  - qingtui: 轻推聊天消息 + 待办任务
  - git    : 各项目 Git 提交 (复用现有 git 扫描)
  - medical: (预留) 健康/医疗数据

存储: SQLite backend/timeline/events.db
展示: 前端 Timeline 页面 + Obsidian 日报 Base 视图
"""
from .collector import (
    Collector,
    FileCollector,
    BrowserCollector,
    QingtuiCollector,
    GitCollector,
    run_all_collectors,
)
from .db import (
    EventDB,
    get_db,
    migrate,
)
from .reporter import (
    LifeOSDailyReport,
    generate_daily_report,
    generate_obsidian_daily,
    generate_obsidian_base,
    render_lifeos_daily,
    ensure_project,
    ensure_projects_from_events,
)
from .daily_report import (
    events_to_projects,
    render_preview,
    preview_daily_report,
    commit_daily_report,
)

__all__ = [
    # collectors
    "Collector", "FileCollector", "BrowserCollector",
    "QingtuiCollector", "GitCollector", "run_all_collectors",
    # database
    "EventDB", "get_db", "migrate",
    # reporters
    "LifeOSDailyReport", "generate_daily_report",
    "generate_obsidian_daily", "generate_obsidian_base",
    "render_lifeos_daily", "ensure_project", "ensure_projects_from_events",
    # daily report v2
    "events_to_projects", "render_preview",
    "preview_daily_report", "commit_daily_report",
]