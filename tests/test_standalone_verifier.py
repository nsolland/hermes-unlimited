import unittest

from unlimited.authoritative_binding import (
    AuthorityBinding, Ed25519Authority, HmacAuthority,
    VerifiedResolver, VersionAnnouncement,
)


class StandaloneVerifierTests(unittest.TestCase):
    def test_bundled_verifier_imports_without_protocol_package(self):
        self.assertTrue(callable(VerifiedResolver))
        self.assertTrue(callable(AuthorityBinding))
        self.assertTrue(callable(VersionAnnouncement))

    def test_hmac_signature_rejects_altered_binding(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        authority = HmacAuthority("test", b"unit-test-only")
        original = AuthorityBinding(identity="@test", version=1, carrier="hermes-profile",
                                    endpoint="hermes-profile:agent", endpoint_key_id="agent",
                                    authority_key_id="test", valid_from=now,
                                    valid_until=now + timedelta(hours=1))
        signed = authority.sign_binding(original)
        self.assertTrue(authority.verify_binding(signed))
        from dataclasses import replace
        self.assertFalse(authority.verify_binding(replace(signed, endpoint="changed")))


if __name__ == "__main__":
    unittest.main()
