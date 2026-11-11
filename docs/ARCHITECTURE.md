# Hermes Unlimited — public plugin architecture

## Canonical objective
Enable a provider to create, operate, and sell AI-native companies and services to independent customers through one native Hermes plugin.

## Ownership and boundaries

| Component | Responsibility | Status |
| --- | --- | --- |
| Hermes plugin entrypoint | Register tools, hooks and CLI without core override | Skeleton implemented |
| Provider control plane | Own company templates, catalog and customer lifecycle | Contract only |
| Company/tenant boundary | Isolate identity, storage, roles, costs and results | Contract only |
| JustYou | Mandatory verified identity binding before effects | Interface only |
| Company orchestration | Provision roles, tasks, model routing and lifecycle | Interface only |
| Service catalog and billing | Package, meter and invoice provider services | Interface only |
| Result harvesting | Return outcome and evidence, not a success guess | Interface only |
| Optional adapters | Captain's Bridge, Jackets, Veritas, The Thread, channels and compute | Deferred |

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
