"""Optional T3 access via an injected, authorized World Commander service.

No direct T3 execution, no alternative authority path, and no credentials stored.
The trusted host must scope each call to its authenticated company and project.
"""

import re

_THREAD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class T3ClientError(RuntimeError):
    pass


class T3WorldCommanderClient:
    def __init__(self, dispatch, *, tenant, project_id):
        if not callable(dispatch):
            raise TypeError("trusted World Commander dispatcher required")
        if not isinstance(tenant, str) or not tenant or not tenant.replace("-", "").isalnum():
            raise ValueError("invalid tenant")
        if not isinstance(project_id, str) or not project_id or not project_id.replace("_", "").replace("-", "").isalnum():
            raise ValueError("invalid project")
        self._dispatch = dispatch
        self._tenant = tenant
        self._project = project_id

    def _call(self, operation, **params):
        # Tenant/project are host-bound values, never accepted from task payloads.
        result = self._dispatch(operation, tenant=self._tenant,
                                project_id=self._project, **params)
        if not isinstance(result, dict) or not result.get("evidence_ref"):
            raise T3ClientError("World Commander effect observation missing")
        if result.get("verified") is True:
            raise T3ClientError("T3 agent output cannot imply independent verification")
        return result

    def start(self, instruction):
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("empty instruction")
        result = self._call("t3.start", instruction=instruction)
        if not isinstance(result.get("thread_id"), str) or not result["thread_id"]:
            raise T3ClientError("thread ID missing")
        if result.get("completed") is not False:
            raise T3ClientError("start is not completion")
        if result.get("project_id") != self._project:
            raise T3ClientError("T3 returned another project")
        return result

    def read(self, thread_id):
        if not isinstance(thread_id, str) or not _THREAD_ID.fullmatch(thread_id):
            raise ValueError("invalid thread ID")
        result = self._call("t3.show", thread_id=thread_id)
        if result.get("project_id") != self._project or result.get("thread_id") != thread_id:
            raise T3ClientError("T3 readback scope mismatch")
        return result
