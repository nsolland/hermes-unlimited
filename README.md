![Hermes Unlimited — by REHT](assets/brand/github-banner.svg)

<div align="center">

**All you need to run an AI-native company.**

Create companies. Deploy agents. Deliver services. Grow without limits.

**A REHT Research Group product.**

</div>

<div align="center">
  <img src="assets/brand/hermes-mascot.jpg" alt="Hermes Unlimited character with infinity emblem" width="320" />
  <p><em>Meet the Hermes Unlimited crew.</em></p>
</div>

A native [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin for providers to create and operate AI-native companies and deliver services to their own customers.

**Public Core status: experimental integration, not a production release.**

## What works

- Installable Hermes plugin with seven native tools and no Hermes core override.
- Provider/tenant-scoped company and service registry backed by SQLite.
- Priced service publishing and customer request intake (recorded as queued; not executed).
- JustYou session + signed Hermes profile binding verifier, with no token files bundled.
- Native Hermes Kanban task submission and scoped state reader.
- Fail-closed checks for missing identity, mismatched profile, tenant boundaries and duplicate request IDs.

The native tool handles for company creation, service publishing and requests are functional with a trusted JustYou verifier supplied by the Hermes host.

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

Local green tests remain canonical. Public GitHub Actions independently run
offline unit tests on Python 3.11–3.13 and CodeQL security analysis on pull
requests. CI results are advisory and do not attest to live Hermes dispatch,
customer effects, or production readiness. Dependabot checks action updates.

## Boundary

Hermes owns the worker, channels, scheduler and Kanban execution. JustYou supplies verified identity. Unlimited supplies provider/customer company and service semantics, task routing and result retrieval. Task state is not independent evidence. Company Memory (The Thread), Captain's Bridge, Jackets, Veritas, model routing and commercial optimization are optional integrations and are not bundled here.

See `docs/ARCHITECTURE.md`. The public code is Apache-2.0 licensed; private customer data and separately licensed extensions are not included.

## Visual identity

The GitHub hero is [`assets/brand/github-banner.svg`](assets/brand/github-banner.svg). The official product lockup is [`assets/brand/wordmark.svg`](assets/brand/wordmark.svg). Use [`assets/brand/icon.svg`](assets/brand/icon.svg) for app icons and [`assets/brand/infinity.svg`](assets/brand/infinity.svg) where the standalone infinity mark is needed.

Brand colors: midnight `#0B0F17`, champagne gold `#C9A76A`, and ivory `#F8F9F5`. The product name is **Hermes Unlimited**; the endorsement is **by REHT**. These assets are product branding, not a claim that optional integrations are included in this repository.
