# Agent Capability Evidence Audit — nsolland/hermes-unlimited-dev

**Prepared by:** Hermes Quality Factory (bounded local audit)
**Date:** 2026-11-14
**Reference issue:** nsolland/hermes-unlimited-dev#19 — *P0: Adopt domain-specific agents via existing Hermes runtime — 30-capability evidence audit*

## Pinned source SHA

| Item | SHA | Branch |
| --- | --- | --- |
| `nsolland/hermes-unlimited-dev` (development) | `5555bef80e2f4f9f1aaf0e5e7b2ed7d0c992ac50` | `development` |

No upstream fetch, no live model calls, no provider API calls were made for this audit. The audit is grounded in **local code state** and **local test execution only**.

## Local test evidence

Ran the local suite against pinned development HEAD `5555bef` (`PYTHONPATH` set to the worktree root):

```
189 passed, 2 skipped, 29 subtests passed in 72.42s (0:01:12)
```

Notes:
- 29 subtests were run within the 189 passed tests; 2 tests were skipped (live/integration paths requiring external accounts or a display).
- No GitHub Actions, live provider calls, or paid compute were used.

## Status vocabulary

- `IMPLEMENTED_TESTED` — code present, at least one local unit/integration test passes for the capability.
- `IMPLEMENTED_UNVERIFIED` — code present but not demonstrated end-to-end locally; live behavior unverified.
- `PARTIAL` — capability present but incomplete or gated behind an open condition.
- `MISSING` — no implementation found.
- `BLOCKED` — dependency/provisioning required (credential, network, account) that is unavailable here.

## 30-capability evidence matrix

