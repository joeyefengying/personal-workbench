"""轻推 API 客户端 — 独立调用, 无需轻推界面.

签名算法 (从 app.asar 逆向, 219 样本验证 72/73 匹配):
  Signature = sha256(ts + nonce + accountId + client + paramStr) | ts | nonce | accountId
  paramStr = c(data): qs-stringify 后按 key 分组, 多值 k=[sorted,vals], 单值 k=v, sortBy 后 join("&")

token (Bearer JWT) 通过 CDP 从运行中的轻推 localStorage 获取, 需轻推以
--remote-debugging-port=9222 --remote-allow-origins=* 启动.
"""
import hashlib
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://web.qingtui.com/api"
CLIENT = "QingTui/71301;Macintosh, Intel Mac OS X 10_15_7, 26.5.2;PC;0"
MY_ACCOUNT_ID = "344548d972f44d799aeea39ae3e231ba"  # 张浩 W12094

CDP_PORT = 9222


# ---------- 参数序列化 (复刻源码里的 c()) ----------
def _c(data):
    """qs-stringify data, group by key, multi-value -> k=[sorted,vals], sort items, join &."""
    if not data:
        return ""
    grouped = {}
    for k, v in data.items():
        if isinstance(v, list):
            grouped.setdefault(k, [])
            grouped[k].extend(str(x) for x in v)
        else:
            grouped.setdefault(k, []).append(str(v))
    items = []
    for k, vals in grouped.items():
        if len(vals) > 1:
            items.append(urllib.parse.unquote(f"{k}=[{','.join(sorted(vals))}]"))
        else:
            items.append(urllib.parse.unquote(f"{k}={vals[0]}"))
    return "&".join(sorted(items))


def sign_url(account_id, data, ts, nonce, client=CLIENT):
    """生成 Signature 头. 返回 hash|ts|nonce[|accountId]."""
    parts = [str(ts), str(nonce)]
    if account_id:
        parts.append(account_id)
    parts.append(client)
    u = _c(data)
    if u:
        parts.append(u)
    h = hashlib.sha256("".join(parts).encode()).hexdigest()
    sig = f"{h}|{ts}|{nonce}"
    if account_id:
        sig += f"|{account_id}"
    return sig


