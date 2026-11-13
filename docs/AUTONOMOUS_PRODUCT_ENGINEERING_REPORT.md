# Hermes Unlimited — Autonomous Company OS & Live SLA Resilience Report (2026-11-13)

## 1. Root-Cause Forensics of the Acer Live Runs (`db95cc0` & `38fd6a9`)

Inspection of `/home/njaal/.hermes/logs/agent.log`, `docs/live_acceptance_attempt_20261113.json`, and `docs/live_acceptance_attempt_nous_alibaba_20261113.json` revealed why `obj-live-1-security-audit` exceeded its 300s SLA budget (`331.495s` elapsed across 7 model calls) even after excluding Gemini (`429` free-tier quota exhausted):

| Root Cause | Evidence in `/home/njaal/.hermes/logs/agent.log` | Fix Implemented |
| --- | --- | --- |
| **1. Unbounded output/thinking tokens on `alibaba/qwen3.8-max`** | Every `qwen3.8-max` call generated `2,490–4,115` output tokens and took **58.6s–109.7s** per API call, whereas `nous/openai/gpt-5.4-mini` completed steps in **4.7s–7.3s**. | Added `alibaba/qwen3.5-plus` (`balanced` tier) to `LIVE_HERMES_MODEL_CATALOG` and `LIVE_NOUS_ALIBABA_MODEL_CATALOG`, passed bounded `max_tokens` (`550–1100`) and `reasoning_config={"effort": "low"}` to `AIAgent`. |
| **2. Multi-turn tool loop on `step-2-research`** | With `max_iterations=5`, `qwen3.8-max` executed 6 `read_file`/`search_files` tool calls across 2 turns (`12,778` input tokens), taking **138.6s** on a single step attempt. | Capped tool-enabled `step-2-research` at `max_iterations=2` (1 tool turn + 1 JSON synthesis turn). |
| **3. Incidental `"placeholder"` false-positive retries on `step-2-research` & `step-4-critique`** | `_sanitize_incidental_placeholder_words` was only applied to `step-3-build`. When `step-2-research` or `step-4-critique` wrote prose such as *"verified no placeholder values remain"*, `_validate_step_output` rejected the step with `FORBIDDEN_PLACEHOLDER_IN_KEY`, triggering a redundant 2nd attempt (+197s wasted). | Applied recursive `_sanitize_structure_placeholders` across all normalized step outputs (`step-1-triage`, `step-2-research`, `step-3-build`, `step-4-critique`). |
| **4. Soft `run_budget_seconds` in Hermes `AIAgent`** | In Hermes `conversation_loop.py` and `chat_completion_helpers.py`, `run_budget_seconds` only injects a soft wrap-up prompt at 80% budget and floors `cap_to_run_budget` at `60.0s`, while `HERMES_API_TIMEOUT` defaults to `1800.0s`. | Enforced hard per-step wall-clock deadlines (`step_deadline_seconds`, default `25s–35s`) in both `AutonomousMissionEngine._invoke_worker_with_deadline` and `HermesLiveWorkerAdapter._bounded_hermes_call` (`SIGALRM` + `tools.interrupt.set_interrupt(True)` + bounded `HERMES_API_TIMEOUT`). |
| **5. `rt.get("model", runtime_model_id)` when `model` key is `None`** | `HermesLiveWorkerAdapter` used `rt.get("model", runtime_model_id)` instead of `rt.get("model") or runtime_model_id`. | Fixed to `str(rt.get("model") or runtime_model_id)` and added `ProviderCircuitBreaker` to trip providers on HTTP `401/402/403/429` or repeated timeouts. |

---

## 2. Complete Vertical Slice: Owner Charter to Authorized Customer Delivery

`AutonomousCompanyOperatingSystem.run_operating_cycle` (`unlimited/company_os.py`) executes the complete AI-native company operation end-to-end:

