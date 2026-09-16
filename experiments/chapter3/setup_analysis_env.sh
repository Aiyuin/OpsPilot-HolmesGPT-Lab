#!/usr/bin/env bash
set -euo pipefail

lab_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
env_name="${OPSPILOT_ANALYSIS_ENV:-opspilot-thesis}"

if ! conda env list | awk '{print $1}' | grep -Fxq "${env_name}"; then
  conda create -y -n "${env_name}" python=3.12 pip
fi

conda run -n "${env_name}" python -m pip install \
  -r "${lab_dir}/experiments/chapter3/requirements-analysis.txt"

conda run -n "${env_name}" python -c \
  'import matplotlib, pandas, scipy, seaborn; print("analysis_environment=ready")'
