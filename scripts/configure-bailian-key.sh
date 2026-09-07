#!/usr/bin/env bash
set -euo pipefail

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"

read -r -s -p "请输入阿里百炼 DASHSCOPE_API_KEY（不会回显）: " bailian_key
printf '\n'

if [[ -z "${bailian_key}" ]]; then
  echo "API Key 不能为空" >&2
  exit 1
fi

printf '%s\n' "${bailian_key}" | \
  ssh "${user}@${server}" /opt/opspilot-holmes/set-bailian-key.sh

unset bailian_key
echo "密钥已更新，HolmesGPT 容器已重新创建。"
