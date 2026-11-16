"""Independent, descriptive analysis for checkpointed Hermes harness trials.

Pure offline evaluation; never represents an execution authorization decision.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def analyze(data):
    records = data["records"]
    expected_count = data["expected_invocations"]
    if len(records) != expected_count:
        raise ValueError(f"incomplete trial: {len(records)}/{expected_count}")
    if expected_count < 2 or expected_count % 2:
        raise ValueError("expected two variants per task")
    arm_pairs = {}
    for r in records:
        task, arm = r["task"], r["arm"]
        if arm not in ("baseline", "checker") or not isinstance(r["oracle_match"], bool):
            raise ValueError("invalid record")
        if not isinstance(r["seconds"], (int, float)) or not math.isfinite(r["seconds"]) or r["seconds"] < 0:
            raise ValueError("invalid duration")
        if (task, arm) in arm_pairs:
            raise ValueError("duplicate task/arm")
        arm_pairs[(task, arm)] = r
    tasks = sorted({r["task"] for r in records})
    if len(tasks)*2 != expected_count:
        raise ValueError("incomplete paired task set")
    paired = [(arm_pairs[(t, "baseline")], arm_pairs[(t, "checker")]) for t in tasks]
    b_success = sum(int(b["oracle_match"]) for b, _ in paired)
    c_success = sum(int(c["oracle_match"]) for _, c in paired)
    b_only = sum(b["oracle_match"] and not c["oracle_match"] for b, c in paired)
    c_only = sum(c["oracle_match"] and not b["oracle_match"] for b, c in paired)
    discordant = b_only + c_only
    if discordant:
        k = min(b_only, c_only)
        pvalue = min(1.0, 2*sum(math.comb(discordant, i) for i in range(k+1)) / (2**discordant))
    else:
        pvalue = 1.0
    return {
        "task_count": len(tasks),
        "invocations": len(records),
        "baseline_correct": b_success,
        "checker_correct": c_success,
        "baseline_completion_rate": b_success / len(tasks),
        "checker_completion_rate": c_success / len(tasks),
        "completion_delta_checker_minus_baseline": (c_success-b_success) / len(tasks),
        "baseline_only_correct": b_only,
        "checker_only_correct": c_only,
        "mcnemar_exact_two_sided_p_exploratory": pvalue,
        "baseline_timeouts": sum(int(b["exit_code"] == 124) for b, _ in paired),
        "checker_timeouts": sum(int(c["exit_code"] == 124) for _, c in paired),
        "mean_paired_duration_delta_seconds": sum(c["seconds"]-b["seconds"] for b,c in paired)/len(tasks),
        "interpretation": "Exploratory stress test. McNemar p is descriptive and does NOT address unpinned model RNG, shared-host load, order effects, latency censoring, or causal identification.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raw = Path(args.input).read_bytes()
    data = json.loads(raw)
    result = {"source_sha256": hashlib.sha256(raw).hexdigest(), "analysis": analyze(data)}
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result["analysis"], indent=2))


if __name__ == "__main__":
    main()
