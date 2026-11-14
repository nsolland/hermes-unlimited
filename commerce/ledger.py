"""Durable no-double-submit commerce orchestrator.

This module is deliberately disconnected from live payment rails. An interrupted
submission is UNKNOWN and requires reconciliation, never an automatic retry.
"""
import sqlite3
from dataclasses import dataclass
from typing import Protocol

from commerce.authority import Approval, PurchaseDenied, PurchaseIntent, clear_purchase


@dataclass(frozen=True)
class PaymentResult:
    provider_reference: str
    state: str  # CONFIRMED or UNKNOWN


class PaymentAdapter(Protocol):
    def submit(self, intent: PurchaseIntent, idempotency_key: str) -> PaymentResult: ...


class MockPaymentAdapter:
    """Synthetic merchant. Never communicates externally."""
    def __init__(self):
        self.calls = []

    def submit(self, intent: PurchaseIntent, idempotency_key: str) -> PaymentResult:
        self.calls.append(idempotency_key)
        return PaymentResult("synthetic:" + idempotency_key, "CONFIRMED")


class PurchaseLedger:
    def __init__(self, path: str):
        self.path = path
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS purchase_ledger (
                tenant TEXT NOT NULL, request_id TEXT NOT NULL,
                intent_digest TEXT NOT NULL, state TEXT NOT NULL,
                provider_reference TEXT,
                PRIMARY KEY(tenant, request_id)
            )""")

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def submit(self, intent: PurchaseIntent, approval: Approval | None, adapter: PaymentAdapter, *, now=None) -> PaymentResult:
        digest = clear_purchase(intent, approval, now=now)
        key = intent.tenant + ":" + intent.request_id
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT intent_digest, state, provider_reference FROM purchase_ledger WHERE tenant=? AND request_id=?",
                (intent.tenant, intent.request_id),
            ).fetchone()
            if existing:
                if existing[0] != digest:
                    raise PurchaseDenied("request id used for different intent")
                if existing[1] == "CONFIRMED":
                    return PaymentResult(existing[2], "CONFIRMED")
                # Submission may have reached PSP before crash: do not resubmit.
                return PaymentResult(existing[2] or "", "UNKNOWN")
            db.execute(
                "INSERT INTO purchase_ledger(tenant,request_id,intent_digest,state) VALUES(?,?,?,?)",
                (intent.tenant, intent.request_id, digest, "SUBMITTING"),
            )
            db.commit()
        try:
            result = adapter.submit(intent, key)
        except Exception:
            # The provider may have received a payment. State remains uncertain.
            return PaymentResult("", "UNKNOWN")
        if result.state != "CONFIRMED" or not result.provider_reference:
            return PaymentResult(result.provider_reference, "UNKNOWN")
        with self._connect() as db:
            db.execute(
                "UPDATE purchase_ledger SET state='CONFIRMED',provider_reference=? WHERE tenant=? AND request_id=? AND intent_digest=? AND state='SUBMITTING'",
                (result.provider_reference, intent.tenant, intent.request_id, digest),
            )
        return result

    def reconcile(self, tenant: str, request_id: str, intent_digest: str, provider_reference: str):
        """Store externally verified payment reference; caller must independently verify PSP status."""
        if not provider_reference:
            raise PurchaseDenied("missing verified reference")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT intent_digest,state FROM purchase_ledger WHERE tenant=? AND request_id=?",
                (tenant, request_id),
            ).fetchone()
            if row is None or row[0] != intent_digest:
                raise PurchaseDenied("unrecognized transaction")
            db.execute("UPDATE purchase_ledger SET state='CONFIRMED', provider_reference=? WHERE tenant=? AND request_id=?",
                       (provider_reference, tenant, request_id))
            db.commit()
