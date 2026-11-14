"""Deterministic purchase clearance; no payment credential handling.

Standalone boundary prototype, not a payment processor or REHT permit.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256


class PurchaseDenied(ValueError):
    pass


@dataclass(frozen=True)
class PurchaseIntent:
    tenant: str
    request_id: str
    merchant: str
    currency: str
    amount: str
    items: tuple[tuple[str, int], ...]

    def digest(self) -> str:
        payload = {
            "tenant": self.tenant, "request_id": self.request_id,
            "merchant": self.merchant, "currency": self.currency,
            "amount": self.amount, "items": self.items,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Approval:
    tenant: str
    request_id: str
    intent_digest: str
    max_amount: str
    currency: str
    expires_at: datetime
    approved: bool


def clear_purchase(intent: PurchaseIntent, approval: Approval | None, *, now: datetime | None = None) -> str:
    """Return bound intent digest or fail closed; never executes a payment."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise PurchaseDenied("naive clock")
    if not intent.tenant or not intent.request_id or not intent.merchant:
        raise PurchaseDenied("incomplete identity")
    if not intent.items or any(not sku or type(qty) is not int or qty <= 0 for sku, qty in intent.items):
        raise PurchaseDenied("invalid items")
    if not intent.currency or len(intent.currency) != 3 or not intent.currency.isalpha() or not intent.currency.isupper():
        raise PurchaseDenied("invalid currency")
    if approval is None or not approval.approved:
        raise PurchaseDenied("no approval")
    if approval.expires_at.tzinfo is None or now >= approval.expires_at:
        raise PurchaseDenied("approval expired")
    if intent.tenant != approval.tenant or intent.request_id != approval.request_id:
        raise PurchaseDenied("wrong approval scope")
    if intent.currency != approval.currency or intent.digest() != approval.intent_digest:
        raise PurchaseDenied("changed purchase")
    try:
        amount, cap = Decimal(intent.amount), Decimal(approval.max_amount)
    except (InvalidOperation, ValueError):
        raise PurchaseDenied("invalid amount") from None
    if not amount.is_finite() or not cap.is_finite() or amount <= 0 or cap <= 0 or amount > cap:
        raise PurchaseDenied("out of budget")
    return intent.digest()
