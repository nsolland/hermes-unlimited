"""Shadow-only agent commerce contract: no network, wallet, or real settlement.

Adapters are explicit boundaries, not claims of a deployed REHT, TraXin or x402 integration.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol


@dataclass(frozen=True)
class Purchase:
    tenant_id: str
    company_id: str
    agent_id: str
    intent_id: str
    service_id: str
    provider_id: str
    amount: str
    currency: str = "USD"

    def __post_init__(self):
        if not all((self.tenant_id, self.company_id, self.agent_id, self.intent_id,
                    self.service_id, self.provider_id)):
            raise ValueError("Purchase identifiers are mandatory")
        if self.currency != "USD":
            raise ValueError("Shadow contract supports USD only")
        try:
            value = Decimal(self.amount)
        except (InvalidOperation, TypeError):
            raise ValueError("Invalid amount") from None
        if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2:
            raise ValueError("Amount must be positive USD with at most 2 decimals")


@dataclass(frozen=True)
class Clearance:
    intent_id: str
    tenant_id: str
    company_id: str
    service_id: str
    provider_id: str
    amount: str
    currency: str
    authorized: bool
    permit_ref: str
    # The verifier must attest authority out of band. A receipt is not a permit.


@dataclass(frozen=True)
class Delivery:
    intent_id: str
    accepted: bool
    evidence_ref: str


@dataclass(frozen=True)
class Outcome:
    intent_id: str
    state: str
    permit_ref: str | None = None
    reservation_ref: str | None = None
    evidence_ref: str | None = None
    settlement_ref: str | None = None


class Authority(Protocol):
    def clear(self, purchase: Purchase) -> Clearance: ...


class Payment(Protocol):
    def reserve(self, purchase: Purchase, permit_ref: str) -> str: ...
    def capture(self, reservation_ref: str, evidence_ref: str) -> str: ...
    def release(self, reservation_ref: str) -> None: ...


class Executor(Protocol):
    def execute(self, purchase: Purchase, permit_ref: str) -> Delivery: ...


class CommerceShadow:
    """One-shot, in-memory test harness. Not durable and not production-safe.

    It is deliberately incapable of live payment: callers must supply all adapters.
    """

    def __init__(self, authority: Authority, payment: Payment, executor: Executor):
        self.authority = authority
        self.payment = payment
        self.executor = executor
        self._seen: set[tuple[str, str]] = set()

    def run(self, purchase: Purchase) -> Outcome:
        key = (purchase.tenant_id, purchase.intent_id)
        if key in self._seen:
            return Outcome(purchase.intent_id, "duplicate_denied")
        # Fail closed even if an adapter crashes. Retrying requires a new intent.
        self._seen.add(key)
        try:
            clearance = self.authority.clear(purchase)
        except Exception:
            return Outcome(purchase.intent_id, "authority_error")
        if not self._matches(purchase, clearance):
            return Outcome(purchase.intent_id, "denied")
        try:
            reservation = self.payment.reserve(purchase, clearance.permit_ref)
        except Exception:
            return Outcome(purchase.intent_id, "reservation_error", clearance.permit_ref)
        if not reservation:
            return Outcome(purchase.intent_id, "reservation_error", clearance.permit_ref)
        try:
            delivery = self.executor.execute(purchase, clearance.permit_ref)
            if (delivery.intent_id != purchase.intent_id or
                    not delivery.accepted or not delivery.evidence_ref):
                self.payment.release(reservation)
                return Outcome(purchase.intent_id, "delivery_rejected",
                               clearance.permit_ref, reservation)
        except Exception:
            try:
                self.payment.release(reservation)
            except Exception:
                return Outcome(purchase.intent_id, "manual_reconciliation_required",
                               clearance.permit_ref, reservation)
            return Outcome(purchase.intent_id, "failed_released",
                           clearance.permit_ref, reservation)
        # A capture timeout may mean funds moved. Never automatically release or
        # retry an ambiguous capture; require independent reconciliation.
        try:
            settlement = self.payment.capture(reservation, delivery.evidence_ref)
        except Exception:
            return Outcome(purchase.intent_id, "manual_reconciliation_required",
                           clearance.permit_ref, reservation, delivery.evidence_ref)
        if not settlement:
            return Outcome(purchase.intent_id, "manual_reconciliation_required",
                           clearance.permit_ref, reservation, delivery.evidence_ref)
        return Outcome(purchase.intent_id, "settled_shadow", clearance.permit_ref,
                       reservation, delivery.evidence_ref, settlement)

    @staticmethod
    def _matches(p: Purchase, c: Clearance) -> bool:
        return bool(
            c.authorized and c.permit_ref and
            c.intent_id == p.intent_id and c.tenant_id == p.tenant_id and
            c.company_id == p.company_id and c.service_id == p.service_id and
            c.provider_id == p.provider_id and c.currency == p.currency and
            c.amount == p.amount
        )
