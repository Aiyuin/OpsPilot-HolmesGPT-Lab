#!/usr/bin/env bash
set -euo pipefail

umask 077
IFS= read -r new_key

if [[ ! "${new_key}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "API Key 格式不合法" >&2
  exit 1
fi

env_file=/opt/opspilot-holmes/.env
temp_file=$(mktemp)

awk -v key="${new_key}" '
  BEGIN { updated=0 }
  /^DASHSCOPE_API_KEY=/ { print "DASHSCOPE_API_KEY=" key; updated=1; next }
  { print }
  END { if (!updated) print "DASHSCOPE_API_KEY=" key }
' "${env_file}" > "${temp_file}"

install -m 600 "${temp_file}" "${env_file}"
rm -f "${temp_file}"
unset new_key

cd /opt/opspilot-holmes
docker compose up -d --force-recreate
