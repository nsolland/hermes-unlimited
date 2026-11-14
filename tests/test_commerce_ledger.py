"""Synthetic end-to-end commerce simulation, including crash ambiguity."""
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from commerce.authority import Approval, PurchaseDenied, PurchaseIntent
from commerce.ledger import MockPaymentAdapter, PaymentResult, PurchaseLedger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "commerce.sqlite")
        self.ledger = PurchaseLedger(self.path)
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.intent = PurchaseIntent("tenant-a", "req-1", "merchant-a", "USD", "20.00", (("sku-1", 2),))
        self.approval = Approval("tenant-a", "req-1", self.intent.digest(), "20.00", "USD", self.now + timedelta(minutes=5), True)
        self.adapter = MockPaymentAdapter()

    def test_synthetic_confirmed_and_replay_and_restart(self):
        actual = self.ledger.submit(self.intent, self.approval, self.adapter, now=self.now)
        self.assertEqual(actual.state, "CONFIRMED")
        self.assertEqual(len(self.adapter.calls), 1)
        again = PurchaseLedger(self.path).submit(self.intent, self.approval, self.adapter, now=self.now)
        self.assertEqual(again, actual)
        self.assertEqual(len(self.adapter.calls), 1)

    def test_denied_before_adapter_call(self):
        with self.assertRaises(PurchaseDenied):
            self.ledger.submit(self.intent, None, self.adapter, now=self.now)
        self.assertFalse(self.adapter.calls)

    def test_mutated_cart_rejected_and_no_second_charge(self):
        self.ledger.submit(self.intent, self.approval, self.adapter, now=self.now)
        changed = replace(self.intent, items=(("sku-2", 2),))
        changed_approval = replace(self.approval, intent_digest=changed.digest())
        with self.assertRaises(PurchaseDenied):
            self.ledger.submit(changed, changed_approval, self.adapter, now=self.now)
        self.assertEqual(len(self.adapter.calls), 1)

    def test_unknown_state_must_not_resubmit(self):
        class Interrupted:
            def __init__(self):
                self.calls = 0

            def submit(self, intent, idempotency_key):
                self.calls += 1
                raise ConnectionError("lost response after PSP submission")

        provider = Interrupted()
        first = self.ledger.submit(self.intent, self.approval, provider, now=self.now)
        second = PurchaseLedger(self.path).submit(self.intent, self.approval, provider, now=self.now)
        self.assertEqual(first.state, "UNKNOWN")
        self.assertEqual(second.state, "UNKNOWN")
        self.assertEqual(provider.calls, 1)

    def test_reconcile_unknown_after_independent_verification(self):
        class Uncertain:
            def submit(self, intent, idempotency_key):
                return PaymentResult("", "UNKNOWN")

        self.ledger.submit(self.intent, self.approval, Uncertain(), now=self.now)
        self.ledger.reconcile("tenant-a", "req-1", self.intent.digest(), "verified-external-ref")
        outcome = PurchaseLedger(self.path).submit(self.intent, self.approval, self.adapter, now=self.now)
        self.assertEqual(outcome.provider_reference, "verified-external-ref")
        self.assertFalse(self.adapter.calls)


if __name__ == "__main__":
    unittest.main()