class QtClient:
    """轻推 HTTP 客户端. token 由 get_token() 提供."""

    def __init__(self, token=None, account_id=MY_ACCOUNT_ID):
        self.token = token
        self.account_id = account_id

    def _req(self, path, method="GET", params=None, body=None, timeout=20):
        url = f"{API_BASE}/{path}"
        ts = int(time.time() * 1000)
        nonce = int(65535 * random.random())
        data = params if method == "GET" else (body or {})
        sig = sign_url(self.account_id, data, ts, nonce)
        headers = {
            "CLIENT": CLIENT,
            "Signature": sig,
            "Content-Language": "zh",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; 26.5.2) "
                           "AppleWebKit/537.36 QingTui/71301 Chrome/132.0.6834.210 "
                           "Electron/34.5.8 Safari/537.36"),
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if method == "GET" and params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        elif body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, method=method,
            data=json.dumps(body).encode() if body else None,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8", "replace"))
            except Exception:
                return e.code, {"error": "http error"}
        except Exception as e:
            return -1, {"error": str(e)}

    # ---------- IM APIs ----------
    def account_info_self(self):
        return self._req("account/info/self")

    def chat_list(self):
        """会话列表 (最近活跃 ~100 个). 返回 {chatList, chatTopList}."""
        return self._req("msg/chat/list")

    def session_recent(self, session_obj, page_size=100, object_type=1):
        """某会话最近消息. object_type: 1=单聊 2=群聊."""
        return self._req("msg/session_recent", params={
            "pageSize": page_size, "objectType": object_type, "sessionObj": session_obj})

    def msg_sync(self, msg_id, direction=1, page_size=500):
        """翻历史消息. direction=1 往更早翻, direction=0 往更新翻."""
        return self._req("msg/sync", params={
            "msgId": msg_id, "direction": direction, "pageSize": page_size})

    def channel_info_list(self, channel_ids):
        """批量查群信息. 返回 {resultList:[{id,name,...}]}."""
        return self._req("channel/info/list", params={"channelIds": list(channel_ids)})

    def account_info_base(self, account_ids):
        """批量查人员信息. 返回 {accountInfos:[{accountId,userName,...}]}."""
        return self._req("account/other/info/base", params={"accountIds": list(account_ids)})

    # ---------- 拉取历史消息 (翻页到指定时间窗) ----------
    def pull_session_history(self, session_obj, object_type, start_ms, end_ms, max_pages=120):
        """拉某会话在 [start_ms, end_ms) 内的消息.

        先用 session_recent 拿最近消息作为起点, 再用 msg_sync direction=1 往前翻,
        直到消息时间早于 start_ms 或翻完.

        注意: session_recent 的 objectType 实测对单聊/群聊都用 1 才返回数据,
        传入的 object_type 仅用于记录, 不影响拉取.
        """
        st, r = self.session_recent(session_obj, page_size=100, object_type=1)
        data = r.get("data") if isinstance(r.get("data"), list) else []
        collected = {m["id"]: m for m in data if isinstance(m, dict) and "id" in m}
        if not collected:
            return []
        cursor = min(collected.keys())
        for _ in range(max_pages):
            st, r = self.msg_sync(cursor, direction=1, page_size=500)
            page = r.get("data") if isinstance(r.get("data"), list) else []
            if not page:
                break
            new = 0
            oldest_t = None
            for m in page:
                if not isinstance(m, dict) or "id" not in m:
                    continue
                if m["id"] not in collected:
                    collected[m["id"]] = m
                    new += 1
                mt = m.get("msgTime", 0)
                if oldest_t is None or mt < oldest_t:
                    oldest_t = mt
            if new == 0:
                break
            cursor = min(m["id"] for m in page if "id" in m)
            if oldest_t and oldest_t < start_ms - 7 * 86400000:
                break
            time.sleep(0.12)
        out = []
        for m in collected.values():
            mt = m.get("msgTime", 0)
            if start_ms <= mt < end_ms:
                out.append(m)
        out.sort(key=lambda x: x.get("msgTime", 0))
        return out

    def pull_context_around(self, session_obj, msg_id, before=15, after=15):
        """拉某条消息前后的上下文. 用 msg/sync 两个方向各翻一页.

        返回排序后的消息列表 (含图片/链接/引用等完整 content).
        """
        collected = {}
        # 往前 (direction=1, 更早)
        st, r = self.msg_sync(msg_id, direction=1, page_size=before)
        page = r.get("data") if isinstance(r.get("data"), list) else []
        for m in page:
            if isinstance(m, dict) and "id" in m:
                collected[m["id"]] = m
        # 往后 (direction=0, 更新)
        st, r = self.msg_sync(msg_id, direction=0, page_size=after)
        page = r.get("data") if isinstance(r.get("data"), list) else []
        for m in page:
            if isinstance(m, dict) and "id" in m:
                collected[m["id"]] = m
        out = list(collected.values())
        out.sort(key=lambda x: x.get("msgTime", 0))
        return out


def get_token():
    """从运行中的轻推 (CDP 9222) 获取当前 Bearer JWT. 失败返回 None."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3) as r:
            targets = json.loads(r.read())
    except Exception:
        return None
    # 优先用聊天页 target
    tgt = next((t for t in targets if "/chat/" in t.get("url", "")), None)
    if not tgt:
        tgt = next((t for t in targets if t.get("type") == "page"), None)
    if not tgt or not tgt.get("webSocketDebuggerUrl"):
        return None
    try:
        import websocket  # websocket-client
        ws = websocket.create_connection(tgt["webSocketDebuggerUrl"], timeout=8)
    except Exception:
        return None
    # localStorage 里可能有 token; 否则触发一次轻推请求从 hook 捕获
    js = r"""
    (()=>{
      const keys=Object.keys(localStorage);
      const hit={};
      for(const k of keys){const v=localStorage.getItem(k)||""; if(v.includes('eyJhbGci')) hit[k]=v;}
      return JSON.stringify(hit);
    })()
    """
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True, "timeout": 8000}}))
    end = time.time() + 10
    token = None
    while time.time() < end:
        try:
            m = json.loads(ws.recv())
        except Exception:
            break
        if m.get("id") == 1:
            v = m.get("result", {}).get("result", {}).get("value", "{}")
            d = json.loads(v) if v else {}
            for val in d.values():
                m2 = re.search(r"eyJhbGci[A-Za-z0-9_\.\-]+", val)
                if m2:
                    token = m2.group(0)
                    break
            break
    try:
        ws.close()
    except Exception:
        pass
    return token


def make_client():
    """便捷构造: 自动取 token. 失败返回 None."""
    tok = get_token()
    if not tok:
        return None
    return QtClient(token=tok)
