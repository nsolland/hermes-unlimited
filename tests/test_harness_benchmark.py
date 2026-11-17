import unittest

from unlimited.harness_benchmark import Trial, summarize, paired_delta


def trial(harness="base", **kwargs):
    props = dict(task_id="task", harness=harness, seed=42, goal_met=True,
                 verification_passed=True, proof_present=True,
                 scope_preserved=True, resumed_correctly=True,
                 interventions=0, runtime_seconds=10, cost_usd=1)
    props.update(kwargs)
    return Trial(**props)


class HarnessBenchmarkTests(unittest.TestCase):
    def test_completed_requires_proof(self):
        for key in ("goal_met", "verification_passed", "proof_present", "scope_preserved"):
            with self.subTest(key=key):
                self.assertFalse(trial(**{key: False}).verified_completion)
        self.assertTrue(trial().verified_completion)

    def test_summary(self):
        s = summarize([trial(), trial("treated", proof_present=False)])
        self.assertEqual(s["base"]["verified_completion_rate"], 1)
        self.assertEqual(s["treated"]["verified_completion_rate"], 0)
        self.assertEqual(s["treated"]["claimed_goal_rate"], 1)

    def test_paired_delta(self):
        d = paired_delta([trial(proof_present=False, interventions=3),
                          trial("treated")], "base", "treated")
        self.assertEqual(d["verified_completion_delta"], 1)
        self.assertEqual(d["interventions_delta"], -3)

    def test_reject_unpaired(self):
        with self.assertRaises(ValueError):
            paired_delta([trial(), trial("treated", seed=7)], "base", "treated")

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            summarize([trial(), trial()])

    def test_reject_invalid_nonfinite(self):
        for value in (float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                trial(cost_usd=value)
        with self.assertRaises(ValueError):
            trial(interventions=-1)
        with self.assertRaises(ValueError):
            trial(goal_met="true")


if __name__ == "__main__":
    unittest.main()
