"""Minimal read-only Gmail API adapter for a host-owned authenticated Gmail client.

The Hermes host resolves OAuth and verified account/tenant binding before building
this adapter. No credentials, account selection, sends, drafts or deletes here.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

_MESSAGE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class GmailJuniorReadAdapter:
    def __init__(self, authenticated_gmail_service: Any):
        if authenticated_gmail_service is None or not callable(getattr(authenticated_gmail_service, "users", None)):
            raise PermissionError("GMAIL_VERIFIED_HOST_SERVICE_REQUIRED")
        self._service = authenticated_gmail_service

    def __call__(self, operation: str, arguments: Mapping[str, str]) -> dict:
        if operation == "list_messages":
            query = arguments.get("query") if isinstance(arguments, dict) else None
            if not isinstance(query, str) or not query.strip() or len(query) > 256:
                raise ValueError("GMAIL_QUERY_INVALID")
            # API returns message identifiers, not full bodies. Constrain page size.
            result = (self._service.users().messages()
                      .list(userId="me", q=query, maxResults=20).execute())
            if not isinstance(result, dict):
                raise RuntimeError("GMAIL_UNEXPECTED_RESPONSE")
            rows = result.get("messages", [])
            if not isinstance(rows, list):
                raise RuntimeError("GMAIL_UNEXPECTED_RESPONSE")
            return {"messages": [{"id": m.get("id"), "threadId": m.get("threadId")}
                                  for m in rows[:20] if isinstance(m, dict) and
                                  isinstance(m.get("id"), str)],
                    "resultSizeEstimate": result.get("resultSizeEstimate", 0)}
        if operation == "get_message":
            mid = arguments.get("message_id") if isinstance(arguments, dict) else None
            if not isinstance(mid, str) or not _MESSAGE_ID.fullmatch(mid):
                raise ValueError("GMAIL_MESSAGE_ID_INVALID")
            result = (self._service.users().messages().get(
                userId="me", id=mid, format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]).execute())
            if not isinstance(result, dict):
                raise RuntimeError("GMAIL_UNEXPECTED_RESPONSE")
            headers = result.get("payload", {}).get("headers", [])
            allowed = {"from", "to", "subject", "date"}
            return {"id": result.get("id"), "threadId": result.get("threadId"),
                    "snippet": str(result.get("snippet", ""))[:2048],
                    "labelIds": result.get("labelIds", [])[:30],
                    "headers": {h["name"].lower(): str(h.get("value", ""))[:512]
                                for h in headers if isinstance(h, dict) and
                                isinstance(h.get("name"), str) and
                                h["name"].lower() in allowed}}
        raise PermissionError("GMAIL_READ_ONLY_OPERATION_REQUIRED")
