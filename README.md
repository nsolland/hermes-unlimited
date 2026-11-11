# Hermes Unlimited

A native [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin for providers to create and operate AI-native companies and deliver services to their own customers.

**Public Core status: experimental integration, not a production release.**

## What works

- Installable Hermes plugin with seven native tools and no Hermes core override.
- Provider/tenant-scoped company and service registry backed by SQLite.
- Priced service publishing and customer request intake (recorded as queued; not executed).
- JustYou session + signed Hermes profile binding verifier, with no token files bundled.
- Native Hermes Kanban task submission and scoped state reader.
- Fail-closed checks for missing identity, mismatched profile, tenant boundaries and duplicate request IDs.

The native tool handles for company creation, service publishing and requests are functional with a trusted JustYou verifier supplied by the Hermes host. The task adapter uses the real Hermes Kanban CLI but **has not yet passed a live end-to-end dispatch on a production profile**.

## Native tools

- `hermes_unlimited_status`
- `unlimited_company_create`
- `unlimited_company_list`
- `unlimited_service_publish`
- `unlimited_service_request`
- `unlimited_company_task`
- `unlimited_company_result`

## Trusted profile setup

This plugin requires the Hermes host to provide `ctx.justyou_session_store` and `ctx.justyou_resolver` from the canonical JustYou implementation. The plugin cannot create these objects, and refuses execution without them. The Hermes secret scope must provide:

- `HERMES_UNLIMITED_PROVIDER_ID`
- `HERMES_UNLIMITED_TENANT_ID`
- `HERMES_UNLIMITED_JUSTYOU_IDENTITY`
- `HERMES_UNLIMITED_JUSTYOU_SESSION_TOKEN`
- `HERMES_UNLIMITED_REGISTRY_DB`
- Optional `HERMES_UNLIMITED_HERMES_CLI`

The JustYou session token is read only through `agent.secret_scope.get_secret`. Do not put credentials, customer data or keys in the plugin repository.

## Validate

```bash
python3 -m unittest discover -s tests -v
hermes plugins validate . --install-deps
```

Local tests are canonical; this repository deliberately has no GitHub Actions workflow.

## Boundary

Hermes owns the worker, channels, scheduler and Kanban execution. JustYou supplies verified identity. Unlimited supplies provider/customer company and service semantics, task routing and result retrieval. Task state is not independent evidence. Company Memory (The Thread), Captain's Bridge, Jackets, Veritas, model routing and commercial optimization are optional integrations and are not bundled here.

See `docs/ARCHITECTURE.md`. The public code is Apache-2.0 licensed; private customer data and separately licensed extensions are not included.
