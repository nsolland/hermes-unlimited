# Hermes Unlimited — public plugin architecture

## Canonical objective
Enable a provider to create, operate, and sell AI-native companies and services to independent customers through one native Hermes plugin.

## Ownership and boundaries

| Component | Responsibility | Status |
| --- | --- | --- |
| Hermes plugin entrypoint | Register 17 native tools without Hermes core override | Implemented (`__init__.py`, `plugin.yaml`) |
| Provider control plane | Tenant-scoped company, service, request, and mission registry | Implemented (`unlimited/runtime.py`) |
| Company/tenant boundary | Isolate identity, SQLite storage, Kanban boards, costs and results | Implemented (`unlimited/runtime.py`, `unlimited/hermes_kanban.py`) |
| JustYou | Mandatory verified identity + signed profile binding before effects | Implemented (`unlimited/justyou.py`, `unlimited/justyou_host.py`) |
| Autonomous Completion Engine | Decompose business objectives into crew DAGs, recover from failures, checkpoint/resume | Implemented (`unlimited/autonomy.py`) |
| Economic Intelligence & AI Bridge Router | Continuous marginal EV stopping engine + static, dynamic & outcome-driven routing | Implemented (`unlimited/economics.py`) |
| Independent Outcome Verifier | Deterministic deliverable, invariant, and skeptic-gate verification (`independently_verified`) | Implemented (`unlimited/autonomy.py`) |
| Company Memory & Service Factory | Epistemically separated memory (`RECORDED_UNVERIFIED` vs `VERIFIED_OUTCOME`) + blueprint synthesis | Implemented (`unlimited/memory_factory.py`) |
| Socratic Council | Blind multi-lens deliberation preserving dissent with `execution_authority=False` | Implemented (`unlimited/socratic_council.py`, `unlimited/tools.py`) |
| Captain's Bridge A2UI 1.0 | Read-only A2UI 1.0 Basic Catalog surfaces (`companies`, `requests`, `missions`) + loopback bridge | Implemented (`unlimited/a2ui_adapter.py`, `unlimited/a2ui_bridge.py`) |

## Trust and execution
Observation and planning do not grant execution authority. A task receipt records an outcome, not a permit. The runtime must refuse effects if mandatory JustYou binding is absent or invalid. Credentials are requested through the Hermes profile-scoped secret API, not read from token files. Provider and customer tenants never share identities or data by default.

## Required journey / P0
1. Provider installs plugin and binds JustYou securely.
2. Provider creates an isolated company for a customer.
3. Provider configures roles, a service and a price/usage policy.
4. Customer submits a service request.
5. Hermes executes with verified identity and scoped tool access.
6. Provider harvests a real result and evidence, then accounts for usage.

## P1
Optional channel, memory, Captain's Bridge, model routing and external execution adapters; recovery, resume, idempotence and observability.

## P2
Marketplace, multi-provider federation, enterprise governance add-ons, large-scale analytics.

## Proof before release
- Install/validate from a clean public clone on Mac and Acer, using exact commit SHA.
- Unit and integration tests green locally; no GitHub Actions dependency.
- Live scoped provider→company→customer→task→result→usage happy path and negative isolation tests.
- Verify missing/invalid JustYou and missing credentials fail closed.
- Verify no bundled private code, credentials, personal data, hidden dependencies or self-updating behavior.
- Record a demo and publish a pinned catalog entry only after these checks.

## Explicit non-goals
Not a Hermes fork, one bespoke managed company, a replacement identity provider, a mandatory governance suite or a generic background autonomous worker.
