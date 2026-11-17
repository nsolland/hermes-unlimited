"""Ember -> Hermes Unlimited intake with trusted JustYou and room-scoped routing.

Ember payloads are untrusted. The host supplies room mapping and JustYou verifier.
This adapter queues a service request; it does not execute Hermes tasks or send
messages back to Ember. No HTTP listener is exposed by this module.
"""
from dataclasses import dataclass
from typing import Mapping
import hashlib
import hmac
import json
from .runtime import UnverifiedIdentity


@dataclass(frozen=True)
class RoomRoute:
    provider: str
    tenant: str
    company: str
    service: str
    identity: str


class EmberBridge:
    def __init__(self, provider_store, justyou_verifier, room_routes: Mapping[str, RoomRoute], gateway_key: bytes):
        self.store = provider_store
        self.verifier = justyou_verifier
        self.routes = dict(room_routes)
        if not isinstance(gateway_key, bytes) or len(gateway_key) < 32:
            raise ValueError("TRUSTED_GATEWAY_KEY_REQUIRED")
        self._gateway_key = gateway_key

    def intake(self, payload: dict, gateway_signature: str = "") -> dict:
        # This signature must come from an independently authenticated local
        # ingress. Ember does not natively sign these outgoing bot webhooks.
        # A shared key alone cannot authenticate the original Ember sender.
        if not isinstance(payload, dict):
            raise ValueError("EMBER_PAYLOAD_INVALID")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(canonical) > 16384:
            raise ValueError("EMBER_PAYLOAD_OVERSIZE")
        expected = hmac.new(self._gateway_key, canonical, hashlib.sha256).hexdigest()
        if not isinstance(gateway_signature, str) or not hmac.compare_digest(expected, gateway_signature):
            raise UnverifiedIdentity("EMBER_GATEWAY_UNVERIFIED")
        room = payload.get("room")
        message = payload.get("message")
        user = payload.get("user")
        if not isinstance(room, dict) or not isinstance(message, dict) or not isinstance(user, dict):
            raise ValueError("EMBER_PAYLOAD_INVALID")
        room_id, message_id, plain, user_id = (
            room.get("id"), message.get("id"), (message.get("body") or {}).get("plain")
            if isinstance(message.get("body"), dict) else None, user.get("id")
        )
        if not all(isinstance(v, str) and v for v in (room_id, message_id, user_id)):
            raise ValueError("EMBER_IDENTIFIERS_INVALID")
        if not isinstance(plain, str) or not plain.strip() or len(plain) > 8192:
            raise ValueError("EMBER_TEXT_INVALID")
        route = self.routes.get(room_id)
        if route is None:
            raise UnverifiedIdentity("EMBER_ROOM_UNMAPPED")
        # Verification is provided by trusted Hermes host, not from webhook fields.
        if not self.verifier.authorize_provider_tenant(route.provider, route.tenant, route.identity):
            raise UnverifiedIdentity("JUSTYOU_IDENTITY_NOT_VERIFIED")
        # Correlation key is derived from configured room and original message id.
        # Input is escaped into a safe fixed length digest to avoid ID grammar ambiguity.
        request_id = "ember-" + hashlib.sha256(
            (room_id + "\x00" + message_id).encode("utf-8")).hexdigest()[:32]
        return self.store.request_service(
            route.provider, route.tenant, route.company, request_id,
            route.service, {"source": "ember", "room_id": room_id,
                            "message_id": message_id, "user_id": user_id,
                            "text": plain}, route.identity)

    def submit_to_hermes(self, payload: dict, gateway_signature: str, dispatch_handler) -> dict:
        """Queue via the registry, then call Hermes' existing trusted dispatch tool.

        Host must inject the actual registered unlimited_service_dispatch handler.
        No API key, tenant or execution authority is accepted from the message.
        """
        if not callable(dispatch_handler):
            raise TypeError("TRUSTED_DISPATCH_REQUIRED")
        queued = self.intake(payload, gateway_signature)
        route = self.routes[payload["room"]["id"]]
        response = dispatch_handler({"company_id": route.company, "request_id": queued["request"]})
        if not isinstance(response, str):
            raise RuntimeError("HERMES_DISPATCH_INVALID")
        try:
            result = json.loads(response)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("HERMES_DISPATCH_INVALID") from exc
        if not isinstance(result, dict) or result.get("ok") is False:
            return {"request": queued["request"], "state": "queued",
                    "executed": False, "dispatch_pending": True}
        if result.get("request") != queued["request"] or result.get("executed") is not False:
            raise RuntimeError("HERMES_DISPATCH_UNVERIFIED")
        if result.get("state") not in ("queued", "running"):
            raise RuntimeError("HERMES_DISPATCH_UNVERIFIED")
        return result
