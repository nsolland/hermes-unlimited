# T3 Code (optional local CLI adapter)

The optional `unlimited.t3code.T3Code` wrapper runs an **existing, trusted local**
[T3 Code](https://github.com/pingdotgg/t3code) CLI installation. It does not
install T3, modify Hermes core, create external user accounts, or copy T3 code.
Upstream interface: [T3 outside-agent/CLI documentation](https://github.com/pingdotgg/t3code/blob/main/docs/user/outside-agents.md).
License: the wrapper is Apache-2.0 as part of Hermes Unlimited; verify the
upstream T3 license separately before redistribution.

```python
from unlimited.t3code import T3Code
t3 = T3Code(timeout=120)
thread_id = t3.start("trusted_project_id", "Investigate failing tests")
print(t3.show(thread_id))
# Explicitly wait for a follow-up; nonzero exit raises T3CodeError.
print(t3.send(thread_id, "Run focused checks", wait=True))
```

Only a trusted Hermes host may select the T3 environment, project ID, instruction
and worktree. T3 has access to the host filesystem and provider credentials.
Do not expose this wrapper directly to untrusted customers. The caller must
enforce tenant isolation and ownership before each operation. Do not interpret
`start()` as completion; it only returns a thread identifier. `show()` and
`list()` return the CLI's raw text, not a verified completion state. The
`--wait` mode returns the agent reply, not independent evidence of code quality.
No secrets are persisted or logged by this adapter.

Run focused tests: `python -m unittest tests.test_t3code -v`.
Local Acer/Mac installation, provider authentication, real execution, and
Quality Factory result verification remain separate acceptance requirements.
