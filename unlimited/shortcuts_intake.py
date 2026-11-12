"""Hermes Shortcuts -> Hermes Unlimited scoped task intake.

The upstream hermes-shortcuts plugin owns HTTPS, authentication and media parsing.
This adapter is invoked only AFTER host-authenticated identity and JustYou
verification. It does not expose an HTTP listener or accept scope from the phone.
"""

import json
import re
from dataclasses import dataclass
from typing import Callable

from .hermes_kanban import board_for

_ALLOWED = frozenset({"ask", "auto", "summarize", "remember", "remind", "post",
                      "receipt", "whiteboard", "document", "event"})
_EVENT_NAMES = frozenset({"arrived_home", "arrived_office", "alarm_off", "charger_connected"})
_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FORBIDDEN = frozenset({"tenant", "tenant_id", "provider", "provider_id", "company_id",
                        "assignee", "profile", "identity", "identity_evidence", "tools",
                        "toolsets", "command", "execute", "authority", "url_token"})


@dataclass(frozen=True)
class TrustedMobileScope:
    provider_id: str
    tenant_id: str
    profile: str
    identity_evidence: dict

    def validate(self):
        board_for(self.provider_id, self.tenant_id)
        ev = self.identity_evidence
        if (not isinstance(ev, dict) or ev.get("verified") is not True
                or ev.get("authority_granted") is not False
                or ev.get("profile") != self.profile
                or not isinstance(ev.get("binding_digest"), str)
                or not ev["binding_digest"]):
            raise PermissionError("JUSTYOU_PROFILE_NOT_VERIFIED")
        if not isinstance(self.profile, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", self.profile):
            raise ValueError("PROFILE_INVALID")


def enqueue_shortcut(payload: dict, *, scope: TrustedMobileScope,
                     kanban_factory: Callable, max_body_bytes: int = 8192) -> dict:
    """Submit a safe mobile intent; no execution or external publish here.

    scope MUST come from the host's authenticated JustYou context, never payload.
    kanban_factory constructs the existing HermesKanban(board=...).
    """
    if not isinstance(scope, TrustedMobileScope):
        raise PermissionError("TRUSTED_SCOPE_REQUIRED")
    scope.validate()
    if not isinstance(payload, dict) or _FORBIDDEN.intersection(payload):
        raise ValueError("MOBILE_PAYLOAD_INVALID")
    if set(payload) - {"request_id", "action", "text", "url", "event"}:
        raise ValueError("MOBILE_FIELDS_UNSUPPORTED")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
        raise ValueError("REQUEST_ID_REQUIRED")
    action = payload.get("action", "ask")
    if action not in _ALLOWED:
        raise ValueError("ACTION_NOT_ALLOWED")
    if action == "event" and payload.get("event") not in _EVENT_NAMES:
        raise ValueError("EVENT_NOT_ALLOWED")
    if action != "event" and "event" in payload:
        raise ValueError("UNEXPECTED_EVENT")
    content = payload.get("text", "")
    url = payload.get("url", "")
    if not isinstance(content, str) or not isinstance(url, str):
        raise ValueError("CONTENT_INVALID")
    if url and (len(url) > 2048 or not url.startswith("https://") or any(c.isspace() for c in url)):
        raise ValueError("URL_INVALID")
    if action != "event" and not (content.strip() or url):
        raise ValueError("EMPTY_INTENT")
    body = json.dumps({"origin": "hermes-shortcuts", "action": action,
                       "text": content, "url": url,
                       "event": payload.get("event") if action == "event" else None},
                      ensure_ascii=False, separators=(",", ":"))
    if len(body.encode("utf-8")) > max_body_bytes:
        raise ValueError("BODY_TOO_LARGE")
    board = board_for(scope.provider_id, scope.tenant_id)
    response = kanban_factory(board=board).enqueue(
        tenant=scope.tenant_id, assignee=scope.profile, task_id=request_id,
        title="Mobile shortcut: " + action, body=body,
        identity_evidence=scope.identity_evidence)
    if response.get("status") != "TASK_QUEUED" or not response.get("task_id"):
        raise RuntimeError("TASK_NOT_CONFIRMED")
    return {"accepted": True, "status": "queued", "task_id": response["task_id"],
            "source": "hermes-shortcuts", "executed": False}
