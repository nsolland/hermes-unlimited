# AGY next execution mandate — Hermes Unlimited DEV
Date: 2026-11-13
Canonical repository: nsolland/hermes-unlimited-dev (PRIVATE)
Current integration PR: #6, branch feat/agy-autonomous-company-20261113
DO NOT publish to transitional public nsolland/hermes-unlimited or rrglab without a verified release gate.

## What was actually delivered
- Autonomous Company OS: charter, goal fidelity, six governing questions, CAVO opportunity allocator, product readiness matrix.
- Mission engine: planning, execution, retries, checkpoint/resume, SQLite idempotency, multi-provider live worker.
- Quality: step-level output validation, independent critic with provider failover, separate signing authority with scope binding and replay checks.
- Captain's Bridge: readiness view, unlimited_company_cycle native tool.
- Verified offline on Acer; full live acceptance still not passed. Nous/Alibaba-only live attempt ongoing.

## Next primary objective
Demonstrate one real, bounded, repeatable company operation in which a user goal produces an independently verified result, measured economics, durable company memory, a reusable service, and owner-visible status. Do not substitute offline tests or generated prose for real outcomes.

## Execute in order
1. Finish live acceptance using available Nous and Alibaba providers; keep cross-provider critic and independent signing. Record exact provider/model, step receipts, file digests, latency, token and USD costs. Investigate SLA and runtime hangs. Do not inflate SLA simply to make tests pass; choose realistic per-step deadlines, bounded retries, backoff, and genuine failover. Skip unavailable Gemini without weakening validation.
2. Repair actual failures, add negative regression tests, run full local suite. Keep DEV changes in private feature branch, push and update PR #6. No public release.
3. Build the smallest real Company Engine vertical slice: owner-defined company/charter -> opportunity triage -> authorized goal -> Crew assignment -> tools execution -> independent verification -> CAVO marginal ROI decision -> durable memory -> service blueprint -> Captain's Bridge outcome.
4. Make completion semantics explicit: no self-certified success; distinguish produced artifact, verified artifact, actual external effect and measured business result. Preserve stop/retry/human escalation.
5. Make multi-machine workers and model/provider fallback resilient to process restart, no single Acer gateway dependency. Test recovery with deliberate interruption.
6. Implement adapter registry with CORE, VERIFIED, EXPERIMENTAL; only independently tested adapters eligible for release. Keep JustYou mandatory, other jackets optional. Add per-tenant scopes.
7. Build integration tests for at least one actual customer communication + service delivery path with authorization; no real outbound emails or payments without explicit authority.
8. Produce reproducible evidence and a truthful readiness matrix for all 15 areas. Verify cost of human supervision and marginal value of next spend.
9. Commit/push only private DEV; keep PR draft until acceptance and security review. Never merge experimental work into public nsolland or rrglab.

## Acceptance
Green offline suite plus real live end-to-end evidence across all 3 acceptance objectives, including checkpoint/resume, critic failover and injected adversarial failure. Actual external effects must be separately authorized and verified. Report precise blockers, not blanket success.
