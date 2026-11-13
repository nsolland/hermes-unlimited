import unittest
from integrations.skillspector.vaig_consumer import review_vaig_component


class ConsumerTest(unittest.TestCase):
    digest = "a" * 64

    def signal(self):
        return {
            "state": "REVIEW_ELIGIBLE",
            "source_digest_sha256": self.digest,
            "execution_authority": False,
            "installation_approval": False,
            "requires_reht_clearance": True,
        }

    def test_clean_never_installs(self):
        result = review_vaig_component(self.signal(),
            expected_source_digest=self.digest, trusted_vaig_origin=True)
        self.assertEqual(result.state, "REVIEW_REQUIRED")
        self.assertFalse(result.installation_approved)
        self.assertFalse(result.execution_authorized)

    def test_untrusted_origin_rejected(self):
        result = review_vaig_component(self.signal(), expected_source_digest=self.digest)
        self.assertEqual(result.state, "UNVERIFIED")

    def test_digest_change_rejected(self):
        result = review_vaig_component(self.signal(), expected_source_digest="b"*64,
                                       trusted_vaig_origin=True)
        self.assertEqual(result.state, "BLOCKED")

    def test_forged_authority_rejected(self):
        sig = self.signal()
        sig["execution_authority"] = True
        result = review_vaig_component(sig, expected_source_digest=self.digest,
                                       trusted_vaig_origin=True)
        self.assertEqual(result.state, "BLOCKED")

    def test_blocked_scan_rejected(self):
        sig = self.signal()
        sig["state"] = "BLOCKED"
        result = review_vaig_component(sig, expected_source_digest=self.digest,
                                       trusted_vaig_origin=True)
        self.assertEqual(result.state, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
