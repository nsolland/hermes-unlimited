"""Opt-in live JustYou inbound -> actual Hermes Kanban acceptance.

Uses a real loopback JustYou registry, signed identity/profile proof, the
canonical JustYou InboundFrontDoor, and an actual Hermes Kanban SQLite board.
No model dispatch, external messages, or production Hermes data are used.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
import urllib.request
from datetime import datetime, timedelta, timezone


from unlimited.hermes_kanban import HermesKanban, board_for
from unlimited.justyou import JustYouVerifier
from unlimited.justyou_host import LoopbackSessionStore, load_resolver
from unlimited.justyou_inbound import JustYouInboundBridge
from unlimited.justyou_durable_inbox import DurableInboundInbox
from unlimited.justyou_hermes_sink import HermesInboundSink
from unlimited.justyou_webhook import HMACWebhookIngress
from unlimited.justyou_telegram import TelegramInboundAdapter
import hashlib
import hmac



CRASH_CHILD_CODE = """
import json, os, sys
from unlimited.justyou_durable_inbox import DurableInboundInbox
from unlimited.justyou_hermes_sink import HermesInboundSink
from unlimited.hermes_kanban import HermesKanban
p=json.loads(sys.argv[1])
sink=HermesInboundSink(
    HermesKanban(hermes=p["hermes"],board=p["board"]),
    p["tenant"],p["assignee"],p["identity"])
def crash_after_effect(delivery):
    sink(delivery)
    os._exit(73)
