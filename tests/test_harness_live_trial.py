import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from scripts.harness_live_trial import invoke, BASE_RULE, CHECK_RULE, TASKS


class HarnessLiveTrialTests(unittest.TestCase):
    def test_extended_suite_has_20_unique_task_oracles(self):
        self.assertEqual(len(TASKS), 20)
        self.assertEqual(len(set(TASKS)), 20)
        self.assertTrue(all(prompt and answer for prompt, answer in TASKS.values()))

    def test_oracle_success_and_variant_files(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("scripts.harness_live_trial.subprocess.run", return_value=SimpleNamespace(stdout="650\n", stderr="", returncode=0)):
                row, record = invoke(Path(temp), "squares", 3, "baseline", 5, None)
            self.assertTrue(row.verified_completion)
            self.assertTrue(record["oracle_match"])
            self.assertEqual((Path(temp) / "squares-3-baseline" / "AGENTS.md").read_text(), BASE_RULE)
            with patch("scripts.harness_live_trial.subprocess.run", return_value=SimpleNamespace(stdout="650\n", stderr="", returncode=0)):
                other, _ = invoke(Path(temp), "squares", 3, "checker", 5, None)
            self.assertEqual((Path(temp) / "squares-3-checker" / "AGENTS.md").read_text(), CHECK_RULE)
            self.assertTrue(other.verified_completion)

    def test_oracle_rejects_extra_text(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("scripts.harness_live_trial.subprocess.run", return_value=SimpleNamespace(stdout="Answer: 650\n", stderr="", returncode=0)):
                row, _ = invoke(Path(temp), "squares", 1, "baseline", 5, None)
            self.assertFalse(row.verified_completion)

    def test_oracle_rejects_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("scripts.harness_live_trial.subprocess.run", return_value=SimpleNamespace(stdout="650\n", stderr="failed", returncode=1)):
                row, record = invoke(Path(temp), "squares", 1, "baseline", 5, None)
            self.assertFalse(row.verified_completion)
            self.assertEqual(record["exit_code"], 1)

    def test_timeout_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("scripts.harness_live_trial.subprocess.run", side_effect=subprocess.TimeoutExpired("hermes", 5, output=b"650\n")):
                row, record = invoke(Path(temp), "squares", 1, "baseline", 5, None)
            self.assertFalse(row.verified_completion)
            self.assertTrue(record["timed_out"])


if __name__ == "__main__":
    unittest.main()
