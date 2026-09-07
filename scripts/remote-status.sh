#!/usr/bin/env bash
set -euo pipefail

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"

ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 \
  "${user}@${server}" \
  'cd /opt/opspilot-holmes && docker compose ps && curl --connect-timeout 3 --max-time 10 -fsS http://127.0.0.1:5050/healthz && printf "\n" && docker stats --no-stream opspilot-holmes'
