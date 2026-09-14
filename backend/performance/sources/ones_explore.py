#!/usr/bin/env python3
"""
ONES ("万") API 探索器 — 第一步
================================
目标: 连入 ONES, 拦截所有网络请求, 找到:
  1. 项目列表 (含名字叫"测试"的项目)
  2. 筛选(filters) tab 的 GraphQL 查询结构
  3. 可用的 GraphQL API endpoint

方法(与低码平台抓包一致):
  Playwright 连入 ONES → 拦截 request/response → 模拟点击
  → 截图 + 可访问性树找可点击元素 → 记录所有 /api/ 请求的 URL + body + response

认证:
  复用低码工作台的 .cookies/ones_cookies.json
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

LOWCODE_ROOT = Path("/Users/zhanghao/Downloads/project/cisdigital/low-code")
ONES_COOKIE_FILE = LOWCODE_ROOT / ".cookies" / "ones_cookies.json"
ONES_BASE = "http://10.13.253.17:30011"
OUT_DIR = Path(__file__).resolve().parent.parent / "ones_probe"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_ones_cookies():
    """加载 ONES cookies (Playwright 格式)"""
    data = json.loads(ONES_COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = []
    for c in data:
        cookies.append({
            "name": c.get("name"),
            "value": c.get("value"),
            "domain": c.get("domain", "10.13.253.17"),
            "path": c.get("path", "/"),
        })
    return cookies


def main():
    from playwright.sync_api import sync_playwright

    captured = []  # 记录所有 API 请求
    cookies = load_ones_cookies()

    with sync_playwright() as p:
        # 优先用系统 Chrome (避免 playwright install chromium)
        try:
            browser = p.chromium.launch(headless=True, channel="chrome")
        except Exception:
            browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale="zh-CN",
        )
        context.add_cookies(cookies)
        page = context.new_page()

        # 拦截所有请求和响应
        def on_request(req):
            if "/api/" in req.url or "graphql" in req.url.lower():
                info = {
                    "method": req.method,
                    "url": req.url,
                    "post_data": None,
                }
                try:
                    pd = req.post_data
                    if pd:
                        info["post_data"] = pd[:2000]
                except Exception:
                    pass
                captured.append(info)

        def on_response(resp):
            # 尝试记录 API 响应内容
            try:
                if "/api/" in resp.url or "graphql" in resp.url.lower():
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct:
                        body = resp.text()
                        # 找最后一个匹配的请求记录，附加响应
                        for c in reversed(captured):
                            if c["method"] and resp.url in c["url"]:
                                c["response"] = body[:3000]
                                break
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)

        # 1. 访问 ONES 首页
        print("== 访问 ONES 首页 ==")
        page.goto(f"{ONES_BASE}/project/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        # 检查是否被重定向到登录
        if "login" in page.url.lower() or "auth" in page.url.lower():
            print(f"❌ Cookie 已过期, 被重定向: {page.url}")
            browser.close()
            return

        print(f"✅ 已登录, 当前 URL: {page.url}")
        print(f"页面标题: {page.title()}")

        # 截图
        page.screenshot(path=str(OUT_DIR / "01_home.png"), full_page=False)
        print("📸 已截图 01_home.png")

        # 2. 输出可访问性树(找可点击元素)
        print("\n== 页面可访问性快照(前 200 行) ==")
        try:
            snapshot = page.accessibility.snapshot() if hasattr(page, 'accessibility') else None
        except Exception:
            snapshot = None

        # 用 JS 提取所有可点击元素文本
        clickable = page.evaluate("""
            () => {
                const els = document.querySelectorAll('a, button, [role="tab"], [role="button"], .tab, .nav-item, [class*="tab"], [class*="menu"]');
                const out = [];
                els.forEach((el, i) => {
                    const txt = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                    if (txt && txt.length < 60 && i < 300) {
                        out.push({tag: el.tagName, text: txt, href: el.href || '', cls: el.className || ''});
                    }
                });
                return out;
            }
        """)
        seen = set()
        for item in clickable:
            key = item["text"]
            if key and key not in seen:
                seen.add(key)
                print(f"  [{item['tag']}] {item['text'][:50]}  {item['href'][:60]}")

        # 3. 输出捕获到的 API 请求
        print(f"\n== 捕获到 {len(captured)} 个 API 请求 ==")
        api_urls = set()
        for c in captured:
            u = c["url"]
            # 提取路径部分
            path = urlparse(u).path
            if path not in api_urls:
                api_urls.add(path)
                print(f"  {c['method']} {path}")

        # 保存完整捕获数据
        out_file = OUT_DIR / "probe_result.json"
        out_file.write_text(json.dumps({
            "url": page.url,
            "title": page.title(),
            "captured": captured,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n💾 已保存: {out_file}")

        browser.close()


if __name__ == "__main__":
    main()
