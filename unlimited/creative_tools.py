"""Hermes Creative Studio tools with trusted workflow and ownership boundaries."""
import json
import re

from .adapter_gate import AdapterDenied, authorize_adapter
from pathlib import Path
from .comfyui import ComfyUI, ComfyUIError

_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SCHEMAS = (
    {"name": "unlimited_creative_render", "description": "Render a curated ComfyUI workflow for the verified profile.",
     "parameters": {"type": "object", "properties": {
         "workflow": {"type": "string", "maxLength": 64},
         "prompt": {"type": "string", "minLength": 1, "maxLength": 4096}},
         "required": ["workflow", "prompt"], "additionalProperties": False}},
    {"name": "unlimited_creative_result", "description": "Read state of a ComfyUI job owned by the verified profile.",
     "parameters": {"type": "object", "properties": {"prompt_id": {"type": "string", "maxLength": 128}},
                    "required": ["prompt_id"], "additionalProperties": False}},
)


def register_creative_tools(ctx, scoped_secret, scoped_identity):
    def handler(args=None, *, kind):
        schema = SCHEMAS[kind]["parameters"]
        if not isinstance(args, dict) or set(args) != set(schema["required"]):
            return json.dumps({"ok": False, "reason": "INVALID_ARGUMENTS"})
        try:
            tenant, evidence = scoped_identity()
            identity = evidence["identity"]
            # Host-owned approval must be checked before creating a client or
            # dispatching optional media work. Catalog metadata grants nothing.
            root = Path(__file__).resolve().parents[1]
            authorize_adapter("comfyui", catalog_path=root / "adapters/catalog.json",
                approvals_path=root / "adapters/approvals.json", host_scope=tenant,
                capability="render" if kind == 0 else "result")
            origin = scoped_secret("HERMES_UNLIMITED_COMFYUI_URL", "")
            resolver = getattr(ctx, "comfyui_workflow_resolver", None)
            store = getattr(ctx, "comfyui_job_store", None)
            if not origin or not callable(resolver) or store is None:
                raise PermissionError("CREATIVE_BACKEND_NOT_CONFIGURED")
            client_factory = getattr(ctx, "comfyui_client_factory", ComfyUI)
            client = client_factory(origin)
            if kind == 0:
                name, prompt = args["workflow"], args["prompt"]
                if not isinstance(name, str) or not _NAME.fullmatch(name) or not isinstance(prompt, str) or not 1 <= len(prompt) <= 4096:
                    raise ValueError("INVALID_ARGUMENTS")
                # Resolver must return reviewed API-format nodes, not caller-supplied code.
                workflow = resolver(name, prompt, tenant=tenant, identity=identity)
                if not isinstance(workflow, dict) or not workflow:
                    raise PermissionError("WORKFLOW_NOT_ALLOWED")
                ack = client.submit(workflow)
                store.record(tenant, identity, ack["prompt_id"])
                return json.dumps({"ok": True, "state": "submitted", "prompt_id": ack["prompt_id"]})
            prompt_id = args["prompt_id"]
            if not isinstance(prompt_id, str) or not _NAME.fullmatch(prompt_id) or not store.owns(tenant, identity, prompt_id):
                raise PermissionError("JOB_NOT_OWNED")
            return json.dumps({"ok": True, **client.result(prompt_id)})
        except (PermissionError, RuntimeError, ValueError, KeyError, TypeError, AttributeError, ComfyUIError, AdapterDenied) as exc:
            return json.dumps({"ok": False, "reason": type(exc).__name__})

    for index, schema in enumerate(SCHEMAS):
        ctx.register_tool(name=schema["name"], toolset="hermes_unlimited", schema=schema,
                          handler=lambda args=None, _index=index, **kwargs: handler(args, kind=_index))
