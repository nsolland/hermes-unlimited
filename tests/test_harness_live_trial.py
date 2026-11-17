import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from scripts.harness_live_trial import invoke, BASE_RULE, CHECK_RULE, TASKS, main
from unlimited.harness_benchmark import Trial


class HarnessLiveTrialTests(unittest.TestCase):
    def test_non_string_harness_identifiers_rejected(self):
        for field, value in (("task_id", ["task"]), ("harness", ["baseline"])):
            args=dict(task_id="task",harness="baseline",seed=1,
                      goal_met=True,verification_passed=True,proof_present=True,
                      scope_preserved=True,resumed_correctly=False,
                      interventions=0,runtime_seconds=1.0,cost_usd=0.0)
            args[field]=value
            with self.assertRaises(ValueError):
                Trial(**args)

    def test_preflight_errors_never_invoke_paid_cli(self):
        from unittest.mock import patch
        from contextlib import redirect_stderr
        from io import StringIO
        invalid=[
            ["--tasks","squares","squares","--limit","4"],
            ["--tasks","squares","reverse","--limit","2"],
            ["--tasks","squares","--limit","0"],
            ["--tasks","squares","--model"," "],
            ["--tasks","squares","--provider"," "],
        ]
        for options in invalid:
            argv=["trial","--out","/tmp/unwritten.json","--model","m","--provider","p",*options]
            with self.subTest(argv=argv):
                with patch("sys.argv",argv), patch("scripts.harness_live_trial.subprocess.run") as execute:
                    with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                        main()
                    execute.assert_not_called()

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
