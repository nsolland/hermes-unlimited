"""Portable read-only completion assessment; no worker invocation or authority.

A successful process return code is not evidence that a customer's goal was met.
The caller must provide an independently checked receipt for every required task.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Task:
    task_id: str
    dependencies: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class Observation:
    state: str
    evidence_digest: str = ""
    independently_verified: bool = False


def assess(tasks: Sequence[Task], observations: Mapping[str, Observation]) -> dict:
    if not tasks:
        raise ValueError("at least one task required")
    indexed = {task.task_id: task for task in tasks}
    if len(indexed) != len(tasks) or any(not key for key in indexed):
        raise ValueError("unique task identifiers required")
    if set(observations) - set(indexed):
        raise ValueError("unknown task result")
    for task in tasks:
        if task.task_id in task.dependencies or any(dep not in indexed for dep in task.dependencies):
            raise ValueError("invalid dependency")
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting:
            raise ValueError("cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for dep in indexed[node].dependencies:
            visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in indexed:
        visit(node)
    remaining = []
    for task in tasks:
        if not task.required:
            continue
        result = observations.get(task.task_id)
        if (result is None or result.state != "COMPLETED" or
                not result.independently_verified or not result.evidence_digest):
            remaining.append(task.task_id)
    return {"status": "TASKS_VERIFIED" if not remaining else "INCOMPLETE",
            "remaining": remaining,
            "goal_verified": False,
            "note": "Task evidence alone never proves the overarching goal completed.",
            "execution_authority": False}


def ready(tasks: Sequence[Task], observations: Mapping[str, Observation]) -> tuple[str, ...]:
    assess(tasks, observations)
    indexed = {task.task_id: task for task in tasks}
    return tuple(task.task_id for task in tasks if task.task_id not in observations and
                 all((observations.get(dep) is not None and
                      observations[dep].state == "COMPLETED" and
                      observations[dep].independently_verified and
                      bool(observations[dep].evidence_digest))
                     for dep in task.dependencies))
