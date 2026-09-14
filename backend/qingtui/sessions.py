"""会话发现 — 列出全部最近会话, 补全名称, 标注活跃度与"我是否回复过"."""
import time

from .qingtui_api import QtClient, MY_ACCOUNT_ID

# 会话对象类型
TYPE_SINGLE = 1   # 单聊
TYPE_GROUP = 2    # 群聊
TYPE_SYSTEM = 0   # 系统/应用入口 (chatObjId 是数字串)


def _batch_groups(cli, ids, batch=20):
    res = {}
    for i in range(0, len(ids), batch):
        st, r = cli.channel_info_list(ids[i:i + batch])
        for item in (r.get("data", {}) or {}).get("resultList", []) or []:
            res[item["id"]] = item.get("name") or "(无名)"
        time.sleep(0.1)
    return res


def _batch_people(cli, ids, batch=20):
    res = {}
    for i in range(0, len(ids), batch):
        st, r = cli.account_info_base(ids[i:i + batch])
        for item in (r.get("data", {}) or {}).get("accountInfos", []) or []:
            res[item["accountId"]] = item.get("userName") or item.get("remarks") or "(无名)"
        time.sleep(0.1)
    return res


def get_session_name(cli, chat_obj_id, obj_type):
    """查单个会话名称. 群->channel/info, 单聊->account/other/info."""
    try:
        if obj_type == TYPE_GROUP:
            st, r = cli.channel_info_list([chat_obj_id])
            rl = (r.get("data", {}) or {}).get("resultList", []) or []
            return rl[0].get("name") if rl else None
        if obj_type == TYPE_SINGLE:
            st, r = cli.account_info_base([chat_obj_id])
            ai = (r.get("data", {}) or {}).get("accountInfos", []) or []
            return ai[0].get("userName") if ai else None
    except Exception:
        return None
    return None


def list_sessions(cli=None, fetch_names=True):
    """列出最近活跃会话, 返回按最后消息时间倒序的列表.

    每项: {cid, type, type_name, name, last_t, last_t_str, my_replies, msg_count, unack}
    my_replies: 最近消息里我回复的条数 (>0 说明我近期在沟通)
    """
    own = False
    if cli is None:
        from .qingtui_api import make_client
        cli = make_client()
        own = True
        if cli is None:
            return {"ok": False, "error": "未取到轻推 token (轻推是否以调试端口运行?)", "sessions": []}

    st, r = cli.chat_list()
    if r.get("code") != 0:
        return {"ok": False, "error": f"chat_list 失败: code={r.get('code')}", "sessions": []}
    chats = (r.get("data", {}) or {}).get("chatList", []) or []

    group_ids, single_ids = [], []
    for ch in chats:
        s = ch.get("status", {}) or {}
        cid, tp = s.get("chatObjId", ""), s.get("chatObjType")
        if tp == TYPE_GROUP:
            group_ids.append(cid)
        elif tp == TYPE_SINGLE:
            single_ids.append(cid)

    gnames = _batch_groups(cli, group_ids) if fetch_names else {}
    anames = _batch_people(cli, single_ids) if fetch_names else {}

    import datetime
    rows = []
    for ch in chats:
        s = ch.get("status", {}) or {}
        msgs = ch.get("msgList", []) or []
        cid = s.get("chatObjId", "")
        tp = s.get("chatObjType")
        last_t = max((m.get("msgTime", 0) for m in msgs if isinstance(m, dict)), default=0)
        my_rep = sum(1 for m in msgs if isinstance(m, dict) and m.get("from") == MY_ACCOUNT_ID)
        name = gnames.get(cid) if tp == TYPE_GROUP else anames.get(cid, "?")
        rows.append({
            "cid": cid,
            "type": tp,
            "type_name": {TYPE_SINGLE: "单聊", TYPE_GROUP: "群聊", TYPE_SYSTEM: "系统"}.get(tp, "?"),
            "name": name or "?",
            "last_t": last_t,
            "last_t_str": datetime.datetime.fromtimestamp(last_t / 1000).strftime("%m-%d %H:%M") if last_t else "",
            "my_replies": my_rep,
            "msg_count": len(msgs),
            "unack": s.get("unack", 0),
        })
    rows.sort(key=lambda x: -x["last_t"])

    summary = {
        "total": len(rows),
        "groups": sum(1 for r in rows if r["type"] == TYPE_GROUP),
        "singles": sum(1 for r in rows if r["type"] == TYPE_SINGLE),
        "i_replied": sum(1 for r in rows if r["my_replies"] > 0),
    }
    return {"ok": True, "sessions": rows, "summary": summary}
