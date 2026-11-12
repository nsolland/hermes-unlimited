"""Read-only Discord channel adapter for one Hermes Unlimited profile.

A bot must be installed by a Discord server administrator. No user tokens,
DM access, gateway connection or channel discovery are used.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHANNEL_ID = re.compile(r"^[0-9]{17,22}$")
API = "https://discord.com/api/v10"


def read_messages(*, bot_token, channel_id, allowed_channels, limit=20, opener=urlopen):
    """Fetch messages from an explicitly allowed channel; never expose token."""
    allowed = {c.strip() for c in allowed_channels.split(",") if CHANNEL_ID.fullmatch(c.strip())}
    if not bot_token or not allowed:
        return {"ok": False, "reason": "DISCORD_NOT_CONFIGURED"}
    if not isinstance(channel_id, str) or not CHANNEL_ID.fullmatch(channel_id):
        return {"ok": False, "reason": "INVALID_CHANNEL"}
    if channel_id not in allowed:
        return {"ok": False, "reason": "CHANNEL_NOT_ALLOWED"}
    if type(limit) is not int or not 1 <= limit <= 50:
        return {"ok": False, "reason": "INVALID_LIMIT"}
    request = Request(
        f"{API}/channels/{channel_id}/messages?limit={limit}",
        headers={"Authorization": "Bot " + bot_token, "User-Agent": "HermesUnlimitedDiscord/1.0"},
        method="GET",
    )
    try:
        with opener(request, timeout=8) as response:
            payload = json.load(response)
    except HTTPError as exc:
        return {"ok": False, "reason": "DISCORD_HTTP_ERROR", "status": exc.code}
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        return {"ok": False, "reason": "DISCORD_UNAVAILABLE"}
    if not isinstance(payload, list):
        return {"ok": False, "reason": "DISCORD_INVALID_RESPONSE"}
    messages = []
    for item in payload[:limit]:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        author = author if isinstance(author, dict) else {}
        messages.append({
            "id": str(item.get("id", "")),
            "channel_id": channel_id,
            "author_id": str(author.get("id", "")),
            "author_name": str(author.get("username", ""))[:128],
            "content": str(item.get("content", ""))[:4000],
            "timestamp": str(item.get("timestamp", "")),
        })
    return {"ok": True, "channel_id": channel_id, "messages": messages, "count": len(messages)}


def register_discord_tools(ctx, scoped_secret, scoped_identity):
    schema = {
        "name": "unlimited_discord_read_channel",
        "description": "Read recent messages from a preapproved Discord channel using a scoped bot; no sending or DMs.",
        "parameters": {"type": "object", "properties": {
            "channel_id": {"type": "string", "pattern": "^[0-9]{17,22}$"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            "required": ["channel_id"], "additionalProperties": False},
    }

    def handler(args=None, **_kwargs):
        if not isinstance(args, dict) or set(args) - {"channel_id", "limit"} or "channel_id" not in args:
            return json.dumps({"ok": False, "reason": "INVALID_ARGUMENTS"})
        try:
            scoped_identity()
        except (PermissionError, RuntimeError, ValueError):
            return json.dumps({"ok": False, "reason": "IDENTITY_NOT_VERIFIED"})
        result = read_messages(
            bot_token=scoped_secret("HERMES_UNLIMITED_DISCORD_BOT_TOKEN", ""),
            allowed_channels=scoped_secret("HERMES_UNLIMITED_DISCORD_ALLOWED_CHANNELS", ""),
            channel_id=args["channel_id"], limit=args.get("limit", 20),
        )
        return json.dumps(result, sort_keys=True)

    ctx.register_tool(name=schema["name"], toolset="hermes_unlimited", schema=schema, handler=handler)
