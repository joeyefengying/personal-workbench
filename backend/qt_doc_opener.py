#!/usr/bin/env python3
"""从轻推 app 的 localStorage LevelDB 中提取缓存的 webofficeUrl。

轻推 app (Electron) 打开文档时，会在 localStorage 中缓存:
  {fileId}-webofficeUrl = base64(完整WPS在线编辑器URL)
  {fileId}-wbo_accessToken = WPS JWT
  {fileId}-wbo_refreshToken = WPS refreshToken

读取方式: 调用 Node.js classic-level (全量迭代，95 个文档)
"""

import base64
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
LDB_READER = os.path.join(BACKEND_DIR, "ldb_reader.js")

# WPS API
WPS_BASE = "https://wps.qingtui.com/wps/api"


def _run_node_reader(file_id: str = "") -> dict:
    """调用 Node.js ldb_reader.js 读取 LevelDB，返回 JSON 结果。"""
    if not os.path.isfile(LDB_READER):
        return {"ok": False, "error": "ldb_reader.js 不存在"}

    try:
        cmd = ["node", LDB_READER]
        if file_id:
            cmd.append(file_id)
        r = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
        if r.returncode != 0:
            return {"ok": False, "error": f"node 退出 {r.returncode}: {r.stderr[:200]}"}
        return json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "node 读取超时 (30s)"}
    except Exception as e:
        return {"ok": False, "error": f"node 执行失败: {e}"}


def _is_token_expired(access_token: str) -> bool:
    """检查 JWT accessToken 是否过期。"""
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return True
        # JWT payload base64 decode (需要 padding)
        payload_b64 = parts[1] + "=="
        payload = json.loads(base64.b64decode(payload_b64))
        return time.time() * 1000 > payload.get("expireTime", 0)
    except Exception:
        return True


def _find_valid_token_doc(docs: list) -> dict:
    """从缓存文档中找一个 accessToken 未过期的文档。"""
    for d in docs:
        at = d.get("accessToken", "")
        if at and not _is_token_expired(at):
            return d
    return None


