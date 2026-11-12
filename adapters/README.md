# Adapter lifecycle

The Hermes Unlimited core is dependency-isolated. Adapter metadata does not load adapter code or grant permissions.

States: `proposed` → `evaluation` → `verified` → `approved` → `deprecated` / `revoked`. `verified` means tests passed for an exact version and SHA; `approved` additionally requires an explicit maintainer decision. `revoked` cannot be used in production.

Origins: `internal`, `external-integration`. Both use the same evidence standard. Unreviewed external contributions start as `proposed`.

An approval must bind adapter ID, immutable source SHA, exact version, upstream compatibility, license, test evidence, security review, allowed capabilities, and an accountable reviewer. Runtime must reject any adapter not in an approved, pinned allowlist. This catalog is discovery metadata only, not that allowlist.

Contributors: submit an issue with a use case and compatibility target, then a PR containing isolated adapter code, mock-based contract tests, installation instructions, license and dependency inventory, negative security tests, and a reproducible local test command. Reviewers can tune and benchmark proposals in the evaluation area without altering core or competition releases. No automatic promotion or deployment.

Optional media tests: `python -m unittest discover -s tests_optional_media -v` (requires FFmpeg for full integration coverage). Core tests: `python -m unittest discover -s tests -q` (no FFmpeg requirement).

Approval additionally requires `checks` with `unit`, `contract`, `security`, and `integration` all `passed`, plus `tested_sha256` and `tested_version` matching the pinned source and version. Failed, pending, missing or stale evidence blocks loading immediately when the host updates its approval manifest. No CI status is inferred from a catalog entry. CI-to-host revocation synchronization is not implemented; a previously issued approval must not be assumed automatically revoked merely because a remote CI run fails.
