#!/usr/bin/env python3
"""将 pytest-json-report 转为适合统计分析的逐次实验 CSV。"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


FIELDS = [
    "run_id",
    "phase",
    "variant",
    "scenario_id",
    "model",
    "env_config",
    "outcome",
    "correctness",
    "duration_seconds",
    "holmes_duration_seconds",
    "llm_calls",
    "tool_calls",
    "total_tokens",
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "cost",
    "error_type",
    "error_message",
    "nodeid",
]


def properties(test: dict[str, Any]) -> dict[str, Any]:
    raw = test.get("user_properties") or []
    if isinstance(raw, dict):
        return raw
    result: dict[str, Any] = {}
    for item in raw:
        if isinstance(item, dict):
            result.update(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            result[str(item[0])] = item[1]
    return result


def scenario_from_nodeid(nodeid: str) -> str:
    match = re.search(r"test_ask_holmes\[([^-\]]+)", nodeid)
    return match.group(1) if match else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_report", type=Path)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.json_report.read_text(encoding="utf-8"))
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    for test in report.get("tests", []):
        nodeid = str(test.get("nodeid", ""))
        if "test_ask_holmes" not in nodeid:
            continue
        props = properties(test)
        call = test.get("call") or {}
        has_call_report = bool(test.get("call"))
        outcome = call.get("outcome", test.get("outcome", "unknown"))
        error_type = props.get("error_type", "")
        error_message = props.get("error_message", "")
        if not has_call_report:
            outcome = "incomplete"
            error_type = error_type or "MissingCallReport"
            error_message = error_message or (
                "pytest report has no call phase; the run was interrupted or the worker crashed"
            )
        rows.append(
            {
                "run_id": metadata.get("run_id", ""),
                "phase": metadata.get("phase", "pilot"),
                "variant": metadata.get("variant", ""),
                "scenario_id": props.get("clean_test_case_id")
                or scenario_from_nodeid(nodeid),
                "model": props.get("model", metadata.get("model", "")),
                "env_config": props.get("env_config", "default"),
                "outcome": outcome,
                "correctness": props.get("actual_correctness_score", 0),
                "duration_seconds": call.get("duration", ""),
                "holmes_duration_seconds": props.get("holmes_duration", ""),
                "llm_calls": props.get("num_llm_calls", ""),
                "tool_calls": props.get("tool_call_count", ""),
                "total_tokens": props.get("total_tokens", 0),
                "prompt_tokens": props.get("prompt_tokens", 0),
                "completion_tokens": props.get("completion_tokens", 0),
                "cached_tokens": props.get("cached_tokens", ""),
                "cost": props.get("cost", 0),
                "error_type": error_type,
                "error_message": error_message,
                "nodeid": nodeid,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote_rows={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
