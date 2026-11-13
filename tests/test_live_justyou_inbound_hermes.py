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
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone


from unlimited.hermes_kanban import HermesKanban, board_for
from unlimited.justyou import JustYouVerifier
from unlimited.justyou_host import LoopbackSessionStore, load_resolver
from unlimited.justyou_inbound import JustYouInboundBridge


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
                print(json.dumps({
                    "live_inbound": "PASS", "signed_session": "PASS",
                    "real_hermes_kanban": "PASS", "duplicate": "BLOCKED",
                    "invalid_origins": "BLOCKED",
                    "external_provider": "NOT_TESTED",
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
