import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
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
        self.ctx.get_config = lambda name, default="": settings.get(name, default)
        self.submissions = []
        self.kanban_unavailable = False
        outer = self
        class FakeKanban:
            def __init__(self, **_kwargs):
                pass
            def enqueue(self, **kwargs):
                if outer.kanban_unavailable:
                    raise RuntimeError("HERMES_KANBAN_UNAVAILABLE")
                outer.submissions.append(kwargs)
                return {"task_id": "task-" + str(len(outer.submissions))}
            def result(self, **kwargs):
                return {"found": True, "completed": True, "status": "done",
                        "independently_verified": False}
        self.patcher = patch("unlimited.hermes_kanban.HermesKanban", FakeKanban)
        self.patcher.start()

        spec = importlib.util.spec_from_file_location("hermes_unlimited_test_entry", ROOT / "__init__.py")
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        plugin.register(self.ctx)

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()
        for key, prior in (("agent", self.previous_agent), ("agent.secret_scope", self.previous_scope)):
            if prior is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = prior

    def call(self, tool, args=None):
        return json.loads(self.ctx.handlers[tool](args or {}))

    def test_hermes_connection_management_requires_host_approval(self):
        tool = "unlimited_connection_manage"
        connect = {"operation": "connect", "connection_id": "mail",
                   "provider": "smtp", "secret_ref": "vault://tenant-a/mail",
                   "config": {"host": "smtp.example.org", "sender": "sender@example.org"}}
        denied = self.call(tool, connect)
        self.assertFalse(denied["ok"])
        self.ctx.approve_customer_connection = lambda tenant, identity, operation, cid: (
            tenant == "tenant-a" and identity == "@owner" and cid == "mail")
        created = self.call(tool, connect)
        self.assertEqual(created["connection_id"], "mail")
        self.assertEqual(self.call(tool, {"operation": "status", "connection_id": "mail"})["provider"], "smtp")
        self.assertFalse(self.call(tool, {"**": "invalid"})["ok"])
        disconnected = self.call(tool, {"operation": "disconnect", "connection_id": "mail"})
        self.assertFalse(disconnected["enabled"])
        self.assertFalse(self.call(tool, {"operation": "status", "connection_id": "mail"})["ok"])

    def test_native_hermes_secure_onboarding_never_receives_credentials(self):
        tool = "unlimited_connection_manage"
        args = {"operation": "onboard", "connection_id": "billing", "provider": "stripe", "config": {}}
        self.ctx.approve_customer_connection = lambda *scope: True
        self.assertFalse(self.call(tool, args)["ok"])
        seen = []
        def onboard(*scope):
            seen.append(scope)
            return {"approved": True, "secret_ref": "vault://tenant-a/billing"}
        self.ctx.onboard_customer_connection = onboard
        self.assertEqual(self.call(tool, args)["provider"], "stripe")
        self.assertEqual(seen, [("tenant-a", "@owner", "billing", "stripe", {})])
        self.assertEqual(self.call(tool, {**args, "secret_ref": "vault://tenant-a/billing"})["ok"], False)
        self.assertEqual(self.call(tool, {"operation":"status", "connection_id":"billing"})["enabled"], True)

    def test_manifest_declares_all_registered_tools(self):
        manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        tools_section = manifest.split("provides_tools:", 1)[1].split("\nrequires_env:", 1)[0]
        names = set(line.strip()[2:] for line in tools_section.splitlines()
                    if line.strip().startswith("- "))
        self.assertEqual(names, set(self.ctx.handlers),
                         "plugin.yaml must match registered tools exactly")

    def test_junior_gmail_read_uses_real_adapter_shape_without_credentials(self):
        from unlimited.gmail_junior_adapter import GmailJuniorReadAdapter
        class FakeGmail:
            def users(self): return self
            def messages(self): return self
            def list(self, **kwargs):
                assert kwargs == {"userId":"me","q":"in:inbox","maxResults":20}
                class Request:
                    def execute(self): return {"messages":[{"id":"aabb11","threadId":"thread1"}]}
                return Request()
        self.ctx.authorize_junior_operation=lambda *scope: scope == ("tenant-a","@owner","gmail","list_messages")
        self.ctx.execute_junior_gmail_read=GmailJuniorReadAdapter(FakeGmail())
        out=self.call("unlimited_junior_factory",{"operation":"read","family":"gmail",
                    "selected_operations":["list_messages"],
                    "target_operation":"list_messages","arguments":{"query":"in:inbox"}})
        self.assertEqual(out["result"]["messages"],[{"id":"aabb11","threadId":"thread1"}])
        self.assertFalse(out["external_write"])

    def test_junior_propose_tool_uses_hermes_registry_and_host_effect_review(self):
        name="unlimited_junior_factory"
        class FakeRegistry:
            def get_all_tool_names(self): return ["dns_lookup", "other"]
            def get_toolset_for_tool(self, tool): return "dns" if tool == "dns_lookup" else "other"
            def get_definitions(self, names, quiet=False):
                return [{"function": {"name": "dns_lookup", "description": "Read DNS",
                        "parameters": {"type": "object", "properties": {"zone": {"type": "string"}},
                                       "required": ["zone"]}}}] if names else []
        registry_module=types.ModuleType("tools.registry")
        registry_module.registry=FakeRegistry()
        previous=sys.modules.get("tools.registry")
        sys.modules["tools.registry"]=registry_module
        try:
            args={"operation": "propose_tool", "toolset": "dns", "tool_name": "dns_lookup",
                  "objective": "Read DNS zone"}
            self.assertFalse(self.call(name,args)["ok"])
            self.ctx.reviewed_junior_tool_effect=lambda *scope: "read"
            proposed=self.call(name,args)
            self.assertEqual(proposed["tool"],"dns_lookup")
            self.assertFalse(proposed["execution_authorized"])
            self.assertEqual(len(proposed["operations"]),1)
            self.assertEqual(proposed["operations"][0]["name"],"dns_lookup")
            self.assertFalse(self.call(name,{**args,"tool_name":"unlisted"})["ok"])
            self.ctx.reviewed_junior_tool_effect=lambda *scope: "unknown"
            self.assertFalse(self.call(name,args)["ok"])
        finally:
            if previous is None: sys.modules.pop("tools.registry",None)
            else: sys.modules["tools.registry"]=previous

    def test_junior_gmail_read_requires_host_binding(self):
        name = "unlimited_junior_factory"
        templates = self.call(name, {"operation":"catalog"})
        self.assertFalse(templates["execution_authorized"])
        proposal = self.call(name, {"operation":"propose", "family":"gmail",
                                    "selected_operations":["list_messages"]})
        self.assertEqual(proposal["tool"], "gmail")
        self.assertFalse(proposal["execution_authorized"])
        payload={"operation":"read", "family":"gmail",
                 "selected_operations":["list_messages"],
                 "target_operation":"list_messages", "arguments":{"query":"in:inbox"}}
        self.assertFalse(self.call(name,payload)["ok"])
        recorded=[]
        self.ctx.authorize_junior_operation=lambda *scope: scope == ("tenant-a","@owner","gmail","list_messages")
        self.ctx.execute_junior_gmail_read=lambda operation,args: recorded.append((operation,args)) or ["m1"]
        answer=self.call(name,payload)
        self.assertEqual(answer["result"],["m1"])
        self.assertEqual(recorded,[("list_messages",{"query":"in:inbox"})])
        self.assertFalse(self.call(name,{**payload,"target_operation":"send_message",
                                         "selected_operations":["send_message"],
                                         "arguments":{"message_id":"m1"}})["ok"])
        self.assertEqual(len(recorded),1)

    def test_specialist_factory_live_probe_requires_opt_in(self):
        from types import SimpleNamespace
        invocations = []
        def fake_completion(messages, **kwargs):
            invocations.append((messages, kwargs))
            return SimpleNamespace(text="OK", model="small",
                                   usage=SimpleNamespace(cost_usd=0.002))
        self.ctx.llm = SimpleNamespace(complete=fake_completion)
        payload = {"operation": "probe", "model_id": "small", "case_id": "exact",
                   "prompt": "Return OK", "expected": "OK", "run_id": "run1",
                   "cost_usd_to_minor": 100}
        denied = self.call("unlimited_specialist_factory", payload)
        self.assertFalse(denied["ok"])
        self.assertEqual(invocations, [])
        accepted = self.call("unlimited_specialist_factory", {
            **payload, "allow_live_probe": True})
        self.assertTrue(accepted["passed"])
        self.assertEqual(accepted["cost_minor"], .2)
        self.assertEqual(len(invocations), 1)

    def test_specialist_factory_tool_end_to_end(self):
        schema = {"name": "dns_lookup", "effect": "read", "description": "Lookup DNS",
                  "parameters": {"type": "object", "properties": {"zone": {"type": "string"}},
                                 "required": ["zone"]}}
        inventory = self.call("unlimited_specialist_factory", {
            "operation": "discover", "tool_schemas": [schema]})
        self.assertEqual(inventory["capabilities"][0]["tool_name"], "dns_lookup")
        self.assertFalse(inventory["execution_authorized"])
        proposal = self.call("unlimited_specialist_factory", {
            "operation": "propose", "tool_schemas": [schema],
            "objective": "Check DNS", "selected_tools": ["dns_lookup"]})
        self.assertEqual(proposal["status"], "DRAFT_UNVERIFIED")
        self.assertFalse(proposal["execution_authorized"])
        evaluation = self.call("unlimited_specialist_factory", {
            "operation": "evaluate", "required_cases": ["normal"],
            "trials": [{"model_id": "small", "case_id": "normal", "passed": True,
                        "cost_minor": 1, "latency_seconds": 0.3,
                        "independently_verified": True, "run_id": f"r{i}"}
                       for i in range(3)]})
        self.assertEqual(evaluation["recommended_model"], "small")
        self.assertFalse(self.call("unlimited_specialist_factory", {
            "operation": "propose", "tool_schemas": [schema],
            "objective": "Change DNS", "selected_tools": ["missing"]})["ok"])

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
        self.assertEqual(req["state"], "running")
        self.assertEqual(req["task_id"], "task-1")
        self.assertEqual(len(self.submissions), 1)
        result = self.call("unlimited_service_result", {"company_id": "company-a",
                                                      "request_id": "request-a"})
        self.assertTrue(result["completed"])
        self.assertFalse(result["independently_verified"])
        self.assertEqual(self.call("unlimited_company_list")["companies"][0]["company"], "company-a")

    def test_a2ui_loopback_bridge_calls_real_registered_hermes_handler(self):
        import threading
        import urllib.request
        from unlimited.a2ui_bridge import make_bridge, new_transport_token
        self.call("unlimited_company_create", {"company_id":"company-a", "display_name":"Live through Hermes"})
        token = new_transport_token()
        server = make_bridge(self.ctx.handlers["unlimited_a2ui_surface"], token=token)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/surface?view=companies&surface_id=live"
            request = urllib.request.Request(url, headers={"Authorization":"Bearer "+token})
            with urllib.request.urlopen(request, timeout=3) as response:
                self.assertIn("Live through Hermes", response.read().decode())
            self.settings["HERMES_UNLIMITED_JUSTYOU_IDENTITY"]="@other"
            with self.assertRaises(urllib.error.HTTPError) as blocked:
                urllib.request.urlopen(request, timeout=3)
            self.assertEqual(blocked.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_a2ui_native_tool_is_read_only_and_tenant_scoped(self):
        self.call("unlimited_company_create", {"company_id": "company-a", "display_name": "Research Firm"})
        surface = self.call("unlimited_a2ui_surface", {"view": "companies", "surface_id": "companies_1"})
        self.assertEqual(surface["version"], "1.0")
        self.assertIn("Research Firm", json.dumps(surface))
        self.assertNotIn("action", json.dumps(surface))
        self.assertEqual(len(self.submissions), 0)
        invalid = self.call("unlimited_a2ui_surface", {"view": "companies", "company_id": "company-a", "surface_id": "x"})
        self.assertFalse(invalid["ok"])
        invalid = self.call("unlimited_a2ui_surface", {"view": "requests", "surface_id": "x"})
        self.assertFalse(invalid["ok"])
        self.settings["HERMES_UNLIMITED_TENANT_ID"] = "tenant-b"
        isolated = self.call("unlimited_a2ui_surface", {"view": "companies", "surface_id": "companies_2"})
        self.assertEqual(isolated["version"], "1.0")
        self.assertNotIn("Research Firm", json.dumps(isolated))

    def test_dispatch_idempotent_and_scoped(self):
        self.call("unlimited_company_create", {"company_id": "company-a", "display_name": "A"})
        self.call("unlimited_service_publish", {"company_id": "company-a", "service_id": "brief",
                                               "title": "Brief", "price_minor": 0, "currency": "NOK"})
        self.call("unlimited_service_request", {"company_id": "company-a", "service_id": "brief",
                                               "request_id": "req-1", "payload": {}})
        again = self.call("unlimited_service_dispatch", {"company_id": "company-a", "request_id": "req-1"})
        self.assertEqual(again["task_id"], "task-1")
        self.assertEqual(len(self.submissions), 1)
        self.settings["HERMES_UNLIMITED_TENANT_ID"] = "tenant-b"
        self.settings["HERMES_UNLIMITED_JUSTYOU_IDENTITY"] = "@owner"
        denied = self.call("unlimited_service_result", {"company_id": "company-a", "request_id": "req-1"})
        self.assertFalse(denied.get("found", False))

    def test_subscription_first_dispatch_persists_profile_for_result(self):
        from unlimited.subscription_dispatch import ProfileCapacity
        from unlimited.runtime import ProviderStore

        self.ctx.subscription_profile_capacities = lambda tenant, company, service: [
            ProfileCapacity(tenant, "paid-profile", "hermes_paid", (service,), .99, 0),
            ProfileCapacity(tenant, "customer-cli", "customer_owned", (service,), .93, 2),
        ]
        self.ctx.subscription_dispatch_policy = lambda *args: {
            "min_quality": .9, "max_marginal_cost_minor": 3,
            "allow_paid_fallback": True,
        }
        self.ctx.subscription_profile_evidence = lambda tenant, profile: {
            "profile": profile, "verified": True,
            "authority_granted": False, "binding_digest": "trusted-binding",
        }
        self.call("unlimited_company_create", {"company_id": "company-a", "display_name": "A"})
        self.call("unlimited_service_publish", {
            "company_id": "company-a", "service_id": "brief",
            "title": "Brief", "price_minor": 0, "currency": "EUR"})
        queued = self.call("unlimited_service_request", {
            "company_id": "company-a", "service_id": "brief",
            "request_id": "req-1", "payload": {"request": "brief"}})
        self.assertEqual(queued["selected_profile"], "customer-cli")
        self.assertEqual(self.submissions[0]["assignee"], "customer-cli")
        self.assertFalse(queued["executed"])
        result = self.call("unlimited_service_result", {
            "company_id": "company-a", "request_id": "req-1"})
        self.assertTrue(result["found"])
        store = ProviderStore(self.settings["HERMES_UNLIMITED_REGISTRY_DB"],
                              lambda p, t, i: p == "owner" and t == "tenant-a" and i == "@owner")
        item = store.get_request("owner", "tenant-a", "company-a", "req-1", "@owner")
        self.assertEqual(item["assignee_profile"], "customer-cli")

    def test_paid_subscription_fallback_requires_host_approval(self):
        from unlimited.subscription_dispatch import ProfileCapacity

        self.ctx.subscription_profile_capacities = lambda tenant, company, service: [
            ProfileCapacity(tenant, "paid-profile", "hermes_paid", (service,), .99, 1)
        ]
        self.ctx.subscription_dispatch_policy = lambda *args: {
            "min_quality": .9, "max_marginal_cost_minor": 3,
            "allow_paid_fallback": False,
        }
        self.ctx.subscription_profile_evidence = lambda *args: {
            "profile": "paid-profile", "verified": True,
            "authority_granted": False, "binding_digest": "trusted-binding",
        }
        self.call("unlimited_company_create", {"company_id": "company-a", "display_name": "A"})
        self.call("unlimited_service_publish", {
            "company_id": "company-a", "service_id": "brief",
            "title": "Brief", "price_minor": 0, "currency": "EUR"})
        denied = self.call("unlimited_service_request", {
            "company_id": "company-a", "service_id": "brief",
            "request_id": "req-2", "payload": {}})
        self.assertFalse(denied["ok"])
        self.assertEqual(self.submissions, [])

    def test_unavailable_kanban_keeps_request_for_retry(self):
        self.call("unlimited_company_create", {"company_id": "company-a", "display_name": "A"})
        self.call("unlimited_service_publish", {"company_id": "company-a", "service_id": "brief",
                                               "title": "Brief", "price_minor": 0, "currency": "NOK"})
        self.kanban_unavailable = True
        queued = self.call("unlimited_service_request", {"company_id": "company-a", "service_id": "brief",
                                                       "request_id": "req-1", "payload": {}})
        self.assertTrue(queued["dispatch_pending"])
        self.assertEqual(queued["state"], "queued")
        self.kanban_unavailable = False
        dispatched = self.call("unlimited_service_dispatch", {"company_id": "company-a", "request_id": "req-1"})
        self.assertEqual(dispatched["task_id"], "task-1")
        self.assertEqual(len(self.submissions), 1)

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

    def test_unavailable_creative_backend_not_advertised(self):
        self.assertNotIn("unlimited_creative_render", self.ctx.handlers)
        self.assertNotIn("unlimited_creative_result", self.ctx.handlers)


if __name__ == "__main__":
    unittest.main()
