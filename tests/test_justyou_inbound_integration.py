"""Real JustYou inbound primitive connected to Hermes Unlimited development sink."""
import unittest

from identity_layer import ActorKind, IdentityLayer, JustYouAddressSpace, Protocol
from identity_layer.inbound import InboundFrontDoor, VerifiedOrigin

from unlimited.justyou_inbound import JustYouInboundBridge


class JustYouInboundIntegrationTests(unittest.TestCase):
    def setUp(self):
        identities = IdentityLayer()
        addresses = JustYouAddressSpace(identities)
        for address, kind in (("@operator", ActorKind.HUMAN),
                              ("@supplier", ActorKind.COMPANY)):
            actor = identities.register_actor(kind)
            addresses.claim(address, actor.actor_id, f"continuity:{address}")
        addresses.bind_channel("@supplier", "provider", "supplier:1")
        self.messages = []
        self.bridge = JustYouInboundBridge(
            InboundFrontDoor(addresses, Protocol(identities, addresses=addresses)),
            self.messages.append,
        )
        self.origin = VerifiedOrigin("provider", "supplier:1", "proof:validated")

    def receive(self, **overrides):
        args = dict(origin=self.origin, recipient_address="@operator",
                    message_id="m-1", text="Invoice available")
        args.update(overrides)
        return self.bridge.receive(**args)

    def test_real_verified_origin_delivered_once(self):
        first = self.receive()
        self.assertEqual((first.sender, first.recipient), ("@supplier", "@operator"))
        self.assertEqual(first.proof_ref, "proof:validated")
        self.assertIs(first, self.receive())
        self.assertEqual(self.messages, [first])

    def test_unknown_origin_and_recipient_rejected(self):
        with self.assertRaises(PermissionError):
            self.receive(origin=None)
        with self.assertRaises(KeyError):
            self.receive(origin=VerifiedOrigin("provider", "unknown", "proof"))
        with self.assertRaises(KeyError):
            self.receive(recipient_address="@other")
        self.assertEqual(self.messages, [])

    def test_replay_mutations_rejected_without_redelivery(self):
        self.receive()
        for overrides in (dict(text="Pay immediately"),
                          dict(origin=VerifiedOrigin("provider", "supplier:1", "other")),
                          dict(recipient_address="@supplier")):
            with self.assertRaises(ValueError):
                self.receive(**overrides)
        self.assertEqual(len(self.messages), 1)

    def test_failed_delivery_can_retry(self):
        attempts = []
        def fail_once(message):
            attempts.append(message)
            if len(attempts) == 1:
                raise RuntimeError("delivery failed")
        self.bridge._deliver = fail_once
        with self.assertRaises(RuntimeError):
            self.receive()
        self.assertEqual(len(attempts), 1)
        self.receive()
        self.assertEqual(len(attempts), 2)


if __name__ == "__main__":
    unittest.main()
