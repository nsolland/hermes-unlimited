import unittest
from unlimited.verified_work_experiment import summarize


def row(task="1", arm="human", **overrides):
    base = dict(task_id=task, arm=arm, accepted=True,
                human_active_seconds=20, elapsed_seconds=30,
                human_interventions=1, escalations=0, rework_count=0,
                independently_verified=True, agent_cost_usd=0)
    base.update(overrides)
    return base


class ExperimentTests(unittest.TestCase):
    def test_paired(self):
        result = summarize([row(arm=a) for a in ("human", "single_agent", "agent_team")])
        self.assertTrue(result["comparison"]["paired"])
        self.assertEqual(result["human"]["human_seconds_per_accepted"], 20)

    def test_unpaired_not_comparable(self):
        result = summarize([row(), row("2", "agent_team")])
        self.assertEqual(result["comparison"]["status"], "INCOMPLETE_BASELINE")

    def test_reject_unverified_acceptance(self):
        with self.assertRaises(ValueError):
            summarize([row(independently_verified=False)])

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            summarize([row(), row()])

    def test_reject_negative_cost(self):
        with self.assertRaises(ValueError):
            summarize([row(agent_cost_usd=-1)])

    def test_no_accepted_denominator(self):
        r = summarize([row(accepted=False, independently_verified=False)])
        self.assertIsNone(r["human"]["human_seconds_per_accepted"])


if __name__ == "__main__":
    unittest.main()
