#!/usr/bin/env bash
set -euo pipefail

chapter_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export MPLCONFIGDIR="${chapter_dir}/.matplotlib"
mkdir -p "${MPLCONFIGDIR}"

cd "${chapter_dir}"
conda run -n "${OPSPILOT_ANALYSIS_ENV:-opspilot-thesis}" python analyze_results.py
conda run -n "${OPSPILOT_ANALYSIS_ENV:-opspilot-thesis}" python validate_completion.py
