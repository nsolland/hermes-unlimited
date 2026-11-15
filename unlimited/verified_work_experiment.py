"""Evidence-first comparison of human, single-agent and agent-team work.

No model calls or external effects. Accepts JSONL observations produced by
existing Hermes tooling; missing measurements remain missing.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

REQUIRED = {"task_id", "arm", "accepted", "human_active_seconds",
            "elapsed_seconds", "human_interventions", "escalations",
            "rework_count", "independently_verified", "agent_cost_usd"}
ARMS = {"human", "single_agent", "agent_team"}


def validate(row):
    missing = REQUIRED - row.keys()
    if missing:
        raise ValueError("missing fields: " + ", ".join(sorted(missing)))
    if row["arm"] not in ARMS:
        raise ValueError("unknown arm")
    for field in ("accepted", "independently_verified"):
        if type(row[field]) is not bool:
            raise ValueError(field + " must be boolean")
    for field in ("human_active_seconds", "elapsed_seconds", "human_interventions",
                  "escalations", "rework_count", "agent_cost_usd"):
        v = row[field]
        if type(v) not in (int, float) or not 0 <= v < float("inf"):
            raise ValueError(field + " must be finite nonnegative")
    if row["human_active_seconds"] > row["elapsed_seconds"]:
        raise ValueError("active time exceeds elapsed time")
    if row["accepted"] and not row["independently_verified"]:
        raise ValueError("accepted work requires independent verification")
    return row


def summarize(rows):
    groups = defaultdict(list)
    seen = set()
    for raw in rows:
        r = validate(raw)
        key = (r["task_id"], r["arm"])
        if key in seen:
            raise ValueError("duplicate task/arm: " + repr(key))
        seen.add(key)
        groups[r["arm"]].append(r)
    result = {}
    for arm, group in sorted(groups.items()):
        accepted = [r for r in group if r["accepted"]]
        count = len(accepted)
        result[arm] = {
            "attempted": len(group),
            "accepted": count,
            "acceptance_rate": count / len(group),
            "human_seconds_per_accepted": (
                sum(r["human_active_seconds"] for r in group) / count if count else None),
            "mean_elapsed_seconds": statistics.mean(r["elapsed_seconds"] for r in group),
            "rework_total": sum(r["rework_count"] for r in group),
            "escalation_rate": sum(r["escalations"] > 0 for r in group) / len(group),
            "human_interventions_total": sum(r["human_interventions"] for r in group),
            "independent_verification_rate": (
                sum(r["independently_verified"] for r in group) / len(group)),
            "agent_cost_usd_total": sum(r["agent_cost_usd"] for r in group),
        }
    task_sets = {arm: {r["task_id"] for r in group} for arm, group in groups.items()}
    comparable = len(task_sets) == 3 and len(set(map(frozenset, task_sets.values()))) == 1
    result["comparison"] = {
        "paired": comparable,
        "task_count": len(next(iter(task_sets.values()))) if comparable else 0,
        "status": "MEASURED_NOT_CAUSAL" if comparable else "INCOMPLETE_BASELINE",
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.observations.read_text().splitlines() if line.strip()]
    report = summarize(rows)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
