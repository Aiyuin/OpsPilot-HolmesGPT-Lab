#!/usr/bin/env python3
"""运行不访问任何环境工具的 Qwen 基线，并保存逐次可追溯结果。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


FIELDS = [
    "run_id",
    "phase",
    "variant",
    "scenario_id",
    "category",
    "repetition",
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


def read_dotenv_value(path: Path, key: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def keyword_score(output: str, groups: list[list[str]]) -> int:
    lowered = output.casefold()
    return int(all(any(keyword.casefold() in lowered for keyword in group) for group in groups))


def git_commit(workspace: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(workspace / "holmesgpt"), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def checkpoint(
    processed_file: Path,
    raw_responses_file: Path,
    rows: list[dict[str, Any]],
    raw_responses: list[dict[str, Any]],
) -> None:
    """每次调用后落盘；意外中断时保留已完成样本。"""
    with processed_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    raw_responses_file.write_text(
        json.dumps(raw_responses, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--label", default="direct_llm")
    parser.add_argument("--phase", choices=("pilot", "formal"), default="pilot")
    args = parser.parse_args()
    if args.repetitions < 1 or args.repetitions > 30:
        raise SystemExit("repetitions 必须在 1..30")

    chapter_dir = Path(__file__).resolve().parent
    lab_dir = chapter_dir.parent.parent
    workspace = lab_dir.parent
    env_file = Path(os.environ.get("OPSPILOT_ENV_FILE", lab_dir / "deployment/.env"))
    api_key = read_dotenv_value(env_file, "DASHSCOPE_API_KEY")
    if not api_key or api_key == "replace-me":
        raise SystemExit(f"DASHSCOPE_API_KEY 未配置：{env_file}")
    base_url = os.environ.get(
        "BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    scenarios = json.loads(
        (chapter_dir / "config/scenario_manifest.json").read_text(encoding="utf-8")
    )
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"{args.label}-{timestamp}"
    raw_dir = chapter_dir / "results/raw" / run_id
    processed_file = chapter_dir / "results/processed" / f"{run_id}.csv"
    raw_responses_file = raw_dir / "responses.json"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=api_key, base_url=base_url)

    metadata = {
        "run_id": run_id,
        "phase": args.phase,
        "variant": "direct_llm",
        "label": args.label,
        "git_commit": git_commit(workspace),
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "repetitions": args.repetitions,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scoring": "deterministic keyword groups; semantic/human audit pending",
    }
    (raw_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rows: list[dict[str, Any]] = []
    raw_responses: list[dict[str, Any]] = []
    system_prompt = (
        "You are an SRE diagnosing a live Kubernetes environment. You have no access "
        "to cluster state, logs, events, metrics, or tools. Do not invent observations. "
        "State clearly when the supplied evidence is insufficient, then list the exact "
        "evidence required to confirm a root cause."
    )

    for repetition in range(1, args.repetitions + 1):
        for scenario in scenarios:
            started = time.perf_counter()
            outcome = "passed"
            output = ""
            error_type = ""
            error_message = ""
            prompt_tokens = completion_tokens = total_tokens = 0
            try:
                response = client.chat.completions.create(
                    model=args.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": scenario["prompt"]},
                    ],
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                )
                output = response.choices[0].message.content or ""
                if response.usage:
                    prompt_tokens = response.usage.prompt_tokens
                    completion_tokens = response.usage.completion_tokens
                    total_tokens = response.usage.total_tokens
            except Exception as error:  # raw experiment must retain failures
                outcome = "error"
                error_type = type(error).__name__
                error_message = str(error)[:500]
            duration = time.perf_counter() - started
            correctness = keyword_score(output, scenario["keyword_groups"]) if outcome == "passed" else 0
            rows.append(
                {
                    "run_id": run_id,
                    "phase": args.phase,
                    "variant": "direct_llm",
                    "scenario_id": scenario["scenario_id"],
                    "category": scenario["category"],
                    "repetition": repetition,
                    "model": args.model,
                    "env_config": "no_tools",
                    "outcome": outcome,
                    "correctness": correctness,
                    "duration_seconds": duration,
                    "holmes_duration_seconds": "",
                    "llm_calls": 1,
                    "tool_calls": 0,
                    "total_tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": "",
                    "cost": "",
                    "error_type": error_type,
                    "error_message": error_message,
                    "nodeid": f"direct::{scenario['scenario_id']}::{repetition}",
                }
            )
            raw_responses.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "repetition": repetition,
                    "prompt": scenario["prompt"],
                    "output": output,
                    "correctness": correctness,
                    "outcome": outcome,
                    "duration_seconds": duration,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "error_type": error_type,
                    "error_message": error_message,
                }
            )
            checkpoint(processed_file, raw_responses_file, rows, raw_responses)
            print(
                f"{scenario['scenario_id']} repetition={repetition} "
                f"correct={correctness} latency={duration:.2f}s outcome={outcome}"
            )

    metadata["completed_at"] = datetime.now(timezone.utc).isoformat()
    metadata["status"] = "completed"
    (raw_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"run_id={run_id} rows={len(rows)} processed={processed_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
