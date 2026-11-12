"""Provider/tenant/company/service boundaries for the public plugin."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CompanySpec:
    provider_id: str
    tenant_id: str
    company_id: str
    display_name: str
    justyou_binding: str

    def __post_init__(self):
        if not all((self.provider_id, self.tenant_id, self.company_id, self.display_name, self.justyou_binding)):
            raise ValueError("Company identity and JustYou binding are mandatory")


@dataclass(frozen=True)
class ServiceSpec:
    company_id: str
    service_id: str
    title: str
    billing_model: Literal["fixed", "usage", "subscription"]


@dataclass(frozen=True)
class TaskReceipt:
    tenant_id: str
    company_id: str
    task_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    evidence_ref: str | None = None
