"""Subscription-first assignment to existing Hermes Kanban profiles.

This is a business-level profile preference, not a model router, provider
credential reader, authority grant, or replacement for Hermes fallback.
Only trusted owner configuration may supply the bindings.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, Mapping, Sequence

from .hermes_kanban import HermesKanban, ROLE_ID

BillingSource = Literal["customer_owned", "hermes_paid"]


@dataclass(frozen=True)
class ProfileCapacity:
    tenant_id: str
    profile: str
    billing_source: BillingSource
    task_kinds: tuple[str, ...]
    expected_quality: float
    marginal_cost_minor: int
    available: bool = True
    permitted: bool = True
    quota_remaining: int = 1

    def __post_init__(self) -> None:
        if (not isinstance(self.tenant_id, str) or not isinstance(self.profile, str)
                or not ROLE_ID.fullmatch(self.tenant_id)
                or not ROLE_ID.fullmatch(self.profile)):
            raise ValueError("INVALID_PROFILE_SCOPE")
        if self.billing_source not in ("customer_owned", "hermes_paid"):
            raise ValueError("INVALID_BILLING_SOURCE")
        if (not self.task_kinds or any(
                not isinstance(kind, str) or not kind.strip()
                for kind in self.task_kinds)):
            raise ValueError("TASK_CAPABILITIES_REQUIRED")
        if (type(self.expected_quality) not in (int, float)
                or not isfinite(self.expected_quality)
                or not 0 <= self.expected_quality <= 1):
            raise ValueError("PROFILE_QUALITY_INVALID")
        if type(self.marginal_cost_minor) is not int or self.marginal_cost_minor < 0:
            raise ValueError("PROFILE_COST_INVALID")
        if type(self.quota_remaining) is not int or self.quota_remaining < 0:
            raise ValueError("PROFILE_QUOTA_INVALID")


def choose_hermes_profile(
    profiles: Sequence[ProfileCapacity],
    *,
    tenant_id: str,
    task_kind: str,
    min_quality: float,
    max_marginal_cost_minor: int,
    allow_paid_fallback: bool = False,
) -> ProfileCapacity:
    """Choose among already-approved Hermes profiles, preferring customer-owned.

    No credentials, OAuth token or subscription availability is inferred here.
    A trusted host must have validated each configured profile before selection.
    """
    if not isinstance(tenant_id, str) or not ROLE_ID.fullmatch(tenant_id) or not isinstance(task_kind, str) or not task_kind.strip():
        raise ValueError("PROFILE_REQUEST_INVALID")
    if (type(min_quality) not in (int, float) or not isfinite(min_quality)
            or not 0 <= min_quality <= 1):
        raise ValueError("MIN_QUALITY_INVALID")
    if type(max_marginal_cost_minor) is not int or max_marginal_cost_minor < 0:
        raise ValueError("MAX_COST_INVALID")
    if type(allow_paid_fallback) is not bool:
        raise ValueError("PAID_FALLBACK_FLAG_INVALID")
    seen = set()
    eligible = []
    for item in profiles:
        if not isinstance(item, ProfileCapacity):
            raise TypeError("TRUSTED_PROFILE_CAPACITY_REQUIRED")
        key = (item.tenant_id, item.profile)
        if key in seen:
            raise ValueError("DUPLICATE_PROFILE_BINDING")
        seen.add(key)
        if (item.tenant_id != tenant_id or not item.available or not item.permitted
                or item.quota_remaining <= 0 or task_kind not in item.task_kinds
                or item.expected_quality < min_quality
                or item.marginal_cost_minor > max_marginal_cost_minor
                or (item.billing_source == "hermes_paid" and not allow_paid_fallback)):
            continue
        eligible.append(item)
    if not eligible:
        raise LookupError("NO_ELIGIBLE_AUTHORIZED_HERMES_PROFILE")
    return min(eligible, key=lambda p: (
        p.billing_source != "customer_owned",
        p.marginal_cost_minor,
        -p.expected_quality,
        p.profile,
    ))


def enqueue_subscription_first(
    kanban: HermesKanban,
    *,
    profiles: Sequence[ProfileCapacity],
    identity_evidence_by_profile: Mapping[str, dict],
    tenant_id: str,
    task_kind: str,
    min_quality: float,
    max_marginal_cost_minor: int,
    task_id: str,
    title: str,
    body: str,
    allow_paid_fallback: bool = False,
) -> dict:
    """Dispatch through Hermes's existing native Kanban/JustYou boundary.

    The trusted host provides profile-scoped JustYou evidence; absence or
    mismatch fails closed and never triggers a switch to a paid profile.
    A queued task is NOT an independently verified or completed outcome.
    """
    selected = choose_hermes_profile(
        profiles, tenant_id=tenant_id, task_kind=task_kind,
        min_quality=min_quality, max_marginal_cost_minor=max_marginal_cost_minor,
        allow_paid_fallback=allow_paid_fallback,
    )
    evidence = identity_evidence_by_profile.get(selected.profile)
    if not isinstance(evidence, dict) or evidence.get("profile") != selected.profile:
        raise PermissionError("SELECTED_HERMES_PROFILE_IDENTITY_NOT_VERIFIED")
    result = kanban.enqueue(
        tenant=tenant_id, assignee=selected.profile, task_id=task_id,
        title=title, body=body, identity_evidence=evidence,
    )
    return {**result, "billing_source": selected.billing_source,
            "selected_profile": selected.profile,
            "marginal_cost_minor_estimate": selected.marginal_cost_minor}
