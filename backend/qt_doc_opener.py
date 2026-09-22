#!/usr/bin/env python3
"""从轻推 app 的 localStorage LevelDB 中提取缓存的 webofficeUrl。

轻推 app (Electron) 打开文档时，会在 localStorage 中缓存:
  {fileId}-webofficeUrl = base64(完整WPS在线编辑器URL)
  {fileId}-wbo_accessToken = WPS JWT
  {fileId}-wbo_refreshToken = WPS refreshToken

解码 webofficeUrl 后得到的 URL 包含所有认证参数，
直接用 Chrome 打开即可访问，无需扫码。

读取方式: 调用 Node.js classic-level (全量迭代，95 个文档)
替代旧的 Python 二进制搜索 (只找到 13 个，漏率 86%)。
"""

import json
import os
import subprocess
from urllib.parse import unquote

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


def list_cached_docs() -> dict:
    """列出所有缓存的文档 URL (通过 Node.js classic-level 全量读取)。"""
    result = _run_node_reader()
    if not result.get("ok"):
        return result

    docs = result.get("docs", [])
    sorted_docs = sorted(docs, key=lambda x: x.get("name") or x["file_id"])
    return {"ok": True, "count": len(sorted_docs), "docs": sorted_docs}


def get_doc_url(file_id: str) -> dict:
    """获取指定文档的 webofficeUrl。"""
    result = _run_node_reader(file_id)
    if not result.get("ok"):
        return result
    return result


def open_doc_in_chrome(file_id: str) -> dict:
    """用 Chrome 打开指定文档。"""
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


def generate_doc_url(file_id: str, file_name: str = "", file_type: str = "") -> dict:
    """对没有缓存的文档，用 API 生成新的 webofficeUrl。

    链路: refreshToken → 新 accessToken → editUrl → webofficeUrl
    需要从任意已缓存文档借用 refreshToken。
    """
    import urllib.request
    import urllib.parse

    # 1. 获取任意已缓存文档的 refreshToken + accessToken
    all_result = _run_node_reader()
    if not all_result.get("ok"):
        return all_result

    docs = all_result.get("docs", [])
    if not docs:
        return {"ok": False, "error": "没有任何缓存文档可借用 refreshToken"}

    # 找同类型的缓存文档借用 token
    donor = None
    for d in docs:
        if d.get("refreshToken") and d.get("accessToken"):
            donor = d
            break
    if not donor:
        return {"ok": False, "error": "缓存文档中没有 refreshToken/accessToken"}

    old_access_token = donor["accessToken"]
    refresh_token = donor["refreshToken"]

    # 2. 刷新 token
    refresh_url = f"{WPS_BASE}/drive/token/refresh?refreshToken={refresh_token}"
    req = urllib.request.Request(refresh_url, headers={
        "Authorization": f"Bearer {old_access_token}",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_body = resp.read().decode("utf-8")
    except Exception as e:
        return {"ok": False, "error": f"刷新 token 失败: {e}"}

    import re
    m_at = re.search(r"<accessToken>([^<]+)</accessToken>", xml_body)
    m_rt = re.search(r"<refreshToken>([^<]+)</refreshToken>", xml_body)
    if not m_at:
        return {"ok": False, "error": f"刷新 token 响应无 accessToken: {xml_body[:200]}"}

    new_access_token = m_at.group(1)

    # 3. 获取 editUrl
    if not file_name:
        file_name = file_id
    if not file_type:
        file_type = "xlsx"

    edit_params = urllib.parse.urlencode({
        "fileId": file_id,
        "fileName": file_name,
        "fileType": file_type,
        "businessCode": "weboffice.drive",
        "requestPermission": "write",
    })
    edit_url = f"{WPS_BASE}/drive/document/url/edit?{edit_params}"
    req2 = urllib.request.Request(edit_url, headers={
        "Authorization": f"Bearer {new_access_token}",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req2, timeout=10) as resp:
            xml2 = resp.read().decode("utf-8")
    except Exception as e:
        return {"ok": False, "error": f"获取 editUrl 失败: {e}"}

    m_eu = re.search(r"<editUrl>([^<]+)</editUrl>", xml2)
    if not m_eu:
        return {"ok": False, "error": f"editUrl 响应无 editUrl: {xml2[:200]}"}

    edit_url_b64 = m_eu.group(1)
    try:
        import base64
        weboffice_url = base64.b64decode(edit_url_b64).decode("utf-8")
    except Exception:
        weboffice_url = edit_url_b64  # 可能不是 base64

    return {
        "ok": True,
        "file_id": file_id,
        "name": file_name,
        "type": file_type,
        "url": weboffice_url,
        "generated": True,
        "msg": f"API 生成新 URL (可能报 24002)",
    }


def open_or_generate(file_id: str, file_name: str = "", file_type: str = "") -> dict:
    """优先用缓存 URL 直开，无缓存则用 API 生成。"""
    # 先查缓存
    result = _run_node_reader(file_id)
    if result.get("ok") and result.get("url"):
        return open_doc_in_chrome(file_id)

    # 无缓存，尝试 API 生成
    gen = generate_doc_url(file_id, file_name, file_type)
    if not gen.get("ok"):
        return gen

    url = gen["url"]
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "Google Chrome" to open location "{url}"'],
            timeout=10,
            capture_output=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"打开 Chrome 失败: {e}"}

    return {"ok": True, "msg": f"已用 API 生成并在 Chrome 中打开: {file_name or file_id}", **gen}


if __name__ == "__main__":
    result = list_cached_docs()
    if not result.get("ok"):
        print(f"错误: {result.get('error')}")
    else:
        print(f"找到 {result['count']} 个缓存文档:")
        for doc in result["docs"]:
            print(f"  {doc['file_id']} | {doc.get('type',''):6s} | {doc.get('permission',''):5s} | {doc.get('name','')}")