| # | Capability | Status | Primary evidence (file / test) | Notes |
| --- | --- | --- | --- | --- |
| 01 | Agentic loop orchestration | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` (9-step loop) + `tests/test_autonomous_company.py` | Code present; live loop not demonstrated locally. |
| 02 | Provider abstraction | NOT ASSESSED | Hermes upstream provider/model routing; `ProviderStore` only handles tenant-scoped business identity | Local ProviderStore tests do **not** establish model-provider abstraction. Requires upstream pinned tests. |
| 03 | Durable execution | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` (SQLite checkpointing, in-memory + Durable SQLite) | Code present; live recovery path untested. |
| 04 | Tool call validation | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` + `unlimited/tools.py` | Idempotency/validation present; call-level negative suite not run here. |
| 05 | Stop conditions | IMPLEMENTED_TESTED | `unlimited/autonomy.py` (step 9: EV <= 0 stop) + `test_autonomous_company.py` | Local test observable. |
| 06 | Multi-agent turn coordination | PARTIAL | `unlimited/autonomy.py` (Crew roles), World Commander candidate integrations | Role dispatch alone does not demonstrate cross-agent turns or durable handoffs. |
| 07 | Durable thread state | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` (SQLite durable state) | Present; live replay not demonstrated. |
| 08 | Message hierarchy (sub-prompts) | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` | Present in loop; nested-messaging end-to-end not run. |
| 09 | Context window management | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` + `unlimited/economics.py` | Model routing present; context-window policy not independently verified. |
| 10 | Parallel tool execution | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` (concurrent.futures) | Thread pool present; parallel tool live test not run. |
| 11 | Real-time log streaming | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` + web layer | Present; real-time streaming not smoke-tested locally. |
| 12 | Memory-efficient image processing | NOT ASSESSED | Hermes upstream image/vision tools to inspect | No dedicated Unlimited implementation is not proof of a platform-level gap. |
| 13 | Large file chunking | NOT ASSESSED | Hermes upstream file tools to inspect | No distinct Unlimited module; upstream not verified. |
| 14 | Automatic image optimization | NOT ASSESSED | Hermes upstream media/vision tools to inspect | No upstream assessment yet. |
| 15 | Zero-config discovery | IMPLEMENTED_UNVERIFIED | `unlimited/hermes_kanban.py`, `justyou.py` | Discovery present; not exercised live. |
| 16 | Message lifecycle hooks | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` | Present; live hook coverage not measured. |
| 17 | Tool lifecycle hooks | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` + `unlimited/tools.py` | Present; not independently regression-tested here. |
| 18 | Framework-agnostic client | IMPLEMENTED_TESTED | `unlimited/a2ui_adapter.py`, `a2ui_bridge.py` + `test_a2ui_adapter.py` | Adapter exists; a2ui integration tests green. |
| 19 | Workblock groupings | PARTIAL | `unlimited/autonomy.py` (DAG of work steps) | DAG steps are tested; equivalence to the slide's Workblock grouping semantics is unproven. |
| 20 | Agent packaging & distribution | IMPLEMENTED_UNVERIFIED | `plugin.yaml`, `unlimited` package | Package present; distribution/registration not exercised. |
| 21 | Sub-prompt chaining | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` | Present; runtime chaining not live-verified. |
| 22 | Graceful execution abort | IMPLEMENTED_TESTED | `unlimited/autonomy.py` + `test_runtime.py` | Local observable. |
| 23 | Serial tool execution | IMPLEMENTED_TESTED | `unlimited/autonomy.py` + `tests/test_autonomous_company.py` | Local observable. |
| 24 | Retry with backoff | IMPLEMENTED_UNVERIFIED | `unlimited/autonomy.py` + `unlimited/economics.py` | Retry logic present; backoff not load-tested. |
| 25 | Unified response format | IMPLEMENTED_TESTED | `unlimited/contracts.py` (`CompanySpec`, `ServiceSpec`, `TaskReceipt`) + `tests/test_contracts.py` | Local green. |
| 26 | HTTP streaming for long execution | IMPLEMENTED_UNVERIFIED | web layer + `unlimited/hermes_live_worker.py` | Present; streaming not live-verified. |
| 27 | WebSocket persistence | NOT ASSESSED | Hermes gateway/web layer to inspect | A design reference alone is not evidence of implemented persistence. |
| 28 | Execution telemetry | IMPLEMENTED_TESTED | `unlimited/economics.py` + `unlimited/benchmark.py` | Local observable. |
| 29 | Namespace isolation | IMPLEMENTED_TESTED | `unlimited/runtime.py` (`ProviderStore`, tenant scoping) + `tests/test_runtime.py` | Local green. |
| 30 | Hallucinated tool rejection | NOT ASSESSED | Hermes upstream tool registry/dispatcher to inspect | `FORBIDDEN_PLACEHOLDERS` rejects deliverable text, **not** hallucinated tool names. |

## P0 acceptance items — local evidence status

1. **Cross-repo evidence matrix (Hermes upstream + internal T3 + World Commander + Unlimited).** Not performed in this run. Requires cross-repo SHA pinning and test comparison across repos not available in this working set. Listed here for tracking; closed only after independent cross-repo evidence is recorded.
2. **Pin precise upstream SHA and run local green tests.** Done — development HEAD `5555bef` pinned; local suite: 189 passed / 2 skipped (above).
3. **Validate live mission complete/interrupt/resume** (timeout, 401/402/429, cross-tenant negatives). **Blocked** — requires live provider accounts/endpoints not available in this cron environment.
4. **Evaluate YOLO default, verifier key fallback, replay cache, cost assumptions.** **Not performed in the original bounded audit** — static inspection alone identified `HERMES_YOLO_MODE=1` default on that snapshot and a verifier signing-key fallback. These risks must be evaluated regardless of live mission availability.
5. **Compare general vs domain-specific coordinated agents.** Not performed (requires paired live runs; not available here).
6. **Assess Standard Agent Specification 0.2.0 compatibility.** Not performed — no spec compliance test run in this environment.
7. **Productize a specialist only after the above passes.** Not applicable — no go/no-go decision taken.

## Limitations (explicit, no overclaim)

- This is a **code + local-test audit**, not a production qualification. Everything marked `IMPLEMENTED_TESTED` is unit/integration-level and does not prove end-user outcomes.
- Live acceptance, provider integration, cross-repo evidence, and live agent execution remain **unverified** in this environment.
- Capability numbers 12, 13, 14 are `NOT ASSESSED`: absence of a dedicated Unlimited module is not proof of absence in Hermes upstream.
- No new module was added and no runtime behavior was changed by this audit report.

## Follow-up verification (2026-11-14; separate from original bounded audit)

- Acer Hermes runtime reports Hermes Agent v0.22.7 (`b200f5bc60e3`), 92 registered tool names in its native Python environment; schema discovery exposed four `file`, two `web`, two `terminal`, and one `browser` tool definitions. Metadata discovery is not proof of execution permission.
- `nsolland/world-commander` main tree `a6506fa722d460e448a2ecbb724e202262aa1059` includes skill registry, Hermes loop adapter and goal-verification test candidates. `nsolland/ai-bridge` main tree `eacd7a2e1b3466dedf802208f86a0ce451ad2cc4` includes model routing and Hermes Unlimited integration/test candidates. Neither source tree was run end to end in this addendum. T3 source remains unidentified.
- `nsolland/hermes-unlimited-dev` already merged specialist factory via PR #20, development commit `e74bb336a8269d6a580f2018d393c4faf9b08e9b`. Candidate branch `6f576594535aa403eaa13aa169a8fb91797fddfe` has identical tree content relative to that development commit (`git diff --quiet` exit 0). Duplicate draft PR #23 was closed.
- Acer local suite on that specialist branch with the existing JustYou module on PYTHONPATH: **192 tests passed, 2 skipped** (50.583s), exit 0. Specialist-only suite: **11 passed**, exit 0. Two skipped tests are not proof of production integration.
- One bounded Hermes CLI read-only prompt using Nous Portal model `upstage/solar-mini4:free` returned exactly `VERIFIED`, exit 0. This is **one real model call** but not model comparison, service workflow, external effect or independent customer-outcome verification. Earlier attempts failed on CLI flags; the successful invocation used safe mode and no tool calls.
- The mission runtime's default verifier key and in-process replay cache remain unqualified; a later branch `fix/hermes-preserve-operator-permissions-22` removes implicit `HERMES_YOLO_MODE=1`, but that change was not present in development at the original pinned base.
