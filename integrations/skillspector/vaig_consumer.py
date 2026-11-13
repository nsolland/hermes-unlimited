"""Hermes consumer of VAIG component-risk signals (never a scanner/authorizer).

A trusted transport must authenticate the VAIG emitter independently; callers
must not accept a 'trusted' flag from untrusted skill metadata or agent text.
"""
from dataclasses import dataclass
from typing import Mapping
import re

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ComponentReview:
    state: str
    reason: str
    installation_approved: bool = False
    execution_authorized: bool = False


def review_vaig_component(
    signal: Mapping[str, object],
    *,
    expected_source_digest: str,
    trusted_vaig_origin: bool = False,
) -> ComponentReview:
    """Return review eligibility, not an installation permission."""
    if not isinstance(expected_source_digest, str) or not _DIGEST.fullmatch(expected_source_digest):
        raise ValueError("expected_source_digest must be a full sha256 hex digest")
    if not trusted_vaig_origin or not isinstance(signal, Mapping):
        return ComponentReview("UNVERIFIED", "VAIG_origin_unverified")
    if (
        signal.get("source_digest_sha256") != expected_source_digest
        or signal.get("execution_authority") is not False
        or signal.get("installation_approval") is not False
        or signal.get("requires_reht_clearance") is not True
    ):
        return ComponentReview("BLOCKED", "VAIG_binding_or_authority_invalid")
    if signal.get("state") == "REVIEW_ELIGIBLE":
        return ComponentReview("REVIEW_REQUIRED", "assessment_not_approval")
    return ComponentReview("BLOCKED", "VAIG_risk_signal_not_eligible")
