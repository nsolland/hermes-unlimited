"""Tool-first specialist factory: discover capabilities, derive bounded tasks, and evaluate models.

No provider calls or permissions are created by this module. Tool schemas are
untrusted descriptions, not proof of access. Model qualification is based only
on independently scored observations supplied by the caller.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Capability:
    tool_name: str
    description: str
    parameters: Mapping[str, Any]
    required: tuple[str, ...]
    schema_digest: str
    effect: str
    verified_access: bool = False


@dataclass(frozen=True)
class Specialist:
    specialist_id: str
    objective: str
    tools: tuple[str, ...]
    capability_digests: tuple[str, ...]
    allowed_effects: tuple[str, ...]
    status: str = "DRAFT_UNVERIFIED"


@dataclass(frozen=True)
class Trial:
    model_id: str
    case_id: str
    passed: bool
    cost_minor: float
    latency_seconds: float
    independently_verified: bool = False
    run_id: str = ""


def discover_capabilities(schemas: Sequence[Mapping[str, Any]]) -> tuple[Capability, ...]:
    """Normalize MCP/Hermes-style schemas without granting authority."""
    capabilities = []
    seen = set()
    for raw in schemas:
        name = raw.get("name")
        params = raw.get("parameters", raw.get("inputSchema"))
        if not isinstance(name, str) or not name.strip() or name in seen:
            raise ValueError("INVALID_OR_DUPLICATE_TOOL_NAME")
        if not isinstance(params, dict) or params.get("type") != "object":
            raise ValueError("INVALID_TOOL_SCHEMA")
        properties = params.get("properties", {})
        required = params.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list) or any(
            not isinstance(k, str) or k not in properties for k in required
        ):
            raise ValueError("INVALID_TOOL_PARAMETERS")
        effect = raw.get("effect", "unknown")
        if effect not in ("read", "write", "execute", "unknown"):
            raise ValueError("INVALID_EFFECT")
        seen.add(name)
        capabilities.append(Capability(
            tool_name=name,
            description=str(raw.get("description", "")),
            parameters=params,
            required=tuple(required),
            schema_digest=_digest({"name": name, "parameters": params, "description": raw.get("description", "")}),
            effect=effect,
        ))
    return tuple(capabilities)



def review_capability_effects(catalog: Sequence[Capability],
                              reviewed_effects: Mapping[str, str]) -> tuple[Capability, ...]:
    """Apply explicitly reviewed operation effects; never treat review as authority."""
    from dataclasses import replace
    known = {item.tool_name for item in catalog}
    if not isinstance(reviewed_effects, dict) or set(reviewed_effects) - known:
        raise ValueError("UNKNOWN_EFFECT_REVIEW_TARGET")
    if any(effect not in ("read", "write", "execute") for effect in reviewed_effects.values()):
        raise ValueError("INVALID_EFFECT_REVIEW")
    return tuple(replace(cap, effect=reviewed_effects.get(cap.tool_name, cap.effect)) for cap in catalog)


def build_specialist(
    objective: str, selected_tools: Sequence[str], catalog: Sequence[Capability],
    *, allowed_effects: Sequence[str] = ("read",),
) -> Specialist:
    """Build a proposal from selected capabilities; never silently approve execution."""
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("OBJECTIVE_REQUIRED")
    if not selected_tools or len(set(selected_tools)) != len(selected_tools):
        raise ValueError("TOOLS_REQUIRED_OR_DUPLICATED")
    known = {cap.tool_name: cap for cap in catalog}
    if any(name not in known for name in selected_tools):
        raise ValueError("UNDISCOVERED_TOOL")
    effects = set(allowed_effects)
    if not effects.issubset({"read", "write", "execute"}):
        raise ValueError("INVALID_ALLOWED_EFFECTS")
    if any(known[name].effect not in effects for name in selected_tools):
        raise PermissionError("TOOL_EFFECT_NOT_APPROVED")
    digests = tuple(known[name].schema_digest for name in selected_tools)
    return Specialist(
        specialist_id="specialist-" + _digest({"objective": objective, "tools": list(selected_tools), "digests": digests})[:16],
        objective=objective.strip(),
        tools=tuple(selected_tools),
        capability_digests=digests,
        allowed_effects=tuple(sorted(effects)),
    )


def rank_models(
    trials: Sequence[Trial], required_cases: Sequence[str], *,
    min_pass_rate: float = 0.98, min_repetitions: int = 3,
    max_latency_seconds: float | None = None,
) -> dict[str, Any]:
    """Qualify only independent, complete test matrices; cost counts failed attempts.

    Each required case needs min_repetitions independent verified observations.
    Observations must have distinct nonempty run IDs to avoid duplicate receipts.
    No claim of statistical confidence is made from the empirical pass rate.
    """
    if not 0 < min_pass_rate <= 1 or min_repetitions < 1:
        raise ValueError("INVALID_ACCEPTANCE_CRITERIA")
    if not required_cases or len(set(required_cases)) != len(required_cases):
        raise ValueError("REQUIRED_CASES_INVALID")
    if max_latency_seconds is not None and max_latency_seconds <= 0:
        raise ValueError("INVALID_LATENCY_BOUND")
    per_model: dict[str, list[Trial]] = {}
    for trial in trials:
        if (not trial.model_id or not trial.case_id or not math.isfinite(trial.cost_minor)
            or not math.isfinite(trial.latency_seconds)
            or trial.cost_minor < 0 or trial.latency_seconds < 0):
            raise ValueError("INVALID_TRIAL")
        per_model.setdefault(trial.model_id, []).append(trial)
    results = []
    for model, rows in sorted(per_model.items()):
        valid = [t for t in rows if t.independently_verified and t.run_id and t.case_id in required_cases]
        ids = [t.run_id for t in valid]
        duplicate = len(ids) != len(set(ids))
        covered = all(sum(t.case_id == case for t in valid) >= min_repetitions for case in required_cases)
        # Use only required-case observations in the comparison, including failures.
        success = (sum(t.passed for t in valid) / len(valid)) if valid else 0.0
        cost = (sum(t.cost_minor for t in valid) / len(valid)) if valid else None
        latency = (sum(t.latency_seconds for t in valid) / len(valid)) if valid else None
        qualified = (covered and not duplicate and success >= min_pass_rate
                     and (max_latency_seconds is None or (latency is not None and latency <= max_latency_seconds)))
        results.append({
            "model_id": model, "qualified": qualified, "verified_runs": len(valid),
            "coverage_complete": covered, "duplicate_receipts": duplicate,
            "pass_rate": success, "mean_cost_minor": cost, "mean_latency_seconds": latency,
        })
    winners = sorted((r for r in results if r["qualified"]),
                     key=lambda r: (r["mean_cost_minor"], r["mean_latency_seconds"], r["model_id"]))
    return {
        "status": "QUALIFIED" if winners else "NO_QUALIFIED_MODEL",
        "recommended_model": winners[0]["model_id"] if winners else None,
        "models": results,
        "acceptance": {"required_cases": list(required_cases), "min_pass_rate": min_pass_rate,
                       "min_repetitions": min_repetitions, "max_latency_seconds": max_latency_seconds},
        "evidence_class": "INDEPENDENT_OBSERVATIONS" if trials else "NO_OBSERVATIONS",
    }


def specialist_manifest(specialist: Specialist, evaluation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Export a reviewable proposal; qualification alone grants no execution rights."""
    result = asdict(specialist)
    result["model_evaluation"] = dict(evaluation or {})
    result["execution_authorized"] = False
    return result


