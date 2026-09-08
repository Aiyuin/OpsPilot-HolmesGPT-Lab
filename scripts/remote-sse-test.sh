#!/usr/bin/env bash
set -euo pipefail

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"

ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 \
  "${user}@${server}" '
  set -e
  cd /opt/opspilot-holmes
  api_key=$(sed -n "s/^HOLMES_API_KEY=//p" .env)
  response_file=$(mktemp)
  trap '\''rm -f "${response_file}"'\'' EXIT
  curl --connect-timeout 5 --max-time 180 -fsS -N \
    -X POST http://127.0.0.1:5050/api/chat \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${api_key}" \
    --data-binary "{\"ask\":\"Reply exactly: HOLMES_SSE_OK\",\"stream\":true}" \
    > "${response_file}"
  grep -q "HOLMES_SSE_OK" "${response_file}"
  echo "SSE stream passed: HOLMES_SSE_OK"
  echo "Received event types:"
  grep "^event:" "${response_file}" | sort -u
'
