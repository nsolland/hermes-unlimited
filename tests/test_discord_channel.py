import io
import json
import unittest
from urllib.error import HTTPError
from unlimited.discord_channel import read_messages, register_discord_tools

ID = "123456789012345678"
OTHER = "987654321098765432"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class DiscordTests(unittest.TestCase):
    def test_read_allowlisted_and_secret_not_returned(self):
        called = []

        def opener(request, timeout):
            called.append((request.full_url, request.get_header("Authorization"), timeout))
            return FakeResponse(json.dumps([{"id": "2", "author": {"id": "3", "username": "user"},
                                             "content": "hello", "timestamp": "now"}]).encode())
        result = read_messages(bot_token="secret", channel_id=ID, allowed_channels=ID, opener=opener)
        self.assertTrue(result["ok"])
        self.assertEqual(result["messages"][0]["content"], "hello")
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(called[0][0], f"https://discord.com/api/v10/channels/{ID}/messages?limit=20")

    def test_blocks_non_allowlisted_without_network(self):
        result = read_messages(bot_token="secret", channel_id=OTHER, allowed_channels=ID,
                               opener=lambda *_: self.fail("network"))
        self.assertEqual(result["reason"], "CHANNEL_NOT_ALLOWED")

    def test_missing_token_fail_closed(self):
        self.assertEqual(read_messages(bot_token="", channel_id=ID, allowed_channels=ID)["reason"],
                         "DISCORD_NOT_CONFIGURED")

    def test_rejects_invalid_parameters(self):
        for limit in (0, 51, True, "5"):
            self.assertEqual(read_messages(bot_token="secret", channel_id=ID,
                                           allowed_channels=ID, limit=limit)["reason"], "INVALID_LIMIT")
        self.assertEqual(read_messages(bot_token="secret", channel_id="../users/@me",
                                       allowed_channels=ID)["reason"], "INVALID_CHANNEL")

    def test_registration_requires_identity(self):
        class Ctx:
            def register_tool(self, **kwargs):
                self.handler = kwargs["handler"]
        ctx = Ctx()
        register_discord_tools(
            ctx,
            lambda name, default="": {"HERMES_UNLIMITED_DISCORD_BOT_TOKEN": "secret",
                                      "HERMES_UNLIMITED_DISCORD_ALLOWED_CHANNELS": ID}.get(name, default),
            lambda: (_ for _ in ()).throw(PermissionError()),
        )
        self.assertEqual(json.loads(ctx.handler({"channel_id": ID}))["reason"],
                         "IDENTITY_NOT_VERIFIED")

    def test_http_errors_sanitized(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 403, "no", None, None)
        result = read_messages(bot_token="secret", channel_id=ID,
                               allowed_channels=ID, opener=opener)
        self.assertEqual(result["status"], 403)
        self.assertNotIn("secret", json.dumps(result))
