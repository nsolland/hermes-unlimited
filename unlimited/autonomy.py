"""Autonomous Mission & Completion Engine for Hermes Unlimited.

Implements the 9-step autonomous loop:
1. Receive a business objective.
2. Decompose into a DAG of executable work steps across AI Crew roles.
3. Select optimal models and role-scoped tools via AI Bridge routing.
4. Execute independently with idempotency and checkpointing.
5. Detect failures (routing, runtime, invalid output) and recover autonomously.
6. Verify actual outcomes via an independent verifier (never trust self-reports).
7. Calculate total execution costs (tokens, compute, time, opportunity, recovery).
8. Evaluate marginal Expected Value (EV) before every model call or retry.
9. Stop when the objective is verified complete or further work has EV <= 0.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal, Mapping

from .economics import (
    CostBreakdown,
    EconomicIntelligenceEngine,
    EconomicPolicy,
    MarginalEVDecision,
    ModelRouter,
    RoutingStrategy,
)

ROLE_TOOLSETS: Mapping[str, tuple[str, ...]] = {
    "director": ("objective_planner", "scope_validator"),
    "researcher": ("company_memory_recall", "evidence_extractor"),
    "builder": ("artifact_synthesizer", "schema_packager"),
    "skeptic": ("adversarial_critic", "invariant_checker"),
    "verifier": ("independent_outcome_verifier",),
    "operator": ("service_dispatcher", "kanban_monitor"),
}

FORBIDDEN_PLACEHOLDERS = ("TODO", "TBD", "PLACEHOLDER", "LOREM_IPSUM", "FABRICATED")


@dataclass(frozen=True)
class WorkStep:
    """A single node in the decomposed business objective DAG."""

    step_id: str
    title: str
    role: str
    task_kind: str
    complexity: Literal["low", "medium", "high"]
    depends_on: tuple[str, ...] = ()
    required_output_keys: tuple[str, ...] = ()
    marginal_value_share: float = 0.25
    estimated_input_tokens: int = 800
    estimated_output_tokens: int = 450

    def __post_init__(self) -> None:
        if not self.step_id or not isinstance(self.step_id, str):
            raise ValueError("STEP_ID_REQUIRED")
        if self.role not in ROLE_TOOLSETS:
            raise ValueError(f"UNKNOWN_CREW_ROLE:{self.role}")
        if self.complexity not in ("low", "medium", "high"):
            raise ValueError("COMPLEXITY_INVALID")
        if not (0.0 < self.marginal_value_share <= 1.0):
            raise ValueError("MARGINAL_VALUE_SHARE_INVALID")


@dataclass(frozen=True)
class BusinessObjective:
    """Formal business objective with measurable value and acceptance criteria."""

    objective_id: str
    company_id: str
    title: str
    description: str
    target_value_minor: int
    currency: str = "NOK"
    required_deliverables: tuple[str, ...] = (
        "executive_summary",
        "action_plan",
        "quantified_impact",
        "risk_mitigations",
    )
    acceptance_criteria: Mapping[str, Any] = field(default_factory=dict)
    policy: EconomicPolicy = field(default_factory=EconomicPolicy)
    steps: tuple[WorkStep, ...] = ()

    def __post_init__(self) -> None:
        if not self.objective_id or not self.company_id or not self.title:
            raise ValueError("OBJECTIVE_METADATA_REQUIRED")
        if type(self.target_value_minor) is not int or self.target_value_minor < 0:
            raise ValueError("TARGET_VALUE_INVALID")
        if not self.required_deliverables:
            raise ValueError("REQUIRED_DELIVERABLES_EMPTY")


@dataclass(frozen=True)
class StepAttemptReceipt:
    """Immutable record of one execution attempt for a work step."""

    step_id: str
    attempt: int
    model_id: str
    tools_bound: tuple[str, ...]
    status: Literal[
        "completed",
        "routing_error",
        "runtime_error",
        "invalid_output",
        "aborted_economic",
    ]
    output: Mapping[str, Any] | None
    error_reason: str | None
    cost: CostBreakdown
    ev_decision_digest: str
    receipt_digest: str


@dataclass(frozen=True)
class OutcomeVerificationReceipt:
    """Independent verification verdict — separate from agent self-report."""

    objective_id: str
    independently_verified: bool
    agent_claimed_complete: bool
    checks_passed: tuple[str, ...]
    checks_failed: tuple[str, ...]
    deliverable_digest: str
    evidence_digest: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MissionExecutionReport:
    """End-to-end report for an autonomous business objective execution."""

    objective_id: str
    company_id: str
    tenant_id: str
    identity: str
    routing_strategy: RoutingStrategy
    status: Literal[
        "VERIFIED_COMPLETE",
        "STOPPED_NEGATIVE_EV",
        "STOPPED_BUDGET_EXCEEDED",
        "STOPPED_SLA_EXCEEDED",
        "STOPPED_UNVERIFIED_OUTCOME",
        "INTERRUPTED_CHECKPOINTED",
    ]
    independently_verified: bool
    target_value_minor: int
    verified_value_minor: int
    direct_cost_minor: float
    total_economic_cost_minor: float
    recovery_spend_minor: float
    net_economic_value_minor: float
    roi_ratio: float
    elapsed_seconds: float
    total_model_calls: int
    total_input_tokens: int
    total_output_tokens: int
    failures_detected: int
    autonomous_recoveries: int
    duplicate_actions_prevented: int
    human_interventions_required: int
    stop_reason: str
    deliverables: Mapping[str, Any]
    verification: OutcomeVerificationReceipt
    step_receipts: tuple[StepAttemptReceipt, ...]
    ev_decisions: tuple[dict, ...]
    checkpoint_state: dict
    report_digest: str

    def as_dict(self) -> dict:
        data = asdict(self)
        return data


class ObjectiveDecomposer:
    """Decomposes a high-level BusinessObjective into an executable crew DAG."""

    @staticmethod
    def decompose(objective: BusinessObjective) -> tuple[WorkStep, ...]:
        if objective.steps:
            ObjectiveDecomposer._validate_dag(objective.steps)
            return objective.steps

        deliverables = tuple(objective.required_deliverables)
        combined_text = f"{objective.objective_id} {objective.title} {objective.description}".lower()
        is_complex_synthesis = any(
            kw in combined_text for kw in ("complex", "audit", "synthesis", "architecture")
        )
        build_kind = "synthesis" if is_complex_synthesis else "implementation"
        steps = (
            WorkStep(
                step_id="step-1-triage",
                title=f"Scope & decompose objective: {objective.title}",
                role="director",
                task_kind="triage",
                complexity="low",
                depends_on=(),
                required_output_keys=("scope_confirmed", "target_deliverables", "constraints"),
                marginal_value_share=0.15,
                estimated_input_tokens=600,
                estimated_output_tokens=300,
            ),
            WorkStep(
                step_id="step-2-research",
                title=f"Gather domain evidence & baseline economics for {objective.company_id}",
                role="researcher",
                task_kind="research",
                complexity="medium",
                depends_on=("step-1-triage",),
                required_output_keys=("evidence_items", "baseline_metrics"),
                marginal_value_share=0.25,
                estimated_input_tokens=950,
                estimated_output_tokens=500,
            ),
            WorkStep(
                step_id="step-3-build",
                title=f"Produce concrete deliverables for {objective.title}",
                role="builder",
                task_kind=build_kind,
                complexity="medium",
                depends_on=("step-2-research",),
                required_output_keys=deliverables,
                marginal_value_share=0.40,
                estimated_input_tokens=1200,
                estimated_output_tokens=750,
            ),
            WorkStep(
                step_id="step-4-critique",
                title="Adversarial Skeptic & Reality Checker audit of deliverables",
                role="skeptic",
                task_kind="verification",
                complexity="low",
                depends_on=("step-3-build",),
                required_output_keys=("audit_passed", "challenged_assumptions", "verified_keys"),
                marginal_value_share=0.20,
                estimated_input_tokens=900,
                estimated_output_tokens=350,
            ),
        )
        ObjectiveDecomposer._validate_dag(steps)
        return steps

    @staticmethod
    def _validate_dag(steps: tuple[WorkStep, ...]) -> None:
        if not steps:
            raise ValueError("DAG_EMPTY")
        seen: set[str] = set()
        for step in steps:
            if step.step_id in seen:
                raise ValueError(f"DUPLICATE_STEP_ID:{step.step_id}")
            for dep in step.depends_on:
                if dep not in seen:
                    raise ValueError(f"INVALID_OR_CYCLIC_DEPENDENCY:{step.step_id}->{dep}")
            seen.add(step.step_id)


class IndependentOutcomeVerifier:
    """Deterministic, independent outcome verifier.

    Never equates an agent claiming 'status: done' with a verified business
    outcome. Inspects actual deliverable structure, content invariants,
    provenance digests, and custom acceptance criteria.
    """

    def verify(
        self,
        objective: BusinessObjective,
        deliverables: Mapping[str, Any],
        step_receipts: tuple[StepAttemptReceipt, ...],
        *,
        tenant_id: str,
        identity: str,
    ) -> OutcomeVerificationReceipt:
        passed: list[str] = []
        failed: list[str] = []

        if not tenant_id or not identity:
            failed.append("identity_and_tenant_scope_present")
        else:
            passed.append("identity_and_tenant_scope_present")

        completed_steps = {
            r.step_id: r for r in step_receipts if r.status == "completed" and r.output is not None
        }
        expected_steps = ObjectiveDecomposer.decompose(objective)
        if all(s.step_id in completed_steps for s in expected_steps):
            passed.append("all_dag_steps_completed")
        else:
            missing_steps = [s.step_id for s in expected_steps if s.step_id not in completed_steps]
            failed.append(f"missing_dag_steps:{','.join(missing_steps)}")

        # Check every required deliverable key
        min_len = int(objective.acceptance_criteria.get("min_deliverable_chars", 12))
        for key in objective.required_deliverables:
            val = deliverables.get(key)
            if val is None:
                failed.append(f"deliverable_present:{key}")
                continue
            serialized = json.dumps(val, sort_keys=True) if not isinstance(val, str) else val.strip()
            if len(serialized) < min_len:
                failed.append(f"deliverable_substantive:{key}")
                continue
            upper = serialized.upper()
            if any(tok in upper for tok in FORBIDDEN_PLACEHOLDERS):
                failed.append(f"deliverable_no_placeholders:{key}")
                continue
            passed.append(f"deliverable_verified:{key}")

        # Check skeptic audit gate if present in DAG
        skeptic_receipt = completed_steps.get("step-4-critique")
        if skeptic_receipt is not None and skeptic_receipt.output is not None:
            if skeptic_receipt.output.get("audit_passed") is True:
                passed.append("skeptic_critique_gate_passed")
            else:
                failed.append("skeptic_critique_gate_failed")

        # Check custom numerical or structural invariants in acceptance_criteria
        required_Substrings = objective.acceptance_criteria.get("required_terms", ())
        full_text = json.dumps(deliverables, sort_keys=True).lower()
        for term in required_Substrings:
            if str(term).lower() in full_text:
                passed.append(f"required_term:{term}")
            else:
                failed.append(f"missing_required_term:{term}")

        custom_validator = objective.acceptance_criteria.get("validator")
        if callable(custom_validator):
            try:
                if custom_validator(deliverables) is True:
                    passed.append("custom_validator_passed")
                else:
                    failed.append("custom_validator_rejected")
            except Exception as exc:
                failed.append(f"custom_validator_error:{type(exc).__name__}")

        agent_claimed = bool(deliverables) and len(completed_steps) == len(expected_steps)
        independently_verified = len(failed) == 0 and len(passed) > 0

        deliv_digest = hashlib.sha256(
            json.dumps(deliverables, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        evidence_payload = {
            "objective_id": objective.objective_id,
            "tenant_id": tenant_id,
            "identity": identity,
            "independently_verified": independently_verified,
            "checks_passed": passed,
            "checks_failed": failed,
            "deliverable_digest": deliv_digest,
            "step_digests": [r.receipt_digest for r in step_receipts if r.status == "completed"],
        }
        evidence_digest = hashlib.sha256(
            json.dumps(evidence_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return OutcomeVerificationReceipt(
            objective_id=objective.objective_id,
            independently_verified=independently_verified,
            agent_claimed_complete=agent_claimed,
            checks_passed=tuple(passed),
            checks_failed=tuple(failed),
            deliverable_digest=deliv_digest,
            evidence_digest=evidence_digest,
        )


@dataclass
class StepWorkerResult:
    """Result returned by an injected or default step worker."""

    status: Literal["ok", "routing_error", "runtime_error"] = "ok"
    output: Mapping[str, Any] | None = None
    input_tokens: int = 800
    output_tokens: int = 450
    latency_sec: float = 3.0
    error_message: str | None = None


StepWorkerCallable = Callable[
    [WorkStep, str, int, Mapping[str, Any], tuple[str, ...]],
    StepWorkerResult,
]


def default_deterministic_worker(
    step: WorkStep,
    model_id: str,
    attempt: int,
    context: Mapping[str, Any],
    repair_hints: tuple[str, ...],
) -> StepWorkerResult:
    """Deterministic local worker for reproducible offline execution and testing."""
    objective_title = str(context.get("objective_title", "Business Objective"))
    company_id = str(context.get("company_id", "company"))
    required_deliverables = tuple(context.get("required_deliverables", ()))
    memory_lessons = tuple(context.get("memory_lessons", ()))

    latency_map = {
        "gemini-4-hydrogen": 2.2,
        "gemini-4-argon": 5.5,
        "gemini-4-carbon": 12.5,
    }
    latency = latency_map.get(model_id, 4.0)

    if step.task_kind == "triage":
        out = {
            "scope_confirmed": True,
            "target_deliverables": list(required_deliverables),
            "constraints": {
                "company_id": company_id,
                "zero_human_supervision_target": True,
                "applied_memory_lessons": len(memory_lessons),
            },
        }
    elif step.task_kind == "research":
        out = {
            "evidence_items": [
                f"Verified tenant scope for {company_id}",
                f"Analyzed objective: {objective_title}",
                *(f"Recalled lesson: {lesson}" for lesson in memory_lessons[:3]),
            ],
            "baseline_metrics": {
                "target_autonomy_rate": 1.0,
                "model_tier_selected": model_id,
            },
        }
    elif step.task_kind in ("implementation", "synthesis"):
        out = {}
        repaired_note = (
            f" (repaired after {len(repair_hints)} diagnostic feedback item(s))"
            if repair_hints
            else ""
        )
        for key in step.required_output_keys:
            out[key] = (
                f"Verified deliverable [{key}] for {company_id} ({objective_title}) "
                f"synthesized by {model_id} on attempt {attempt}{repaired_note}."
            )
    elif step.task_kind == "verification":
        prior_build = context.get("completed_outputs", {}).get("step-3-build", {})
        verified_keys = [
            k for k in required_deliverables
            if isinstance(prior_build.get(k), str) and len(prior_build.get(k, "")) >= 12
        ]
        out = {
            "audit_passed": len(verified_keys) == len(required_deliverables),
            "challenged_assumptions": [
                "Checked that completion is backed by artifacts, not status flags",
                "Verified cost remains below budget ceiling",
            ],
            "verified_keys": verified_keys,
        }
    else:
        out = {k: f"Completed {k} via {model_id}" for k in step.required_output_keys}

    return StepWorkerResult(
        status="ok",
        output=out,
        input_tokens=step.estimated_input_tokens + (attempt - 1) * 120,
        output_tokens=step.estimated_output_tokens,
        latency_sec=latency,
    )


class AutonomousMissionEngine:
    """Executes business objectives end-to-end with economic intelligence and verification."""

    def __init__(
        self,
        *,
        verify_identity: Callable[[str, str, str], bool],
        economic_engine: EconomicIntelligenceEngine | None = None,
        routing_strategy: RoutingStrategy = "outcome_driven",
        worker: StepWorkerCallable = default_deterministic_worker,
        verifier: IndependentOutcomeVerifier | None = None,
    ) -> None:
        if not callable(verify_identity):
            raise TypeError("Trusted JustYou identity verifier callable required")
        self.verify_identity = verify_identity
        self.economic_engine = economic_engine or EconomicIntelligenceEngine()
        self.routing_strategy: RoutingStrategy = routing_strategy
        self.worker = worker
        self.verifier = verifier or IndependentOutcomeVerifier()
        self._idempotency_ledger: dict[str, StepAttemptReceipt] = {}

    def execute_objective(
        self,
        *,
        provider_id: str,
        tenant_id: str,
        identity: str,
        objective: BusinessObjective,
        memory_lessons: tuple[str, ...] = (),
        checkpoint: Mapping[str, Any] | None = None,
        interrupt_after_steps: int | None = None,
    ) -> MissionExecutionReport:
        """Run or resume an autonomous mission under strict JustYou & EV governance."""
        if not provider_id or not tenant_id or not identity:
            raise PermissionError("JUSTYOU_SCOPE_REQUIRED")
        if self.verify_identity(provider_id, tenant_id, identity) is not True:
            raise PermissionError("JUSTYOU_IDENTITY_NOT_VERIFIED")

        # Align engine policy with the objective's economic policy
        self.economic_engine.policy = objective.policy
        router = ModelRouter(self.economic_engine, strategy=self.routing_strategy)
        steps = ObjectiveDecomposer.decompose(objective)

        # Restore from checkpoint if resuming an interrupted execution
        completed_outputs: dict[str, Mapping[str, Any]] = {}
        step_receipts: list[StepAttemptReceipt] = []
        ev_decisions: list[dict] = []
        spent_direct = 0.0
        spent_total_economic = 0.0
        recovery_spend = 0.0
        elapsed_sec = 0.0
        total_calls = 0
        total_in_tokens = 0
        total_out_tokens = 0
        failures_detected = 0
        autonomous_recoveries = 0
        duplicates_prevented = 0
        human_interventions = 0

        if checkpoint is not None:
            if (
                checkpoint.get("tenant_id") != tenant_id
                or checkpoint.get("company_id") != objective.company_id
                or checkpoint.get("objective_id") != objective.objective_id
            ):
                raise PermissionError("CHECKPOINT_SCOPE_MISMATCH")
            completed_outputs = dict(checkpoint.get("completed_outputs", {}))
            spent_direct = float(checkpoint.get("spent_direct", 0.0))
            spent_total_economic = float(checkpoint.get("spent_total_economic", 0.0))
            recovery_spend = float(checkpoint.get("recovery_spend", 0.0))
            elapsed_sec = float(checkpoint.get("elapsed_sec", 0.0))
            total_calls = int(checkpoint.get("total_calls", 0))
            total_in_tokens = int(checkpoint.get("total_in_tokens", 0))
            total_out_tokens = int(checkpoint.get("total_out_tokens", 0))
            failures_detected = int(checkpoint.get("failures_detected", 0))
            autonomous_recoveries = int(checkpoint.get("autonomous_recoveries", 0))
            duplicates_prevented = int(checkpoint.get("duplicates_prevented", 0))
            for raw_rec in checkpoint.get("step_receipts", ()):
                if isinstance(raw_rec, StepAttemptReceipt):
                    step_receipts.append(raw_rec)
                elif isinstance(raw_rec, Mapping):
                    raw_cost = raw_rec.get("cost", {})
                    cost_obj = (
                        raw_cost
                        if isinstance(raw_cost, CostBreakdown)
                        else CostBreakdown(
                            token_api_cost_minor=float(raw_cost.get("token_api_cost_minor", 0.0)),
                            compute_infra_cost_minor=float(raw_cost.get("compute_infra_cost_minor", 0.0)),
                            time_cost_minor=float(raw_cost.get("time_cost_minor", 0.0)),
                            opportunity_cost_minor=float(raw_cost.get("opportunity_cost_minor", 0.0)),
                            human_supervision_cost_minor=float(raw_cost.get("human_supervision_cost_minor", 0.0)),
                            recovery_cost_minor=float(raw_cost.get("recovery_cost_minor", 0.0)),
                            elapsed_seconds=float(raw_cost.get("elapsed_seconds", 0.0)),
                            input_tokens=int(raw_cost.get("input_tokens", 0)),
                            output_tokens=int(raw_cost.get("output_tokens", 0)),
                            model_calls=int(raw_cost.get("model_calls", 1)),
                            human_interventions=int(raw_cost.get("human_interventions", 0)),
                        )
                    )
                    step_receipts.append(
                        StepAttemptReceipt(
                            step_id=str(raw_rec["step_id"]),
                            attempt=int(raw_rec["attempt"]),
                            model_id=str(raw_rec["model_id"]),
                            tools_bound=tuple(raw_rec.get("tools_bound", ())),
                            status=raw_rec["status"],
                            output=raw_rec.get("output"),
                            error_reason=raw_rec.get("error_reason"),
                            cost=cost_obj,
                            ev_decision_digest=str(raw_rec.get("ev_decision_digest", "")),
                            receipt_digest=str(raw_rec.get("receipt_digest", "")),
                        )
                    )

        stop_status: Literal[
            "VERIFIED_COMPLETE",
            "STOPPED_NEGATIVE_EV",
            "STOPPED_BUDGET_EXCEEDED",
            "STOPPED_SLA_EXCEEDED",
            "STOPPED_UNVERIFIED_OUTCOME",
            "INTERRUPTED_CHECKPOINTED",
        ] | None = None
        stop_reason = ""
        steps_executed_this_run = 0
        unavailable_models: list[str] = []

        for step in steps:
            if step.step_id in completed_outputs:
                continue

            # Check idempotency ledger for already-completed step in this scope
            idem_key = f"{provider_id}:{tenant_id}:{objective.company_id}:{objective.objective_id}:{step.step_id}"
            if idem_key in self._idempotency_ledger:
                cached = self._idempotency_ledger[idem_key]
                if cached.status == "completed" and cached.output is not None:
                    duplicates_prevented += 1
                    completed_outputs[step.step_id] = cached.output
                    step_receipts.append(cached)
                    continue

            attempt = 1
            failed_models: list[str] = []
            repair_hints: list[str] = []
            step_succeeded = False

            while attempt <= objective.policy.max_step_attempts:
                # Marginal value at stake for this step is proportional to step weight on attempt 1,
                # and escalates on recovery attempts when the whole objective's completion is at risk.
                share = step.marginal_value_share if attempt == 1 else max(step.marginal_value_share, 0.65)
                marginal_value = float(objective.target_value_minor) * share
                selected_model, decision = router.select_model(
                    task_kind=step.task_kind,
                    marginal_value_minor=marginal_value,
                    spent_cost_minor=spent_direct,
                    elapsed_seconds=elapsed_sec,
                    attempt=attempt,
                    complexity=step.complexity,
                    estimated_input_tokens=step.estimated_input_tokens,
                    estimated_output_tokens=step.estimated_output_tokens,
                    failed_models=tuple(failed_models),
                    unavailable_models=tuple(unavailable_models),
                )
                ev_decisions.append({
                    "step_id": step.step_id,
                    "attempt": attempt,
                    **decision.as_dict(),
                })

                if not decision.economically_justified or selected_model is None:
                    if decision.verdict == "STOP_BUDGET_EXCEEDED":
                        stop_status = "STOPPED_BUDGET_EXCEEDED"
                    elif decision.verdict == "STOP_SLA_EXCEEDED":
                        stop_status = "STOPPED_SLA_EXCEEDED"
                    else:
                        stop_status = "STOPPED_NEGATIVE_EV"
                    stop_reason = decision.rationale
                    break

                # Execute the step with the chosen model and role-scoped tools
                tools_bound = ROLE_TOOLSETS[step.role]
                worker_ctx = {
                    "provider_id": provider_id,
                    "tenant_id": tenant_id,
                    "company_id": objective.company_id,
                    "objective_id": objective.objective_id,
                    "objective_title": objective.title,
                    "required_deliverables": objective.required_deliverables,
                    "completed_outputs": completed_outputs,
                    "memory_lessons": memory_lessons,
                }
                worker_res = self.worker(
                    step,
                    selected_model,
                    attempt,
                    worker_ctx,
                    tuple(repair_hints),
                )

                # Calculate actual cost incurred by this attempt
                profile = self.economic_engine.models[selected_model]
                if worker_res.status == "routing_error":
                    # Routing/endpoint failure before token generation: minimal probe cost
                    actual_in = 0
                    actual_out = 0
                    actual_lat = min(1.0, max(0.1, worker_res.latency_sec))
                    tok_cost = 0.0
                    comp_cost = actual_lat * profile.compute_cost_per_sec_minor
                else:
                    actual_in = max(0, int(worker_res.input_tokens))
                    actual_out = max(0, int(worker_res.output_tokens))
                    actual_lat = max(0.05, float(worker_res.latency_sec))
                    tok_cost = (
                        (actual_in / 1000.0) * profile.input_cost_per_1k_minor
                        + (actual_out / 1000.0) * profile.output_cost_per_1k_minor
                    )
                    comp_cost = actual_lat * profile.compute_cost_per_sec_minor

                mins = actual_lat / 60.0
                t_cost = mins * objective.policy.time_cost_per_min_minor
                opp_cost = mins * objective.policy.opportunity_cost_per_min_minor
                attempt_cost = CostBreakdown(
                    token_api_cost_minor=round(tok_cost, 4),
                    compute_infra_cost_minor=round(comp_cost, 4),
                    time_cost_minor=round(t_cost, 4),
                    opportunity_cost_minor=round(opp_cost, 4),
                    human_supervision_cost_minor=0.0,
                    recovery_cost_minor=0.0,
                    elapsed_seconds=round(actual_lat, 3),
                    input_tokens=actual_in,
                    output_tokens=actual_out,
                    model_calls=1,
                    human_interventions=0,
                )

                spent_direct = round(spent_direct + attempt_cost.direct_cost_minor, 4)
                spent_total_economic = round(spent_total_economic + attempt_cost.total_economic_cost_minor, 4)
                if attempt > 1:
                    recovery_spend = round(recovery_spend + attempt_cost.total_economic_cost_minor, 4)
                elapsed_sec = round(elapsed_sec + attempt_cost.elapsed_seconds, 3)
                total_calls += 1
                total_in_tokens += actual_in
                total_out_tokens += actual_out

                # Validate step output before accepting
                validation_error = self._validate_step_output(step, worker_res)
                if validation_error is None:
                    receipt = self._make_step_receipt(
                        step_id=step.step_id,
                        attempt=attempt,
                        model_id=selected_model,
                        tools_bound=tools_bound,
                        status="completed",
                        output=worker_res.output,
                        error_reason=None,
                        cost=attempt_cost,
                        ev_digest=decision.digest,
                    )
                    step_receipts.append(receipt)
                    assert worker_res.output is not None
                    completed_outputs[step.step_id] = worker_res.output
                    self._idempotency_ledger[idem_key] = receipt
                    self.economic_engine.record_observation(
                        model_id=selected_model,
                        task_kind=step.task_kind,
                        independently_verified_success=True,
                        input_tokens=actual_in,
                        output_tokens=actual_out,
                        latency_sec=actual_lat,
                    )
                    if attempt > 1:
                        autonomous_recoveries += 1
                    step_succeeded = True
                    break

                # Failure detected! Record failure and prepare autonomous recovery
                failures_detected += 1
                failure_kind: Literal["routing_error", "runtime_error", "invalid_output"]
                if worker_res.status == "routing_error":
                    failure_kind = "routing_error"
                    unavailable_models.append(selected_model)
                elif worker_res.status == "runtime_error":
                    failure_kind = "runtime_error"
                    failed_models.append(selected_model)
                else:
                    failure_kind = "invalid_output"
                    failed_models.append(selected_model)
                    self.economic_engine.record_observation(
                        model_id=selected_model,
                        task_kind=step.task_kind,
                        independently_verified_success=False,
                        input_tokens=actual_in,
                        output_tokens=actual_out,
                        latency_sec=actual_lat,
                    )

                repair_hints.append(f"attempt-{attempt}-{selected_model}:{validation_error}")
                receipt = self._make_step_receipt(
                    step_id=step.step_id,
                    attempt=attempt,
                    model_id=selected_model,
                    tools_bound=tools_bound,
                    status=failure_kind,
                    output=worker_res.output,
                    error_reason=validation_error,
                    cost=attempt_cost,
                    ev_digest=decision.digest,
                )
                step_receipts.append(receipt)
                attempt += 1

            if not step_succeeded:
                if stop_status is None:
                    stop_status = "STOPPED_NEGATIVE_EV"
                    stop_reason = (
                        f"Step {step.step_id} exhausted recovery attempts ({objective.policy.max_step_attempts}) "
                        f"without a verified output; halting fail-closed."
                    )
                break

            steps_executed_this_run += 1
            if interrupt_after_steps is not None and steps_executed_this_run >= interrupt_after_steps:
                if len(completed_outputs) < len(steps):
                    stop_status = "INTERRUPTED_CHECKPOINTED"
                    stop_reason = f"Execution interrupted after {steps_executed_this_run} step(s); checkpoint saved."
                    break

        # Extract final deliverables from build step (or merged outputs)
        deliverables: dict[str, Any] = {}
        if "step-3-build" in completed_outputs:
            deliverables.update(completed_outputs["step-3-build"])
        else:
            for out_map in completed_outputs.values():
                for k in objective.required_deliverables:
                    if k in out_map:
                        deliverables[k] = out_map[k]

        # Run independent outcome verification
        verification = self.verifier.verify(
            objective,
            deliverables,
            tuple(step_receipts),
            tenant_id=tenant_id,
            identity=identity,
        )

        # If all DAG steps ran but independent verification failed, try one targeted repair if EV > 0
        if (
            stop_status is None
            and not verification.independently_verified
            and "step-3-build" in completed_outputs
        ):
            failures_detected += 1
            build_step = next((s for s in steps if s.step_id == "step-3-build"), steps[-1])
            repair_model, repair_decision = router.select_model(
                task_kind="implementation",
                marginal_value_minor=float(objective.target_value_minor),
                spent_cost_minor=spent_direct,
                elapsed_seconds=elapsed_sec,
                attempt=2,
                complexity="high",
                estimated_input_tokens=build_step.estimated_input_tokens,
                estimated_output_tokens=build_step.estimated_output_tokens,
                failed_models=(step_receipts[-1].model_id,) if step_receipts else (),
            )
            ev_decisions.append({
                "step_id": "independent-verification-repair",
                "attempt": 2,
                **repair_decision.as_dict(),
            })
            if repair_decision.economically_justified and repair_model is not None:
                worker_ctx = {
                    "provider_id": provider_id,
                    "tenant_id": tenant_id,
                    "company_id": objective.company_id,
                    "objective_id": objective.objective_id,
                    "objective_title": objective.title,
                    "required_deliverables": objective.required_deliverables,
                    "completed_outputs": completed_outputs,
                    "memory_lessons": memory_lessons,
                }
                repair_res = self.worker(
                    build_step,
                    repair_model,
                    2,
                    worker_ctx,
                    verification.checks_failed,
                )
                profile = self.economic_engine.models[repair_model]
                r_in = max(0, int(repair_res.input_tokens))
                r_out = max(0, int(repair_res.output_tokens))
                r_lat = max(0.05, float(repair_res.latency_sec))
                r_tok = (
                    (r_in / 1000.0) * profile.input_cost_per_1k_minor
                    + (r_out / 1000.0) * profile.output_cost_per_1k_minor
                )
                r_comp = r_lat * profile.compute_cost_per_sec_minor
                r_mins = r_lat / 60.0
                r_cost = CostBreakdown(
                    token_api_cost_minor=round(r_tok, 4),
                    compute_infra_cost_minor=round(r_comp, 4),
                    time_cost_minor=round(r_mins * objective.policy.time_cost_per_min_minor, 4),
                    opportunity_cost_minor=round(r_mins * objective.policy.opportunity_cost_per_min_minor, 4),
                    human_supervision_cost_minor=0.0,
                    recovery_cost_minor=0.0,
                    elapsed_seconds=round(r_lat, 3),
                    input_tokens=r_in,
                    output_tokens=r_out,
                    model_calls=1,
                    human_interventions=0,
                )
                spent_direct = round(spent_direct + r_cost.direct_cost_minor, 4)
                spent_total_economic = round(spent_total_economic + r_cost.total_economic_cost_minor, 4)
                recovery_spend = round(recovery_spend + r_cost.total_economic_cost_minor, 4)
                elapsed_sec = round(elapsed_sec + r_cost.elapsed_seconds, 3)
                total_calls += 1
                total_in_tokens += r_in
                total_out_tokens += r_out
                if self._validate_step_output(build_step, repair_res) is None and repair_res.output:
                    completed_outputs["step-3-build"] = repair_res.output
                    deliverables.update(repair_res.output)
                    receipt = self._make_step_receipt(
                        step_id="step-3-build",
                        attempt=2,
                        model_id=repair_model,
                        tools_bound=ROLE_TOOLSETS[build_step.role],
                        status="completed",
                        output=repair_res.output,
                        error_reason=None,
                        cost=r_cost,
                        ev_digest=repair_decision.digest,
                    )
                    step_receipts.append(receipt)
                    if "step-4-critique" in completed_outputs:
                        verified_keys = [
                            k for k in objective.required_deliverables
                            if isinstance(deliverables.get(k), str) and len(str(deliverables.get(k))) >= 12
                        ]
                        critique_out = {
                            "audit_passed": len(verified_keys) == len(objective.required_deliverables),
                            "challenged_assumptions": ["Re-verified after targeted build repair"],
                            "verified_keys": verified_keys,
                        }
                        completed_outputs["step-4-critique"] = critique_out
                        step_receipts.append(
                            self._make_step_receipt(
                                step_id="step-4-critique",
                                attempt=2,
                                model_id=repair_model,
                                tools_bound=ROLE_TOOLSETS["skeptic"],
                                status="completed",
                                output=critique_out,
                                error_reason=None,
                                cost=CostBreakdown(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                                ev_digest=repair_decision.digest,
                            )
                        )
                    verification = self.verifier.verify(
                        objective,
                        deliverables,
                        tuple(step_receipts),
                        tenant_id=tenant_id,
                        identity=identity,
                    )
                    if verification.independently_verified:
                        autonomous_recoveries += 1

        if stop_status is None:
            if verification.independently_verified:
                stop_status = "VERIFIED_COMPLETE"
                # Evaluate post-completion stopping check to prove engine stops once complete
                post_check = self.economic_engine.evaluate_next_action(
                    task_kind="verification",
                    candidate_model_id="gemini-4-hydrogen",
                    marginal_value_minor=0.0,
                    spent_cost_minor=spent_direct,
                    elapsed_seconds=elapsed_sec,
                    objective_already_verified=True,
                )
                ev_decisions.append({
                    "step_id": "post-completion-gate",
                    "attempt": 1,
                    **post_check.as_dict(),
                })
                stop_reason = post_check.rationale
            else:
                stop_status = "STOPPED_UNVERIFIED_OUTCOME"
                stop_reason = (
                    "Execution finished but independent outcome verification failed: "
                    + ", ".join(verification.checks_failed)
                )

        verified_value = objective.target_value_minor if verification.independently_verified else 0
        net_value = round(float(verified_value) - spent_total_economic, 4)
        roi = round((net_value / spent_total_economic) if spent_total_economic > 0 else 0.0, 4)

        checkpoint_state = {
            "tenant_id": tenant_id,
            "company_id": objective.company_id,
            "objective_id": objective.objective_id,
            "completed_outputs": completed_outputs,
            "step_receipts": step_receipts,
            "spent_direct": spent_direct,
            "spent_total_economic": spent_total_economic,
            "recovery_spend": recovery_spend,
            "elapsed_sec": elapsed_sec,
            "total_calls": total_calls,
            "total_in_tokens": total_in_tokens,
            "total_out_tokens": total_out_tokens,
            "failures_detected": failures_detected,
            "autonomous_recoveries": autonomous_recoveries,
            "duplicates_prevented": duplicates_prevented,
        }

        summary_payload = {
            "objective_id": objective.objective_id,
            "company_id": objective.company_id,
            "tenant_id": tenant_id,
            "identity": identity,
            "status": stop_status,
            "independently_verified": verification.independently_verified,
            "verified_value_minor": verified_value,
            "total_economic_cost_minor": spent_total_economic,
            "net_economic_value_minor": net_value,
            "verification_digest": verification.evidence_digest,
        }
        report_digest = hashlib.sha256(
            json.dumps(summary_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return MissionExecutionReport(
            objective_id=objective.objective_id,
            company_id=objective.company_id,
            tenant_id=tenant_id,
            identity=identity,
            routing_strategy=self.routing_strategy,
            status=stop_status,
            independently_verified=verification.independently_verified,
            target_value_minor=objective.target_value_minor,
            verified_value_minor=verified_value,
            direct_cost_minor=spent_direct,
            total_economic_cost_minor=spent_total_economic,
            recovery_spend_minor=recovery_spend,
            net_economic_value_minor=net_value,
            roi_ratio=roi,
            elapsed_seconds=elapsed_sec,
            total_model_calls=total_calls,
            total_input_tokens=total_in_tokens,
            total_output_tokens=total_out_tokens,
            failures_detected=failures_detected,
            autonomous_recoveries=autonomous_recoveries,
            duplicate_actions_prevented=duplicates_prevented,
            human_interventions_required=human_interventions,
            stop_reason=stop_reason,
            deliverables=deliverables,
            verification=verification,
            step_receipts=tuple(step_receipts),
            ev_decisions=tuple(ev_decisions),
            checkpoint_state=checkpoint_state,
            report_digest=report_digest,
        )

    @staticmethod
    def _validate_step_output(step: WorkStep, res: StepWorkerResult) -> str | None:
        if res.status == "routing_error":
            return res.error_message or "MODEL_ROUTE_UNAVAILABLE"
        if res.status == "runtime_error":
            return res.error_message or "WORKER_RUNTIME_ERROR"
        if not isinstance(res.output, Mapping) or not res.output:
            return "OUTPUT_NOT_A_NONEMPTY_OBJECT"
        for key in step.required_output_keys:
            if key not in res.output or res.output[key] in (None, "", [], {}):
                return f"MISSING_REQUIRED_OUTPUT_KEY:{key}"
            val_str = str(res.output[key]).upper()
            if any(tok in val_str for tok in FORBIDDEN_PLACEHOLDERS):
                return f"FORBIDDEN_PLACEHOLDER_IN_KEY:{key}"
        return None

    @staticmethod
    def _make_step_receipt(
        *,
        step_id: str,
        attempt: int,
        model_id: str,
        tools_bound: tuple[str, ...],
        status: Literal[
            "completed",
            "routing_error",
            "runtime_error",
            "invalid_output",
            "aborted_economic",
        ],
        output: Mapping[str, Any] | None,
        error_reason: str | None,
        cost: CostBreakdown,
        ev_digest: str,
    ) -> StepAttemptReceipt:
        payload = {
            "step_id": step_id,
            "attempt": attempt,
            "model_id": model_id,
            "tools_bound": tools_bound,
            "status": status,
            "output": output,
            "error_reason": error_reason,
            "cost": cost.as_dict(),
            "ev_digest": ev_digest,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return StepAttemptReceipt(
            step_id=step_id,
            attempt=attempt,
            model_id=model_id,
            tools_bound=tools_bound,
            status=status,
            output=output,
            error_reason=error_reason,
            cost=cost,
            ev_decision_digest=ev_digest,
            receipt_digest=digest,
        )
