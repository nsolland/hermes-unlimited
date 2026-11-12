import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from unlimited.shortcuts_intake import TrustedMobileScope, enqueue_shortcut


class FakeKanban:
    calls = []

    def __init__(self, *, board):
        self.board = board

    def enqueue(self, **kw):
        self.calls.append((self.board, kw))
        return {"status": "TASK_QUEUED", "task_id": "t123"}


class MobileIntakeTests(unittest.TestCase):
    def setUp(self):
        FakeKanban.calls.clear()
        self.scope = TrustedMobileScope(
            "provider", "customer", "responder",
            {"verified": True, "authority_granted": False,
             "profile": "responder", "binding_digest": "abc"})

    def submit(self, payload, scope=None):
        return enqueue_shortcut(payload, scope=self.scope if scope is None else scope,
                                kanban_factory=FakeKanban)

    def test_queue_is_scoped_and_does_not_execute(self):
        out = self.submit({"request_id": "mobile-1", "action": "summarize",
                           "text": "Summarize the meeting"})
        self.assertEqual(out["status"], "queued")
        self.assertFalse(out["executed"])
        board, data = FakeKanban.calls[0]
        self.assertTrue(board.startswith("unlimited-"))
        self.assertEqual(data["tenant"], "customer")
        self.assertEqual(data["assignee"], "responder")
        self.assertEqual(data["task_id"], "mobile-1")

    def test_rejects_phone_claimed_identity_and_toolsets(self):
        for field in ("tenant_id", "profile", "identity", "toolsets", "command", "company_id"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.submit({"request_id": "x", "text": "hello", field: "attacker"})
        self.assertEqual(FakeKanban.calls, [])

    def test_fails_closed_without_verified_binding(self):
        for evidence in ({}, {"verified": True, "profile": "responder",
                              "binding_digest": "x", "authority_granted": True}):
            with self.assertRaises(PermissionError):
                self.submit({"request_id": "x", "text": "hello"},
                            TrustedMobileScope("provider", "customer", "responder", evidence))
        self.assertEqual(FakeKanban.calls, [])

    def test_rejects_unsafe_actions_unknown_events_and_non_https(self):
        for update in ({"action": "shell"}, {"action": "event", "event": "arbitrary"},
                       {"url": "http://internal"}, {"request_id": "invalid id"},
                       {"file": "binary"}):
            payload = {"request_id": "x", "text": "hello", **update}
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.submit(payload)
        self.assertEqual(FakeKanban.calls, [])

    def test_unicode_byte_limit(self):
        with self.assertRaises(ValueError):
            self.submit({"request_id": "x", "text": "ø" * 5000})

    def test_known_event(self):
        out = self.submit({"request_id": "x", "action": "event", "event": "alarm_off"})
        self.assertTrue(out["accepted"])

    def test_board_is_tenant_distinct(self):
        self.submit({"request_id": "x", "text": "one"})
        first = FakeKanban.calls[0][0]
        other = TrustedMobileScope("provider", "other", "responder", self.scope.identity_evidence)
        self.submit({"request_id": "x", "text": "one"}, other)
        self.assertNotEqual(first, FakeKanban.calls[1][0])


if __name__ == "__main__":
    unittest.main()
