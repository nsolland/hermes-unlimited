import unittest
from types import SimpleNamespace
from unlimited.justyou_durable_inbox import Delivery
from unlimited.justyou_inbound import AcceptedInbound
from unlimited.justyou_hermes_sink import HermesInboundSink


class FakeKanban:
    def __init__(self):
        self.created = {}
        self.visible = True

    def enqueue(self, *, task_id, **kwargs):
        self.created.setdefault(task_id, kwargs)
        return {"task_id": task_id}

    def result(self, *, task_id, **kwargs):
        return {"found": self.visible and task_id in self.created}


class HermesSinkTests(unittest.TestCase):
    def setUp(self):
        self.kanban = FakeKanban()
        self.sink = HermesInboundSink(
            self.kanban, "tenant", "operator",
            {"identity": "@operator", "verified": True})
        self.delivery = Delivery(
            "a" * 64,
            AcceptedInbound("@supplier", "@operator", "m1", "proof", "text"))

    def test_stable_idempotency_key(self):
        self.sink(self.delivery)
        self.sink(self.delivery)
        self.assertEqual(len(self.kanban.created), 1)
        self.assertIn("inbound-" + "a" * 64, self.kanban.created)

    def test_effect_must_be_observed(self):
        self.kanban.visible = False
        with self.assertRaisesRegex(RuntimeError, "NOT_OBSERVED"):
            self.sink(self.delivery)

    def test_wrong_recipient_rejected(self):
        bad = Delivery("b" * 64, AcceptedInbound(
            "@supplier", "@other", "m2", "proof", "text"))
        with self.assertRaises(PermissionError):
            self.sink(bad)
        self.assertFalse(self.kanban.created)
