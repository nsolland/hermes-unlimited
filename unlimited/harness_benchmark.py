"""Deterministic, offline evaluation of agent harness traces.

Evidence metrics are advisory only, never execution authority.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Trial:
    task_id: str
    harness: str
    seed: int
    goal_met: bool
    verification_passed: bool
    proof_present: bool
    scope_preserved: bool
    resumed_correctly: bool
    interventions: int
    runtime_seconds: float
    cost_usd: float

    def __post_init__(self):
        if not self.task_id or not self.harness or isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("task_id, harness, integer seed required")
        for key in ("goal_met", "verification_passed", "proof_present", "scope_preserved", "resumed_correctly"):
            if not isinstance(getattr(self, key), bool):
                raise ValueError(f"{key} must be a bool")
        if isinstance(self.interventions, bool) or not isinstance(self.interventions, int) or self.interventions < 0:
            raise ValueError("interventions must be nonnegative integer")
        for key in ("runtime_seconds", "cost_usd"):
            val = getattr(self, key)
            if isinstance(val, bool) or not isinstance(val, (float, int)) or not 0 <= val < float("inf"):
                raise ValueError(f"{key} must be finite nonnegative number")

    @property
    def verified_completion(self) -> bool:
        return self.goal_met and self.verification_passed and self.proof_present and self.scope_preserved


def summarize(trials: Iterable[Trial]) -> dict:
    rows = list(trials)
    if not rows:
        raise ValueError("at least one trial required")
    by, seen = {}, set()
    for trial in rows:
        identity = (trial.harness, trial.task_id, trial.seed)
        if identity in seen:
            raise ValueError(f"duplicate trial: {identity}")
        seen.add(identity)
        by.setdefault(trial.harness, []).append(trial)
    result = {}
    for harness, group in sorted(by.items()):
        n = len(group)
        result[harness] = {
            "n": n,
            "verified_completion_rate": sum(t.verified_completion for t in group) / n,
            "claimed_goal_rate": sum(t.goal_met for t in group) / n,
            "scope_preservation_rate": sum(t.scope_preserved for t in group) / n,
            "resume_rate": sum(t.resumed_correctly for t in group) / n,
            "mean_interventions": sum(t.interventions for t in group) / n,
            "mean_runtime_seconds": sum(t.runtime_seconds for t in group) / n,
            "mean_cost_usd": sum(t.cost_usd for t in group) / n,
            "task_seed_pairs": sorted((t.task_id, t.seed) for t in group),
        }
    return result


def paired_delta(trials: Iterable[Trial], baseline: str, treatment: str) -> dict:
    rows = list(trials)
    summarize(rows)
    a = {(t.task_id, t.seed): t for t in rows if t.harness == baseline}
    b = {(t.task_id, t.seed): t for t in rows if t.harness == treatment}
    if not a or a.keys() != b.keys() or baseline == treatment:
        raise ValueError("baseline/treatment must have identical nonempty task/seed pairs")
    keys = sorted(a)
    return {
        "baseline": baseline, "treatment": treatment, "n_pairs": len(keys),
        "verified_completion_delta": sum(int(b[k].verified_completion) - int(a[k].verified_completion) for k in keys) / len(keys),
        "interventions_delta": sum(b[k].interventions - a[k].interventions for k in keys) / len(keys),
        "runtime_seconds_delta": sum(b[k].runtime_seconds - a[k].runtime_seconds for k in keys) / len(keys),
        "cost_usd_delta": sum(b[k].cost_usd - a[k].cost_usd for k in keys) / len(keys),
    }
