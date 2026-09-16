#!/usr/bin/env bash
set -euo pipefail

lab_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
workspace_dir=$(cd "${lab_dir}/.." && pwd)
holmes_dir="${workspace_dir}/holmesgpt"
env_file="${OPSPILOT_ENV_FILE:-${lab_dir}/deployment/.env}"
scenario_filter="${1:-09_crashpod}"
iterations="${2:-1}"
run_label="${3:-pilot}"
phase="${4:-pilot}"

if [[ "${phase}" != "pilot" && "${phase}" != "formal" ]]; then
  echo "phase 必须是 pilot 或 formal" >&2
  exit 1
fi

if [[ ! -f "${env_file}" ]]; then
  echo "找不到本地密钥文件：${env_file}" >&2
  exit 1
fi

bailian_key=$(sed -n 's/^DASHSCOPE_API_KEY=//p' "${env_file}" | tail -n 1)
if [[ -z "${bailian_key}" || "${bailian_key}" == "replace-me" ]]; then
  echo "DASHSCOPE_API_KEY 未配置" >&2
  exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "Kubernetes 实验集群不可访问；先运行 setup_kind.sh" >&2
  exit 1
fi

timestamp=$(date '+%Y%m%d-%H%M%S')
run_id="${run_label}-${timestamp}"
raw_dir="${lab_dir}/experiments/chapter3/results/raw/${run_id}"
mkdir -p "${raw_dir}"

# 上游 OOM 夹具固定为 amd64 专有镜像；Apple Silicon Kind 节点无法调度。
# 仅在该场景且节点为非 amd64 时临时应用等价故障补丁，退出时必定还原，
# 从而保持上游仓库仍固定在记录的 commit。
oom_patch="${lab_dir}/experiments/chapter3/patches/arm64-oom-fixture.patch"
oom_patch_applied=false
restore_fixture_patch() {
  if [[ "${oom_patch_applied}" == true ]]; then
    git -C "${holmes_dir}" apply -R "${oom_patch}"
  fi
}
trap restore_fixture_patch EXIT

node_arch=$(kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.architecture}')
if [[ "${scenario_filter}" == *"17_oom_kill"* && "${node_arch}" != "amd64" ]]; then
  if ! git -C "${holmes_dir}" apply --check "${oom_patch}"; then
    echo "ARM64 OOM 夹具补丁无法干净应用；请检查 HolmesGPT 工作区" >&2
    exit 1
  fi
  git -C "${holmes_dir}" apply "${oom_patch}"
  oom_patch_applied=true
  echo "已为 ${node_arch} 节点临时应用等价 OOM 夹具补丁"
fi

export OPENAI_API_KEY="${bailian_key}"
export OPENAI_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
export MODEL="openai/qwen-plus"
export CLASSIFIER_MODEL="qwen-plus"
export RUN_LIVE=true
export UPLOAD_DATASET=false
export ITERATIONS="${iterations}"
export OVERRIDE_MAX_OUTPUT_TOKEN="${HOLMES_MAX_OUTPUT_TOKENS:-8192}"
export EXPERIMENT_ID="${run_id}"
export PYTHONPATH="${holmes_dir}${PYTHONPATH:+:${PYTHONPATH}}"

cat > "${raw_dir}/metadata.json" <<EOF
{
  "run_id": "${run_id}",
  "phase": "${phase}",
  "git_commit": "$(git -C "${holmes_dir}" rev-parse HEAD)",
  "model": "openai/qwen-plus",
  "classifier_model": "qwen-plus",
  "variant": "${run_label}",
  "scenario_filter": "${scenario_filter}",
  "iterations": ${iterations},
  "kubernetes_context": "$(kubectl config current-context)",
  "kubernetes_arch": "${node_arch}",
  "fixture_compatibility_patch": ${oom_patch_applied},
  "max_output_tokens": ${OVERRIDE_MAX_OUTPUT_TOKEN},
  "started_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
}
EOF

echo "实验编号：${run_id}"
echo "场景过滤：${scenario_filter}"
echo "重复次数：${iterations}"
echo "原始结果：${raw_dir}"

set +e
(
  cd "${holmes_dir}"
  conda run -n holmesgpt python -m pytest \
    tests/llm/test_ask_holmes.py \
    -k "${scenario_filter}" \
    -n 1 \
    --strict-setup-mode=true \
    --timeout="${HOLMES_TEST_TIMEOUT_SECONDS:-180}" \
    --timeout-method=signal \
    --no-cov \
    --tb=short \
    -v -s \
    --json-report \
    --json-report-file="${raw_dir}/pytest.json"
) 2>&1 | tee "${raw_dir}/console.log"
pytest_status=${PIPESTATUS[0]}
set -e

unset bailian_key OPENAI_API_KEY
printf '%s\n' "${pytest_status}" > "${raw_dir}/exit_code.txt"

conda run -n holmesgpt python \
  "${lab_dir}/experiments/chapter3/summarize_pytest.py" \
  "${raw_dir}/pytest.json" \
  --metadata "${raw_dir}/metadata.json" \
  --output "${lab_dir}/experiments/chapter3/results/processed/${run_id}.csv"

echo "pytest_exit_code=${pytest_status}"
exit "${pytest_status}"
