# WPS WebOffice 前端源码（Source Map 提取）

## 来源

轻推 app 内嵌的 WPS 在线编辑器（`wps.qingtui.com/weboffice/office/s/<fileId>`）在构建时未移除 source map，
通过 `main.6d44a6dc.js.map` 可直接还原完整 TypeScript 源码。

- **提取时间**：2026-08-26
- **文件数**：705（62 个应用源码 + 642 个 node_modules + 1 个 webpack bootstrap）
- **大小**：3.1MB

## 目录结构

```
wps-weboffice-source/
├── App.tsx                          # 主入口 (React + HashRouter)
├── api/
│   ├── TokenApi.ts                  # Token API：刷新token / QR码URL / SMS登录
│   ├── fileApi.ts                   # 文件API：编辑权限 / 编辑URL
│   └── ShareApi.ts                  # 分享API：公开分享 / 下载签名
├── features/
│   ├── Home/index.tsx               # 📌 WPS编辑器主页面（核心）
│   ├── Home/open-jssdk-v0.0.3.es.js # 📌 WPS JSSDK v1.1.19
│   ├── Login/index.tsx              # 登录页（QR码 + 短信验证码）
│   ├── ClientVersion/               # 客户端版本检查（redux-saga）
│   └── Language/                    # 多语言切换
├── services/
│   ├── TokenService.ts              # Token 解析 / 验证 / 刷新逻辑
│   └── ScheduleService.ts           # 定时刷新 token（防过期）
├── utils/
│   ├── RequestUtil.ts               # HTTP 请求封装（基于 axios）
│   ├── SecurityUtil.ts              # MD5 / Base64 加解密
│   ├── UrlUtil.ts                   # URL 参数解析 / webofficeUrl 缓存
│   └── DateUtil.ts                  # 服务器时间校正
├── store/                           # Redux store 配置
├── exceptions/                      # 业务异常处理（ErrorCode / Handler）
├── transformers/                    # 数据转换
├── locales/                         # 中英文文案
└── node_modules/                    # 第三方库（react / axios / crypto-js 等）
```

## 关键发现

### 认证流程

1. 轻推 app 打开文档时，在 URL 中带 `accessToken` 参数
2. 前端调用 `api/drive/token/refresh` 用 `refreshToken` 换取新的 `accessToken`
3. `ScheduleService` 定时刷新 token 防止过期
4. WPS JSSDK 通过 `WebOfficeSDK.config()` 创建 iframe 加载实际编辑器
5. 父子页面通过 `postMessage` 通信

### API 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `api/drive/token/refresh` | GET | 刷新 accessToken |
| `api/drive/security/ack` | GET | 确认 refreshToken |
| `api/drive/file/teamwork/open` | POST | 打开团队文档 |
| `api/drive/share/open/file/detail` | GET | 获取分享文件详情 |
| `api/drive/file/edit/url` | GET | 获取编辑器 URL |

### 安全相关

- MD5 加密盐值：`7zs1JKiilF`
- Token 格式：JWT（payload 含 `accountId`）
- `webofficeUrl` 缓存在 localStorage：`{fileId}-webofficeUrl`

### 与 Chrome 直开的关系

工作台的「🔗 Chrome直开」功能就是利用 `webofficeUrl` 这个缓存：
1. 轻推 app 打开文档 → localStorage 缓存 `{fileId}-webofficeUrl`（含完整认证参数）
2. 我们从 LevelDB 读取这个 URL
3. 直接用 Chrome 打开 → 无需扫码

**限制**：文档必须先在轻推 app 中打开过一次；URL 签名约 2 小时过期。
