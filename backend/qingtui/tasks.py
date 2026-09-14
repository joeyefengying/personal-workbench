"""任务提取与状态追踪.

需求 2: 从消息提取需要我处理的工作项 (to-do)
需求 3: 追踪处理进度 — 我回复了=已读; 回复内容含"已完成/已提交/已修复"等=已处理; 标注判断依据
需求 4: 人工核实 — 用户点一下确认完成/未完成
"""
import datetime
import json
import os
import re

from .qingtui_api import QtClient, MY_ACCOUNT_ID
from .sessions import get_session_name, TYPE_SINGLE, TYPE_GROUP

TASKS_FILE = os.path.join(os.path.dirname(__file__), "..", "qingtui_data", "tasks.json")

# @我 的消息 (需要我处理) — 排除我自己发的
AT_ME_PATTERN = re.compile(r"@\S*张浩|@所有人|@all", re.IGNORECASE)

# "需要处理"的信号词 (别人发给我、@我、含疑问/请求)
TODO_SIGNAL = ["@张浩", "@所有人", "麻烦", "请", "看一下", "帮看", "帮忙", "处理一下",
               "确认一下", "核实", "需要你", "麻烦你", "帮我", "看一下这个", "看下",
               "什么时候", "能不能", "可以吗", "怎么", "？", "?", "检查", "跟进", "推进"]

# "已处理"的信号词 (我回复里含这些 = 我处理过了)
DONE_SIGNAL = ["已完成", "已提交", "已修复", "已处理", "已解决", "已经", "搞定了", "好了",
               "发你了", "已发", "提交了", "部署了", "更新了", "改好了", "修复了", "处理了",
               "我看了", "确认了", "核对完", "验证通过", "可以了", "已同步", "已配置", "已加",
               "我联系", "我转给", "已经安排", "已安排"]

# "已读但未明确处理" 的信号 (我回复了但只是应答)
READ_ONLY = ["好的", "收到", "了解", "嗯", "👌", "ok", "看一下", "我看看", "稍后", "马上",
             "在弄", "在处理", "我看下", "好的我看下", "收到我看下"]


def _parse_body(content):
    try:
        c = json.loads(content) if content else {}
    except Exception:
        return content or ""
    return c.get("body", "") or ""


def _load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            return json.loads(open(TASKS_FILE, encoding="utf-8").read())
        except Exception:
            pass
    return {"tasks": [], "verified": {}}


def _save_tasks(d):
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    open(TASKS_FILE, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))


def _task_key(session_obj, msg_id):
    return f"{session_obj}:{msg_id}"


