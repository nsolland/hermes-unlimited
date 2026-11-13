"""Authenticated webhook ingress, with provider-scoped HMAC proof.

Not a Telegram/WhatsApp/email adapter: requires a provider that can sign the
exact request body with a provisioned per-channel shared secret.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Callable

from .justyou_durable_inbox import DurableInboundInbox, Delivery


class HMACWebhookIngress:
    def __init__(self, *, secret: bytes, channel: str, endpoint: str,
                 frontdoor, inbox: DurableInboundInbox,
                 max_skew_seconds: int = 300,
                 clock: Callable[[], float] = time.time):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("strong HMAC secret required")
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("channel required")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("verified endpoint required")
        if not callable(getattr(frontdoor, "accept", None)):
            raise TypeError("canonical JustYou frontdoor required")
        if not isinstance(inbox, DurableInboundInbox):
            raise TypeError("durable inbox required")
        if not 1 <= max_skew_seconds <= 900:
            raise ValueError("invalid timestamp window")
        self._secret = secret
        self._channel = channel
        self._endpoint = endpoint
        self._frontdoor = frontdoor
        self._inbox = inbox
        self._skew = max_skew_seconds
        self._clock = clock

    def receive(self, *, body: bytes, timestamp: str,
                signature_hex: str) -> Delivery:
        if not isinstance(body, bytes) or not 0 < len(body) <= 65536:
            raise ValueError("invalid request body")
        if not isinstance(timestamp, str) or not timestamp.isascii() or (
            not timestamp.isdecimal() or len(timestamp) > 12
        ):
            raise PermissionError("invalid timestamp")
        if abs(self._clock() - int(timestamp)) > self._skew:
            raise PermissionError("expired webhook")
        if not isinstance(signature_hex, str) or len(signature_hex) != 64:
            raise PermissionError("invalid signature")
        signed = timestamp.encode() + b"." + body
        expected = hmac.new(self._secret, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature_hex):
            raise PermissionError("webhook signature mismatch")
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or set(payload) != {
                "endpoint", "message_id", "recipient", "text"
            }:
                raise ValueError("unexpected payload")
            endpoint = payload["endpoint"]
            message_id = payload["message_id"]
            recipient = payload["recipient"]
            text = payload["text"]
            if not all(isinstance(v, str) and v.strip()
                       for v in (endpoint, message_id, recipient, text)):
                raise ValueError("invalid message fields")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid webhook JSON") from exc

        # Endpoint is bound to the configured secret, never trusted from body.
        if endpoint != self._endpoint:
            raise PermissionError("endpoint credential mismatch")

        # Import the private JustYou type only AFTER authentication.
        from identity_layer.inbound import VerifiedOrigin

        proof = hashlib.sha256(body).hexdigest()
        origin = VerifiedOrigin(self._channel, endpoint, proof)
        envelope = self._frontdoor.accept(
            origin=origin, recipient_address=recipient,
            message_id=message_id, text=text)
        from .justyou_inbound import AcceptedInbound
        return self._inbox.accept(
            channel=self._channel, endpoint=endpoint,
            message=AcceptedInbound(
                sender=envelope.sender_address,
                recipient=envelope.recipient_address,
                message_id=envelope.provenance["message_id"],
                proof_ref=envelope.provenance["proof_ref"],
                text=envelope.payload["text"]))
