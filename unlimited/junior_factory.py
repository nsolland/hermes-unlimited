"""Tool-first junior agent profiles and fail-closed, tenant-scoped read execution.

A junior owns exactly one adapter family. Descriptors do not imply a real
connection, credentials, model qualification, or permission to perform effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence

from .specialist_factory import Capability, Trial, rank_models, _digest


@dataclass(frozen=True)
class JuniorOperation:
    name: str
    effect: str
    required_arguments: tuple[str, ...]


@dataclass(frozen=True)
class JuniorBlueprint:
    id: str
    family: str
    role: str
    tool: str
    operations: tuple[JuniorOperation, ...]
    schema_digest: str
    tenant: str
    model_id: str | None = None
    status: str = "DRAFT_UNVERIFIED"


GMAIL_OPERATIONS = (
    JuniorOperation("list_messages", "read", ("query",)),
    JuniorOperation("get_message", "read", ("message_id",)),
    JuniorOperation("create_draft", "write", ("to", "subject", "body")),
    JuniorOperation("send_message", "write", ("message_id",)),
    JuniorOperation("trash_message", "write", ("message_id",)),
)

TEMPLATES = {
    "gmail": ("Junior Gmail Agent", "gmail", GMAIL_OPERATIONS),
    "outlook": ("Junior Outlook Agent", "outlook", (
        JuniorOperation("search_messages", "read", ("query",)),
        JuniorOperation("get_message", "read", ("message_id",)),
        JuniorOperation("create_draft", "write", ("to", "subject", "body")),
        JuniorOperation("send_message", "write", ("message_id",)),
    )),
    "slack": ("Junior Slack Agent", "slack", (
        JuniorOperation("search_messages", "read", ("query",)),
        JuniorOperation("get_thread", "read", ("channel", "thread_ts")),
        JuniorOperation("post_message", "write", ("channel", "text")),
    )),
    "github": ("Junior GitHub Agent", "github", (
        JuniorOperation("list_issues", "read", ("repository",)),
        JuniorOperation("get_issue", "read", ("repository", "number")),
        JuniorOperation("create_issue", "write", ("repository", "title", "body")),
    )),
    "cloudflare": ("Junior Cloudflare Agent", "cloudflare", (
        JuniorOperation("list_dns_records", "read", ("zone_id",)),
        JuniorOperation("get_zone", "read", ("zone_id",)),
        JuniorOperation("update_dns_record", "write", ("zone_id", "record_id")),
    )),
}


def catalog() -> dict[str, Any]:
    """Advertise templates, not a claim of installed host connections."""
    from .crew_hierarchy import validate_placement
    return {name: {"role": role, "tool": tool,
                   "parent_group": validate_placement(name)[0],
                   "parent_role": validate_placement(name)[1],
                   "operations": [asdict(op) for op in operations],
                   "connected": False, "execution_authorized": False,
                   "runtime_adapter_available": name == "gmail"}
            for name, (role, tool, operations) in TEMPLATES.items()}


def propose_junior(family: str, tenant: str, operations: Sequence[str],
                   *, model_evaluation: Mapping[str, Any] | None = None) -> JuniorBlueprint:
    if family not in TEMPLATES or not isinstance(tenant, str) or not tenant.strip():
        raise ValueError("INVALID_JUNIOR_SCOPE")
    role, tool, allowed = TEMPLATES[family]
    names = [x.name for x in allowed]
    if not operations or len(set(operations)) != len(operations) or any(x not in names for x in operations):
        raise ValueError("UNKNOWN_OR_DUPLICATED_OPERATION")
    selected = tuple(op for op in allowed if op.name in operations)
    digest = _digest({"family": family, "tool": tool, "operations": [asdict(x) for x in selected]})
    # An untrusted model_evaluation argument must never certify a model.
    return JuniorBlueprint("junior-" + digest[:16], family, role, tool, selected, digest,
                           tenant)



def propose_tool_junior(capability: Capability, tenant: str, *, objective: str) -> JuniorBlueprint:
    """Build a one-tool junior from a reviewed *actual* Hermes/MCP schema.

    Descriptive metadata alone cannot grant access. Unknown effects remain blocked,
    and only a host-approved read dispatch can execute the resulting blueprint.
    """
    if not isinstance(capability, Capability) or capability.effect not in ("read", "write", "execute"):
        raise PermissionError("JUNIOR_CAPABILITY_EFFECT_UNREVIEWED")
    if not isinstance(tenant, str) or not tenant.strip() or not isinstance(objective, str) or not objective.strip():
        raise ValueError("JUNIOR_OBJECTIVE_OR_SCOPE_INVALID")
    op = JuniorOperation(capability.tool_name, capability.effect, capability.required)
    digest = _digest({"tool": capability.tool_name, "schema": capability.schema_digest,
                      "effect": capability.effect, "objective": objective.strip()})
    return JuniorBlueprint("junior-"+digest[:16], "tool", objective.strip(),
                           capability.tool_name, (op,), digest, tenant)


def evaluate_models(trials: Sequence[Trial], required_cases: Sequence[str],
                    *, min_pass_rate: float = 0.98, min_repetitions: int = 3) -> dict[str, Any]:
    return rank_models(trials, required_cases, min_pass_rate=min_pass_rate,
                       min_repetitions=min_repetitions)


def junior_manifest(blueprint: JuniorBlueprint) -> dict[str, Any]:
    return {**asdict(blueprint), "execution_authorized": False,
            "connected": False, "model_qualified": blueprint.model_id is not None}


def dispatch_read(blueprint: JuniorBlueprint, operation: str, arguments: Mapping[str, Any], *,
                  tenant: str, identity: str, verify_identity: Callable[[str, str], bool],
                  authorize: Callable[[str, str, str, str], bool],
                  adapter: Callable[[str, Mapping[str, Any]], Any]) -> dict[str, Any]:
    """Invoke a host-injected Gmail adapter. Never execute arbitrary writes.

    Identity and operation authorization are independently verified by the host.
    A proposal or a model verdict by itself never enables a Gmail operation.
    """
    if not isinstance(blueprint, JuniorBlueprint) or tenant != blueprint.tenant or not identity:
        raise PermissionError("JUNIOR_TENANT_DENIED")
    if verify_identity(tenant, identity) is not True:
        raise PermissionError("JUNIOR_IDENTITY_DENIED")
    candidates = [x for x in blueprint.operations if x.name == operation]
    if len(candidates) != 1 or candidates[0].effect != "read":
        raise PermissionError("JUNIOR_OPERATION_NOT_READ_ONLY")
    if not isinstance(arguments, dict) or set(arguments) != set(candidates[0].required_arguments):
        raise ValueError("JUNIOR_ARGUMENTS_INVALID")
    if any(not isinstance(v, str) or not v.strip() or len(v) > 2048 for v in arguments.values()):
        raise ValueError("JUNIOR_ARGUMENTS_INVALID")
    if authorize(tenant, identity, blueprint.tool, operation) is not True:
        raise PermissionError("JUNIOR_HOST_AUTHORIZATION_DENIED")
    if not callable(adapter):
        raise PermissionError("JUNIOR_HOST_ADAPTER_UNAVAILABLE")
    result = adapter(operation, dict(arguments))
    return {"tool": blueprint.tool, "operation": operation, "result": result,
            "execution_authorized": True, "external_write": False}
