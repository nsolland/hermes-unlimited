"""Tenant-isolated company and service registry with explicit identity enforcement.

This is a local provider control plane, not a Hermes task executor. All operations
require caller-supplied verified JustYou identity from a trusted adapter. Never
accept identity or verification claims from a customer payload.
"""
import json
import re
import sqlite3
import time
from pathlib import Path

IDENT = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class UnverifiedIdentity(PermissionError):
    pass


class ProviderStore:
    def __init__(self, database, verify_identity):
        if not callable(verify_identity):
            raise TypeError("Trusted JustYou verifier required")
        self.database = str(database)
        self.verify_identity = verify_identity
        path = Path(self.database)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _db(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self):
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS companies (
                    provider TEXT NOT NULL, tenant TEXT NOT NULL,
                    company TEXT NOT NULL, name TEXT NOT NULL,
                    identity_ref TEXT NOT NULL,
                    PRIMARY KEY(provider, tenant, company)
                );
                CREATE TABLE IF NOT EXISTS services (
                    provider TEXT NOT NULL, tenant TEXT NOT NULL,
                    company TEXT NOT NULL, service TEXT NOT NULL,
                    title TEXT NOT NULL, price_minor INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    PRIMARY KEY(provider, tenant, company, service),
                    FOREIGN KEY(provider, tenant, company)
                        REFERENCES companies(provider, tenant, company)
                );
                CREATE TABLE IF NOT EXISTS requests (
                    provider TEXT NOT NULL, tenant TEXT NOT NULL,
                    company TEXT NOT NULL, request TEXT NOT NULL,
                    service TEXT NOT NULL, payload TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued',
                    result TEXT,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY(provider, tenant, company, request),
                    FOREIGN KEY(provider, tenant, company, service)
                        REFERENCES services(provider, tenant, company, service)
                );
            """)

    @staticmethod
    def _ids(*values):
        if any(not isinstance(value, str) or not IDENT.fullmatch(value) for value in values):
            raise ValueError("INVALID_SCOPE_IDENTIFIER")

    def _authorize(self, provider, tenant, identity):
        self._ids(provider, tenant)
        # Verifier must be a trusted object controlled by the host, never a payload flag.
        if not identity or self.verify_identity(provider, tenant, identity) is not True:
            raise UnverifiedIdentity("JUSTYOU_IDENTITY_NOT_VERIFIED")

    def create_company(self, provider, tenant, company, name, identity):
        self._authorize(provider, tenant, identity)
        self._ids(company)
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            raise ValueError("COMPANY_NAME_INVALID")
        with self._db() as db:
            db.execute(
                "INSERT INTO companies VALUES(?,?,?,?,?)",
                (provider, tenant, company, name.strip(), identity),
            )
        return {"provider": provider, "tenant": tenant, "company": company, "created": True}

    def list_companies(self, provider, tenant, identity):
        self._authorize(provider, tenant, identity)
        with self._db() as db:
            rows = db.execute(
                "SELECT company,name FROM companies WHERE provider=? AND tenant=? ORDER BY company",
                (provider, tenant),
            ).fetchall()
        return [{"company": c, "name": n} for c, n in rows]

    def publish_service(self, provider, tenant, company, service, title, price_minor, currency, identity):
        self._authorize(provider, tenant, identity)
        self._ids(company, service)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("SERVICE_TITLE_INVALID")
        if type(price_minor) is not int or price_minor < 0:
            raise ValueError("PRICE_INVALID")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("CURRENCY_INVALID")
        with self._db() as db:
            db.execute(
                "INSERT INTO services VALUES(?,?,?,?,?,?,?)",
                (provider, tenant, company, service, title.strip(), price_minor, currency),
            )
        return {"service": service, "published": True, "price_minor": price_minor, "currency": currency}

    def request_service(self, provider, tenant, company, request, service, payload, identity):
        self._authorize(provider, tenant, identity)
        self._ids(company, request, service)
        serialized = json.dumps(payload, separators=(",", ":"))
        if not isinstance(payload, dict) or len(serialized) > 16384:
            raise ValueError("PAYLOAD_INVALID")
        with self._db() as db:
            db.execute(
                "INSERT INTO requests(provider,tenant,company,request,service,payload,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (provider, tenant, company, request, service, serialized, int(time.time())),
            )
        # Queued is not executed, authorized, billed or completed.
        return {"request": request, "state": "queued", "executed": False}

    def list_requests(self, provider, tenant, company, identity):
        self._authorize(provider, tenant, identity)
        self._ids(company)
        with self._db() as db:
            rows = db.execute(
                "SELECT request,service,state,result FROM requests "
                "WHERE provider=? AND tenant=? AND company=? ORDER BY created_at,request",
                (provider, tenant, company),
            ).fetchall()
        return [{"request": r, "service": s, "state": st, "result": json.loads(res) if res else None}
                for r, s, st, res in rows]
