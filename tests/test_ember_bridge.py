import hashlib
import hmac
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from unlimited.ember_bridge import EmberBridge, RoomRoute
from unlimited.justyou import JustYouVerifier
from unlimited.runtime import ProviderStore, UnverifiedIdentity


class Binding:
    identity = "@owner"
    carrier = "hermes-profile"
    endpoint = "hermes-profile:owner-test"
    version = 2
    def digest(self):
        return "digest"


class Store:
    def validate(self, token, audience, required_scope):
        return SimpleNamespace(valid=True, authority=False, audience=audience,
                               scopes=("read-profile",), address="@owner")


class Resolver:
    def resolve(self, identity, **kwargs):
        return Binding(), SimpleNamespace(identity=identity, binding_digest="digest",
                                          resolved_version=2, status="RESOLVED")


class EmberIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.verifier = JustYouVerifier(Store(), Resolver(), "owner-test", "session")
        self.provider_store = ProviderStore(pathlib.Path(self.tmp.name) / "test.sqlite",
            lambda p, t, i: p == "provider" and t == "tenant-a"
            and i == "@owner" and self.verifier.authorize_provider_tenant(p, t, i))
        self.provider_store.create_company("provider", "tenant-a", "agency", "Agency", "@owner")
        self.provider_store.publish_service("provider", "tenant-a", "agency", "research", "Research", 0, "NOK", "@owner")
        self.key = b"gateway-key-must-be-32-bytes-minimum!"
        self.bridge = EmberBridge(self.provider_store, self.verifier, {
            "r-100": RoomRoute("provider", "tenant-a", "agency", "research", "@owner")}, self.key)
        self.payload = {"room":{"id":"r-100","name":"Team"},
                        "message":{"id":"m-001","body":{"plain":"Research this market"}},
                        "user":{"id":"u-01","name":"User"}}

    def signed(self, payload, bridge=None):
        if not isinstance(payload, dict):
            return (payload, "")
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return (payload, hmac.new(self.key, data, hashlib.sha256).hexdigest())

    def tearDown(self):
        self.tmp.cleanup()

    def test_ember_message_justyou_to_tenant_service_queue(self):
        result = self.bridge.intake(*self.signed(self.payload))
        self.assertEqual(result["state"], "queued")
        self.assertFalse(result["executed"])
        request = self.provider_store.get_request("provider", "tenant-a", "agency",
                                                    result["request"], "@owner")
        self.assertEqual(request["payload"]["text"], "Research this market")
        self.assertEqual(request["payload"]["source"], "ember")

    def test_unmapped_room_rejected_even_if_tenant_claimed(self):
        p = {**self.payload, "room":{"id":"r-other"},
             "tenant":"tenant-a", "identity_verified":True}
        with self.assertRaises(UnverifiedIdentity):
            self.bridge.intake(*self.signed(p))

    def test_forged_tenant_fields_ignored(self):
        p = {**self.payload, "tenant":"tenant-b", "identity":"attacker",
             "verified":True}
        result = self.bridge.intake(*self.signed(p))
        self.assertIsNotNone(self.provider_store.get_request(
            "provider", "tenant-a", "agency", result["request"], "@owner"))

    def test_bad_justyou_refused_without_queue_effect(self):
        bad_verifier = JustYouVerifier(Store(), Resolver(), "other-profile", "session")
        bridge = EmberBridge(self.provider_store, bad_verifier, self.bridge.routes, self.key)
        with self.assertRaises(UnverifiedIdentity):
            bridge.intake(*self.signed(self.payload))
        self.assertEqual(self.provider_store.list_requests("provider", "tenant-a", "agency", "@owner"), [])

    def test_replay_does_not_double_queue(self):
        self.bridge.intake(*self.signed(self.payload))
        with self.assertRaises(Exception):
            self.bridge.intake(*self.signed(self.payload))
        self.assertEqual(len(self.provider_store.list_requests(
            "provider", "tenant-a", "agency", "@owner")), 1)

    def test_malformed_and_oversize_payload_rejected(self):
        for payload in (None, {}, {"room":{},"message":{},"user":{}},
                        {**self.payload, "message":{"id":"m-1","body":{"plain":"x"*8193}}}):
            with self.subTest(payload=str(payload)[:30]), self.assertRaises(ValueError):
                self.bridge.intake(*self.signed(payload))

    def test_not_executed_no_fake_agent_response(self):
        receipt = self.bridge.intake(*self.signed(self.payload))
        self.assertEqual(receipt, {"request":receipt["request"],"state":"queued","executed":False})

    def test_unsigned_and_forged_signatures_fail_closed(self):
        with self.assertRaises(UnverifiedIdentity):
            self.bridge.intake(self.payload)
        with self.assertRaises(UnverifiedIdentity):
            self.bridge.intake(self.payload, "0" * 64)
        self.assertEqual(self.provider_store.list_requests(
            "provider", "tenant-a", "agency", "@owner"), [])

    def test_message_mutation_invalidates_gateway_signature(self):
        _, signature = self.signed(self.payload)
        altered = {**self.payload, "message": {"id": "m-001",
                   "body": {"plain": "Different command"}}}
        with self.assertRaises(UnverifiedIdentity):
            self.bridge.intake(altered, signature)

    def test_reject_short_gateway_key(self):
        with self.assertRaises(ValueError):
            EmberBridge(self.provider_store, self.verifier, self.bridge.routes, b"short")


    def test_submit_to_existing_hermes_dispatch_contract(self):
        calls = []
        def handler(args):
            calls.append(args)
            return json.dumps({"request": args["request_id"], "state": "running",
                               "task_id": "synthetic-task", "executed": False})
        result = self.bridge.submit_to_hermes(*self.signed(self.payload), handler)
        self.assertEqual(result["state"], "running")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["company_id"], "agency")
        self.assertFalse(result["executed"])

    def test_failed_dispatch_remains_queued_without_false_completion(self):
        def handler(args):
            return json.dumps({"ok": False, "reason": "JUSTYOU_NOT_VERIFIED"})
        result = self.bridge.submit_to_hermes(*self.signed(self.payload), handler)
        self.assertTrue(result["dispatch_pending"])
        self.assertFalse(result["executed"])
