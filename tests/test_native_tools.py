import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ToolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_agent = sys.modules.get("agent")
        self.previous_scope = sys.modules.get("agent.secret_scope")
        settings = {
            "HERMES_UNLIMITED_PROVIDER_ID": "owner",
            "HERMES_UNLIMITED_TENANT_ID": "tenant-a",
            "HERMES_UNLIMITED_JUSTYOU_IDENTITY": "@owner",
            "HERMES_UNLIMITED_JUSTYOU_SESSION_TOKEN": "session",
            "HERMES_UNLIMITED_REGISTRY_DB": str(pathlib.Path(self.temp.name) / "data.sqlite"),
        }
        self.settings = settings
        agent = types.ModuleType("agent")
        agent.__path__ = []
        scope = types.ModuleType("agent.secret_scope")
        scope.get_secret = lambda name, default="": settings.get(name, default)
        sys.modules["agent"] = agent
        sys.modules["agent.secret_scope"] = scope

        class SessionStore:
            def validate(self, token, audience, required_scope):
                return SimpleNamespace(valid=True, authority=False, address="@owner",
                                       audience=audience, scopes=("read-profile",))
        class Binding:
            identity, carrier, endpoint, version = "@owner", "hermes-profile", "hermes-profile:role-a", 1
            def digest(self):
                return "digest"
        class Resolver:
            def resolve(self, identity, **kwargs):
                return Binding(), SimpleNamespace(identity=identity, binding_digest="digest",
                                                  resolved_version=1, status="RESOLVED")
        self.ctx = SimpleNamespace(profile_name="role-a", justyou_session_store=SessionStore(),
                                   justyou_resolver=Resolver(), handlers={})
        def register_tool(name, toolset, schema, handler):
            self.ctx.handlers[name] = handler
        self.ctx.register_tool = register_tool

        spec = importlib.util.spec_from_file_location("hermes_unlimited_test_entry", ROOT / "__init__.py")
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        plugin.register(self.ctx)

    def tearDown(self):
        self.temp.cleanup()
        for key, prior in (("agent", self.previous_agent), ("agent.secret_scope", self.previous_scope)):
            if prior is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = prior

    def call(self, tool, args=None):
        return json.loads(self.ctx.handlers[tool](args or {}))

    def test_public_company_service_request_path(self):
        created = self.call("unlimited_company_create",
                            {"company_id": "company-a", "display_name": "Research Firm"})
        self.assertTrue(created["created"])
        service = self.call("unlimited_service_publish",
                            {"company_id": "company-a", "service_id": "brief",
                             "title": "Research brief", "price_minor": 9900, "currency": "NOK"})
        self.assertTrue(service["published"])
        req = self.call("unlimited_service_request",
                        {"company_id": "company-a", "service_id": "brief",
                         "request_id": "request-a", "payload": {"topic": "market"}})
        self.assertEqual(req["state"], "queued")
        self.assertEqual(self.call("unlimited_company_list")["companies"][0]["company"], "company-a")

    def test_identity_mismatch_fails_all_writes(self):
        self.settings["HERMES_UNLIMITED_JUSTYOU_IDENTITY"] = "@other"
        response = self.call("unlimited_company_create",
                             {"company_id": "company-a", "display_name": "Research Firm"})
        self.assertFalse(response["ok"])

    def test_caller_cannot_choose_tenant(self):
        response = self.call("unlimited_company_create",
                             {"company_id": "company-a", "display_name": "Research Firm",
                              "tenant": "other"})
        self.assertEqual(response["reason"], "INVALID_ARGUMENTS")


if __name__ == "__main__":
    unittest.main()
