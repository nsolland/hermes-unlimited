"""Durable inbound inbox with crash recovery and explicit at-least-once semantics.

External effects MUST use the stable delivery_key for sink-side idempotency.
A database cannot atomically commit with an arbitrary external callback.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .justyou_inbound import AcceptedInbound


@dataclass(frozen=True)
class Delivery:
    key: str
    message: AcceptedInbound


class DurableInboundInbox:
    def __init__(self, db_path: str, deliver: Callable[[Delivery], None]):
        if not callable(deliver):
            raise TypeError("delivery callback required")
        path = Path(db_path)
        if path.is_symlink():
            raise ValueError("symlink database forbidden")
        if path.exists() and not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("regular database file required")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), isolation_level=None,
                                   timeout=30, check_same_thread=False)
        if os.name == "posix" and path.exists():
            os.chmod(path, 0o600)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA busy_timeout=30000")
        self._db.execute("""CREATE TABLE IF NOT EXISTS inbound (
            key TEXT PRIMARY KEY, payload TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('pending','delivered')),
            created_at INTEGER NOT NULL, delivered_at INTEGER
        )""")
        self._deliver = deliver
        self._lock = threading.RLock()

    @staticmethod
    def _key(channel: str, endpoint: str, message_id: str) -> str:
        return hashlib.sha256(json.dumps(
            [channel, endpoint, message_id], separators=(",", ":")
        ).encode()).hexdigest()

    @staticmethod
    def _serialize(message: AcceptedInbound) -> str:
        return json.dumps({
            "sender": message.sender, "recipient": message.recipient,
            "message_id": message.message_id, "proof_ref": message.proof_ref,
            "text": message.text,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def accept(self, *, channel: str, endpoint: str,
               message: AcceptedInbound) -> Delivery:
        if not all(isinstance(x, str) and x.strip()
                   for x in (channel, endpoint, message.message_id)):
            raise ValueError("inbound identity required")
        key = self._key(channel, endpoint, message.message_id)
        payload = self._serialize(message)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT payload,state FROM inbound WHERE key=?", (key,)
                ).fetchone()
                if row is not None and row[0] != payload:
                    raise ValueError("conflicting inbound replay")
                if row is None:
                    self._db.execute(
                        "INSERT INTO inbound(key,payload,state,created_at)"
                        " VALUES(?,?,'pending',?)", (key, payload, int(time.time())))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
        delivery = Delivery(key, message)
        self._attempt(delivery)
        return delivery

    def _attempt(self, delivery: Delivery) -> None:
        # Hold a database write transaction across callback: serializes
        # delivery across processes, but an external effect before COMMIT
        # can still be repeated after crash. Sink MUST dedupe by key.
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT payload,state FROM inbound WHERE key=?",
                    (delivery.key,)
                ).fetchone()
                if row is None or row[0] != self._serialize(delivery.message):
                    raise ValueError("missing or conflicting inbox entry")
                if row[1] != "delivered":
                    self._deliver(delivery)
                    self._db.execute(
                        "UPDATE inbound SET state='delivered',delivered_at=?"
                        " WHERE key=?", (int(time.time()), delivery.key))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def recover(self) -> int:
        rows = self._db.execute(
            "SELECT key,payload FROM inbound WHERE state='pending'"
            " ORDER BY created_at,key").fetchall()
        recovered = 0
        for key, payload in rows:
            try:
                self._attempt(Delivery(
                    key, AcceptedInbound(**json.loads(payload))))
                recovered += 1
            except Exception:
                # Leave pending for retry; no silent acknowledgement.
                continue
        return recovered

    def status(self, key: str) -> str | None:
        row = self._db.execute(
            "SELECT state FROM inbound WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._db.close()
