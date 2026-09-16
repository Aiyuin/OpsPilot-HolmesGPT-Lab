#!/usr/bin/env bash
set -euo pipefail

cluster_name="${OPSPILOT_KIND_CLUSTER:-opspilot-thesis}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop 未运行。请先启动并完成 macOS 管理员授权。" >&2
  exit 1
fi

if ! command -v kind >/dev/null 2>&1; then
  echo "未安装 kind；macOS 可运行：brew install kind" >&2
  exit 1
fi

if kind get clusters | grep -Fxq "${cluster_name}"; then
  echo "Kind 集群已存在：${cluster_name}"
else
  kind create cluster --name "${cluster_name}" --wait 120s
fi

kubectl config use-context "kind-${cluster_name}" >/dev/null
kubectl wait --for=condition=Ready nodes --all --timeout=120s
kubectl cluster-info
kubectl get nodes -o wide
