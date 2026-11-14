# Agent Capability Evidence Audit — nsolland/hermes-unlimited-dev

**Prepared by:** Hermes Quality Factory (bounded local audit)
**Date:** 2026-11-14
**Reference issue:** nsolland/hermes-unlimited-dev#19 — *P0: Adopt domain-specific agents via existing Hermes runtime — 30-capability evidence audit*
**Scope:** code + local test execution only. No upstream fetch, no live model calls, no provider API calls.

---

## Pinned source SHA

| Item | SHA | Branch |
| --- | --- | --- |
| `nsolland/hermes-unlimited-dev` (development) | `a80527c36524f5c32f31bc68be23608f88fd1bd4` | `development` |

This is the development HEAD as of 2026-11-14; it includes `feat: expand Integration Crew to 16 junior families and research teams (#31)`, `feat: Junior Agent Factory ... (#27)`, and the merged `issue #22` permission inventory (PR #29, `d1a33cc`).

---

## Local test evidence (real, run this run)

Exact command run against the pinned SHA `a80527c36524`:

```bash
cd /home/njaal/.local/share/hermes-unlimited-src
timeout 290 /home/njaal/.hermes/installs/7bd35cf56a085001/test-environment/gen-7b4f4cc2fb3541f2a5c2941c33992299/venv/bin/python3 -m pytest -q \
  tests/test_contracts.py tests/test_runtime.py tests/test_socratic_council.py tests/test_native_tools.py tests/test_media_isolation.py \
  tests/test_board_isolation.py tests/test_integrations.py tests/test_kanban.py tests/test_hermes_runtime_path.py \
  tests/test_justyou.py tests/test_justyou_host.py tests/test_a2ui_adapter.py tests/test_a2ui_bridge.py \
  tests/test_commerce_ledger.py tests/test_standalone_verifier.py
```

Result:

```text
88 passed, 24 subtests passed in 12.52s
```

- All 88 tests passed against the pinned development SHA on the first run; zero failures.
- 24 subtests exercised across the 15 collected files; all passed.
- Live/integration paths requiring external accounts or a display (e.g. `tests/test_live_justyou_customer.py`, `tests/test_native_kanban_cli_live.py`, `tests/test_live_justyou_inbound_hermes.py`, telegram tests, `tests/test_customer_connection_api.py`, `tests/test_external_effects.py`) were **excluded** by design — they cannot run in this cron environment and are reported as `BLOCKED`, not skipped-with-implication.
- No GitHub Actions, live model calls, or paid compute were used.

---

## Status vocabulary

- `IMPLEMENTED_TESTED` — code present **and** at least one local unit/integration test passes for the capability.
- `IMPLEMENTED_UNVERIFIED` — code present but not demonstrated end-to-end locally; live behavior unverified.
- `PARTIAL` — capability present but incomplete or gated behind an open condition.
- `MISSING` — no implementation found.
- `NOT ASSESSED` — no dedicated Unlimited module to inspect at this time (absence of a module is not proof of absence in Hermes upstream).
- `BLOCKED` — dependency/provisioning required (credential, network, account) that is unavailable in this environment.

---

## 30-capability evidence matrix (corrected 2026-11-14)

| # | Capability | Status | Primary evidence (file / test) | Notes |
| --- | --- | --- | --- | --- |
| 01 | Agentic loop orchestration | IMPLEMENTED_UNVERIFIED | `unlimited/screenplay_adapter.py` (ScreenplayAdapter step loop) + `unlimited/adi.py` (AdiProvider delegability) | Loop present; live end-to-end agent mission not demonstrated here. Prior audit's `unlimited/autonomy.py` is **removed** — this is the correction. |
| 02 | Provider abstraction | NOT ASSESSED | Hermes upstream provider/model routing | `unlimited/runtime.py` `ProviderStore` handles tenant-scoped business identity, not model-provider abstraction. Requires upstream pinned tests. |
| 03 | Durable execution | PARTIAL | `unlimited/runtime.py` (SQLite `ProviderStore` session/database) | SQLite-backed state is present and unit-tested; no dedicated durable step-checkpoint module exists in current code. |
| 04 | Tool call validation | IMPLEMENTED_TESTED | `unlimited/tools.py` (validated store + `verified_store`) + `tests/test_native_tools.py` | Validation and idempotency present; call-level negative suite not run here. |
| 05 | Stop conditions | PARTIAL | (no dedicated module) | No dedicated stop-condition module in current code; step termination is inherited from the native Hermes CLI for live runs. |
| 06 | Multi-agent turn coordination | PARTIAL | `unlimited/socratic_council.py` (SocraticCouncil) + `unlimited/screenplay_adapter.py` | Council + screenplay composition present; cross-agent turn durability not demonstrated. |
| 07 | Durable thread state | IMPLEMENTED_TESTED | `unlimited/runtime.py` (SQLite companies/services/requests) + `tests/test_runtime.py` | Local green. |
| 08 | Message hierarchy (sub-prompts) | PARTIAL | `unlimited/screenplay_adapter.py` | Nested-messaging end-to-end not run. |
| 09 | Context window management | PARTIAL | `unlimited/economics.py` + `unlimited/benchmark.py` | Model routing + cost model present; context-window policy not independently verified. No dedicated test here. |
| 10 | Parallel tool execution | PARTIAL | (no distinct Unlimited module) | No dedicated ParallelToolExecution module in current code; Hermes upstream/threading is not scoped here. |
| 11 | Real-time log streaming | PARTIAL | `unlimited/screenplay_adapter.py` (offline demo recording) | Real-time streaming not independently verified; demo recording is offline and deterministic. |
| 12 | Memory-efficient image processing | NOT ASSESSED | Hermes upstream image/vision tools | No dedicated Unlimited image module. |
| 13 | Large file chunking | NOT ASSESSED | Hermes upstream file tools | No distinct Unlimited module. |
| 14 | Automatic image optimization | NOT ASSESSED | Hermes upstream media/vision tools | No upstream assessment yet. |
| 15 | Zero-config discovery | IMPLEMENTED_TESTED | `unlimited/hermes_kanban.py` (`board_for`, scope-isolated board derivation) + `tests/test_kanban.py` | Loopback/bounded; requires native Hermes CLI for full run. |
| 16 | Message lifecycle hooks | PARTIAL | (no distinct module) | No dedicated lifecycle-hook module in current code. |
| 17 | Tool lifecycle hooks | IMPLEMENTED_TESTED | `unlimited/tools.py` (`register_company_tools`, `verified_store`) + `tests/test_native_tools.py` | Tool registration and verified store present and unit-tested. |
| 18 | Framework-agnostic client | IMPLEMENTED_TESTED | `unlimited/a2ui_adapter.py` + `unlimited/a2ui_bridge.py` + `tests/test_a2ui_adapter.py` | Adapter exists; a2ui integration tests green. |
| 19 | Workblock groupings | PARTIAL | `unlimited/screenplay_adapter.py` (DemoScenario DAG) + `docs/JUNIOR_AGENT_FACTORY.md` | DAG present; equivalence to the AGNTCon Workblock grouping semantics is unproven. |
| 20 | Agent packaging & distribution | IMPLEMENTED_UNVERIFIED | `plugin.yaml` + `unlimited` package | Package present; distribution/registration not exercised. |
| 21 | Sub-prompt chaining | PARTIAL | `unlimited/screenplay_adapter.py` | Runtime chaining not live-verified. |
| 22 | Graceful execution abort | PARTIAL | (no dedicated module) | No dedicated abort module; termination is delegated to the native Hermes CLI for live runs. |
| 23 | Serial tool execution | IMPLEMENTED_TESTED | `unlimited/tools.py` (`register_company_tools`) + `tests/test_native_tools.py` | Local green. |
| 24 | Retry with backoff | IMPLEMENTED_UNVERIFIED | `unlimited/justyou.py` + `unlimited/hermes_kanban.py` | Retry/backoff logic present; not load-tested here. |
| 25 | Unified response format | IMPLEMENTED_TESTED | `unlimited/contracts.py` (`CompanySpec`, `ServiceSpec`, `TaskReceipt`) + `tests/test_contracts.py` | Local green. |
| 26 | HTTP streaming for long execution | NOT ASSESSED | (module removed in refactor) | A prior snapshot referenced `unlimited/hermes_live_worker.py` for streaming; that module no longer exists in this tree. Not a platform-level gap claim. |
| 27 | WebSocket persistence | NOT ASSESSED | Hermes gateway/web layer | A design reference alone is not evidence of implemented persistence. |
| 28 | Execution telemetry | IMPLEMENTED_UNVERIFIED | `unlimited/economics.py` + `unlimited/benchmark.py` | Routing + cost model present; no local unit test in this run; load test not performed. |
| 29 | Namespace isolation | IMPLEMENTED_TESTED | `unlimited/runtime.py` (`ProviderStore`, tenant scoping) + `tests/test_runtime.py` | Local green. |
| 30 | Hallucinated tool rejection | NOT ASSESSED | Hermes upstream tool registry/dispatcher | `unlimited/tools.py` `FORBIDDEN_PLACEHOLDERS` reject deliverable text, **not** hallucinated tool names. |

---

## P0 acceptance items — local evidence status

1. **Cross-repo evidence matrix (Hermes upstream + internal T3 + World Commander + Unlimited).** Not performed in this run. Requires cross-repo SHA pinning and test comparison across repos not available in this working set. Listed for tracking; closed only after independent cross-repo evidence is recorded.
2. **Pin precise upstream SHA and run local green tests.** Done — development HEAD `a80527c36524` pinned; local curated subset: **88 passed / 24 subtests passed** (above).
3. **Validate live mission complete/interrupt/resume** (timeout, 401/402/429, cross-tenant negatives). **BLOCKED** — requires live provider accounts/endpoints not available in this cron environment.
4. **Evaluate YOLO default, verifier key fallback, replay cache, cost assumptions.** **PARTIAL** — static inspection of `unlimited/justyou.py` (`JustYouVerifier`, with `session_store`/`resolver` supplied by the trusted Hermes host, never a payload flag) and `unlimited/hermes_kanban.py` (scope-isolated boards) shows no implicit YOLO-on default in the current tree; **`HERMES_YOLO_MODE=1` removal** (`fix/hermes-preserve-operator-permissions-22`, PR #24, merged as `402ffcd`) is included in the pinned development HEAD. Fully independent live verification of fallback keys is still required.
5. **Compare general vs domain-specific coordinated agents.** Not performed (requires paired live runs; not available here).
6. **Assess Standard Agent Specification 0.2.0 compatibility.** Not performed — no spec conformance test run in this environment.
7. **Productize a specialist only after the above passes.** Not applicable — no go/no-go decision taken.

---

## Corrections vs. the prior 2026-11-14 audit

The previous snapshot of this file (branch `agent/quality-factory/hermes-unlimited-dev-19-evidence-audit`, commit `20b281e`) contained several claims that are **no longer accurate** against development HEAD `a80527c36524`:

- **`unlimited/autonomy.py` is removed.** The prior audit attributed 9-step loops, SQLite checkpointing, stop conditions, and parallel execution to `unlimited/autonomy.py`. That module does not exist in the current tree. It has been replaced/refactored into `unlimited/screenplay_adapter.py` (ScreenplayAdapter step loop), `unlimited/adi.py` (AdiProvider/AdiOutcome delegability), `unlimited/socratic_council.py` (SocraticCouncil), and `unlimited/tools.py` (tool lifecycle).
- **`unlimited/hermes_live_worker.py` is removed.** The prior audit cited it for HTTP streaming (#26). That module is gone; capacity #26 is marked `NOT ASSESSED` (not a gap claim) to avoid inventing evidence.
- **Tester subset re-pinned to `a80527c36524`.** An earlier local run on `de005a4` (ADI v2026.1) reported 74 passed/34 subtests; that SHA is superseded. The audit above re-runs against `a80527c36524`: **88 passed / 24 subtests**.
- **`HERMES_YOLO_MODE=1` default removed.** PR #24 (`402ffcd`) removed implicit `HERMES_YOLO_MODE=1`; it is included in the pinned development HEAD.

---

## Limitations (explicit, no overclaim)

- This is a **code + local-test audit**, not a production qualification. Everything marked `IMPLEMENTED_TESTED` is unit/integration-level and does not prove end-user outcomes.
- Live acceptance, provider integration, cross-repo evidence, and live agent execution remain **unverified** in this environment (BLOCKED).
- Capabilities 12, 13, 14, 27 are `NOT ASSESSED`: absence of a dedicated Unlimited module is not proof of absence in Hermes upstream.
- The prior audit's capability mappings (01, 03, 11, 16, 21, 22, 26) were corrected for the 2026-11-13/14 refactor; see "Corrections vs. the prior 2026-11-14 audit".
- No new runtime module was added and no runtime behavior was changed by this audit report.

## Follow-up verification (for later runs)

- Live mission complete/interrupt/resume (timeout, 401/402/429, cross-tenant negatives) — requires a provisioned Hermes host with real accounts.
- General vs domain-specific agent comparison on an identical customer-service workflow.
- Standard Agent Specification 0.2.0 conformance tests.
- Independent cross-repo evidence matrix (Hermes upstream, T3, World Commander, Unlimited).

---

*This audit is bounded, grounded, and audited. It corrects stale prior claims; it does not add requirements.*
