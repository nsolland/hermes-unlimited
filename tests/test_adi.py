import unittest

from unlimited.adi import (
    ADI_BARRIERS,
    AdiProvider,
    dataset_hash,
)


class AdiProviderContractTests(unittest.TestCase):
    def setUp(self):
        self.provider = AdiProvider()

    def test_levels_and_barriers_contract(self):
        level_cases = [
            ("routine administrative", "L0"),
            ("research analyst", "L1"),
            ("field operator", "L2"),
            ("remote executor", "L3"),
        ]
        for text, expected in level_cases:
            with self.subTest(text=text):
                s = self.provider.score(text)
                self.assertEqual(s.level, expected)
                self.assertTrue(s.advisory_only)
                self.assertFalse(s.unmapped)
        for barrier in ADI_BARRIERS:
            s = self.provider.score("routine administrative task")
            self.assertIn(barrier, s.barriers)
            self.assertIsInstance(s.barriers[barrier], bool)

    def test_unmapped_occupation_never_silently_assigned(self):
        s = self.provider.score("audit the quarterly ledger and report only")
        self.assertTrue(s.unmapped)
        self.assertIsNone(s.level)
        self.assertIsNone(s.confidence)
        self.assertIn("unmapped", s.reason)
        self.assertEqual(s.as_dict()["advisory_only"], True)

    def test_provenance(self):
        s = self.provider.score("research analyst")
        self.assertEqual(s.source, "ADI v2026.1")
        self.assertEqual(s.version, "2026.1")
        self.assertEqual(dataset_hash(), s.dataset_hash)

    def test_offline_mode_returns_fallback_without_dataset(self):
        p = AdiProvider(offline=True)
        s = p.score("anything")
        self.assertTrue(s.advisory_only)
        self.assertTrue(s.unmapped)


class AdiSuccessTests(unittest.TestCase):
    def setUp(self):
        self.provider = AdiProvider()

    def test_levels(self):
        for text, expected in [
            ("routine administrative", "L0"),
            ("research analyst", "L1"),
            ("builder developer", "L2"),
            ("verifier auditor", "L2"),
            ("field operator", "L2"),
            ("remote executor", "L3"),
        ]:
            with self.subTest(text=text):
                s = self.provider.score(text)
                self.assertEqual(s.level, expected)
                self.assertFalse(s.unmapped)

    def test_barriers_are_boolean(self):
        s = self.provider.score("field operator requests a run")
        self.assertTrue(s.barriers["physical"])
        self.assertTrue(s.barriers["access"])
        self.assertFalse(s.barriers["accountability"])

    def test_no_authorization_permit(self):
        with self.assertRaises(PermissionError):
            self.provider.require_permit()


if __name__ == "__main__":
    unittest.main()
