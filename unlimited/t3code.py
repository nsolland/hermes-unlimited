"""Optional T3 Code CLI adapter; T3 owns agent execution and authentication.

Upstream: https://github.com/pingdotgg/t3code
Interface: `t3 thread start/send/show/list` documented in
https://github.com/pingdotgg/t3code/blob/main/docs/user/outside-agents.md
No T3 source is vendored. Caller is responsible for tenant/project authorization
before invoking this adapter; a local T3 host is a privileged execution boundary.
"""
import re
import subprocess

_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class T3CodeError(RuntimeError):
    """T3 CLI unavailable, failed or returned an invalid response."""


class T3Code:
    def __init__(self, *, executable="t3", timeout=120, runner=subprocess.run):
        if not isinstance(executable, str) or not executable or any(c in executable for c in "\x00\r\n"):
            raise ValueError("invalid T3 executable")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be positive")
        self.executable = executable
        self.timeout = timeout
        self._run = runner

    def _call(self, *args):
        try:
            result = self._run(
                [self.executable, "thread", *args],
                capture_output=True, text=True, timeout=self.timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise T3CodeError("T3 CLI failed or timed out") from exc
        if result.returncode != 0:
            raise T3CodeError("T3 CLI command failed")
        if not isinstance(result.stdout, str):
            raise T3CodeError("T3 CLI returned invalid output")
        return result.stdout.strip()

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or not _ID.fullmatch(value) or value.startswith("-"):
            raise ValueError("invalid T3 thread or project identifier")
        return value

    def start(self, project_id, instruction, *, worktree=None):
        """Create a thread and return its ID, not a claim that work completed."""
        self._id(project_id)
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction must be nonempty")
        args = ["start", project_id, instruction]
        if worktree is not None:
            if not isinstance(worktree, str) or not worktree or worktree.startswith("-") or "\x00" in worktree:
                raise ValueError("invalid worktree base")
            args.extend(["--worktree", worktree])
        result = self._call(*args)
        if not _ID.fullmatch(result) or result.startswith("-"):
            raise T3CodeError("T3 did not return a valid thread ID")
        return result

    def send(self, thread_id, instruction, *, wait=False):
        """Queue follow-up or await its result (nonzero exits fail closed)."""
        self._id(thread_id)
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction must be nonempty")
        return self._call("send", thread_id, instruction, *(["--wait"] if wait else []))

    def show(self, thread_id):
        """Read raw T3 thread details. No inferred completion state."""
        return self._call("show", self._id(thread_id))

    def list(self):
        """Read raw T3 thread listing."""
        return self._call("list")