def extract_tasks(cli, targets, date_str):
    """从指定会话某天的消息提取待办任务.

    targets: [{"cid":..., "type":..., "name":...}, ...]
    返回: {ok, date, tasks:[...]}
    每个任务:
      id, source(群名), source_obj, text(任务内容摘要), from(谁派的), time,
      status: pending|read|done|verified|cancelled
      evidence: 判断依据 (我回复了什么/何时回复)
      verified: 人工核实状态 (null|done|not_done)
    """
    day = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    start_ms = int(day.timestamp() * 1000)
    end_ms = int((day + datetime.timedelta(days=1)).timestamp() * 1000)

    store = _load_tasks()
    verified_map = store.get("verified", {})

    tasks = []
    for t in targets:
        cid, tp, name = t["cid"], t["type"], t.get("name") or cid[:8]
        msgs = cli.pull_session_history(cid, tp, start_ms, end_ms)
        if not msgs:
            continue
        # 建时间索引: 找我在这条消息之后的回复
        parsed = []
        for m in msgs:
            parsed.append({
                "id": m.get("id"), "from": m.get("from"),
                "time": m.get("msgTime", 0),
                "body": _parse_body(m.get("content", "")),
            })
        parsed.sort(key=lambda x: x["time"])

        for i, m in enumerate(parsed):
            if m["from"] == MY_ACCOUNT_ID:
                continue  # 我自己发的不是任务
            body = m["body"]
            if not body:
                continue
            # 是否是需要我处理的?
            # 1) @我 或 @所有人 -> 一定是我的任务
            # 2) 单聊里对方发的消息 -> 默认都是对我的请求 (单聊就是和我对话)
            # 3) 群聊里 @别人 的消息 -> 不是我的任务 (避免误抓)
            at_me = "@张浩" in body or "@所有人" in body
            if tp == TYPE_SINGLE:
                is_my_task = True  # 单聊: 对方说的每句话都可能是给我的任务
            else:
                is_my_task = at_me  # 群聊: 只有 @我/@所有人 才算
            if not is_my_task:
                continue
            # 单聊里排除纯通知/寒暄 (太短或无实质内容)
            if tp == TYPE_SINGLE and len(body.strip()) < 4:
                continue

            # 找我在这条消息后 30 分钟内的回复
            my_replies = []
            for j in range(i + 1, len(parsed)):
                if parsed[j]["from"] != MY_ACCOUNT_ID:
                    continue
                if parsed[j]["time"] - m["time"] > 30 * 60 * 1000:
                    break
                if parsed[j]["body"]:
                    my_replies.append(parsed[j]["body"])

            # 判断状态
            key = _task_key(cid, m["id"])
            verified = verified_map.get(key)
            if verified:
                status = "verified"
                evidence = f"人工核实: {verified}"
            elif not my_replies:
                status = "pending"
                evidence = "未检测到我的回复 (可能未读/未处理)"
            elif any(any(d in r for d in DONE_SIGNAL) for r in my_replies):
                status = "done"
                done_reply = next((r for r in my_replies if any(d in r for d in DONE_SIGNAL)), my_replies[0])
                evidence = f"我回复({len(my_replies)}条): \"{done_reply[:60]}\" 含完成信号词"
            elif any(r.strip() in READ_ONLY or any(s in r for s in READ_ONLY) for r in my_replies):
                status = "read"
                evidence = f"我回复: \"{my_replies[0][:60]}\" (仅应答, 未明确处理)"
            else:
                status = "read"
                evidence = f"我回复({len(my_replies)}条): \"{my_replies[0][:60]}\" (已读, 处理情况待确认)"

            # 任务摘要
            text = body.replace("\n", " ").strip()
            if len(text) > 150:
                text = text[:150] + "..."

            tasks.append({
                "id": key,
                "source": name,
                "source_obj": cid,
                "object_type": tp,
                "text": text,
                "from": m["from"],
                "time": datetime.datetime.fromtimestamp(m["time"] / 1000).strftime("%H:%M"),
                "time_ms": m["time"],
                "at_me": at_me,
                "status": status,
                "evidence": evidence,
                "verified": verified,
                "my_replies": [r[:100] for r in my_replies[:5]],
            })

    tasks.sort(key=lambda x: x["time_ms"])
    return {
        "ok": True,
        "date": date_str,
        "total": len(tasks),
        "by_status": {
            "pending": sum(1 for t in tasks if t["status"] == "pending"),
            "read": sum(1 for t in tasks if t["status"] == "read"),
            "done": sum(1 for t in tasks if t["status"] == "done"),
            "verified": sum(1 for t in tasks if t["status"] == "verified"),
        },
        "tasks": tasks,
    }


def verify_task(task_id, verified_status):
    """人工核实任务. verified_status: 'done' | 'not_done'."""
    if verified_status not in ("done", "not_done"):
        return {"ok": False, "error": "status 必须是 done 或 not_done"}
    store = _load_tasks()
    store.setdefault("verified", {})[task_id] = verified_status
    _save_tasks(store)
    return {"ok": True, "task_id": task_id, "verified": verified_status}


def load_tasks():
    """读取已保存的核实记录."""
    return _load_tasks()
