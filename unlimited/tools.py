"""Native public management tools for provider-owned company/service lifecycle.

All provider, tenant and identity fields come exclusively from Hermes scoped
configuration plus validated JustYou session, never user-supplied tool args.
"""
import json

SCHEMAS = (
    {
        "name": "unlimited_company_create",
        "description": "Create a tenant-scoped AI-native company in the provider registry.",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": "string"},
            "display_name": {"type": "string"}},
            "required": ["company_id", "display_name"], "additionalProperties": False},
    },
    {
        "name": "unlimited_service_publish",
        "description": "Publish a priced service belonging to a tenant-scoped company.",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": "string"}, "service_id": {"type": "string"},
            "title": {"type": "string"}, "price_minor": {"type": "integer", "minimum": 0},
            "currency": {"type": "string"}},
            "required": ["company_id", "service_id", "title", "price_minor", "currency"],
            "additionalProperties": False},
    },
    {
        "name": "unlimited_service_request",
        "description": "Record a customer service request; recording does not execute it.",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": "string"}, "request_id": {"type": "string"},
            "service_id": {"type": "string"}, "payload": {"type": "object"}},
            "required": ["company_id", "request_id", "service_id", "payload"],
            "additionalProperties": False},
    },
    {
        "name": "unlimited_company_list",
        "description": "List only companies in the bound provider and customer tenant.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
)


def register_company_tools(ctx, scoped_secret, scoped_identity):
    from .runtime import ProviderStore

    def verified_store():
        tenant, evidence = scoped_identity()
        provider = scoped_secret("HERMES_UNLIMITED_PROVIDER_ID", "")
        path = scoped_secret("HERMES_UNLIMITED_REGISTRY_DB", "")
        if not provider or not path:
            raise PermissionError("REGISTRY_NOT_CONFIGURED")
        # Identity is tied to the signed session verified on each operation;
        # this closure never trusts a claimed identity passed via tool args.
        def verify(expected_provider, expected_tenant, identity):
            return (expected_provider == provider and expected_tenant == tenant
                    and evidence.get("verified") is True
                    and identity == evidence.get("identity"))
        return ProviderStore(path, verify), provider, tenant, evidence["identity"]

    def make_handler(name):
        def handler(args=None, **_kwargs):
            if not isinstance(args, dict):
                args = {}
            schema = next(item for item in SCHEMAS if item["name"] == name)
            required = set(schema["parameters"].get("required", ()))
            permitted = set(schema["parameters"]["properties"])
            if set(args) - permitted or not required.issubset(args):
                return json.dumps({"ok": False, "reason": "INVALID_ARGUMENTS"})
            try:
                store, provider, tenant, identity = verified_store()
                if name == "unlimited_company_create":
                    out = store.create_company(provider, tenant, args["company_id"],
                                               args["display_name"], identity)
                elif name == "unlimited_service_publish":
                    out = store.publish_service(
                        provider, tenant, args["company_id"], args["service_id"],
                        args["title"], args["price_minor"], args["currency"], identity)
                elif name == "unlimited_service_request":
                    out = store.request_service(
                        provider, tenant, args["company_id"], args["request_id"],
                        args["service_id"], args["payload"], identity)
                else:
                    out = {"companies": store.list_companies(provider, tenant, identity)}
                return json.dumps(out, sort_keys=True)
            except (PermissionError, RuntimeError, ValueError, KeyError, TypeError) as exc:
                return json.dumps({"ok": False, "reason": type(exc).__name__}, sort_keys=True)
        return handler

    for schema in SCHEMAS:
        ctx.register_tool(name=schema["name"], toolset="hermes_unlimited",
                          schema=schema, handler=make_handler(schema["name"]))
