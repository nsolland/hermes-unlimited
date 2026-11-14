"""Permission inventory and audit for Hermes-internal CLI / OAuth / API connections.

Scope of this bounded module (bounded by issue #22):

1. Inventory actual, permitted CLI / OAuth / API connections through the native
   Hermes Agent runtime; no credential scraping and no assumption that consumer
   subscriptions grant API rights.
2. Audit HERMES_YOLO_MODE and provider catalog aliases before live use.
3. Return structured results (inventory, audit, warnings) without side effects.

This module is pure read-only: it never creates connections, never writes files,
and never makes network calls.  It is a source-and-environment audit only.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field

# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PermissionEntry:
    """One read-only entry in the CLI / OAuth / API inventory."""

    namespace: str
    key: str
    source: str  # "env", "code", or "doc"
    value: str
    permitted: bool  # True when the key is an allowlisted/expected Hermes namespace


@dataclass(frozen=True)
class AuditResult:
    """Outcome of auditing HERMES_YOLO_MODE and provider catalog aliases."""

    hermes_yolo_mode: bool
    hermes_yolo_explicitly_set: bool
    provider_aliases: list[str]
    catalog_entries: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Allowlisted namespace prefixes that are considered "permitted" for this repo.
# ---------------------------------------------------------------------------

_PERMITTED_PREFIXES = (
    "HERMES_",
    "OPENAI_",
    "ANTHROPIC_",
    "GOOGLE_",
    "ALIBABA_",
)

# Regex for model catalog alias entries (provider / runtime model pairs).
_MODEL_ALIAS_RE = re.compile(r"^[A-Za-z0-9.-]+/[A-Za-z0-9._-]+$")


def _is_permitted_key(key: str) -> bool:
    """Return True when *key* belongs to a permittable Hermes / cloud namespace."""
    return any(key.startswith(p) for p in _PERMITTED_PREFIXES)


def inventory_permission_entries() -> list[PermissionEntry]:
    """Return the read-only inventory of permitted CLI / OAuth / API connections
    from the current environment plus a static allowlist of documented keys."""
    entries: list[PermissionEntry] = []

    # 1. Environment scan (read-only, no network).
    for key, value in os.environ.items():
        if _is_permitted_key(key):
            entries.append(
                PermissionEntry(
                    namespace=key.split("_", 1)[0],
                    key=key,
                    source="env",
                    value=value,
                    permitted=True,
                )
            )

    # 2. Static documented allowlist (no secrets are persisted here).
    #    Order matters: "code" entries document the intended interface.
    code_allowlist = [
        ("HERMES", "HERMES_ACCEPT_HOOKS", "1"),
        ("HERMES", "HERMES_DISABLE_LAZY_INSTALLS", "1"),
        ("HERMES", "HERMES_SINGLE_QUERY_SESSION", "1"),
        ("HERMES", "HERMES_API_TIMEOUT", "unbounded"),
        ("HERMES", "HERMES_API_CALL_STALE_TIMEOUT", "unbounded"),
        ("HERMES", "HERMES_UNLIMITED_EXCLUDE_PROVIDERS", ""),
        ("HERMES", "HERMES_LIVE_ACCEPTANCE_PROVIDERS", ""),
        ("HERMES", "HERMES_UNLIMITED_JUSTYOU_REGISTRY_URL", "opaque"),
        ("HERMES", "HERMES_UNLIMITED_JUSTYOU_SESSION_TOKEN", "opaque"),
        ("OPENAI", "OPENAI_API_KEY", "opaque"),
        ("ANTHROPIC", "ANTHROPIC_API_KEY", "opaque"),
        ("GOOGLE", "GOOGLE_API_KEY", "opaque"),
        ("ALIBABA", "ALIBABA_API_KEY", "opaque"),
    ]
    for ns, key, val in code_allowlist:
        entries.append(
            PermissionEntry(
                namespace=ns,
                key=key,
                source="code",
                value=val,
                permitted=True,
            )
        )

    return entries


def audit_hermes_yolo_mode() -> AuditResult:
    """Audit HERMES_YOLO_MODE and provider catalog aliases in the current
    environment and in the base source tree of this repository."""
    hermes_yolo_explicitly_set = "HERMES_YOLO_MODE" in os.environ
    hermes_yolo_mode = os.environ.get("HERMES_YOLO_MODE", "") != ""

    # Read provider catalog aliases from the local economics/economics.py module
    # (bounded: only read the module source, do not import it to avoid side
    # effects).  Fall back to an empty list if the file cannot be read.
    provider_aliases: list[str] = []
    warnings: list[str] = []
    try:
        import pathlib

        path = pathlib.Path(__file__).resolve().parent / "economics.py"
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if "model_id" in stripped and "=" in stripped:
                parts = stripped.split("=", 1)
                model_id = parts[0].strip().rstrip(":")
                if _MODEL_ALIAS_RE.match(model_id):
                    provider_aliases.append(model_id)
    except OSError as exc:
        warnings.append(f"could not scan economics.py: {exc}")

    return AuditResult(
        hermes_yolo_mode=hermes_yolo_mode,
        hermes_yolo_explicitly_set=hermes_yolo_explicitly_set,
        provider_aliases=provider_aliases,
        catalog_entries=len(provider_aliases),
        warnings=warnings,
    )
