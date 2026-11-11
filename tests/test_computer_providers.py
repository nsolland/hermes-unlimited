"""Offline compute adapter contract tests: no real network or credentials."""
import io
import json
import unittest
from unittest.mock import Mock

from unlimited.computer_providers import (
    AuthorizationDenied, ComputerProviderError, ComputerProviderRegistry,
    DaytonaComputerProvider, OrgoComputerProvider, SpritesComputerProvider,
    UnsupportedOperation,
)


class Response:
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.value).encode()


class ComputerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def allow(**data):
            self.calls.append(data)
            return data["tenant"] == "tenant-a" and data["resource"] != "foreign"
        self.allow = allow

    def test_orgo_create_and_lifecycle(self):
        requests = []
        def open_request(req, timeout):
            requests.append((req.get_method(), req.full_url, req.data))
            return Response({"id": "pc-1"} if req.full_url.endswith("/computers") else {"state": "running"})
        p = OrgoComputerProvider(authorize=self.allow, api_key="synthetic", workspace_id="workspace-1", opener=open_request)
        self.assertEqual(p.create(tenant="tenant-a", name="worker")["id"], "pc-1")
        self.assertEqual(p.inspect(tenant="tenant-a", resource="pc-1")["id"], "pc-1")
        p.start(tenant="tenant-a", resource="pc-1")
        p.stop(tenant="tenant-a", resource="pc-1")
        self.assertEqual([x[0] for x in requests], ["POST", "GET", "POST", "POST"])
        self.assertIn(b"workspace-1", requests[0][2])
        self.assertEqual(len(self.calls), 4)

    def test_fail_closed_before_remote_call(self):
        opener = Mock(side_effect=AssertionError("remote call"))
        p = OrgoComputerProvider(authorize=self.allow, api_key="synthetic", workspace_id="work", opener=opener)
        with self.assertRaises(AuthorizationDenied):
            p.stop(tenant="tenant-b", resource="pc-1")
        with self.assertRaises(AuthorizationDenied):
            p.inspect(tenant="tenant-a", resource="foreign")
        with self.assertRaises(ValueError):
            p.inspect(tenant="tenant-a", resource="../bad")
        opener.assert_not_called()

    def test_denied_on_broken_host_gate(self):
        p = SpritesComputerProvider(authorize=lambda **kw: (_ for _ in ()).throw(RuntimeError("offline")), client=Mock())
        with self.assertRaises(AuthorizationDenied):
            p.create(tenant="tenant-a", name="work")

    def test_orgo_bad_response(self):
        p = OrgoComputerProvider(authorize=self.allow, api_key="synthetic", workspace_id="work", opener=lambda *a, **kw: Response({}))
        with self.assertRaises(ComputerProviderError):
            p.create(tenant="tenant-a", name="work")

    def test_daytona_contract(self):
        client = Mock()
        client.v2.create.return_value = Mock(id="sb-1", state="started")
        client.v2.get.return_value = Mock(id="sb-1", state="started")
        p = DaytonaComputerProvider(authorize=self.allow, client=client)
        self.assertEqual(p.create(tenant="tenant-a", name="dev")["state"], "started")
        self.assertEqual(p.inspect(tenant="tenant-a", resource="sb-1")["id"], "sb-1")
        p.exec(tenant="tenant-a", resource="sb-1", command="pwd")
        client.v2.get.return_value.exec.assert_called_once_with("pwd", execution_timeout=60)
        p.delete(tenant="tenant-a", resource="sb-1")
        client.v2.delete.assert_called_once_with("sb-1")

    def test_sprites_contract(self):
        client = Mock()
        client.sprite.return_value.command.return_value.output.return_value = b"ok"
        p = SpritesComputerProvider(authorize=self.allow, client=client)
        self.assertEqual(p.create(tenant="tenant-a", name="dev")["id"], "dev")
        self.assertEqual(p.exec(tenant="tenant-a", resource="dev", argv=["echo", "ok"])["stdout"], b"ok")
        client.sprite.return_value.command.assert_called_once_with("echo", "ok")
        with self.assertRaises(ValueError):
            p.exec(tenant="tenant-a", resource="dev", argv=[])

    def test_registry_capabilities(self):
        p = SpritesComputerProvider(authorize=self.allow, client=Mock())
        reg = ComputerProviderRegistry([p])
        self.assertEqual(reg.get("sprites"), p)
        with self.assertRaises(UnsupportedOperation):
            reg.get("missing")
        self.assertEqual(reg.capabilities()["sprites"], ["create", "exec"])


if __name__ == "__main__":
    unittest.main()
