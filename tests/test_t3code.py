import subprocess
import unittest
from types import SimpleNamespace

from unlimited.t3code import T3Code, T3CodeError


class T3CodeTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.outcome = SimpleNamespace(returncode=0, stdout="thread_123\n", stderr="")

        def fake_run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

        self.client = T3Code(runner=fake_run, timeout=4)

    def test_start_and_followup(self):
        self.assertEqual(self.client.start("project_1", "Fix tests", worktree="main"), "thread_123")
        self.assertEqual(self.calls[0][0], ["t3", "thread", "start", "project_1", "Fix tests", "--worktree", "main"])
        self.assertEqual(self.calls[0][1]["timeout"], 4)
        self.client.send("thread_123", "Run checks", wait=True)
        self.assertEqual(self.calls[1][0], ["t3", "thread", "send", "thread_123", "Run checks", "--wait"])
        self.client.show("thread_123")
        self.client.list()
        self.assertEqual(self.calls[2][0][-2:], ["show", "thread_123"])
        self.assertEqual(self.calls[3][0][-1:], ["list"])

    def test_fail_closed(self):
        self.outcome = SimpleNamespace(returncode=1, stdout="ok", stderr="secret")
        with self.assertRaises(T3CodeError) as cm:
            self.client.send("thread_123", "Do work", wait=True)
        self.assertNotIn("secret", str(cm.exception))
        self.outcome = subprocess.TimeoutExpired("t3", 4)
        with self.assertRaises(T3CodeError):
            self.client.show("thread_123")
        self.outcome = OSError("missing executable")
        with self.assertRaises(T3CodeError):
            self.client.list()

    def test_invalid_inputs(self):
        for value in ("", "../oops", "--help", "space id"):
            with self.assertRaises(ValueError):
                self.client.show(value)
        for instruction in ("", "  "):
            with self.assertRaises(ValueError):
                self.client.start("project_1", instruction)
        with self.assertRaises(ValueError):
            self.client.start("project_1", "ok", worktree="--bad")
        with self.assertRaises(ValueError):
            T3Code(timeout=0)

    def test_no_fake_completion_or_malformed_id(self):
        self.outcome = SimpleNamespace(returncode=0, stdout="complete!\n", stderr="")
        with self.assertRaises(T3CodeError):
            self.client.start("project_1", "Do work")
        self.outcome = SimpleNamespace(returncode=0, stdout="running", stderr="")
        self.assertEqual(self.client.send("thread_123", "Do work"), "running")


if __name__ == "__main__":
    unittest.main()
