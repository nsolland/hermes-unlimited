"""Ghost Admin API draft and readback client, using only Python stdlib.

Self-contained adapter to upstream TryGhost/Ghost. No Ghost code is bundled.
The origin and admin key are supplied by a trusted host, not end-user tool args.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

_ID = re.compile(r"^[A-Za-z0-9]+$")
_POST_ID = re.compile(r"^[a-f0-9]{24}$", re.I)


class GhostError(RuntimeError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def admin_jwt(admin_key: str, *, now: int | None = None) -> str:
    """Generate short-lived Ghost Admin API HS256 JWT from id:hexsecret."""
    if not isinstance(admin_key, str) or admin_key.count(":") != 1:
        raise ValueError("Ghost key must be id:hexsecret")
    key_id, secret = admin_key.split(":")
    if not _ID.fullmatch(key_id) or not secret or len(secret) % 2:
        raise ValueError("Invalid Ghost key")
    try:
        signing_key = bytes.fromhex(secret)
    except ValueError:
        raise ValueError("Invalid Ghost key") from None
    if len(signing_key) < 16:
        raise ValueError("Ghost key secret is too short")
    timestamp = int(time.time()) if now is None else int(now)
    header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {"iat": timestamp, "exp": timestamp + 300, "aud": "/admin/"}
    sign_input = ".".join((_b64(json.dumps(item, separators=(",", ":"), sort_keys=True).encode())
                           for item in (header, payload)))
    signature = hmac.new(signing_key, sign_input.encode(), hashlib.sha256).digest()
    return sign_input + "." + _b64(signature)


class GhostAdmin:
    def __init__(self, origin: str, key: str, *, timeout: float = 15, opener=urlopen):
        parsed = urlsplit(origin)
        if (parsed.scheme not in ("https", "http") or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or parsed.fragment or
                parsed.path not in ("", "/") or
                (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"))):
            raise ValueError("Origin must be a bare HTTP(S) URL")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
            raise ValueError("timeout must be between 0 and 120 seconds")
        admin_jwt(key, now=1)  # Validate key without exposing it.
        self.origin, self.key, self.timeout, self.opener = origin.rstrip("/"), key, timeout, opener

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = self.origin + "/ghost/api/admin/" + path
        data = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        req = Request(url, data=data, method=method, headers={
            "Authorization": "Ghost " + admin_jwt(self.key),
            "Content-Type": "application/json",
            "Accept-Version": "v5.0",
        })
        try:
            with self.opener(req, timeout=self.timeout) as response:
                content = response.read(2_000_001)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise GhostError("Ghost request failed") from exc
        if len(content) > 2_000_000:
            raise GhostError("Ghost response exceeds bound")
        try:
            body = json.loads(content)
        except (ValueError, UnicodeError):
            raise GhostError("Ghost returned invalid JSON") from None
        if not isinstance(body, dict):
            raise GhostError("Ghost returned an invalid body")
        return body

    def create_draft(self, title: str, html: str) -> dict:
        if (not isinstance(title, str) or not 1 <= len(title.strip()) <= 200 or
                not isinstance(html, str) or not 1 <= len(html) <= 100_000):
            raise ValueError("Title and HTML are required within configured bounds")
        result = self._request("POST", "posts/?source=html",
                               {"posts": [{"title": title, "html": html, "status": "draft"}]})
        posts = result.get("posts")
        if not isinstance(posts, list) or len(posts) != 1 or not isinstance(posts[0], dict):
            raise GhostError("Ghost did not acknowledge a draft")
        post = posts[0]
        if not isinstance(post.get("id"), str) or not _POST_ID.fullmatch(post["id"]):
            raise GhostError("Ghost returned invalid post ID")
        if post.get("status") != "draft":
            raise GhostError("Ghost returned unexpected publication status")
        return {"id": post["id"], "status": "draft", "submitted": True, "readback_verified": False}

    def read_post(self, post_id: str) -> dict:
        if not isinstance(post_id, str) or not _POST_ID.fullmatch(post_id):
            raise ValueError("Invalid post ID")
        result = self._request("GET", "posts/" + quote(post_id, safe="") + "/")
        posts = result.get("posts")
        if not isinstance(posts, list) or len(posts) != 1 or not isinstance(posts[0], dict):
            raise GhostError("Ghost post readback failed")
        post = posts[0]
        if post.get("id") != post_id:
            raise GhostError("Ghost readback identity mismatch")
        return {"id": post["id"], "status": post.get("status"),
                "title": post.get("title"), "readback_verified": True}