def discover_host_tools(registry: Any, *, toolset: str, limit: int = 100) -> tuple[Capability, ...]:
    """Inspect real Hermes registered tool definitions, not a copied manifest.

    The host registry owns availability checks; these capabilities are still
    descriptive, and require explicit separate authority for any execution.
    """
    if not isinstance(toolset, str) or not toolset.strip() or limit < 1 or limit > 500:
        raise ValueError("INVALID_DISCOVERY_SCOPE")
    names = [n for n in registry.get_all_tool_names()
             if n != "unlimited_specialist_factory" and registry.get_toolset_for_tool(n) == toolset]
    if len(names) > limit:
        raise ValueError("TOOL_DISCOVERY_LIMIT_EXCEEDED")
    definitions = registry.get_definitions(set(names), quiet=True)
    schemas = []
    for definition in definitions:
        raw = definition.get("function", {})
        if not isinstance(raw, dict):
            continue
        schemas.append({"name": raw.get("name"), "description": raw.get("description", ""),
                        "parameters": raw.get("parameters", {}), "effect": "unknown"})
    return discover_capabilities(schemas)


def run_live_probe(llm: Any, *, model_id: str, case_id: str, prompt: str,
                   expected: str, cost_usd_to_minor: float, run_id: str) -> Trial:
    """Read-only exact-output evaluation through Hermes host-owned model interface.

    For non-exact business workflows an external task-specific verifier is
    required. A failed or unpriced call cannot become a qualifying receipt.
    """
    if not all(isinstance(x, str) and x.strip() for x in (model_id, case_id, prompt, expected, run_id)):
        raise ValueError("INVALID_PROBE")
    if not 0 < cost_usd_to_minor < 1e12 or not math.isfinite(cost_usd_to_minor):
        raise ValueError("INVALID_CURRENCY_CONVERSION")
    from time import monotonic
    started = monotonic()
    result = llm.complete(
        [{"role": "system", "content": "Return only the exact requested output. Do not use tools."},
         {"role": "user", "content": prompt}],
        model=model_id, temperature=0, max_tokens=80, timeout=25,
        purpose="tool_first_specialist_read_only_probe",
    )
    elapsed = max(0, monotonic() - started)
    raw_cost = getattr(getattr(result, "usage", None), "cost_usd", None)
    if raw_cost is None or not isinstance(raw_cost, (int, float)) or not math.isfinite(raw_cost) or raw_cost < 0:
        raise ValueError("MISSING_VERIFIABLE_COST")
    if str(getattr(result, "model", "")) != model_id:
        raise ValueError("MODEL_MISMATCH")
    return Trial(model_id=model_id, case_id=case_id,
                 passed=str(getattr(result, "text", "")).strip() == expected.strip(),
                 cost_minor=raw_cost * cost_usd_to_minor,
                 latency_seconds=elapsed, independently_verified=True, run_id=run_id)


