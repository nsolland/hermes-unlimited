"""Idempotent Hermes delivery with stable task identity and effect observation.

A retry after process crash uses the same Hermes idempotency key. The sink
checks that the actual Hermes task is visible before acknowledging the inbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .justyou_durable_inbox import Delivery


@dataclass(frozen=True)
class HermesInboundSink:
    kanban: Any
    tenant: str
    assignee: str
    identity_evidence: dict

    def __call__(self, delivery: Delivery) -> None:
        if self.identity_evidence.get("identity") != delivery.message.recipient:
            raise PermissionError("recipient identity mismatch")
        task_id = "inbound-" + delivery.key
        result = self.kanban.enqueue(
            tenant=self.tenant,
            assignee=self.assignee,
            task_id=task_id,
            title="Verified inbound: " + delivery.message.message_id,
            body=delivery.message.text,
            identity_evidence=self.identity_evidence,
        )
        observed = self.kanban.result(
            tenant=self.tenant, assignee=self.assignee,
            task_id=result["task_id"])
        if not observed.get("found"):
            raise RuntimeError("HERMES_EFFECT_NOT_OBSERVED")
