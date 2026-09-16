#!/usr/bin/env python3
"""聚合第三章逐次实验结果并生成论文表格、统计量和图片。"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def wilson_interval(successes: int, total: int, z: float = 1.95996398454) -> tuple[float, float]:
    if total == 0:
        return (math.nan, math.nan)
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return centre - margin, centre + margin


def percentile95(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(np.percentile(values, 95)) if len(values) else math.nan


def load_results(input_dir: Path, include_pilot: bool = False) -> pd.DataFrame:
    files = sorted(
        path for path in input_dir.glob("*.csv") if not path.name.startswith("summary_")
    )
    if not files:
        raise SystemExit(f"没有 processed CSV：{input_dir}")
    frames = [pd.read_csv(path).assign(source_file=path.name) for path in files]
    data = pd.concat(frames, ignore_index=True)
    # 旧预实验文件没有 phase 字段，按 pilot 处理，避免污染正式统计。
    if "phase" not in data.columns:
        data["phase"] = "pilot"
    else:
        data["phase"] = data["phase"].fillna("pilot")
    if not include_pilot:
        data = data[data["phase"] == "formal"].copy()
        if data.empty:
            raise SystemExit("没有 phase=formal 的正式实验数据；预实验不会纳入论文统计")
    data["correctness"] = pd.to_numeric(data["correctness"], errors="coerce").fillna(0).astype(int)
    for column in ["duration_seconds", "holmes_duration_seconds", "tool_calls", "total_tokens"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def summarize(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (variant, scenario), group in data.groupby(["variant", "scenario_id"], dropna=False):
        total = len(group)
        successes = int(group["correctness"].sum())
        low, high = wilson_interval(successes, total)
        duration = group["holmes_duration_seconds"].fillna(group["duration_seconds"])
        rows.append(
            {
                "variant": variant,
                "scenario_id": scenario,
                "n": total,
                "correct": successes,
                "accuracy": successes / total if total else math.nan,
                "wilson95_low": low,
                "wilson95_high": high,
                "latency_p50_s": duration.median(),
                "latency_p95_s": percentile95(duration),
                "tokens_median": group["total_tokens"].median(),
                "tool_calls_median": group["tool_calls"].median(),
                "setup_or_runtime_failures": int((group["outcome"] != "passed").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "scenario_id"])


def write_markdown(summary: pd.DataFrame, output: Path) -> None:
    columns = [
        "variant",
        "scenario_id",
        "n",
        "correct",
        "accuracy",
        "wilson95_low",
        "wilson95_high",
        "latency_p50_s",
        "latency_p95_s",
        "tokens_median",
        "tool_calls_median",
    ]
    pretty = summary[columns].copy()
    for column in ["accuracy", "wilson95_low", "wilson95_high"]:
        pretty[column] = pretty[column].map(lambda value: f"{value:.3f}")
    for column in ["latency_p50_s", "latency_p95_s", "tokens_median", "tool_calls_median"]:
        pretty[column] = pretty[column].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    output.write_text(pretty.to_markdown(index=False) + "\n", encoding="utf-8")


def plot_accuracy(summary: pd.DataFrame, output: Path) -> None:
    variants = list(summary["variant"].drop_duplicates())
    scenarios = list(summary["scenario_id"].drop_duplicates())
    x = np.arange(len(scenarios))
    width = 0.8 / max(len(variants), 1)
    fig, axis = plt.subplots(figsize=(12, 5.5))
    for index, variant in enumerate(variants):
        subset = summary[summary["variant"] == variant].set_index("scenario_id").reindex(scenarios)
        accuracy = subset["accuracy"].to_numpy(dtype=float)
        low = subset["wilson95_low"].to_numpy(dtype=float)
        high = subset["wilson95_high"].to_numpy(dtype=float)
        positions = x - 0.4 + width / 2 + index * width
        axis.bar(positions, accuracy, width, label=str(variant))
        # Wilson 端点在 p=0/1 时可能因浮点舍入越界约 1e-16；误差条必须非负。
        lower_error = np.maximum(accuracy - low, 0)
        upper_error = np.maximum(high - accuracy, 0)
        axis.errorbar(
            positions,
            accuracy,
            yerr=[lower_error, upper_error],
            fmt="none",
            capsize=3,
            color="black",
        )
    axis.set_ylabel("Diagnostic accuracy")
    axis.set_xlabel("Fault scenario")
    axis.set_ylim(0, 1.08)
    axis.set_xticks(x, scenarios, rotation=25, ha="right")
    axis.legend(frameon=False)
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("results/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/processed"))
    parser.add_argument("--figure-dir", type=Path, default=Path("figures"))
    parser.add_argument(
        "--include-pilot",
        action="store_true",
        help="仅用于调试；把 phase=pilot 的数据也纳入汇总",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.figure_dir.mkdir(parents=True, exist_ok=True)

    data = load_results(args.input_dir, include_pilot=args.include_pilot)
    summary = summarize(data)
    summary.to_csv(args.output_dir / "summary_by_scenario.csv", index=False)
    write_markdown(summary, args.output_dir / "summary_by_scenario.md")
    plot_accuracy(summary, args.figure_dir / "accuracy_by_scenario.png")
    print(f"runs={len(data)} groups={len(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
