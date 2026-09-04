# 🛠 个人项目工作台 (Personal Workbench)

聚合浩哥在 Hermes 上自研的各个项目，卡片化展示 + 一键启动/停止 + Git 状态。
解决"散落各处、找目录麻烦"的问题。

## 入口

- **双击 `start.command`**（会启动后端并打开浏览器）
- Hermes 里说「打开个人工作台」由 skill 拉起

## 技术栈

- 前端：Vue3 + Vite + Ant Design Vue + Pinia + vue-router
- 后端：FastAPI (Python)，端口 `8899`，同时 serve 前端构建产物（单端口访问）

## 目录结构

```
personal-workbench/
├── backend/
│   ├── server.py     # FastAPI 后端: 项目清单 / git状态 / 一键启停
│   └── apps.json     # ⭐ 项目清单配置 (新增项目在此登记)
├── frontend/
│   └── src/          # Vue3 前端
├── start.command     # 一键启动脚本
└── README.md
```

## 新增 / 修改项目

编辑 `backend/apps.json`，字段说明：

```json
{
  "id": "唯一id",
  "name": "显示名",
  "path": "~/项目绝对路径",
  "desc": "一句话描述",
  "cmd": "{python} server.py",        // 启动命令(可选, 无则不显示启动按钮)
  "runDir": "~/运行目录",              // 在哪个目录执行命令
  "port": 8000,                        // 端口(用于活性检测 + 停止)
  "url": "http://127.0.0.1:8000",     // 打开页面的地址
  "type": "web | doc"                  // doc=只能打开目录, 不启服务
}
```

## 命令

```bash
# 后端
python3 backend/server.py            # 启动 (端口 8899)
# 前端 dev (热更新)
cd frontend && npm run dev           # http://127.0.0.1:8898
# 构建
cd frontend && npm run build         # 产物由后端 8899 提供
```

## 已登记项目

| 分类 | 项目 | 位置 | 启动 |
|------|------|------|------|
| 工作台/工具 | 低码工作台 | cisdigital/low-code | 8787 |
| 工作台/工具 | ONES 缺陷修复 | cisdigital/_ones-defect-wf | 8000 |
| 财务系统 | 财务前端 fs | cisdigital/fe-minmetals-fm-fis-fs | 5173 |
| 财务系统 | 财务架构图导航 | 笔记/…/00_架构图导航 | doc |
| 交易/AI | 交易策略 v2 | mine/trading-strategy-system | 8750 |
| 交易/AI | AI 副业情报 | mine/ai-side-hustle | doc |
| 交易/AI | AI 漫剧 | mine/ai-comic-drama | doc |
| 交易/AI | 五矿一企一屏 | mine/jw-deep-water | - |