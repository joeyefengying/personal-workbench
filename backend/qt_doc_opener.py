#!/usr/bin/env python3
"""从轻推 app 的 localStorage LevelDB 中提取缓存的 webofficeUrl。

轻推 app (Electron) 打开文档时，会在 localStorage 中缓存:
  {fileId}-webofficeUrl = base64(完整WPS在线编辑器URL)
  {fileId}-wbo_accessToken = WPS JWT
  {fileId}-wbo_refreshToken = WPS refreshToken

解码 webofficeUrl 后得到的 URL 包含所有认证参数，
直接用 Chrome 打开即可访问，无需扫码。
"""

import base64
import os
import re
from urllib.parse import unquote

QT_LDB = os.path.expanduser(
    "~/Library/Application Support/Qingtui/Partitions/tab--undefined/Local Storage/leveldb/"
)

B64_PREFIX = b"aHR0cHM6"  # base64("https://")


def _extract_b64_urls(ldb_path: str) -> dict[str, dict]:
    """从 LevelDB 文件中提取 webofficeUrl，返回 {fileId: {url, name, type, permission}}."""
    results: dict[str, dict] = {}
    if not os.path.isdir(ldb_path):
        return results

    for fname in sorted(os.listdir(ldb_path)):
        if not (fname.endswith(".log") or fname.endswith(".ldb")):
            continue
        fpath = os.path.join(ldb_path, fname)
        try:
            with open(fpath, "rb") as f:
                data = f.read()
        except OSError:
            continue

        pos = 0
        while True:
            idx = data.find(B64_PREFIX, pos)
            if idx == -1:
                break

            # 向后扫描 base64 字符 (允许 \n\r 在中间)
            end = idx
            i = idx
            while i < len(data):
                c = data[i]
                if c in b"\n\r":
                    i += 1
                    continue
                if (65 <= c <= 90) or (97 <= c <= 122) or (48 <= c <= 57) or c in b"+/=":
                    end = i + 1
                    i += 1
                else:
                    break

            # 向前扫描
            start = idx
            i = idx - 1
            while i >= 0:
                c = data[i]
                if c in b"\n\r":
                    i -= 1
                    continue
                if (65 <= c <= 90) or (97 <= c <= 122) or (48 <= c <= 57) or c in b"+/=":
                    start = i
                    i -= 1
                else:
                    break

            b64_str = (
                data[start:end].replace(b"\n", b"").replace(b"\r", b"").decode("ascii", errors="ignore")
            )
            if len(b64_str) <= 50:
                pos = idx + 1
                continue

            try:
                decoded = base64.b64decode(b64_str).decode("utf-8", errors="ignore")
            except Exception:
                pos = idx + 1
                continue

            if "weboffice" not in decoded or "qingtui" not in decoded:
                pos = idx + 1
                continue

            m = re.search(r"fileId[=:](\d+)", decoded)
            if not m:
                pos = idx + 1
                continue

            file_id = m.group(1)
            if file_id in results:
                pos = idx + 1
                continue

            m_name = re.search(r"fileName=([^&]+)", decoded)
            m_type = re.search(r"fileType=([^&]+)", decoded)
            m_perm = re.search(r"requestPermission=([^&]+)", decoded)

            results[file_id] = {
                "file_id": file_id,
                "url": decoded,
                "name": unquote(m_name.group(1)) if m_name else "",
                "type": m_type.group(1) if m_type else "",
                "permission": m_perm.group(1) if m_perm else "",
            }
            pos = idx + 1

    return results


def list_cached_docs() -> dict:
    """列出所有缓存的文档 URL。"""
    docs = _extract_b64_urls(QT_LDB)
    # 按文件名排序
    sorted_docs = sorted(docs.values(), key=lambda x: x["name"] or x["file_id"])
    return {"ok": True, "count": len(sorted_docs), "docs": sorted_docs}


def get_doc_url(file_id: str) -> dict:
    """获取指定文档的 webofficeUrl。"""
    docs = _extract_b64_urls(QT_LDB)
    doc = docs.get(file_id)
    if not doc:
        return {"ok": False, "error": f"文档 {file_id} 未在轻推缓存中找到，请先在轻推 app 中打开一次"}
    return {"ok": True, **doc}


def open_doc_in_chrome(file_id: str) -> dict:
    """用 Chrome 打开指定文档。"""
    import subprocess

    docs = _extract_b64_urls(QT_LDB)
    doc = docs.get(file_id)
    if not doc:
        return {"ok": False, "error": f"文档 {file_id} 未在轻推缓存中找到"}

    url = doc["url"]
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "Google Chrome" to open location "{url}"'],
            timeout=10,
            capture_output=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"打开 Chrome 失败: {e}"}

    return {"ok": True, "msg": f"已在 Chrome 中打开: {doc['name']}", **doc}


if __name__ == "__main__":
    result = list_cached_docs()
    print(f"找到 {result['count']} 个缓存文档:")
    for doc in result["docs"]:
        print(f"  {doc['file_id']} | {doc['type']:6s} | {doc['permission']:5s} | {doc['name']}")
