#!/usr/bin/env bash
set -euo pipefail

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"

if [[ "${1:-}" == "--env-file" ]]; then
  env_file="${2:-deployment/.env}"
  if [[ ! -f "${env_file}" ]]; then
    echo "找不到密钥文件：${env_file}" >&2
    exit 1
  fi
  bailian_key=$(sed -n 's/^DASHSCOPE_API_KEY=//p' "${env_file}" | tail -n 1)
elif [[ $# -eq 0 ]]; then
  read -r -s -p "请输入阿里百炼 DASHSCOPE_API_KEY（不会回显）: " bailian_key
  printf '\n'
else
  echo "用法：$0 [--env-file [文件路径]]" >&2
  exit 1
fi

if [[ -z "${bailian_key}" || "${bailian_key}" == "replace-me" ]]; then
  echo "API Key 不能为空或占位值" >&2
  exit 1
fi

if [[ ! "${bailian_key}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "API Key 格式不合法" >&2
  exit 1
fi

printf '%s\n' "${bailian_key}" | \
  ssh "${user}@${server}" /opt/opspilot-holmes/set-bailian-key.sh

unset bailian_key
echo "密钥已更新，HolmesGPT 容器已重新创建。"
