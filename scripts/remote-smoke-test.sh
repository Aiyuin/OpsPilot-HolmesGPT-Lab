#!/usr/bin/env bash
set -euo pipefail

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"

ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 \
  "${user}@${server}" '
  set -e
  cd /opt/opspilot-holmes
  api_key=$(sed -n "s/^HOLMES_API_KEY=//p" .env)
  curl --connect-timeout 3 --max-time 15 -fsS http://127.0.0.1:5050/readyz
  printf "\n"
  curl --connect-timeout 5 --max-time 180 -fsS -X POST http://127.0.0.1:5050/api/chat \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${api_key}" \
    --data-binary "{\"ask\":\"Reply exactly: HOLMES_BAILIAN_OK\",\"stream\":false}" \
    | jq "{analysis, usage: .metadata.usage, max_output_tokens: .metadata.max_output_tokens}"
  printf "\n"
'
