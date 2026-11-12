# Discord read-only adapter (public core)

The Hermes Unlimited native tool `unlimited_discord_read_channel` reads up to 50
recent messages from an explicitly allowlisted text channel. It does **not**
send messages, join servers, search other channels, read DMs, or invite bots.

## Administrator setup

1. Create a Discord application and bot at https://discord.com/developers/applications.
2. Have an administrator of the target server install the bot using OAuth2
   `bot` scope with only `View Channel` and `Read Message History`
   permissions in the desired channel. Discord may require Message Content
   privileged intent to make non-mention message content accessible.
3. Enable Discord Developer Mode and copy the numeric channel ID.
4. In the **Hermes profile-scoped secret store** configure:
   - `HERMES_UNLIMITED_DISCORD_BOT_TOKEN` (secret; never commit or paste into chat)
   - `HERMES_UNLIMITED_DISCORD_ALLOWED_CHANNELS` (comma-separated numeric IDs)
   - Existing mandatory `HERMES_UNLIMITED_TENANT_ID` and JustYou identity binding.
5. Invoke `unlimited_discord_read_channel` with `{"channel_id":"<approved-id>","limit":20}`.

There is no browser-user credential scraping or automated server invitation.
Missing credentials or identity fail closed. Access is limited by both Discord
permissions and the Hermes profile allowlist. This adapter intentionally does
not archive messages to The Thread or Company Memory by default.

## Verification status

Six offline adapter tests cover allowlisted reads, disallowed IDs, absent token,
invalid parameters, JustYou rejection, and HTTP failure redaction.
A live Discord read cannot be claimed until bot installation, secret
configuration, an approved channel, and an independently observed readback.
