"""Reproduce observed paired cost/outcomes from archived Salad records.

Pure analysis: never make an inferred Agency or Hermes CLI production claim.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

try:
    from scripts.harness_salad_verify import verify
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from harness_salad_verify import verify


def empirical_outcomes(raw: dict, receipt: dict, task_bytes: bytes) -> dict:
    """Verify evidence first; then independently recompute arm cost and quality."""
    verification = verify(raw, receipt, task_bytes)
    groups: dict[str, list[dict]] = {"baseline": [], "checker": []}
    for row in raw["results"]:
        groups[row["arm"]].append(row)
    costs = {}
    for arm, rows in groups.items():
        try:
            values = [Decimal(r["estimated_usd"]) for r in rows]
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise ValueError(f"invalid cost observation for {arm}") from exc
        if any(not n.is_finite() or n < 0 for n in values):
            raise ValueError(f"nonfinite/negative cost for {arm}")
        if any(not isinstance((r.get("usage") or {}).get("total_tokens"), int)
               or isinstance(r["usage"]["total_tokens"], bool)
               or r["usage"]["total_tokens"] < 0 for r in rows):
            raise ValueError("invalid token usage")
        costs[arm] = {
            "estimated_usd": str(sum(values)),
            "correct": verification["by_arm"][arm]["correct"],
            "n": len(rows),
            "total_tokens": sum(r["usage"]["total_tokens"] for r in rows),
        }
    baseline = Decimal(costs["baseline"]["estimated_usd"])
    checker = Decimal(costs["checker"]["estimated_usd"])
    if baseline <= 0:
        raise ValueError("baseline cost must be positive")
    reduction = (baseline - checker) / baseline
    same_quality = costs["baseline"]["correct"] == costs["checker"]["correct"]
    return {
        "experiment": raw["experiment"],
        "classification": verification["classification"],
        "verified_task_digest": verification["task_digest_verified"],
        "verified_provider_digest": verification["provider_digest_verified"],
        "stopped": verification["stop_confirmed"],
        "arms": costs,
        "estimated_cost_reduction_fraction": str(reduction),
        "unchanged_pass_count": same_quality,
        "meets_20pct_cost_and_quality_gate": reduction >= Decimal("0.20") and same_quality,
        "limit": "Archived Salad instruction-ablation results only; estimated gateway prices, not Hermes/JevRouter routing or Agency results.",
    }


def main():
    root = Path(__file__).resolve().parents[1] / "experiments" / "harness"
    outcome = empirical_outcomes(
        json.loads((root / "20261116_salad_a1_raw.json").read_text()),
        json.loads((root / "20261116_salad_a1_receipt.json").read_text()),
        (root / "tasks_v2.json").read_bytes(),
    )
    print(json.dumps(outcome, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
