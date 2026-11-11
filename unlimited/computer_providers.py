"""Optional, host-authorized compute providers. No implicit execution authority.

Provider methods require a trusted host gate on every operation. The host gate
must enforce tenant/resource ownership and JustYou authorization; it must fail
closed. Remote submission is not proof that an agent completed its work.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")
_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


class ComputerProviderError(RuntimeError):
    pass


class UnsupportedOperation(ComputerProviderError):
    pass


class AuthorizationDenied(ComputerProviderError):
    pass


class ComputerProvider:
    """Uniform lifecycle surface; capability differences are explicit."""

    name = "abstract"
    capabilities = frozenset()

    def __init__(self, *, authorize):
        if not callable(authorize):
            raise ValueError("trusted authorize callback required")
        self._authorize = authorize

    def _check(self, tenant, action, resource=None):
        if not isinstance(tenant, str) or not _ID.fullmatch(tenant):
            raise AuthorizationDenied("invalid tenant")
        if resource is not None and (not isinstance(resource, str) or not _ID.fullmatch(resource)):
            raise AuthorizationDenied("invalid resource")
        try:
            allowed = self._authorize(tenant=tenant, provider=self.name,
                                      action=action, resource=resource)
        except Exception as exc:
            raise AuthorizationDenied("host authorization failed") from exc
        if allowed is not True:
            raise AuthorizationDenied("host authorization denied")

    @staticmethod
    def _name(value):
        if not isinstance(value, str) or not _NAME.fullmatch(value):
            raise ValueError("invalid computer name")
        return value

    def _require(self, capability):
        if capability not in self.capabilities:
            raise UnsupportedOperation(self.name + " does not support " + capability)


class OrgoComputerProvider(ComputerProvider):
    """Orgo REST implementation; scoped workspace and host ownership required."""

    name = "orgo"
    capabilities = frozenset(("create", "inspect", "start", "stop"))

    def __init__(self, *, authorize, api_key, workspace_id, opener=urlopen, timeout=20):
        super().__init__(authorize=authorize)
        if not isinstance(api_key, str) or not api_key or not isinstance(workspace_id, str) or not _ID.fullmatch(workspace_id):
            raise ValueError("Orgo credentials and workspace required")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
            raise ValueError("invalid timeout")
        self._key, self._workspace, self._open, self._timeout = api_key, workspace_id, opener, timeout

    def _request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request("https://www.orgo.ai/api" + path, data=data, method=method,
                      headers={"Authorization": "Bearer " + self._key,
                               "Content-Type": "application/json"})
        try:
            with self._open(req, timeout=self._timeout) as resp:
                raw = resp.read()
            result = json.loads(raw) if raw else {}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise ComputerProviderError("Orgo transport or response failure") from exc
        if not isinstance(result, dict):
            raise ComputerProviderError("Orgo returned invalid response")
        return result

    def create(self, *, tenant, name, auto_stop_minutes=30):
        name = self._name(name)
        if not isinstance(auto_stop_minutes, int) or not 1 <= auto_stop_minutes <= 1440:
            raise ValueError("auto_stop_minutes must be 1..1440")
        self._check(tenant, "create")
        result = self._request("POST", "/computers",
                               {"workspace_id": self._workspace, "name": name,
                                "auto_stop_minutes": auto_stop_minutes})
        identifier = result.get("id") or result.get("computer_id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise ComputerProviderError("Orgo did not return a valid computer ID")
        return {"provider": self.name, "id": identifier, "state": "submitted"}

    def inspect(self, *, tenant, resource):
        self._check(tenant, "inspect", resource)
        result = self._request("GET", "/computers/" + quote(resource, safe=""))
        return {"provider": self.name, "id": resource, "remote": result}

    def start(self, *, tenant, resource):
        self._check(tenant, "start", resource)
        return {"provider": self.name, "id": resource, "remote": self._request("POST", "/computers/" + quote(resource, safe="") + "/start")}

    def stop(self, *, tenant, resource):
        self._check(tenant, "stop", resource)
        return {"provider": self.name, "id": resource, "remote": self._request("POST", "/computers/" + quote(resource, safe="") + "/stop")}


class DaytonaComputerProvider(ComputerProvider):
    """Daytona v2 SDK adapter; supply the trusted, configured Daytona client."""

    name = "daytona"
    capabilities = frozenset(("create", "inspect", "exec", "delete"))

    def __init__(self, *, authorize, client):
        super().__init__(authorize=authorize)
        self._client = client

    def create(self, *, tenant, name):
        self._name(name)
        self._check(tenant, "create")
        sandbox = self._client.v2.create(name=name, wait_seconds=60)
        return {"provider": self.name, "id": sandbox.id, "state": sandbox.state}

    def inspect(self, *, tenant, resource):
        self._check(tenant, "inspect", resource)
        sandbox = self._client.v2.get(resource)
        return {"provider": self.name, "id": sandbox.id, "state": sandbox.state}

    def exec(self, *, tenant, resource, command):
        if not isinstance(command, str) or not command or len(command) > 8192:
            raise ValueError("invalid command")
        self._check(tenant, "exec", resource)
        result = self._client.v2.get(resource).exec(command, execution_timeout=60)
        return {"provider": self.name, "id": resource, "result": result}

    def delete(self, *, tenant, resource):
        self._check(tenant, "delete", resource)
        self._client.v2.delete(resource)
        return {"provider": self.name, "id": resource, "state": "delete_requested"}


class SpritesComputerProvider(ComputerProvider):
    """Fly Sprites Python SDK adapter; idle/sleep is provider-managed."""

    name = "sprites"
    capabilities = frozenset(("create", "exec"))

    def __init__(self, *, authorize, client):
        super().__init__(authorize=authorize)
        self._client = client

    def create(self, *, tenant, name):
        self._name(name)
        self._check(tenant, "create")
        self._client.create_sprite(name)
        return {"provider": self.name, "id": name, "state": "submitted"}

    def exec(self, *, tenant, resource, argv):
        if (not isinstance(argv, (list, tuple)) or not argv or len(argv) > 64
                or any(not isinstance(arg, str) or not arg or len(arg) > 4096 for arg in argv)):
            raise ValueError("expected bounded argv sequence")
        self._check(tenant, "exec", resource)
        output = self._client.sprite(resource).command(*argv).output()
        return {"provider": self.name, "id": resource, "stdout": output}


class ComputerProviderRegistry:
    def __init__(self, providers):
        self._providers = {}
        for provider in providers:
            if not isinstance(provider, ComputerProvider) or provider.name in self._providers:
                raise ValueError("duplicate or invalid provider")
            self._providers[provider.name] = provider

    def get(self, name):
        try:
            return self._providers[name]
        except KeyError as exc:
            raise UnsupportedOperation("provider not configured") from exc

    def capabilities(self):
        return {name: sorted(p.capabilities) for name, p in self._providers.items()}
