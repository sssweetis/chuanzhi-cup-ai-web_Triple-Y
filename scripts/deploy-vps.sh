#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "未安装 Docker。Ubuntu/Debian 请先安装 Docker Engine 和 Compose 插件。"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "未安装 Docker Compose 插件。"
  exit 1
fi

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "已生成 backend/.env。请先填写 LLM_ENABLE_MOCK / LLM_API_KEY / LLM_BASE_URL / LLM_MODEL，然后重新运行本脚本。"
  exit 2
fi

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
echo "等待健康检查..."
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/health >/tmp/tripley-health.json; then
    cat /tmp/tripley-health.json
    echo
    echo "部署完成。公网访问：http://<服务器公网IP>/"
    exit 0
  fi
  sleep 3
done

echo "健康检查未通过，请执行：docker compose -f docker-compose.prod.yml logs --tail=200"
exit 1