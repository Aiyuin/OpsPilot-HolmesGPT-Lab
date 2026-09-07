#!/usr/bin/env bash
set -euo pipefail

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"

echo "HolmesGPT API 将映射到 http://127.0.0.1:5050"
echo "保持本终端运行；按 Ctrl-C 关闭隧道。"
exec ssh -N -L 5050:127.0.0.1:5050 "${user}@${server}"