def run_model_matrix(
    llm: Any, *, models: Sequence[str], cases: Sequence[Mapping[str, str]],
    repetitions: int, cost_usd_to_minor: float, min_pass_rate: float = .98,
) -> dict[str, Any]:
    """Bounded empirical model sweep using Hermes host model calls.

    Exact-output fixtures only; external effects are never performed. Each
    executed observation has its own run identifier and verifiable cost.
    """
    from uuid import uuid4
    if (not models or len(models) > 4 or len(set(models)) != len(models)
            or not cases or len(cases) > 4 or not isinstance(repetitions, int)
            or repetitions < 3 or repetitions > 5
            or len(models) * len(cases) * repetitions > 24):
        raise ValueError("MODEL_MATRIX_BOUNDS_INVALID")
    case_ids = [case.get("case_id", "") for case in cases]
    if len(set(case_ids)) != len(case_ids) or any(
        not isinstance(case.get(k), str) or not case[k].strip()
        for case in cases for k in ("case_id", "prompt", "expected")
    ):
        raise ValueError("MODEL_MATRIX_CASES_INVALID")
    if any(not isinstance(m, str) or not m.strip() for m in models):
        raise ValueError("MODEL_MATRIX_MODELS_INVALID")
    trials = []
    for model in models:
        for case in cases:
            for _ in range(repetitions):
                trials.append(run_live_probe(
                    llm, model_id=model, case_id=case["case_id"],
                    prompt=case["prompt"], expected=case["expected"],
                    cost_usd_to_minor=cost_usd_to_minor, run_id=uuid4().hex))
    result = rank_models(trials, case_ids, min_pass_rate=min_pass_rate,
                         min_repetitions=repetitions)
    return {**result, "observations": [asdict(t) for t in trials]}
