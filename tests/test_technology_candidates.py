import unittest
from unlimited.technology_candidates import CANDIDATES, summary

class TechnologyCandidatesTests(unittest.TestCase):
    def test_full_podcast_coverage(self):
        self.assertEqual(len(CANDIDATES), 17)
        self.assertEqual(len({c.name for c in CANDIDATES}), 17)

    def test_candidates_are_not_approved_integrations(self):
        self.assertFalse(summary()["ready_for_production"])
        self.assertTrue(all(c.stage == "DISCOVERY_UNVERIFIED" for c in CANDIDATES))

    def test_unknown_link_not_invented(self):
        self.assertEqual(summary()["unresolved_repositories"], ["Sprint Wake Projects"])
