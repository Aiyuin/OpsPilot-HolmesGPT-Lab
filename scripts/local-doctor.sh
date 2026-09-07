#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../holmesgpt" && pwd)

echo "== Conda =="
conda run -n holmesgpt python --version
conda run -n holmesgpt poetry --version

echo "== HolmesGPT import =="
conda run -n holmesgpt python -c 'import holmes; print("holmes import: OK")'

echo "== Git =="
git -C "${project_dir}" status --short --branch
git -C "${project_dir}" log -1 --oneline
