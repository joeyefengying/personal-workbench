#!/bin/bash
# 个人项目工作台 - 一键启动 (可双击 .command 或终端运行)
# 启动后端(serve构建产物)并打开浏览器
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
PORT="${WB_PORT:-8899}"

# 若后端未运行, 启动它
if ! lsof -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "启动个人工作台后端 (端口 ${PORT})..."
  "$PYTHON" backend/server.py >/tmp/workbench.log 2>&1 &
  sleep 2
fi

# 确保前端已构建 (若没有则 rebuild)
if [ ! -d frontend/dist ]; then
  echo "首次运行: 构建前端..."
  (cd frontend && npm run build)
fi

echo "打开浏览器: http://127.0.0.1:${PORT}"
sleep 1
open "http://127.0.0.1:${PORT}"
echo ""
echo "✅ 个人项目工作台已启动"
echo "   - 打开 http://127.0.0.1:${PORT}"
echo "   - 日志: /tmp/workbench.log"