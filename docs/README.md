# 文档索引

工作台里的文档都在这里。三种形态：**Markdown**（可 diff、可协作）、**单文件 HTML 文档站**（双击即看，无需构建）、**架构图 HTML**（archify 生成）。

| 文档 | 形态 | 说明 |
|---|---|---|
| [统建项目-新人指南/](./统建项目-新人指南/) | 文件夹（11 篇 Markdown） | 五矿统建项目（财务管控）新人上岗手册：平台全景、应用架构、数据流、人员分工、配置注意事项、设计理念、踩坑、名词表、30 天路径、前端接入 |
| [统建项目-新人指南/index.html](./统建项目-新人指南/index.html) | 单文件 HTML 文档站 | 上面 11 篇的打包版：左侧导航 + 表格样式 + Mermaid 渲染 + 深浅主题 + 打印/存 PDF。**新人直接打开这个** |
| [mission.md](./mission.md) | Markdown | 个人工作台的项目立意与里程碑 |
| [轻推监控系统-架构图.html](./轻推监控系统-架构图.html) | archify 架构图 | 轻推监控系统逆向与架构 |
| [轻推监控系统-启动流程.html](./轻推监控系统-启动流程.html) | archify 架构图 | 轻推监控系统启动流程 |

## 维护《统建项目-新人指南》

```bash
# 1. 知识库补问（答案落到 .ekko-tmp/kb/kb-answers/）
python3 .ekko-tmp/kb/kb_run.py a   # a=平台全景 b=组织人员 c=配置实施 d=设计理念 e=前端接入

# 2. 改完 Markdown 后重新打包 HTML
python3 docs/build_docs_html.py
```

新增一篇：在 `docs/build_docs_html.py` 的 `DOCS` 列表里加一行（文件名, 导航标题, 分组），再在 `统建项目-新人指南/README.md` 的目录表里补一行。