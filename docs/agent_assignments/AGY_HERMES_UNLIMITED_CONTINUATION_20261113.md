# AGY — Hermes Unlimited continuation mandate
Date: 2026-11-13
Repo: nsolland/hermes-unlimited (private development)
Worktree: /home/njaal/hermes-unlimited-agy-autonomous-20261112
Branch: feat/autonomous-company-engine-20261112
Base: 921c779d84ba9d04bdb5fc4a21979e20c1de3d24
Owner: nsolland
Public release: NOT AUTHORIZED.

## Primary objective
Build and verify Hermes Unlimited as an operating system for AI-native companies: a single owner can establish, operate, grow and continuously improve a business through a specialized autonomous agent organization. Never treat a successful subtask as completion of the primary objective.

## Product contract
Captain's Bridge: Company, Crew, Mission Control, Communications, AI Bridge, Toolshed/Jackets, Memory, Operations, Business.
P0: Goal Fidelity, Company Memory, ACE (autonomous company engine).
P1: Completion Engine, Business Economics, Service Factory.
Mandatory JustYou identity. Optional customer-selected Jackets, Veritas, governance modules. Customer chooses local/cloud/Hermes models and machines, capacity, costs and risk.
No critical workflow depends on one vendor/model. Measured outcomes and real costs, not self-asserted ROI.
Agents must discover opportunities, research, propose, plan, execute, verify, learn, and recommend whether the next unit of spend is justified.
Communications: email, phone, messaging, meetings. Business: customers, offers, sales, delivery, billing. Multi-machine isolated workers with recoverable operations. Modular approved adapters; never label untested adapters approved.

## Immediate execution — do not skip
1. Inspect current worktree and preserve all existing uncommitted changes. Do not reset or overwrite.
2. The initial live crash (tuple catalog passed to dict()) was repaired in unlimited/hermes_live_worker.py with normalize_catalog. Targeted tests: 13 passed. Full offline: 92 passed, 1 skipped, 24 subtests.
3. The next live run reached objective 2 but stopped at INDEPENDENT_VERIFICATION_REQUIRED in ServiceFactory. Diagnostic guard LIVE_OBJECTIVE_2_NOT_VERIFIED was added to unlimited/live_acceptance.py. Inspect the actual receipt, step statuses, critic outcome, source artifacts, economic gates, and checkpoint/resume. Do NOT forge, bypass, downgrade or self-certify verification.
4. Add focused regression tests for catalog normalization (tuple, mapping, empty, duplicates, malformed profiles), checkpoint/resume and verification failures. Fix real defects, rerun full offline suite.
5. Run bounded live acceptance in an authorized network environment. Capture three objectives, provider failover, critic evidence, resume/idempotency, measured costs and file artifacts. Bound spend and time; avoid unnecessary repeat calls.
6. Make outcome verifier independent of worker's ability to mint approval: define separate signing authority and key custody, reject invalid or replayed receipts, bind to deliverable digest, tenant, objective and policy. Document residual trust limitations.
7. Complete next vertical slices: Goal Fidelity + Completion Engine; persistent Company Memory and Service Factory; Business Economics/CAVO (true total cost, human supervision, correction, marginal ROI); AI Bridge model/provider fallback; owner-visible Mission Control. Verify each with realistic end-to-end tests.
8. Add explicit acceptance criteria, negative tests, reproducible evidence and clear product readiness status. Keep main untouched. Commit and push only private branch after tests. Open/update private PR; do not merge or publish without passing requirements.

## Definition of done
A reproducible live end-to-end run demonstrates objective -> planning -> bounded real execution -> independent verification -> measured economics -> durable memory -> reusable service -> owner-facing status, including failure/recovery. Tests pass locally. Any missing capability remains explicitly marked incomplete. Do not claim production-ready from green unit tests alone.