inbox=DurableInboundInbox(p["db"],crash_after_effect)
inbox.recover()
os._exit(74)
"""

@unittest.skipUnless(os.environ.get("HERMES_UNLIMITED_LIVE_KANBAN") == "1",
                     "set HERMES_UNLIMITED_LIVE_KANBAN=1 to run against real Hermes")
class LiveInboundToHermesAcceptance(unittest.TestCase):
    def test_verified_inbound_creates_exactly_one_real_hermes_task(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from identity_layer import ActorKind, IdentityLayer, JustYouAddressSpace, Protocol
        from identity_layer.immutable import ZERO_HASH, generate_signing_key, sign_state
        from identity_layer.inbound import InboundFrontDoor, VerifiedOrigin
        from protocol.authoritative_binding import AuthorityBinding, Ed25519Authority
        from registry.auth import ChallengeAuthenticator, sign_auth_challenge
        from registry.recovery import RecoveryStore
        from registry.server import RegistryHTTPServer
        from registry.session import SessionStore
        from registry.store import RegistryStore
        home = pathlib.Path(os.environ["HERMES_HOME"]).resolve()
        self.assertTrue(home.is_dir(), "isolated HERMES_HOME required")
        self.assertNotEqual(home, pathlib.Path.home() / ".hermes")
        hermes = os.environ["HERMES_UNLIMITED_HERMES_CLI"]
        self.assertTrue(pathlib.Path(hermes).is_file())

        with tempfile.TemporaryDirectory(prefix="justyou-inbound-live-") as root:
            state = pathlib.Path(root)
            db = str(state / "registry.sqlite")
            registry = RegistryStore(db)
            recovery = RecoveryStore(registry, db)
            sessions = SessionStore(registry, db)
            auth = ChallengeAuthenticator(registry)
            server = RegistryHTTPServer(("127.0.0.1", 0),
                                        registry, recovery, auth, sessions)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                recipient = "@dev-operator"
                sender = "@dev-supplier"
                profile = "devoperator"
                root_priv, root_pub = generate_signing_key("root", role="root")
                device_priv, device_pub = generate_signing_key("device", role="device")
                registry.publish(sign_state(
                    signers=(("root", root_priv),),
                    core_id="jy:dev:hermes-inbound-live", handle=recipient,
                    entity_kind="human", sequence=0,
                    previous_state_hash=ZERO_HASH,
                    active_keys=(root_pub, device_pub), signature_threshold=1,
                    continuity_ref="justyou-inbound-live"))
                challenge = auth.begin(recipient, "hermes-unlimited")
                proof = sign_auth_challenge(challenge, device_priv)
                token = sessions.issue(
                    auth.verify(challenge.challenge_id, "device", proof)).token

                signer = Ed25519Authority(
                    "authority-live", Ed25519PrivateKey.generate())
                now = datetime.now(timezone.utc)
                binding = signer.sign_binding(AuthorityBinding(
                    identity=recipient, version=1, carrier="hermes-profile",
                    endpoint=f"hermes-profile:{profile}", endpoint_key_id="device",
                    authority_key_id="authority-live",
                    valid_from=now - timedelta(minutes=1),
                    valid_until=now + timedelta(hours=1)))
                bindings_path = state / "bindings.json"
                bindings_path.write_text(json.dumps({
                    "bindings": [{**binding.unsigned_payload(),
                                  "signature": binding.signature}],
                    "announcements": []}))
                key_path = state / "authority.pub"
                key_path.write_text(signer.public_key_b64())
                bindings_path.chmod(0o600)
                key_path.chmod(0o600)
                resolver = load_resolver(
                    str(bindings_path), "authority-live", str(key_path))
                session_store = LoopbackSessionStore(
                    f"http://127.0.0.1:{server.server_port}")
                identity_evidence = JustYouVerifier(
                    session_store, resolver, profile, token).verify()
                self.assertTrue(identity_evidence["verified"], identity_evidence)
                self.assertEqual(identity_evidence["identity"], recipient)
                self.assertIs(identity_evidence["authority_granted"], False)
                self.assertFalse(JustYouVerifier(
                    session_store, resolver, profile, "invalid").verify()["verified"])

                identities = IdentityLayer()
                addresses = JustYouAddressSpace(identities)
                for address, kind in ((recipient, ActorKind.HUMAN),
                                      (sender, ActorKind.COMPANY)):
                    actor = identities.register_actor(kind)
                    addresses.claim(
                        address, actor.actor_id, f"continuity:{address}")
                addresses.bind_channel(sender, "dev-provider",
                                       "provider:test-supplier")
                frontdoor = InboundFrontDoor(
                    addresses, Protocol(identities, addresses=addresses))
                tenant = "devlive-" + uuid.uuid4().hex[:10]
                board = board_for("devprovider", tenant)
                created = subprocess.run(
                    [hermes, "kanban", "boards", "create", board],
                    capture_output=True, text=True, timeout=45, check=False)
                self.assertEqual(created.returncode, 0,
                                 created.stderr + created.stdout)
                kanban = HermesKanban(hermes=hermes, board=board)
                queued = []

                def deliver(message):
                    if message.recipient != identity_evidence["identity"]:
                        raise PermissionError("recipient not bound to session")
                    task = kanban.enqueue(
                        tenant=tenant, assignee=profile,
                        task_id="justyou-" + message.message_id,
                        title="Verified inbound: " + message.message_id,
                        body=message.text,
                        identity_evidence=identity_evidence)
                    queued.append(task)

                bridge = JustYouInboundBridge(frontdoor, deliver)
                origin = VerifiedOrigin(
                    "dev-provider", "provider:test-supplier",
                    "proof:trusted-dev-adapter")
                params = dict(origin=origin, recipient_address=recipient,
                              message_id="live-1", text="Live inbound message")
                accepted = bridge.receive(**params)
                self.assertEqual(
                    (accepted.sender, accepted.recipient), (sender, recipient))
                self.assertIs(accepted, bridge.receive(**params))
                self.assertEqual(len(queued), 1, "duplicate was enqueued twice")
                task = queued[0]
                self.assertEqual(task["status"], "TASK_QUEUED")
                observed = kanban.result(
                    tenant=tenant, assignee=profile,
                    task_id=task["task_id"])
                self.assertTrue(observed["found"], observed)
                self.assertFalse(observed["completed"], observed)

                for invalid in (
                    {**params, "origin": None},
                    {**params, "origin": VerifiedOrigin(
                        "dev-provider", "unrecognized", "proof")},
                    {**params, "recipient_address": "@unrecognized"},
                    {**params, "text": "Changed payload"}):
                    with self.assertRaises((PermissionError, KeyError,
                                            ValueError)):
                        bridge.receive(**invalid)
                self.assertEqual(len(queued), 1)
                # Authenticated webhook -> durable SQLite -> native Hermes.
                webhook_tasks = []
                def deliver_durable(delivery):
                    message = delivery.message
                    if message.recipient != identity_evidence["identity"]:
                        raise PermissionError("recipient not bound to session")
                    task = kanban.enqueue(
                        tenant=tenant, assignee=profile,
                        task_id="inbound-" + delivery.key[:32],
                        title="Durable verified inbound: " + message.message_id,
                        body=message.text, identity_evidence=identity_evidence)
                    webhook_tasks.append(task)
                inbox_path = str(state / "inbound.sqlite")
                inbox = DurableInboundInbox(inbox_path, deliver_durable)
                secret = b"test-isolated-webhook-secret-32bytes-long"
                now_ts = "1700000000"
                payload = json.dumps({
                    "endpoint": "provider:test-supplier",
                    "message_id": "live-webhook-1", "recipient": recipient,
                    "text": "Durable live inbound"}).encode()
                signature = hmac.new(secret, now_ts.encode() + b"." + payload,
                                     hashlib.sha256).hexdigest()
                webhook = HMACWebhookIngress(
                    secret=secret, channel="dev-provider",
                    endpoint="provider:test-supplier", frontdoor=frontdoor,
                    inbox=inbox, clock=lambda: 1700000000)
                first = webhook.receive(
                    body=payload, timestamp=now_ts, signature_hex=signature)
                self.assertEqual(inbox.status(first.key), "delivered")
                inbox.close()
                restarted = DurableInboundInbox(inbox_path, deliver_durable)
                webhook_after_restart = HMACWebhookIngress(
                    secret=secret, channel="dev-provider",
                    endpoint="provider:test-supplier", frontdoor=frontdoor,
                    inbox=restarted, clock=lambda: 1700000000)
                self.assertEqual(first.key, webhook_after_restart.receive(
                    body=payload, timestamp=now_ts,
                    signature_hex=signature).key)
                self.assertEqual(len(webhook_tasks), 1)
                self.assertEqual(restarted.recover(), 0)
                observed_webhook = kanban.result(
                    tenant=tenant, assignee=profile,
                    task_id=webhook_tasks[0]["task_id"])
                self.assertTrue(observed_webhook["found"], observed_webhook)
                restarted.close()
                # Crash actual child process after native Hermes task creation
                # but before SQLite acknowledgement; verify one task on retry.
                from unlimited.justyou_inbound import AcceptedInbound
                crash_message = AcceptedInbound(
                    sender=sender, recipient=recipient,
                    message_id="crash-1", proof_ref="signed-proof",
                    text="Crash recovery effect")
                crash_db = str(state / "crash-inbox.sqlite")
                def pending_only(_delivery):
                    raise RuntimeError("persist pending before crash")
                pending = DurableInboundInbox(crash_db, pending_only)
                with self.assertRaises(RuntimeError):
                    pending.accept(channel="dev-provider",
                                   endpoint="provider:test-supplier",
                                   message=crash_message)
                crash_key = pending._key("dev-provider",
                                         "provider:test-supplier", "crash-1")
                self.assertEqual(pending.status(crash_key), "pending")
                pending.close()
                crash_code = CRASH_CHILD_CODE
                crash_args = dict(hermes=hermes, board=board,
                                  tenant=tenant, assignee=profile,
                                  identity=identity_evidence, db=crash_db)
                crashed = subprocess.run(
                    [sys.executable, "-c", crash_code,
                     json.dumps(crash_args)],
                    capture_output=True, text=True, timeout=90)
                self.assertEqual(crashed.returncode, 73,
                                 crashed.stderr + crashed.stdout)
                stable_sink = HermesInboundSink(
                    kanban, tenant, profile, identity_evidence)
                recovered_crash = DurableInboundInbox(crash_db, stable_sink)
                self.assertEqual(recovered_crash.status(crash_key), "pending")
                self.assertEqual(recovered_crash.recover(), 1)
                self.assertEqual(recovered_crash.status(crash_key), "delivered")
                self.assertEqual(recovered_crash.recover(), 0)
                observed_after_crash = kanban._invoke(
                    ["list", "--tenant", tenant, "--json"])
                matching = [item for item in observed_after_crash
                            if item.get("tenant") == tenant
                            and item.get("title") == "Verified inbound: crash-1"]
                self.assertEqual(len(matching), 1, matching)
                recovered_crash.close()
                telegram_live_status = "NOT_RUN"
                if os.environ.get("HERMES_UNLIMITED_LIVE_TELEGRAM") == "1":
                    # The actual user message must come from authenticated
                    # Telegram Bot API, not a fixture or fabricated update.
                    env_file = pathlib.Path.home() / ".hermes/.env"
                    settings = {}
                    for line in env_file.read_text().splitlines():
                        if line.startswith("TELEGRAM_") and "=" in line:
                            key, value = line.split("=", 1)
                            settings[key] = value.strip().strip('"').strip("'")
                    token = settings["TELEGRAM_BOT_TOKEN"]
                    chat = int(settings["TELEGRAM_HOME_CHANNEL"])
                    allowed = {int(x.strip()) for x in
                               settings["TELEGRAM_ALLOWED_USERS"].split(",")
                               if x.strip().isdigit()}
                    target_id = int(os.environ.get(
                        "HERMES_UNLIMITED_TELEGRAM_MESSAGE_ID", "31057"))
                    request_url = ("https://api.telegram.org/bot" + token +
                                   "/getUpdates?limit=30&timeout=0")
                    with urllib.request.urlopen(request_url, timeout=20) as response:
                        data = json.load(response)
                    self.assertTrue(data.get("ok"), "Telegram Bot API rejected")
                    matching_updates = [update for update in data["result"]
                        if update.get("message", {}).get("message_id") == target_id
                        and update["message"].get("chat", {}).get("id") == chat]
                    self.assertEqual(len(matching_updates), 1,
                                     "original Telegram message not available")
                    update = matching_updates[0]
                    sender_id = update["message"]["from"]["id"]
                    self.assertIn(sender_id, allowed)
                    # Bind authenticated Telegram endpoint to JustYou sender.
                    addresses.bind_channel(sender, "telegram", str(sender_id))
                    telegram_db = str(state / "telegram-live-inbox.sqlite")
                    telegram_inbox = DurableInboundInbox(
                        telegram_db, HermesInboundSink(
                            kanban, tenant, profile, identity_evidence))
                    telegram_adapter = TelegramInboundAdapter(
                        chat_id=chat, allowed_sender_ids=allowed,
                        recipient=recipient, frontdoor=frontdoor,
                        inbox=telegram_inbox)
                    delivery = telegram_adapter.receive_update(update)
                    self.assertEqual(telegram_inbox.status(delivery.key),
                                     "delivered")
                    telegram_inbox.close()
                    restarted_telegram = DurableInboundInbox(
                        telegram_db, HermesInboundSink(
                            kanban, tenant, profile, identity_evidence))
                    restarted_adapter = TelegramInboundAdapter(
                        chat_id=chat, allowed_sender_ids=allowed,
                        recipient=recipient, frontdoor=frontdoor,
                        inbox=restarted_telegram)
                    self.assertEqual(restarted_adapter.receive_update(update).key,
                                     delivery.key)
                    self.assertEqual(restarted_telegram.recover(), 0)
                    matching_tasks = [item for item in kanban._invoke(
                        ["list", "--tenant", tenant, "--json"])
                        if item.get("title") ==
                        "Verified inbound: " + str(target_id)]
                    self.assertEqual(len(matching_tasks), 1,
                                     "Telegram Hermes task not uniquely observed")
                    restarted_telegram.close()
                    telegram_live_status = "PASS"
                print(json.dumps({
                    "live_inbound": "PASS", "signed_session": "PASS",
                    "durable_webhook_to_real_hermes": "PASS",
                    "crash_after_effect_recovery": "PASS",
                    "real_hermes_kanban": "PASS", "duplicate": "BLOCKED",
                    "invalid_origins": "BLOCKED",
                    "external_provider": telegram_live_status,
                    "model_execution": "NOT_RUN",
                    "isolated_home": True,
                    "task_status": observed["status"],
                }, sort_keys=True))
            finally:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()
                sessions.close()
                recovery.close()
                registry.close()


if __name__ == "__main__":
    unittest.main()
