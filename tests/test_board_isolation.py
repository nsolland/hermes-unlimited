"""Hermes Kanban board isolation contract tests."""
import json
import unittest
from types import SimpleNamespace

from unlimited.hermes_kanban import HermesKanban, board_for


class BoardIsolationTests(unittest.TestCase):
    def test_distinct_tenants_and_providers_have_distinct_boards(self):
        self.assertNotEqual(board_for("provider", "tenant-a"), board_for("provider", "tenant-b"))
        self.assertNotEqual(board_for("provider", "tenant-a"), board_for("other", "tenant-a"))

    def test_stable_board(self):
        self.assertEqual(board_for("provider", "tenant-a"), board_for("provider", "tenant-a"))
        self.assertTrue(board_for("provider", "tenant-a").startswith("unlimited-"))

    def test_invalid_scopes_fail_closed(self):
        for value in ("../escape", "", None, "UPPER"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                board_for("provider", value)

    def test_default_board_is_never_accepted(self):
        for value in (None, "default", "../escape"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                HermesKanban(board=value)

    def test_runtime_and_retry_bounds_fail_closed(self):
        board = board_for("provider", "tenant-a")
        for runtime, retries in ((0, 1), (86401, 1), (True, 1),
                                 (900, 0), (900, 6), (900, True)):
            with self.subTest(runtime=runtime, retries=retries), self.assertRaises(ValueError):
                HermesKanban(board=board, max_runtime_seconds=runtime,
                             max_retries=retries)

    def test_enqueue_and_result_pin_same_board(self):
        commands = []

        def runner(command, **_kwargs):
            commands.append(command)
            if "create" in command:
                data = {"id": "t_one"}
            else:
                data = [{"id": "t_one", "tenant": "tenant-a", "assignee": "role-a",
                         "created_by": "hermes-unlimited", "status": "done"}]
            return SimpleNamespace(returncode=0, stdout=json.dumps(data))

        board = board_for("provider", "tenant-a")
        adapter = HermesKanban(run=runner, board=board)
        evidence = {"verified": True, "authority_granted": False,
                    "binding_digest": "digest", "profile": "role-a"}
        queued = adapter.enqueue(tenant="tenant-a", assignee="role-a",
                                 task_id="request", title="Example", body="",
                                 identity_evidence=evidence)
        self.assertEqual(queued["task_id"], "t_one")
        result = adapter.result(tenant="tenant-a", assignee="role-a", task_id="t_one")
        self.assertTrue(result["completed"])
        self.assertFalse(result["independently_verified"])
        self.assertEqual(len(commands), 2)
        self.assertIn("--max-runtime", commands[0])
        self.assertEqual(commands[0][commands[0].index("--max-runtime") + 1], "900")
        self.assertIn("--max-retries", commands[0])
        self.assertEqual(commands[0][commands[0].index("--max-retries") + 1], "1")
        self.assertTrue(all(command[2:4] == ["--board", board] for command in commands))


if __name__ == "__main__":
    unittest.main()
