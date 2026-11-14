# Junior Agent Factory — Hermes Unlimited

**Hierarchy:** owner → frontier coordinator (T3/World Commander) → department role → specialist → junior → one tool family. Roles are an organization model, not separate model instances.

## First reference: Gmail Junior

The `unlimited_junior_factory` native Hermes tool supplies `catalog`, `propose`, `evaluate` and `read`. `gmail` is currently a *template*, not an assertion that Google OAuth is connected. Its controlled operations are `list_messages`, `get_message`, `create_draft`, `send_message`, `trash_message`. Only the first two can be invoked by this initial junior runtime. A Gmail junior owns only the Gmail tool family, not Slack, Outlook or a global communications permission.

To create a proposal, use `{"operation":"propose","family":"gmail","selected_operations":["list_messages","get_message"]}`. All proposals return `DRAFT_UNVERIFIED`, `connected=false` and `execution_authorized=false`. Do not infer successful API access from a proposal.

Before `read`, the *trusted Hermes host* must provide `authorize_junior_operation(tenant, identity, tool, operation) -> bool` and `execute_junior_gmail_read(operation, arguments)`. The native plugin verifies JustYou tenant identity first, checks exact operation/arguments, then calls the host only after affirmative authorization. The host is responsible for OAuth credential custody, Gmail account binding, actual Gmail API access and audit logs. If any hook is absent, access is denied. Never pass OAuth tokens, permission flags or Gmail user IDs as agent arguments.

## Other tools

`propose_tool_junior(capability, tenant, objective=...)` accepts a single *discovered* Hermes/MCP capability with an explicitly reviewed effect. Unknown effects fail closed. The result remains a draft until the host independently verifies tool access and permissions. This avoids pre-building separate models or services per integration.

## Model allocation

`evaluate_models()` reuses the existing specialist factory's independent-trial ranking: min 3 distinct verified repetitions per required case (default), pass-rate floor 0.98, mean cost counting failures, and timing. A lower cost model is eligible only if it passes all acceptance checks. Evaluations and proposed model IDs **never** grant execution rights. No real Gmail account or live model comparison is claimed here.

## Required follow-up for customer use

Connect a customer-owned Gmail OAuth account through a Hermes host adapter; verify correct read-only scope and account/tenant isolation; run cases for search, message extraction, malformed input, prompt injection, quota timeout and revocation; collect tool traces and costs; only then enable a customer-facing Junior. Draft/send/trash need separate explicit approval design and are disabled in this first implementation.

## Read-only Gmail transport

`GmailJuniorReadAdapter(authenticated_gmail_service)` wraps a **host-provided authenticated Gmail API service** (such as a Gmail API v1 discovery service). The host may pass the adapter itself as `execute_junior_gmail_read`; the adapter never reads tokens or contacts a provider until the trusted host has already approved `dispatch_read`. Listing is limited to 20 message IDs; message reading exposes only metadata headers and a short snippet, no bodies or attachments. All write operations are rejected. The `userId` is fixed to `me` so the agent cannot choose another mailbox through an argument. This is a transport implementation verified with a fake Gmail API service, **not** an authenticated live Gmail integration.

## Crew-wide catalog and initial junior families

`unlimited_junior_factory(operation="organization")` returns the role hierarchy and public crew groups, covering leadership, coordination, intelligence, production, operations, business/people and assurance. `catalog` now includes Gmail, Outlook, Slack, GitHub and Cloudflare Junior blueprints, each with a specific parent role, one provider/tool family, and explicit operation-level effects. **Only Gmail has an initial read-only transport implementation**; other provider profiles are descriptors awaiting a real Hermes host adapter and tests. Do not interpret their appearance in the catalog as installed connections or agent availability. The orchestration role remains T3/World Commander, with no mandatory always-on frontier model.
