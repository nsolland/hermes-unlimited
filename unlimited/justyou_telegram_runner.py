"""Fail-closed, restartable Telegram polling runner.

Requires a trusted, freshly verified JustYou identity evidence object from the
host. This module does not mint identity evidence or own production credentials.
Only a single runner may poll a Telegram bot token at a time.
"""
from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .justyou_telegram import TelegramInboundAdapter


class TelegramPollRunner:
    def __init__(self, *, token: str, adapter: TelegramInboundAdapter,
                 state_path: str, fetch=None, sleep=time.sleep):
        if not isinstance(token, str) or ":" not in token or len(token) < 20:
            raise ValueError("Telegram bot token required")
        if not isinstance(adapter, TelegramInboundAdapter):
            raise TypeError("JustYou Telegram adapter required")
        path = Path(state_path)
        if path.is_symlink():
            raise ValueError("state symlink forbidden")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(str(path) + ".lock", "a+b")
        os.chmod(str(path) + ".lock", 0o600)
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_file.close()
            raise RuntimeError("TELEGRAM_POLL_CONSUMER_ALREADY_RUNNING")
        self._db = sqlite3.connect(path, isolation_level=None, timeout=30)
        os.chmod(path, 0o600)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("CREATE TABLE IF NOT EXISTS offset_state (id INTEGER PRIMARY KEY CHECK(id=1), next_update INTEGER NOT NULL)")
        self._db.execute("INSERT OR IGNORE INTO offset_state VALUES(1,0)")
        self._token = token
        self._adapter = adapter
        self._fetch = fetch or self._telegram_fetch
        self._sleep = sleep

    def _telegram_fetch(self, offset):
        url = ("https://api.telegram.org/bot" + self._token + "/getUpdates?" +
               urlencode({"offset": offset, "limit": 25, "timeout": 10,
                          "allowed_updates": json.dumps(["message"])}))
        with urlopen(Request(url), timeout=20) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise RuntimeError("TELEGRAM_RESPONSE_TOO_LARGE")
        data = json.loads(raw)
        if data.get("ok") is not True or not isinstance(data.get("result"), list):
            raise RuntimeError("TELEGRAM_API_FAILED")
        return data["result"]

    def next_offset(self):
        return self._db.execute(
            "SELECT next_update FROM offset_state WHERE id=1").fetchone()[0]

    def poll_once(self):
        updates = self._fetch(self.next_offset())
        if not isinstance(updates, list):
            raise ValueError("invalid Telegram update batch")
        count = 0
        for update in sorted(updates, key=lambda u: u["update_id"]):
            update_id = update.get("update_id")
            if type(update_id) is not int or update_id < 0:
                raise ValueError("invalid Telegram update ID")
            if update_id < self.next_offset():
                continue
            # Any invalid or unauthorized update is quarantined by stopping
            # polling, not silently advancing the offset.
            self._adapter.receive_update(update)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute(
                    "UPDATE offset_state SET next_update=? WHERE id=1",
                    (update_id + 1,))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            count += 1
        return count

    def run_forever(self):
        while True:
            self.poll_once()
            self._sleep(0.5)

    def close(self):
        self._db.close()
        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
        self._lock_file.close()
