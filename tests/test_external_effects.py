import unittest
from unittest.mock import Mock
from unlimited.external_effects import SMTPDeliveryAdapter, StripePaymentAdapter, verify_stripe_webhook


class ExternalEffectTests(unittest.TestCase):
    def setUp(self):
        self.verify = lambda tenant, identity: (tenant, identity) == ("tenant-a", "captain")
        self.approve = lambda tenant, identity, effect: effect == "effect-1"
        self.scope = dict(tenant_id="tenant-a", identity="captain", effect_id="effect-1",
                          verify_identity=self.verify, approve_effect=self.approve)

    def test_email_requires_approval_and_records_acceptance_not_delivery(self):
        smtp = Mock()
        smtp.__enter__ = Mock(return_value=smtp)
        smtp.__exit__ = Mock(return_value=False)
        smtp.send_message.return_value = {}
        factory = Mock(return_value=smtp)
        adapter = SMTPDeliveryAdapter(host="mail.example", username="user", password="secret",
                                      sender="sender@example.org", smtp_factory=factory)
        params = dict(self.scope, recipient="user@example.org", subject="Report", body="Done")
        with self.assertRaises(PermissionError):
            adapter.send(**params)
        factory.assert_not_called()
        receipt = adapter.send(**params, authorized=True)
        self.assertEqual(receipt.state, "provider_accepted")
        self.assertFalse(receipt.externally_delivered)
        self.assertEqual(smtp.send_message.call_count, 1)

    def test_payment_requires_approval_and_never_auto_captures(self):
        client = Mock()
        client.PaymentIntent.create.return_value = {"id": "pi_test", "status": "requires_payment_method"}
        adapter = StripePaymentAdapter(api_key="sk_test_placeholder", stripe_client=client)
        params = dict(self.scope, amount_minor=1200, currency="NOK", customer_id="cus_test")
        with self.assertRaises(PermissionError):
            adapter.create_payment_intent(**params)
        client.PaymentIntent.create.assert_not_called()
        receipt = adapter.create_payment_intent(**params, authorized=True)
        self.assertEqual(receipt.state, "requires_action")
        self.assertFalse(receipt.externally_delivered)
        kwargs = client.PaymentIntent.create.call_args.kwargs
        self.assertFalse(kwargs["confirm"])
        self.assertEqual(kwargs["capture_method"], "manual")
        self.assertEqual(kwargs["idempotency_key"], "hermes:tenant-a:effect-1")

    def test_webhook_requires_signature_and_never_infers_settlement(self):
        client = Mock()
        client.Webhook.construct_event.return_value = {
            "id": "evt_test", "type": "payment_intent.processing",
            "data": {"object": {"id": "pi_test", "status": "processing"}}}
        with self.assertRaises(PermissionError):
            verify_stripe_webhook(payload=b"{}", signature="", webhook_secret="secret", stripe_client=client)
        result = verify_stripe_webhook(payload=b"{}", signature="sig", webhook_secret="secret", stripe_client=client)
        self.assertFalse(result["settled"])

if __name__ == "__main__":
    unittest.main()