def _refresh_token(access_token: str, refresh_token: str) -> dict:
    """用 refreshToken 刷新 accessToken。

    Returns: {"accessToken": ..., "refreshToken": ...} 或 {"error": ...}
    """
    refresh_url = f"{WPS_BASE}/drive/token/refresh?refreshToken={refresh_token}"
    req = urllib.request.Request(refresh_url, headers={
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://wps.qingtui.com",
        "Referer": "https://wps.qingtui.com/wps/",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_body = resp.read().decode("utf-8")
    except Exception as e:
        return {"error": f"刷新 token 失败: {e}"}

    m_at = re.search(r"<accessToken>([^<]+)</accessToken>", xml_body)
    m_rt = re.search(r"<refreshToken>([^<]+)</refreshToken>", xml_body)
    if not m_at:
        return {"error": f"刷新响应无 accessToken: {xml_body[:200]}"}

    return {"accessToken": m_at.group(1), "refreshToken": m_rt.group(1) if m_rt else refresh_token}


def _generate_edit_url(access_token: str, file_id: str, file_name: str = "", file_type: str = "") -> dict:
    """用 accessToken 调用 API 生成新的 webofficeUrl。

    Returns: {"webofficeUrl": ..., "pageUrl": ...} 或 {"error": ...}
    """
    if not file_name:
        file_name = file_id
    if not file_type:
        file_type = "xlsx"

    params = urllib.parse.urlencode({
        "fileId": file_id,
        "fileName": file_name,
        "fileType": file_type,
        "businessCode": "weboffice.drive",
        "requestPermission": "write",
    })
    edit_api = f"{WPS_BASE}/drive/document/url/edit?{params}"
    req = urllib.request.Request(edit_api, headers={
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://wps.qingtui.com",
        "Referer": "https://wps.qingtui.com/wps/",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_body = resp.read().decode("utf-8")
    except Exception as e:
        return {"error": f"获取 editUrl 失败: {e}"}

    m_eu = re.search(r"<editUrl>([^<]+)</editUrl>", xml_body)
    if not m_eu:
        return {"error": f"响应无 editUrl: {xml_body[:200]}"}

    edit_url_raw = m_eu.group(1).replace("&amp;", "&")

    # editUrl 已是完整的 WPS 页面 URL:
    # https://wps.qingtui.com/wps/?webofficeUrl=<base64>&requestPermission=write&...
    # 需要添加 webofficeAccessToken 和 webofficeRefreshToken 参数
    return {"editUrl": edit_url_raw}


def list_cached_docs() -> dict:
    """列出所有缓存的文档 URL (通过 Node.js classic-level 全量读取)。"""
    result = _run_node_reader()
    if not result.get("ok"):
        return result

    docs = result.get("docs", [])
    # 标注 token 是否过期
    for d in docs:
        d["token_expired"] = _is_token_expired(d.get("accessToken", ""))
    sorted_docs = sorted(docs, key=lambda x: x.get("name") or x["file_id"])
    return {"ok": True, "count": len(sorted_docs), "docs": sorted_docs}


def get_doc_url(file_id: str) -> dict:
    """获取指定文档的 webofficeUrl。"""
    result = _run_node_reader(file_id)
    if not result.get("ok"):
        return result
    return result


def open_doc_in_chrome(file_id: str) -> dict:
    """用 Chrome 打开指定文档 (缓存方案 - 需要 Tampermonkey 脚本)。"""
    result = _run_node_reader(file_id)
    if not result.get("ok"):
        return result

    url = result.get("url")
    if not url:
        return {"ok": False, "error": f"文档 {file_id} 没有 webofficeUrl"}

    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "Google Chrome" to open location "{url}"'],
            timeout=10,
            capture_output=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"打开 Chrome 失败: {e}"}

    return {"ok": True, "msg": f"已在 Chrome 中打开: {result.get('name', file_id)}", **result}


def open_doc_with_token(file_id: str) -> dict:
    """打开文档 (新方案): 刷新 token → 构造 WPS 页面 URL (含 token) → Chrome 打开。

    需要配合 Tampermonkey 脚本使用 (拦截 iframe XHR 注入 Authorization 头)。
    """
    # 1. 读取所有缓存文档
    all_result = _run_node_reader()
    if not all_result.get("ok"):
        return all_result

    docs = all_result.get("docs", [])

    # 2. 找目标文档
    target = None
    for d in docs:
        if d["file_id"] == file_id:
            target = d
            break
    if not target:
        return {"ok": False, "error": f"文档 {file_id} 未在缓存中找到"}

    # 3. 找一个有效 token (或刷新)
    valid_doc = _find_valid_token_doc(docs)
    if not valid_doc:
        # 所有 token 都过期了, 尝试用目标文档的 refreshToken 刷新
        valid_doc = target

    old_at = valid_doc.get("accessToken", "")
    old_rt = valid_doc.get("refreshToken", "")
    if not old_at or not old_rt:
        return {"ok": False, "error": "缓存中没有可用的 token"}

    # 4. 刷新 token
    refresh_result = _refresh_token(old_at, old_rt)
    if "error" in refresh_result:
        return {"ok": False, "error": refresh_result["error"]}

    new_at = refresh_result["accessToken"]
    new_rt = refresh_result["refreshToken"]

    # 5. 构造 WPS 页面 URL
    # 使用缓存的 webofficeUrl (base64 编码), 加上 token 参数
    cached_url = target.get("url", "")
    if not cached_url:
        # 没有缓存的 webofficeUrl, 用 API 生成
        gen = _generate_edit_url(new_at, file_id, target.get("name", ""), target.get("type", ""))
        if "error" in gen:
            return {"ok": False, "error": gen["error"]}
        # editUrl 已是完整页面 URL, 添加 token 参数
        page_url = gen["editUrl"]
        if "webofficeAccessToken=" not in page_url:
            sep = "&" if "?" in page_url else "?"
            page_url += f"{sep}webofficeAccessToken={new_at}&webofficeRefreshToken={new_rt}"
    else:
        # 用缓存的 webofficeUrl
        weboffice_url_b64 = base64.b64encode(cached_url.encode()).decode()
        ftype = target.get("type", "xlsx")
        page_url = (
            f"https://wps.qingtui.com/wps/?"
            f"webofficeUrl={urllib.parse.quote(weboffice_url_b64, safe='')}"
            f"&webofficeAccessToken={new_at}"
            f"&webofficeRefreshToken={new_rt}"
            f"&fileId={file_id}"
            f"&fileType={ftype}"
            f"&requestPermission=write"
            f"&businessCode=weboffice.drive"
        )

    # 6. 用 Chrome 打开
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "Google Chrome" to open location "{page_url}"'],
            timeout=10,
            capture_output=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"打开 Chrome 失败: {e}"}

    return {
        "ok": True,
        "msg": f"已在 Chrome 中打开: {target.get('name', file_id)}",
        "file_id": file_id,
        "name": target.get("name", ""),
        "page_url": page_url[:200] + "...",
    }


if __name__ == "__main__":
    result = list_cached_docs()
    if not result.get("ok"):
        print(f"错误: {result.get('error')}")
    else:
        print(f"找到 {result['count']} 个缓存文档:")
        for doc in result["docs"]:
            expired = "⚠️过期" if doc.get("token_expired") else "✓有效"
            print(f"  {doc['file_id']} | {doc.get('type',''):6s} | {expired} | {doc.get('name','')}")
