#!/usr/bin/env bash
# 交互式配置后端环境变量（macOS / Linux / Git Bash）
# 用法：bash configure_env.sh
set -e
cd "$(dirname "$0")"

ENV_FILE=".env"
touch "$ENV_FILE"

get_cur() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- ; }
set_kv() {
  local k="$1" v="$2"
  if grep -qE "^$k=" "$ENV_FILE"; then
    tmp=$(mktemp); awk -v k="$k" -v v="$v" 'BEGIN{FS=OFS="="} $1==k{$2=v; print; next} {print}' "$ENV_FILE" > "$tmp"; mv "$tmp" "$ENV_FILE"
  else
    echo "$k=$v" >> "$ENV_FILE"
  fi
}

echo "===== 通知抽取服务 · 环境变量配置（直接回车 = 保持当前值）====="

read -r -s -p "LLM_API_KEY（当前 $(get_cur LLM_API_KEY | cut -c1-6)…，留空走 Mock）: " KEY; echo
[ -n "$KEY" ] && set_kv LLM_API_KEY "$KEY"

read -r -p "LLM_BASE_URL（当前 $(get_cur LLM_BASE_URL)）: " URL
[ -n "$URL" ] && set_kv LLM_BASE_URL "$URL"

read -r -p "LLM_MODEL（当前 $(get_cur LLM_MODEL)）: " MODEL
[ -n "$MODEL" ] && set_kv LLM_MODEL "$MODEL"

read -r -p "PORT（当前 $(get_cur PORT | sed 's/^$//')$(get_cur PORT | grep -q . || echo 8000)）: " P
[ -n "$P" ] && set_kv PORT "$P"

if [ -n "$(get_cur LLM_API_KEY)" ]; then
  set_kv LLM_ENABLE_MOCK 0
  MODE="real（真实大模型）"
else
  set_kv LLM_ENABLE_MOCK 1
  MODE="mock（返回虚构数据，用于联调）"
fi

echo ""
echo "已写入：$(pwd)/.env   运行模式 = $MODE"
echo "下一步：bash run.sh  →  bash -c 'python test_llm.py'  →  访问 /health 确认 mode"