1. **Owner Charter (`CompanyCharter`):** Defines mission statement, strategic domains, forbidden domains, minimum ROI hurdle ratio, and autonomous budget authority.
2. **Goal Fidelity & Opportunity Triage (`GoalFidelityEvaluator` + `CAVOOpportunityAllocator`):** Evaluates candidate objectives against the charter and ranks them by **CAVO** (*Cost per Autonomous Verified Outcome*) and expected net economic value.
3. **Crew DAG Execution (`AutonomousMissionEngine`):** Decomposes the selected objective into role-specialized steps (`director`, `researcher`, `builder`, `skeptic`) with per-step deadlines (`step_deadline_seconds`), automatic model failover, durable SQLite step idempotency (`step_idempotency_ledger`), and process-restart checkpoint recovery (`mission_checkpoints` with `resume_from_ledger=True`).
4. **Independent Verification (`IndependentOutcomeVerifier` + `VerifierSigningAuthority`):** Enforces 10 verification layers, cross-provider LLM critic (`HermesLiveIndependentCritic`), scope-bound HMAC-SHA256 seals (`tenant_id`, `company_id`, `objective_id`, `policy_digest`), and anti-replay protection.
5. **Explicit Completion Semantics (`CompletionSemanticsReport`):** Explicitly separates:
   - `produced_artifact` (worker produced candidate deliverables)
   - `verified_artifact` (cryptographically sealed & independently verified by critic)
   - `authorized_external_effect` (customer communication/delivery separately authorized and recorded)
   - `measured_business_result` (verified positive net economic value)
6. **Durable Company Memory & Service Factory (`CompanyMemoryStore` + `ServiceFactory`):** Harvests verified lessons (`VERIFIED_OUTCOME`) and synthesizes positive-EV missions into priced `ServiceBlueprint` entries published to `ProviderStore`.
7. **Authorized Customer Delivery (`AuthorizedCustomerDeliveryChannel`):** Issues signed `CustomerDeliveryReceipt` entries in the transactional SQLite outbox (`customer_delivery_outbox`) only when JustYou identity, `TenantAdapterRegistry` capability scope (`customer-delivery-outbox`), independent verification seal, and `authorize_external_effect=True` are all satisfied.
8. **Captain's Bridge (`unlimited/a2ui_adapter.py`):** Exposes read-only A2UI 1.0 surfaces (`companies`, `requests`, `missions`, `readiness`) for the owner.

---

## 3. Adapter Maturity Gate (`TenantAdapterRegistry`)

`unlimited/adapter_gate.py` implements `TenantAdapterRegistry` alongside host manifest admission (`authorize_adapter`):

| Adapter ID | Maturity Tier | Mandatory | Independently Tested | Release Eligible | Capabilities |
| --- | --- | --- | --- | --- | --- |
| `justyou` | `CORE` | Yes (all tenants) | Yes (`unit`, `contract`, `security`, `integration`) | **Yes** | `identity.verify`, `scope.enforce`, `audit.seal` |
| `company-memory` | `CORE` | Optional per tenant | Yes | **Yes** | `memory.read`, `memory.write`, `memory.recall` |
| `service-factory` | `CORE` | Optional per tenant | Yes | **Yes** | `blueprint.register`, `service.deliver`, `sla.verify` |
| `customer-delivery-outbox` | `VERIFIED` | Optional per tenant | Yes | **Yes** | `customer.communicate`, `delivery.receipt.issue` |
| `a2ui-captains-bridge` | `VERIFIED` | Optional per tenant | Yes | **Yes** | `bridge.read`, `bridge.action.propose` |
| `live-email-connector` | `EXPERIMENTAL` | Optional | No | **No (Blocked)** | `email.send.external` |
| `live-payment-settlement` | `EXPERIMENTAL` | Optional | No | **No (Blocked)** | `payment.charge`, `invoice.settle` |
| `live-crm-sync` | `EXPERIMENTAL` | Optional | No | **No (Blocked)** | `crm.write.external` |
