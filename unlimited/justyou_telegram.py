"""Telegram Bot API polling adapter for JustYou receive-only ingress.

Only updates retrieved using the authenticated Bot API token are accepted.
The Telegram sender ID must be explicitly allowlisted; chat scope is pinned.
Never derive identity or permissions from the text of a message.
"""
from __future__ import annotations

import hashlib
import json
from typing import Callable

from identity_layer.inbound import VerifiedOrigin
from .justyou_durable_inbox import DurableInboundInbox, Delivery
from .justyou_inbound import AcceptedInbound


class TelegramInboundAdapter:
    def __init__(self, *, chat_id: int, allowed_sender_ids: set[int],
                 recipient: str, frontdoor, inbox: DurableInboundInbox):
        if type(chat_id) is not int or not chat_id:
            raise ValueError("chat ID required")
        if not allowed_sender_ids or any(type(i) is not int or i <= 0
                                         for i in allowed_sender_ids):
            raise ValueError("sender allowlist required")
        if not isinstance(recipient, str) or not recipient.startswith("@"):
            raise ValueError("JustYou recipient required")
        self.chat_id = chat_id
        self.allowed_sender_ids = frozenset(allowed_sender_ids)
        self.recipient = recipient
        self.frontdoor = frontdoor
        self.inbox = inbox

    def receive_update(self, update: dict) -> Delivery:
        if not isinstance(update, dict):
            raise ValueError("invalid update")
        msg = update.get("message")
        if not isinstance(msg, dict) or type(update.get("update_id")) is not int:
            raise ValueError("unsupported update")
        chat = msg.get("chat", {})
        sender = msg.get("from", {})
        if (type(chat.get("id")) is not int or
            chat["id"] != self.chat_id or
            type(sender.get("id")) is not int or
            sender["id"] not in self.allowed_sender_ids or
            sender.get("is_bot") is not False):
            raise PermissionError("untrusted Telegram sender or chat")
        text = msg.get("text")
        message_id = msg.get("message_id")
        if (not isinstance(text, str) or not text.strip() or
            type(message_id) is not int or message_id <= 0):
            raise ValueError("unsupported Telegram message")
        endpoint = str(sender["id"])
        # Proof ties accepted content to the authenticated Bot API response.
        # Telegram polling authenticates the bot API transport, not an
        # independently signed update. Do not treat as cryptographic
        # evidence of the individual human sender.
        proof_ref = hashlib.sha256(json.dumps(
            [update["update_id"], self.chat_id, sender["id"],
             message_id, text], ensure_ascii=False,
            separators=(",", ":")).encode()).hexdigest()
        envelope = self.frontdoor.accept(
            origin=VerifiedOrigin("telegram", endpoint, proof_ref),
            recipient_address=self.recipient,
            message_id=str(message_id), text=text)
        return self.inbox.accept(
            channel="telegram", endpoint=endpoint,
            message=AcceptedInbound(
                sender=envelope.sender_address,
                recipient=envelope.recipient_address,
                message_id=envelope.provenance["message_id"],
                proof_ref=envelope.provenance["proof_ref"],
                text=envelope.payload["text"]))
