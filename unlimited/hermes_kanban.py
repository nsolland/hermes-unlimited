"""Native Hermes Kanban adapter.

Hermes owns execution. Unlimited submits only after a trusted JustYou
verification and reads actual task state. No synchronous wait/timeout guessing.
"""
import json
import re
import subprocess

TASK_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ROLE_ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class HermesKanban:
    def __init__(self, hermes="hermes", run=None):
        self.hermes = hermes
        self.run = run or subprocess.run

    def _invoke(self, args):
        try:
            result = self.run([self.hermes, "kanban", *args], capture_output=True,
                              text=True, timeout=45)
            if result.returncode != 0:
                raise RuntimeError("HERMES_KANBAN_FAILED")
            return json.loads(result.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            raise RuntimeError("HERMES_KANBAN_UNAVAILABLE") from exc

    def enqueue(self, *, tenant, assignee, task_id, title, body, identity_evidence):
        if (not isinstance(identity_evidence, dict)
                or identity_evidence.get("verified") is not True
                or identity_evidence.get("authority_granted") is not False
                or not identity_evidence.get("binding_digest")
                or identity_evidence.get("profile") != assignee):
            raise PermissionError("JUSTYOU_PROFILE_NOT_VERIFIED")
        if not all(isinstance(v, str) and ROLE_ID.fullmatch(v) for v in (tenant, assignee)):
            raise ValueError("SCOPE_INVALID")
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise ValueError("TASK_ID_INVALID")
        if not isinstance(title, str) or not title.strip() or len(title) > 256:
            raise ValueError("TASK_TITLE_INVALID")
        if not isinstance(body, str) or len(body) > 8192:
            raise ValueError("TASK_BODY_INVALID")
        result = self._invoke([
            "create", title.strip(), "--body", body,
            "--assignee", assignee, "--tenant", tenant,
            "--created-by", "hermes-unlimited", "--idempotency-key",
            f"{tenant}:{task_id}", "--json"])
        if not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError("TASK_CREATE_UNVERIFIED")
        return {"status": "TASK_QUEUED", "task_id": str(result["id"]),
                "tenant": tenant, "assignee": assignee, "executed": False}

    def result(self, *, tenant, assignee, task_id):
        if not all(isinstance(v, str) and ROLE_ID.fullmatch(v) for v in (tenant, assignee)):
            raise ValueError("SCOPE_INVALID")
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise ValueError("TASK_ID_INVALID")
        items = self._invoke(["list", "--tenant", tenant, "--json"])
        if not isinstance(items, list):
            raise RuntimeError("TASK_LIST_INVALID")
        matches = [x for x in items if isinstance(x, dict)
                   and str(x.get("id")) == task_id and x.get("tenant") == tenant
                   and x.get("assignee") == assignee
                   and x.get("created_by") == "hermes-unlimited"]
        if len(matches) != 1:
            return {"found": False, "completed": False}
        status = matches[0].get("status")
        if status not in {"triage", "todo", "ready", "running", "review", "done",
                          "blocked", "scheduled", "archived"}:
            raise RuntimeError("TASK_STATE_INVALID")
        return {"found": True, "completed": status == "done",
                "status": status, "independently_verified": False}
