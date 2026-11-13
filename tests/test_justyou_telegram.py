import tempfile
import unittest
from pathlib import Path

from identity_layer import ActorKind, IdentityLayer, JustYouAddressSpace, Protocol
from identity_layer.inbound import InboundFrontDoor
from unlimited.justyou_durable_inbox import DurableInboundInbox
from unlimited.justyou_telegram import TelegramInboundAdapter


class TelegramAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        identities = IdentityLayer()
        addresses = JustYouAddressSpace(identities)
        for address in ("@sender", "@recipient"):
            actor = identities.register_actor(ActorKind.HUMAN)
            addresses.claim(address, actor.actor_id, "continuity:" + address)
        addresses.bind_channel("@sender", "telegram", "123")
        frontdoor = InboundFrontDoor(
            addresses, Protocol(identities, addresses=addresses))
        self.delivered = []
        inbox = DurableInboundInbox(
            str(Path(tmp.name) / "telegram.sqlite"), self.delivered.append)
        self.addCleanup(inbox.close)
        self.adapter = TelegramInboundAdapter(
            chat_id=999, allowed_sender_ids={123},
            recipient="@recipient", frontdoor=frontdoor, inbox=inbox)
        self.update = {
            "update_id": 200, "message": {
                "message_id": 100, "text": "Test just you",
                "chat": {"id": 999},
                "from": {"id": 123, "is_bot": False}}}

    def test_valid_durable_delivery_and_replay(self):
        a = self.adapter.receive_update(self.update)
        b = self.adapter.receive_update(self.update)
        self.assertEqual(a.key, b.key)
        self.assertEqual(len(self.delivered), 1)
        self.assertEqual(a.message.sender, "@sender")

    def test_reject_wrong_chat_and_sender(self):
        for changes in (
            {"chat": {"id": 998}},
            {"from": {"id": 124, "is_bot": False}},
            {"from": {"id": 123, "is_bot": True}},
        ):
            update = dict(self.update)
            update["message"] = {**self.update["message"], **changes}
            with self.assertRaises(PermissionError):
                self.adapter.receive_update(update)
        self.assertEqual(len(self.delivered), 0)

    def test_reject_conflicting_replay(self):
        self.adapter.receive_update(self.update)
        update = dict(self.update)
        update["message"] = {**self.update["message"], "text": "altered"}
        with self.assertRaises(ValueError):
            self.adapter.receive_update(update)

    def test_reject_invalid_message(self):
        for invalid in ({"update_id": 200}, {"message": {}},
                        {"update_id": "x", "message": self.update["message"]}):
            with self.assertRaises(ValueError):
                self.adapter.receive_update(invalid)
