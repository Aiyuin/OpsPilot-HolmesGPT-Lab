#!/usr/bin/env python3
"""第三章实验完成门禁：防止用少量或缺失数据生成毕业论文结论。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_SCENARIOS = {
    "09_crashpod",
    "10_image_pull_backoff",
    "15_failed_readiness_probe",
    "17_oom_kill",
    "80_pvc_storage_class_mismatch",
    "176_network_policy_blocking_traffic_no_skills",
}
REQUIRED_VARIANTS = {"direct_llm", "tool_agent", "opspilot_bounded"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("results/processed"))
    parser.add_argument("--minimum-repetitions", type=int, default=10)
    args = parser.parse_args()

    files = sorted(path for path in args.input_dir.glob("*.csv") if not path.name.startswith("summary_"))
    failures: list[str] = []
    if not files:
        failures.append("没有逐次实验 CSV")
        data = pd.DataFrame(columns=["variant", "scenario_id"])
    else:
        data = pd.concat([pd.read_csv(path) for path in files], ignore_index=True)
        if "phase" not in data.columns:
            data["phase"] = "pilot"
        else:
            data["phase"] = data["phase"].fillna("pilot")
        data = data[data["phase"] == "formal"].copy()
        if data.empty:
            failures.append("没有 phase=formal 的正式实验数据")

    variants = set(data.get("variant", pd.Series(dtype=str)).dropna().astype(str))
    scenarios = set(data.get("scenario_id", pd.Series(dtype=str)).dropna().astype(str))
    if missing := REQUIRED_VARIANTS - variants:
        failures.append(f"缺少对照/方法变体：{sorted(missing)}")
    if missing := REQUIRED_SCENARIOS - scenarios:
        failures.append(f"缺少故障场景：{sorted(missing)}")

    if not data.empty and {"variant", "scenario_id"}.issubset(data.columns):
        counts = data.groupby(["variant", "scenario_id"]).size()
        for variant in sorted(REQUIRED_VARIANTS & variants):
            for scenario in sorted(REQUIRED_SCENARIOS & scenarios):
                count = int(counts.get((variant, scenario), 0))
                if count < args.minimum_repetitions:
                    failures.append(
                        f"{variant}/{scenario} 仅 {count} 次，小于 {args.minimum_repetitions}"
                    )

    expected_artifacts = [
        args.input_dir / "summary_by_scenario.csv",
        args.input_dir / "summary_by_scenario.md",
        args.input_dir.parent.parent / "figures" / "accuracy_by_scenario.png",
    ]
    for artifact in expected_artifacts:
        if not artifact.exists():
            failures.append(f"缺少汇总产物：{artifact}")

    if failures:
        print("CHAPTER3_INCOMPLETE")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("CHAPTER3_DATA_GATE_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
