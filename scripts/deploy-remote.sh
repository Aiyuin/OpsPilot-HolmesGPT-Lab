#!/usr/bin/env bash
set -euo pipefail

# 不把 macOS 扩展属性写入发往 Linux 的源码归档。
export COPYFILE_DISABLE=1

server="${OPSPILOT_SERVER:?请先 export OPSPILOT_SERVER=<服务器IP>}"
user="${OPSPILOT_SSH_USER:-root}"
deployment_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../deployment" && pwd)
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../holmesgpt" && pwd)
stage_dir=$(mktemp -d)
trap 'rm -rf "${stage_dir}"' EXIT

mkdir -p "${stage_dir}/app"
cp "${deployment_dir}/docker-compose.yml" \
   "${deployment_dir}/Dockerfile" \
   "${deployment_dir}/.dockerignore" \
   "${deployment_dir}/config.yaml" \
   "${deployment_dir}/.env.example" \
   "${deployment_dir}/set-bailian-key.sh" \
   "${deployment_dir}/requirements-runtime.txt" \
   "${stage_dir}/"
cp -R "${source_dir}/holmes" "${stage_dir}/app/holmes"
cp "${source_dir}/server.py" "${source_dir}/holmes_cli.py" "${stage_dir}/app/"

tar --no-xattrs -C "${stage_dir}" -czf - . | \
  ssh "${user}@${server}" '
    set -e
    install -d -m 700 /opt/opspilot-holmes
    tar -xzf - -C /opt/opspilot-holmes
    cd /opt/opspilot-holmes
    chmod 700 set-bailian-key.sh
    if [ ! -f .env ]; then
      api_key=$(openssl rand -hex 32)
      printf "%s\n" \
        "DASHSCOPE_API_KEY=replace-me" \
        "BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1" \
        "HOLMES_API_KEY=${api_key}" \
        "TZ=Asia/Shanghai" > .env
      chmod 600 .env
    fi
    docker compose build
    docker compose up -d --force-recreate
  '

echo "部署完成。运行 scripts/remote-status.sh 查看状态。"
