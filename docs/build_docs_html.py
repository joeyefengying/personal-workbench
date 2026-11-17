#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把《统建项目-新人指南》的 Markdown 打包成一个自包含 HTML 文档站。

用法: python build_docs_html.py
产物: docs/统建项目-新人指南/index.html（单文件，含侧边导航 / 表格样式 / Mermaid 渲染 / 打印样式）
"""
import html
import json
import os
import re
import time

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "统建项目-新人指南")
DOCS = [
    ("README.md", "总览与阅读路径", "导航"),
    ("01-平台全景与建设范围.md", "01 平台全景与建设范围", "认知"),
    ("02-应用架构与系统清单.md", "02 应用架构与系统清单", "认知"),
    ("03-业务数据流与系统定位.md", "03 业务数据流与系统定位", "业务"),
    ("04-人员与组织分工.md", "04 人员与组织分工", "组织"),
    ("05-配置与实施注意事项.md", "05 配置与实施注意事项", "实施"),
    ("06-设计理念与池化模型.md", "06 设计理念与池化模型", "设计"),
    ("07-常见问题与踩坑.md", "07 常见问题与踩坑", "实践"),
    ("08-财务名词表.md", "08 财务名词表", "速查"),
    ("09-新人30天上手路径.md", "09 新人 30 天上手路径", "成长"),
    ("10-前端接入与工程规范.md", "10 前端接入与工程规范", "开发"),
    ("11-实施配置作战手册.md", "11 实施配置作战手册", "实施"),
    ("12-资金计划与预算控制.md", "12 资金计划与预算控制", "实施"),
    ("13-单据链路与业务规则.md", "13 单据链路与业务规则", "业务"),
    ("14-接口清单与集成.md", "14 接口清单与集成", "集成"),
    ("15-数据模型与报表取数.md", "15 数据模型与报表取数", "开发"),
    ("16-线下索取清单.md", "16 线下索取清单", "协作"),
]


LINK_MAP = {}
TERMS = {}      # 术语 -> 一句话解释（取自 08 名词表）
TERMS_USED = set()
GLOSSARY_SRC = "08-财务名词表.md"


def load_terms():
    """从 08-财务名词表.md 的表格里抽「名词 -> 解释」。"""
    path = os.path.join(BASE, GLOSSARY_SRC)
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\|\s*\*\*([^*|]{2,20})\*\*\s*\|\s*(.+?)\s*\|\s*$", line.strip())
        if not m:
            continue
        term, desc = m.group(1).strip(), m.group(2).strip()
        desc = re.sub(r"\s+", " ", desc).replace("**", "").replace("`", "")
        if len(desc) > 110:
            desc = desc[:110] + "…"
        TERMS.setdefault(term, desc)


def inline(text):
    """行内标记：先抽出行内代码，再处理转义/粗体/链接/图片。"""
    stash = []

    def keep(fragment):
        stash.append(fragment)
        return "\x00%d\x00" % (len(stash) - 1)

    text = re.sub(r"`([^`]+)`", lambda m: keep("<code>%s</code>" % html.escape(m.group(1))), text)

    # 允许 markdown 里少量原生 HTML：<br> 与 <small>…</small>
    text = text.replace("<small>", keep('<small class="note">')).replace("</small>", keep("</small>"))
    text = re.sub(r"<br\s*/?>", lambda m: keep("<br>"), text)

    # 术语悬停释义：每个术语在每篇里只标注首次出现
    for term in sorted(TERMS, key=len, reverse=True):
        if term in TERMS_USED or len(term) < 2:
            continue
        idx = text.find(term)
        if idx < 0:
            continue
        TERMS_USED.add(term)
        text = (text[:idx]
                + keep('<abbr class="term" title="%s">%s</abbr>' % (html.escape(TERMS[term]), html.escape(term)))
                + text[idx + len(term):])

    def img(m):
        alt, src = m.group(1), m.group(2)
        return "\x00IMG:%s|%s\x00" % (src, alt)

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", img, text)
    def link(m):
        label, href = m.group(1), m.group(2)
        base = href.lstrip("./").split("#")[0]
        if base in LINK_MAP:
            href = "#" + LINK_MAP[base]
        return keep('<a href="%s">%s</a>' % (href, label))

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)

    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # 任务清单：[ ] / [x] → 方框
    text = re.sub(r"^\[\s\]\s*", '<span class="cb">&#9744;</span> ', text)
    text = re.sub(r"^\[[xX]\]\s*", '<span class="cb">&#9745;</span> ', text)

    def restore(m):
        token = stash[int(m.group(1))]
        return token

    text = re.sub(r"\x00(\d+)\x00", restore, text)
    imgs = []

    def unpack_img(m):
        src, alt = m.group(1).split("|", 1)
        imgs.append('<figure><a href="%s" target="_blank" rel="noopener" title="查看原图">'
                    '<img src="%s" alt="%s" loading="lazy"></a><figcaption>%s</figcaption></figure>'
                    % (src, src, html.escape(alt), html.escape(alt)))
        return "\x00I%d\x00" % (len(imgs) - 1)

    text = re.sub(r"\x00IMG:([^\x00]+)\x00", unpack_img, text)
    text = re.sub(r"\x00I(\d+)\x00", lambda m: imgs[int(m.group(1))], text)
    return text


def convert(md):
    TERMS_USED.clear()
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)

    def flush_paragraph(buf):
        if buf:
            out.append("<p>%s</p>" % inline(" ".join(buf).strip()))
            buf.clear()

    para = []
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(para)
            lang = stripped[3:].strip()
            i += 1
            body = []
            while i < n and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(body)
            if lang == "mermaid":
                out.append('<div class="mermaid-note">流程图（Mermaid）：联网时自动渲染图形，否则显示源码</div>'
                           '<div class="mermaid">%s</div>' % html.escape(code))
            else:
                out.append('<pre class="code"><code>%s</code></pre>' % html.escape(code))
            continue

        if not stripped:
            flush_paragraph(para)
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_paragraph(para)
            level = len(m.group(1))
            text = inline(m.group(2))
            out.append("<h%d>%s</h%d>" % (level, text, level))
            i += 1
            continue

        if re.match(r"^(\*\s*\*\s*\*|-\s*-\s*-|_\s*_\s*_)$", stripped):
            flush_paragraph(para)
            out.append("<hr>")
            i += 1
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            flush_paragraph(para)
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join("<th>%s</th>" % inline(c) for c in header)
            tbody = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows)
            out.append('<div class="table-wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                       % (thead, tbody))
            continue

        # 引用
        if stripped.startswith(">"):
            flush_paragraph(para)
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append('<blockquote>%s</blockquote>' % inline(" ".join(buf)))
            continue

        # 列表
        if re.match(r"^([-*]|\d+\.)\s+", stripped):
            flush_paragraph(para)
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            items, depth_stack = [], [0]

            def new_item(text, depth):
                cls = ' class="sub"' if depth else ""
                return '<li%s>%s</li>' % (cls, inline(text))

            while i < n:
                raw = lines[i]
                s = raw.strip()
                mm = re.match(r"^([-*]|\d+\.)\s+(.*)$", s)
                if not mm:
                    if s and items and not s.startswith("|"):
                        items[-1] = items[-1][:-5] + " " + inline(s) + "</li>"  # 续行并入上一条
                        i += 1
                        continue
                    break
                indent = len(raw) - len(raw.lstrip())
                depth = 1 if indent >= 2 else 0
                items.append(new_item(mm.group(2), depth))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join(items), tag))
            continue

        para.append(stripped)
        i += 1

    flush_paragraph(para)
    return "\n".join(out)


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>统建项目（财务管控）新人上岗手册</title>
<style>
:root{
  --bg:#f6f7f9; --panel:#fff; --text:#1c2430; --muted:#5b6675; --line:#e3e7ee;
  --brand:#b91c1c; --brand-soft:#fdf2f2; --code-bg:#f3f4f6; --th:#f8fafc;
  --nav-bg:#fff; --shadow:0 1px 3px rgba(16,24,40,.06),0 8px 24px rgba(16,24,40,.04);
}
[data-theme="dark"]{
  --bg:#0b1220; --panel:#111a2b; --text:#e6edf6; --muted:#98a4b6; --line:#1f2c42;
  --brand:#f87171; --brand-soft:#2a1215; --code-bg:#0f1826; --th:#16233a;
  --nav-bg:#0e1727; --shadow:0 1px 2px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:15px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}
a{color:#1d4ed8;text-decoration:none}
[data-theme="dark"] a{color:#7dd3fc}
a:hover{text-decoration:underline}
.layout{display:flex;min-height:100vh}
aside{width:272px;flex:0 0 272px;background:var(--nav-bg);border-right:1px solid var(--line);
  position:sticky;top:0;height:100vh;overflow:auto;padding:16px 12px 24px}
aside .brand{display:flex;align-items:center;gap:10px;margin:0 0 6px;font-weight:700;font-size:16px}
aside .brand .dot{width:10px;height:10px;border-radius:50%;background:var(--brand)}
aside .sub{color:var(--muted);font-size:11.5px;margin:0 0 10px;line-height:1.5}
.nav-group{margin:9px 0 3px;padding-left:10px;color:var(--muted);font-size:10.5px;letter-spacing:.08em}
.nav a{display:block;padding:4px 10px;border-radius:7px;font-size:12.8px;color:var(--text);line-height:1.3}
.nav a:hover{background:var(--brand-soft);text-decoration:none}
.nav a.active{background:var(--brand);color:#fff}
main{flex:1;min-width:0;padding:28px 40px 80px;max-width:1080px;margin:0 auto}
.doc{display:none;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:30px 38px;box-shadow:var(--shadow)}
.doc.active{display:block}
h1{font-size:27px;margin:0 0 18px;padding-bottom:12px;border-bottom:2px solid var(--brand-soft)}
h2{font-size:20px;margin:34px 0 12px;padding-left:10px;border-left:4px solid var(--brand)}
h3{font-size:16.5px;margin:24px 0 8px;color:var(--text)}
h4{font-size:15px;margin:18px 0 6px;color:var(--muted)}
p{margin:10px 0}
ul,ol{margin:10px 0;padding-left:24px}
li{margin:5px 0}
li.sub{margin-left:18px;list-style:circle}
blockquote{margin:14px 0;padding:10px 16px;border-left:4px solid var(--brand);
  background:var(--brand-soft);border-radius:0 8px 8px 0;color:var(--text)}
blockquote p{margin:4px 0}
code{background:var(--code-bg);padding:1.5px 5px;border-radius:5px;font-size:13px;
  font-family:"JetBrains Mono",Consolas,Monaco,monospace}
pre.code{background:var(--code-bg);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow:auto}
pre.code code{background:none;padding:0;font-size:12.5px;line-height:1.6}
hr{border:none;border-top:1px dashed var(--line);margin:26px 0}
.table-wrap{overflow:auto;margin:16px 0;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:680px;font-size:13.5px}
th,td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top;word-break:break-word;overflow-wrap:anywhere}
th:last-child,td:last-child{border-right:none}
thead th{background:var(--th);font-weight:600;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:var(--brand-soft)}
figure{margin:18px 0;text-align:center}
figure img{max-width:100%;border:1px solid var(--line);border-radius:10px;background:#fff}
figcaption{color:var(--muted);font-size:12.5px;margin-top:8px}
abbr.term{border-bottom:1px dotted var(--brand);text-decoration:none;cursor:help}
.note{display:block;margin:-4px 0 18px;color:var(--muted);font-size:12.3px;line-height:1.6}
.mermaid{background:var(--code-bg);border:1px solid var(--line);border-radius:10px;padding:16px;
  margin:16px 0;font:12.5px/1.6 Consolas,monospace;white-space:pre;overflow:auto;color:var(--muted)}
.mermaid.rendered{background:transparent;border:none;color:var(--text);white-space:normal;text-align:center}
.mermaid-note{color:var(--muted);font-size:11.5px;margin:14px 0 -8px}
.cb{color:var(--brand);font-size:15px}
.toolbar{display:flex;gap:10px;align-items:center;justify-content:flex-end;margin-bottom:14px}
.btn{cursor:pointer;border:1px solid var(--line);background:var(--panel);color:var(--text);
  border-radius:8px;padding:6px 12px;font-size:12.5px}
.btn:hover{border-color:var(--brand);color:var(--brand)}
.meta{color:var(--muted);font-size:12px;margin-right:auto}
@media print{
  aside,.toolbar{display:none}
  main{max-width:none;padding:0}
  .doc{display:block!important;border:none;box-shadow:none;padding:0;page-break-after:always}
}
@media (max-width:960px){
  .layout{flex-direction:column}
  aside{position:relative;width:100%;height:auto;flex:none;border-right:none;border-bottom:1px solid var(--line)}
  main{padding:16px}
  .doc{padding:20px}
}
</style>
</head>
<body>
<div class="layout">
  <aside>
    <div class="brand"><span class="dot"></span>统建项目新人手册</div>
    <p class="sub">财务管控平台 · 新人上岗必读<br>内容源自五矿统建知识库（知微）问答</p>
    <div class="nav" id="nav">__NAV__</div>
  </aside>
  <main>
    <div class="toolbar">
      <span class="meta">生成时间 __DATE__ · 共 __COUNT__ 篇</span>
      <button class="btn" id="themeBtn">切换主题</button>
      <button class="btn" onclick="window.print()">打印 / 存 PDF</button>
    </div>
    __BODY__
  </main>
</div>
<script type="module">
  const navLinks = [...document.querySelectorAll('#nav a')];
  const docs = [...document.querySelectorAll('.doc')];
  function show(slug, push){
    docs.forEach(d => d.classList.toggle('active', d.dataset.slug === slug));
    navLinks.forEach(a => a.classList.toggle('active', a.dataset.slug === slug));
    if (push) history.replaceState(null, '', '#' + slug);
    window.scrollTo({top:0, behavior:'instant'});
    document.querySelector('main').scrollIntoView({block:'start'});
  }
  navLinks.forEach(a => a.addEventListener('click', e => { e.preventDefault(); show(a.dataset.slug, true); }));
  const initial = location.hash.slice(1);
  show(docs.some(d => d.dataset.slug === initial) ? initial : docs[0].dataset.slug, false);
  // 主题
  const tBtn = document.getElementById('themeBtn');
  const saved = localStorage.getItem('tz-theme');
  if (saved) document.documentElement.dataset.theme = saved;
  tBtn.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('tz-theme', next);
  });
  // Mermaid 尽量渲染，失败则保留源码
  try{
    const { default: mermaid } = await import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs');
    mermaid.initialize({ startOnLoad:false, theme: document.documentElement.dataset.theme === 'dark' ? 'dark':'default',
      securityLevel:'loose', flowchart:{htmlLabels:true, curve:'basis'} });
    const nodes = [...document.querySelectorAll('.mermaid')];
    for (const [i, el] of nodes.entries()){
      const src = el.textContent;
      try{
        const { svg } = await mermaid.render('mmd-' + i, src);
        el.innerHTML = svg; el.classList.add('rendered');
        const nt = el.previousElementSibling;
        if (nt && nt.classList.contains('mermaid-note')) nt.remove();
      }catch(err){ /* 保留源码展示 */ }
    }
  }catch(err){ console.warn('mermaid 未加载，保留源码视图', err); }
</script>
</body>
</html>
"""


def main():
    load_terms()
    for idx, (fname, _t, _g) in enumerate(DOCS):
        LINK_MAP[fname] = "doc-%d" % idx
    sections, nav_items, last_group = [], [], None
    for idx, (fname, title, group) in enumerate(DOCS):
        path = os.path.join(BASE, fname)
        if not os.path.exists(path):
            print("skip missing", fname)
            continue
        md = open(path, encoding="utf-8").read()
        slug = "doc-%d" % idx
        html_body = convert(md)
        # 文档内 h1 已存在则不再重复标题块
        sections.append('<section class="doc" data-slug="%s">\n%s\n</section>' % (slug, html_body))
        nav_items.append('<a href="#%s" data-slug="%s">%s</a>' % (slug, slug, html.escape(title)))

    out = (TEMPLATE
           .replace("__NAV__", "\n".join(nav_items))
           .replace("__BODY__", "\n".join(sections))
           .replace("__DATE__", time.strftime("%Y-%m-%d %H:%M"))
           .replace("__COUNT__", str(len(sections))))
    target = os.path.join(BASE, "index.html")
    with open(target, "w", encoding="utf-8") as f:
        f.write(out)
    print("written", target, len(out), "bytes", "docs:", len(sections))


if __name__ == "__main__":
    main()
