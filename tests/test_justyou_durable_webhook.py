import hashlib
import hmac
import json
import multiprocessing
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from identity_layer import ActorKind, IdentityLayer, JustYouAddressSpace, Protocol
from identity_layer.inbound import InboundFrontDoor
from unlimited.justyou_durable_inbox import DurableInboundInbox
from unlimited.justyou_webhook import HMACWebhookIngress


class DurableWebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "inbox.sqlite")
        ids = IdentityLayer()
        addr = JustYouAddressSpace(ids)
        for handle, kind in (("@supplier", ActorKind.COMPANY),
                             ("@operator", ActorKind.HUMAN)):
            actor = ids.register_actor(kind)
            addr.claim(handle, actor.actor_id, "continuity:" + handle)
        addr.bind_channel("@supplier", "test-hmac", "supplier:1")
        self.frontdoor = InboundFrontDoor(addr, Protocol(ids, addresses=addr))
        self.secret = b"x" * 32
        self.delivered = []
        self.inbox = DurableInboundInbox(self.path, self.delivered.append)
        self.addCleanup(self.inbox.close)
        self.ingress = HMACWebhookIngress(
            secret=self.secret, channel="test-hmac", endpoint="supplier:1",
            frontdoor=self.frontdoor, inbox=self.inbox,
            clock=lambda: 1700000000)
        self.payload = dict(endpoint="supplier:1", message_id="m-1",
                            recipient="@operator", text="Invoice ready")

    def send(self, *, payload=None, timestamp="1700000000",
             secret=None, signature=None, ingress=None):
        body = json.dumps(payload if payload is not None else self.payload).encode()
        signature = signature if signature is not None else hmac.new(
            secret if secret is not None else self.secret,
            timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        return (ingress or self.ingress).receive(
            body=body, timestamp=timestamp, signature_hex=signature)

    def test_real_verified_sender_durable_replay_after_restart(self):
        first = self.send()
        self.assertEqual(len(self.delivered), 1)
        self.assertEqual(self.inbox.status(first.key), "delivered")
        self.assertEqual(self.send().key, first.key)
        self.assertEqual(len(self.delivered), 1)
        restarted = DurableInboundInbox(self.path, self.delivered.append)
        self.addCleanup(restarted.close)
        new_ingress = HMACWebhookIngress(
            secret=self.secret, channel="test-hmac", endpoint="supplier:1",
            frontdoor=self.frontdoor, inbox=restarted,
            clock=lambda: 1700000000)
        self.assertEqual(self.send(ingress=new_ingress).key, first.key)
        self.assertEqual(len(self.delivered), 1)
        self.assertEqual(restarted.recover(), 0)

    def test_rejects_signature_expiry_unknown_and_conflicting_replay(self):
        for kwargs in (dict(secret=b"z" * 32),
                       dict(timestamp="1699999000"),
                       dict(signature="a" * 64),
                       dict(payload={**self.payload, "endpoint": "other"}),
                       dict(payload={**self.payload, "recipient": "@missing"})):
            with self.assertRaises((PermissionError, KeyError)):
                self.send(**kwargs)
        self.send()
        with self.assertRaises(ValueError):
            self.send(payload={**self.payload, "text": "Changed"})
        self.assertEqual(len(self.delivered), 1)

    def test_crash_recovery_pending_and_idempotent_sink(self):
        attempts = []
        def fail_once(delivery):
            attempts.append(delivery.key)
            if len(attempts) == 1:
                raise RuntimeError("sink unavailable")
        self.inbox._deliver = fail_once
        with self.assertRaises(RuntimeError):
            self.send()
        key = self.inbox._key("test-hmac", "supplier:1", "m-1")
        self.assertEqual(self.inbox.status(key), "pending")
        recovered = DurableInboundInbox(self.path, fail_once)
        self.addCleanup(recovered.close)
        self.assertEqual(recovered.recover(), 1)
        self.assertEqual(recovered.status(key), "delivered")
        self.assertEqual(attempts, [key, key])

    def test_crash_after_external_effect_requires_sink_idempotency(self):
        effects = set()
        calls = []
        def effect_then_crash(delivery):
            calls.append(delivery.key)
            effects.add(delivery.key)
            if len(calls) == 1:
                raise RuntimeError("crash after effect")
        self.inbox._deliver = effect_then_crash
        with self.assertRaises(RuntimeError):
            self.send()
        restarted = DurableInboundInbox(self.path, effect_then_crash)
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.recover(), 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(effects), 1, "idempotent sink key prevents duplicate effect")

    def test_parallel_duplicate_delivery(self):
        keys = []
        failures = []
        def worker():
            try:
                keys.append(self.send().key)
            except Exception as exc:
                failures.append(exc)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertFalse(failures, failures)
        self.assertEqual(len(keys), 8)
        self.assertEqual(len(self.delivered), 1)

    def test_two_inbox_instances_share_durable_deduplication(self):
        second = DurableInboundInbox(self.path, self.delivered.append)
        self.addCleanup(second.close)
        other = HMACWebhookIngress(
            secret=self.secret, channel="test-hmac", endpoint="supplier:1",
            frontdoor=self.frontdoor, inbox=second, clock=lambda: 1700000000)
        failures = []
        def send_to(ingress):
            try:
                self.send(ingress=ingress)
            except Exception as exc:
                failures.append(exc)
        threads = [threading.Thread(target=send_to, args=(ingress,))
                   for ingress in (self.ingress, other) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(len(self.delivered), 1)

    def test_credential_rotation_and_revocation(self):
        registry = HMACWebhookIngress(
            credentials={"old": self.secret}, channel="test-hmac",
            endpoint="supplier:1", frontdoor=self.frontdoor,
            inbox=self.inbox, clock=lambda: 1700000000)
        body = json.dumps(self.payload).encode()
        def signed(secret):
            return hmac.new(secret, b"1700000000." + body,
                            hashlib.sha256).hexdigest()
        registry.receive(body=body, timestamp="1700000000",
                         signature_hex=signed(self.secret), key_id="old")
        new_secret = b"n" * 32
        registry.rotate_credentials({"old": self.secret, "new": new_secret})
        registry.receive(body=body, timestamp="1700000000",
                         signature_hex=signed(new_secret), key_id="new")
        registry.rotate_credentials({"new": new_secret})
        with self.assertRaises(PermissionError):
            registry.receive(body=body, timestamp="1700000000",
                             signature_hex=signed(self.secret), key_id="old")
        with self.assertRaises(PermissionError):
            registry.receive(body=body, timestamp="1700000000",
                             signature_hex=signed(self.secret), key_id="new")
        self.assertEqual(len(self.delivered), 1)

    def test_rejects_malformed_requests(self):
        for body in (b"{}", b"not-json", b"[]", b""):
            sig = hmac.new(self.secret, b"1700000000." + body,
                           hashlib.sha256).hexdigest()
            with self.assertRaises(ValueError):
                self.ingress.receive(
                    body=body, timestamp="1700000000", signature_hex=sig)
        with self.assertRaises(ValueError):
            HMACWebhookIngress(secret=b"weak", channel="test-hmac", endpoint="supplier:1",
                               frontdoor=self.frontdoor, inbox=self.inbox)


if __name__ == "__main__":
    unittest.main()
