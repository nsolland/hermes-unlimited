import unittest

from scripts.harness_analyze import analyze


def row(task, arm, success, seconds=1.0, exit_code=0):
    return {"task": task, "arm": arm, "oracle_match": success,
            "seconds": seconds, "exit_code": exit_code}


class HarnessAnalysisTests(unittest.TestCase):
    def test_paired_exact_discordance(self):
        d = {"expected_invocations": 4, "records": [
            row("a", "baseline", True), row("a", "checker", False, exit_code=124),
            row("b", "baseline", False), row("b", "checker", True),
        ]}
        x = analyze(d)
        self.assertEqual(x["completion_delta_checker_minus_baseline"], 0)
        self.assertEqual(x["baseline_only_correct"], 1)
        self.assertEqual(x["checker_only_correct"], 1)
        self.assertEqual(x["checker_timeouts"], 1)
        self.assertEqual(x["mcnemar_exact_two_sided_p_exploratory"], 1)

    def test_no_discordance(self):
        d = {"expected_invocations": 2, "records": [
            row("a", "baseline", True), row("a", "checker", True)]}
        self.assertEqual(analyze(d)["mcnemar_exact_two_sided_p_exploratory"], 1)

    def test_reject_incomplete(self):
        d = {"expected_invocations": 4, "records": [
            row("a", "baseline", True), row("a", "checker", True)]}
        with self.assertRaises(ValueError):
            analyze(d)

    def test_reject_duplicate(self):
        d = {"expected_invocations": 4, "records": [
            row("a", "baseline", True), row("a", "baseline", True),
            row("a", "checker", True), row("b", "checker", True)]}
        with self.assertRaises(ValueError):
            analyze(d)


if __name__ == "__main__":
    unittest.main()
