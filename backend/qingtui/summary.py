"""每日总结 — 拉指定会话某天消息, 生成总结 + 我的成果."""
import datetime
import json

from .qingtui_api import QtClient, MY_ACCOUNT_ID
from .sessions import TYPE_SINGLE, TYPE_GROUP, get_session_name

# 主题关键词 (用于消息分类)
THEMES = [
    ("组件库/发版", ["组件", "原子库", "版本", "发版", "封板", "maven", "poseidon", "迭代"]),
    ("缺陷/问题", ["缺陷", "bug", "报错", "问题", "异常", "修复", "验证", "复现", "销项"]),
    ("需求/排期", ["需求", "排期", "计划", "清单", "优先级", "930", "820", "830", "上线"]),
    ("权限/菜单", ["权限", "菜单", "角色", "看不到", "没有权限", "命名规范"]),
    ("主数据/回源", ["主数据", "回源", "字典", "同步", "期初"]),
    ("低代码/工作台", ["低代码", "低开", "高开", "lcdp", "工作台", "页面脚本"]),
    ("单据/审批", ["单据", "审批", "入账", "报销", "应付", "应收", "总账", "报账", "共享"]),
    ("跨团队协调", ["平台", "联系", "协调", "咨询", "转给", "找一下", "对接", "沟通"]),
    ("环境/部署", ["环境", "部署", "发版", "迁移", "test", "uat", "准生产", "生产"]),
]


def _parse_body(content):
    """从 content JSON 串提取正文 + 是否回复引用."""
    try:
        c = json.loads(content) if content else {}
    except Exception:
        return {"body": content or "", "is_reply": False, "ref_body": ""}
    body = c.get("body", "") or ""
    msg = c.get("msg", {}) or {}
    ref = msg.get("refBody", "") if isinstance(msg, dict) else ""
    return {"body": body, "is_reply": bool(ref), "ref_body": ref or ""}


def _classify(body):
    """消息归类到一个主题."""
    if not body:
        return None
    for name, kws in THEMES:
        if any(k in body for k in kws):
            return name
    return None


def daily_summary(cli, session_obj, object_type, date_str, session_name=None):
    """生成某会话某天的总结.

    date_str: "YYYY-MM-DD"
    返回: {ok, session, date, total, mine, by_theme, my_highlights, raw_count}
    my_highlights: 我当天发的高价值消息 (含工作关键词, 去掉纯回复词)
    """
    day = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    start_ms = int(day.timestamp() * 1000)
    end_ms = int((day + datetime.timedelta(days=1)).timestamp() * 1000)

    if session_name is None:
        session_name = get_session_name(cli, session_obj, object_type) or session_obj[:8]

    msgs = cli.pull_session_history(session_obj, object_type, start_ms, end_ms)
    if not msgs:
        return {"ok": True, "session": session_name, "date": date_str, "total": 0, "mine": 0,
                "by_theme": {}, "my_highlights": [], "note": "当天无消息"}

    # 解析
    parsed = []
    for m in msgs:
        p = _parse_body(m.get("content", ""))
        parsed.append({
            "id": m.get("id"), "from": m.get("from"), "time": m.get("msgTime", 0),
            "time_str": datetime.datetime.fromtimestamp(m.get("msgTime", 0) / 1000).strftime("%H:%M"),
            "body": p["body"], "is_reply": p["is_reply"], "theme": _classify(p["body"]),
        })

    mine = [m for m in parsed if m["from"] == MY_ACCOUNT_ID]
    others = [m for m in parsed if m["from"] != MY_ACCOUNT_ID]

    # 主题分布 (全部消息)
    by_theme = {}
    for m in parsed:
        t = m["theme"] or "其他"
        by_theme[t] = by_theme.get(t, 0) + 1
    by_theme = dict(sorted(by_theme.items(), key=lambda x: -x[1]))

    # 我的高价值消息 (含工作关键词, 排除纯语气词)
    skip = {"1", "好的", "👌", "ok", "okk", "嗯", "是的", "对", "收到", "好", "可以", "了解", "👌👌", "图片", "[图片]"}
    high_kw = ["版本", "发版", "封板", "缺陷", "需求", "权限", "加密", "主数据", "低代码", "低开", "高开",
               "工作台", "930", "820", "830", "协调", "平台", "ones", "ONES", "分类汇总", "迭代", "清单",
               "排期", "组件", "原子库", "maven", "部署", "迁移", "环境", "审批", "单据", "共享", "修复", "验证"]
    my_highlights = []
    for m in mine:
        b = (m["body"] or "").strip()
        if not b or b in skip or len(b) < 6:
            continue
        if any(k in b for k in high_kw):
            txt = b.replace("\n", " ")
            if len(txt) > 120:
                txt = txt[:120] + "..."
            my_highlights.append({"time": m["time_str"], "text": txt, "theme": m["theme"]})

    # 我@了谁 / 回复了谁 (体现协作)
    my_at = [m for m in mine if "@" in (m["body"] or "")]

    # 时间分布 (我发消息的小时分布, 体现工作时段)
    my_hours = {}
    for m in mine:
        h = m["time_str"][:2] + ":00"
        my_hours[h] = my_hours.get(h, 0) + 1

    return {
        "ok": True,
        "session": session_name,
        "session_obj": session_obj,
        "object_type": object_type,
        "date": date_str,
        "total": len(parsed),
        "mine": len(mine),
        "others": len(others),
        "by_theme": by_theme,
        "my_highlights": my_highlights[:40],
        "my_at_count": len(my_at),
        "my_hours": dict(sorted(my_hours.items())),
        "raw_count": len(msgs),
    }


def daily_summary_multi(cli, targets, date_str):
    """对多个会话生成每日总结, 汇总我的成果.

    targets: [{"cid":..., "type":..., "name":...}, ...]
    返回: {ok, date, sessions:[...], my_total, all_total, achievement}
    achievement: 汇总我的高价值成果 (跨会话去重主题)
    """
    session_results = []
    my_total = 0
    all_total = 0
    all_highlights = []
    all_themes = {}
    for t in targets:
        r = daily_summary(cli, t["cid"], t["type"], date_str, t.get("name"))
        if r.get("ok") and r.get("total", 0) > 0:
            session_results.append(r)
            my_total += r["mine"]
            all_total += r["total"]
            all_highlights.extend(r["my_highlights"])
            for k, v in r["by_theme"].items():
                all_themes[k] = all_themes.get(k, 0) + v
    all_themes = dict(sorted(all_themes.items(), key=lambda x: -x[1]))
    return {
        "ok": True,
        "date": date_str,
        "sessions": session_results,
        "my_total": my_total,
        "all_total": all_total,
        "achievement": {
            "my_message_count": my_total,
            "top_themes": list(all_themes.items())[:8],
            "highlights": all_highlights[:50],
        },
    }
