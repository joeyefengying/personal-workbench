"""轻推 (Qingtui) 集成模块 — 个人工作台 backend.

能力:
- 会话发现: 列出全部最近会话, 补全名称, 标注"我是否回复过"和活跃度
- 每日总结: 拉指定会话某天消息, 生成总结 + 我的成果
- 任务提取: 从消息提取待办, 判断处理状态(已读/已处理/待处理)并标注依据
- 人工核实: 记录用户对任务的人工确认状态

依赖运行中的轻推桌面端(调试端口 9222)提供 token。
签名算法已逆向, 见 qingtui_api.py。
"""
from .qingtui_api import QtClient, get_token, MY_ACCOUNT_ID
from .sessions import list_sessions, get_session_name
from .summary import daily_summary, daily_summary_multi
from .tasks import extract_tasks, verify_task, load_tasks

__all__ = [
    "QtClient", "get_token", "MY_ACCOUNT_ID",
    "list_sessions", "get_session_name",
    "daily_summary", "extract_tasks", "verify_task", "load_tasks",
]
