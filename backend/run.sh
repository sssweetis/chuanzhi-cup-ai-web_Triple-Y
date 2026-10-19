#!/usr/bin/env bash
# 启动后端服务（macOS / Linux / Git Bash）—— 自动优先使用本目录的 .venv
set -e
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a; . ./.env; set +a   # 让 PORT 等变量在 shell 内生效（代码内也会自己读 .env）
fi

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

PORT="${PORT:-8000}"
echo "启动通知抽取服务：0.0.0.0:${PORT}  （Ctrl+C 停止）"
echo "自检地址：http://127.0.0.1:${PORT}/health"
exec "$PY" -m uvicorn main:app --reload --host 0.0.0.0 --port "${PORT}"