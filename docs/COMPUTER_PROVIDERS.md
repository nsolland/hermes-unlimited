# Computer providers (experimental)

Hermes Unlimited offers one optional, **host-authorized** Python surface for
Orgo, Daytona v2 and Fly Sprites. It does not replace Hermes' terminal backend,
does not issue execution permits, and does not claim task completion.

Code: `unlimited/computer_providers.py`.

| Provider | Supported operations | Unsupported / pending |
| --- | --- | --- |
| Orgo | create, inspect, start, stop | remote exec, screenshot, delete |
| Daytona v2 | create, inspect, exec, delete | desktop streaming, resume parity |
| Fly Sprites | create, exec | explicit stop, inspect, checkpoint |

The provider differences are deliberate. No generic 'run anywhere' claim is made.

## Security and integration

Each provider requires a **trusted host-injected `authorize` callback**, evaluated
for **every** operation: `authorize(tenant=..., provider=..., action=..., resource=...)`.
It must return exactly `True`, and must verify JustYou identity, tenant/resource
ownership and permissions against **trusted persistent host state**. User-supplied
`tenant` strings and provider IDs are not evidence of ownership. A callback
that always returns True is **not** secure or suitable for deployment.
No default callback or autonomous tools registration is provided.

Supply credentials only from trusted profile-scoped host configuration.
Do not include secrets or customer environments in the public repository.
Creation acknowledgments are marked `submitted`, never `completed`.

```python
from unlimited.computer_providers import (
    ComputerProviderRegistry, OrgoComputerProvider,
    DaytonaComputerProvider, SpritesComputerProvider,
)

# authorize MUST be implemented in the trusted JustYou host boundary.
# This is a shape example, not a working authorization implementation.
providers = ComputerProviderRegistry([
    OrgoComputerProvider(authorize=authorize, api_key=orgo_key,
                         workspace_id=workspace_id),
    DaytonaComputerProvider(authorize=authorize, client=daytona_client),
    SpritesComputerProvider(authorize=authorize, client=sprites_client),
])
print(providers.capabilities())
```

SDKs: Daytona official Python v2 SDK (pin to a tested version for deployment);
Fly `sprites-py` official SDK. The Orgo adapter uses Python stdlib HTTPS.
There are no vendored SDK files. Upstream documentation:
- https://docs.orgo.ai/guides/auto-stop
- https://www.daytona.com/docs/python-sdk
- https://fly.io/sprites/

Run offline tests:
`python -m unittest tests.test_computer_providers -v`

**Not production validated:** SDKs are injected and simulated in contract tests.
Requires real-provider smoke tests, external readback, authoritative ownership
storage, durable idempotency, quota controls, cost accounting and host integration.
