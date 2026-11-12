# Hermes Shortcuts mobile intake

Upstream: [sergo565456/hermes-shortcuts](https://github.com/sergo565456/hermes-shortcuts) (MIT).

The upstream Hermes gateway plugin supplies Siri, Share Sheet, QR pairing, HTTPS
bearer authentication, media parsing and reply delivery. The independent
`unlimited.shortcuts_intake` module maps **authenticated** mobile intents to
Hermes Unlimited's existing provider/tenant-scoped Kanban queue. No upstream
code has been copied.

## Wiring requirement

1. Install upstream plugin on the Hermes runtime, bound to loopback behind HTTPS
   and suitable access control. Never use a customer-wide token.
2. Authenticate the phone at the edge and resolve provider, tenant and profile
   from trusted host context, **not** user-supplied fields.
3. Verify the active JustYou session through the host's `scoped_identity()`
   before creating `TrustedMobileScope(provider, tenant, profile, evidence)`.
4. Have the host assign a stable `request_id` for retries. Convert validated
   incoming actions into a bounded dict containing only `request_id`, `action`,
   `text`, `url`, `event`. Binary uploads stay in upstream, not this module.
5. Call `enqueue_shortcut(payload, scope=scope, kanban_factory=HermesKanban)`
   and return its real `task_id` as **queued**, never executed.
6. Read completion through the existing scoped Kanban result reader. Use a
   separate authenticated output-delivery path for mobile notifications.

The adapter refuses client-defined tenant, profile, tools and execution
authority; validates action/event allowlists, HTTPS URL format and UTF-8 size;
and relies on existing scoped Kanban idempotency. The upstream plugin's full
tool profile must not be enabled for unaudited customer content.

## State and proof

Implemented: code-level scoped intake, negative checks, simulated Kanban tests.
Not implemented here: runtime HTTP hook, iPhone QR pairing, The Thread capture,
Telegram return path, binary/media conversion, tenant-specific authentication
at the ingress. These require an actual host integration and live Mac/Acer/iOS
acceptance tests before production deployment.

Local focused tests: `python -m unittest discover -s tests -p 'test_shortcuts_intake.py'`.
