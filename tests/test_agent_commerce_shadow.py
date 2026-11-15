"""Offline acceptance tests. Every adapter is a fake; no funds can move."""
import unittest

from unlimited.agent_commerce_shadow import (
    Purchase, Clearance, Delivery, CommerceShadow,
)


def purchase(**changes):
    data = dict(tenant_id="tenant-a", company_id="company-a", agent_id="agent-a",
                intent_id="intent-001", service_id="api-call", provider_id="seller-b",
                amount="0.20", currency="USD")
    data.update(changes)
    return Purchase(**data)


class FakeAuthority:
    def __init__(self, approved=True, overrides=None):
        self.approved = approved
        self.overrides = overrides or {}

    def clear(self, p):
        data = dict(intent_id=p.intent_id, tenant_id=p.tenant_id,
                    company_id=p.company_id, service_id=p.service_id,
                    provider_id=p.provider_id, amount=p.amount, currency=p.currency,
                    authorized=self.approved, permit_ref="permit-test-001")
        data.update(self.overrides)
        return Clearance(**data)


class FakePayment:
    def __init__(self):
        self.calls = []
        self.fail_capture = False
        self.fail_release = False

    def reserve(self, p, permit):
        self.calls.append(("reserve", p.intent_id, permit))
        return "reservation-test-001"

    def capture(self, reservation, evidence):
        self.calls.append(("capture", reservation, evidence))
        if self.fail_capture:
            raise RuntimeError("capture failed")
        return "settlement-test-001"

    def release(self, reservation):
        self.calls.append(("release", reservation))
        if self.fail_release:
            raise RuntimeError("release failed")


class FakeExecutor:
    def __init__(self, accepted=True, evidence="sha256:test", intent="intent-001"):
        self.accepted, self.evidence, self.intent = accepted, evidence, intent
        self.calls = []

    def execute(self, p, permit):
        self.calls.append((p.intent_id, permit))
        return Delivery(self.intent, self.accepted, self.evidence)


class ShadowAcceptance(unittest.TestCase):
    def test_verified_service_purchase(self):
        payment = FakePayment()
        executor = FakeExecutor()
        flow = CommerceShadow(FakeAuthority(), payment, executor)
        result = flow.run(purchase())
        self.assertEqual(result.state, "settled_shadow")
        self.assertEqual(result.evidence_ref, "sha256:test")
        self.assertEqual([c[0] for c in payment.calls], ["reserve", "capture"])
        self.assertEqual(len(executor.calls), 1)

    def test_denial_blocks_reservation_and_execution(self):
        payment, executor = FakePayment(), FakeExecutor()
        result = CommerceShadow(FakeAuthority(False), payment, executor).run(purchase())
        self.assertEqual(result.state, "denied")
        self.assertFalse(payment.calls)
        self.assertFalse(executor.calls)

    def test_cross_tenant_or_amount_permit_rejected(self):
        for mismatched in ({"tenant_id": "tenant-b"}, {"amount": "0.21"},
                           {"provider_id": "seller-c"}, {"intent_id": "other"}):
            with self.subTest(mismatched=mismatched):
                payment = FakePayment()
                result = CommerceShadow(FakeAuthority(overrides=mismatched),
                                        payment, FakeExecutor()).run(purchase())
                self.assertEqual(result.state, "denied")
                self.assertFalse(payment.calls)

    def test_bad_delivery_releases_reservation(self):
        payment = FakePayment()
        result = CommerceShadow(FakeAuthority(), payment,
                                FakeExecutor(accepted=False)).run(purchase())
        self.assertEqual(result.state, "delivery_rejected")
        self.assertEqual([c[0] for c in payment.calls], ["reserve", "release"])

    def test_duplicate_intent_does_not_pay_twice(self):
        payment = FakePayment()
        flow = CommerceShadow(FakeAuthority(), payment, FakeExecutor())
        self.assertEqual(flow.run(purchase()).state, "settled_shadow")
        self.assertEqual(flow.run(purchase()).state, "duplicate_denied")
        self.assertEqual([c[0] for c in payment.calls], ["reserve", "capture"])

    def test_release_failure_does_not_claim_success(self):
        payment = FakePayment()
        payment.fail_capture = True
        payment.fail_release = True
        result = CommerceShadow(FakeAuthority(), payment, FakeExecutor()).run(purchase())
        self.assertEqual(result.state, "manual_reconciliation_required")

    def test_invalid_amounts_rejected(self):
        for amount in ("0", "-1", "NaN", "Infinity", "0.001", "abc"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                purchase(amount=amount)


if __name__ == "__main__":
    unittest.main()
