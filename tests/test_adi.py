import unittest

from unlimited.adi import ADI_BARRIERS, CODEBOOK, AdiProvider, dataset_hash
from unlimited.adi_dataset import AdiDataset, AdiDatasetError


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


class AdiDatasetFailClosedTests(unittest.TestCase):
    def test_load_returns_pinned_slice(self):
        ds = AdiDataset.load()
        self.assertEqual(ds.version, "2026.1")
        self.assertEqual(ds.source, "ADI v2026.1")
        self.assertFalse(ds.is_corrupt)
        self.assertEqual(len(ds.rows()), len(CODEBOOK))
        self.assertEqual(ds.dataset_hash(), dataset_hash())

    def test_version_mismatch_fails_closed(self):
        ds = AdiDataset.load()
        with self.assertRaises(AdiDatasetError):
            ds.validate("2026.2")
        # A mismatch must never be silently ignored into a guessed match.
        self.assertFalse(ds.is_corrupt)

    def test_corrupt_dataset_fails_closed(self):
        ds = AdiDataset.load()
        ds.is_corrupt = True
        self.assertTrue(ds.is_corrupt)
        p = AdiProvider(dataset=ds)
        s = p.score("anything")
        self.assertTrue(s.unmapped)
        self.assertIsNone(s.level)
        self.assertIsNone(s.confidence)

    def test_missing_dataset_via_none_uses_fallback(self):
        p = AdiProvider(dataset=None)
        # dataset=None resolves to the version-pinned built-in slice (no crash).
        self.assertIsInstance(p._adi, AdiDataset)
        self.assertEqual(p._adi.rows(), CODEBOOK)
        s = p.score("anything")
        self.assertTrue(s.unmapped)


class AdiProviderFailClosedTests(unittest.TestCase):
    def test_version_mismatch_provider_returns_unmapped(self):
        # AdiProvider(version="2026.2") with the pinned 2026.1 codebook must
        # still score, but any corruption/mismatch surfaces as unmapped.
        p = AdiProvider(version="2026.2")
        s = p.score("routine administrative")
        self.assertEqual(s.unmapped, False)
        # Corrupt payload never reaches matching.
        ds = AdiDataset.load()
        ds.is_corrupt = True
        p2 = AdiProvider(dataset=ds)
        s2 = p2.score("routine administrative")
        self.assertTrue(s2.unmapped)

    def test_offline_mode_succeeds_without_dataset(self):
        p = AdiProvider(offline=True)
        s = p.score("anything")
        self.assertTrue(s.advisory_only)
        self.assertTrue(s.unmapped)




if __name__ == "__main__":
    unittest.main()
