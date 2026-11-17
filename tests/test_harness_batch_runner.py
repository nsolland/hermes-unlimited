import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.harness_batch_runner import atomic_save, run
from scripts.harness_live_trial import TASKS


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch("scripts.harness_batch_runner.inspect_host",
                           return_value={"admissible": True, "reasons": []})
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_reject_busy_host(self):
        with patch("scripts.harness_batch_runner.inspect_host",
                   return_value={"admissible": False, "reasons": ["SWAP_PRESSURE"]}):
            with tempfile.TemporaryDirectory() as temp:
                args = SimpleNamespace(out=str(Path(temp)/"state.json"), model="m",
                                       provider="p", timeout=5, order_seed=2, limit=40)
                with self.assertRaisesRegex(RuntimeError, "SWAP_PRESSURE"):
                    run(args)

    def test_atomic_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "nested" / "result.json"
            atomic_save(p, {"a": 1})
            self.assertEqual(json.loads(p.read_text()), {"a": 1})
            self.assertFalse(p.with_name(p.name + ".partial").exists())

    def test_resume_skips_completed_and_keeps_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            args = SimpleNamespace(out=str(path), model="test-model", provider="test-provider",
                                   timeout=5, order_seed=2, limit=40)
            def fake_invoke(root, task, seed, arm, timeout, model, provider):
                return None, {"task": task, "arm": arm, "seed": seed,
                              "oracle_match": True, "exit_code": 0, "seconds": 0}
            calls = []
            def wrapped(*args, **kwargs):
                calls.append(1)
                return fake_invoke(*args, **kwargs)
            with patch("scripts.harness_batch_runner.invoke", new=wrapped):
                first = run(args)
                self.assertEqual(len(first["records"]), len(TASKS)*2)
                self.assertTrue(first["complete"])
                self.assertEqual(len(calls), len(TASKS)*2)
            with patch("scripts.harness_batch_runner.invoke", new=wrapped):
                again = run(args)
                self.assertEqual(len(again["records"]), len(TASKS)*2)
                self.assertEqual(len(calls), len(TASKS)*2)

    def test_manifest_rejects_mismatch_on_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            args = SimpleNamespace(out=str(path), model="m1", provider="p1",
                                   timeout=5, order_seed=2, limit=40)
            def fake(root, task, seed, arm, timeout, model, provider):
                return None, {"task":task,"arm":arm,"oracle_match":False,"exit_code":124,"seconds":5}
            with patch("scripts.harness_batch_runner.invoke", new=fake):
                run(args)
            args.model = "different"
            with self.assertRaisesRegex(ValueError, "resume manifest mismatch"):
                run(args)

    def test_guard_rejects_too_few_invocations(self):
        with tempfile.TemporaryDirectory() as temp:
            args = SimpleNamespace(out=str(Path(temp) / "state.json"),
                                   model="m", provider="p", timeout=5,
                                   order_seed=2, limit=2)
            with self.assertRaisesRegex(ValueError, "limit"):
                run(args)


if __name__ == "__main__":
    unittest.main()
