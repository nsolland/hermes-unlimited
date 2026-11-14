"""Organizational role catalog, independent of model instances and tool authority.

Public crew roles are human-readable responsibility groupings. No role grants
access, starts a new model, or creates a durable worker on its own.
"""
from __future__ import annotations

from typing import Any

CREW_GROUPS: dict[str, tuple[str, ...]] = {
    "leadership": ("CEO", "COO", "CTO", "CFO", "CMO", "CRO"),
    "coordination": ("Conductor", "Coordinator", "Router"),
    "intelligence": ("Strategist", "Planner", "Optimizer", "Memory", "Scout", "Researcher", "Analyst"),
    "production": ("Producer", "Builder", "Coder", "Creator", "Designer", "Director", "Writer", "Composer", "Photographer", "Architect"),
    "operations": ("Tester", "Debugger", "Deployer", "Operator", "Maintainer", "Janitor"),
    "business_people": ("People", "Legal", "Security", "Customer Care", "Educator"),
    "assurance": ("Reviewer", "Verifier", "Skeptic", "Cynic"),
}

# Family maps to a role shown in the organization's visual catalog.
JUNIOR_PLACEMENTS: dict[str, tuple[str, str]] = {
    "gmail": ("business_people", "Customer Care"),
    "outlook": ("business_people", "Customer Care"),
    "slack": ("coordination", "Coordinator"),
    "github": ("production", "Coder"),
    "cloudflare": ("operations", "Operator"),
    "teams": ("coordination", "Coordinator"),
    "drive": ("intelligence", "Memory"),
    "calendar": ("coordination", "Coordinator"),
    "notion": ("intelligence", "Memory"),
    "jira": ("operations", "Operator"),
    "confluence": ("intelligence", "Memory"),
    "stripe": ("leadership", "CFO"),
    "hubspot": ("leadership", "CRO"),
    "telegram": ("business_people", "Customer Care"),
    "whatsapp": ("business_people", "Customer Care"),
    "via": ("operations", "Operator"),
}


# Domain specialist compositions are suggested team structure, not runnable agents.
RESEARCH_SPECIALIST = {
    "role": "Researcher",
    "domains": ["science_and_technology", "market_and_competition", "ip_and_patents",
                "politics_and_regulation", "security_and_risk", "opportunity_and_prediction"],
    "juniors": {
        "github": "Code repository evidence",
        "browser": "Web source retrieval",
        "patent": "Patent search and legal status",
        "papers": "Scientific literature retrieval",
        "prediction": "Forecast and scenario modelling",
        "skeptic": "Adversarial claim review",
        "data": "Data extraction and quality",
        "model": "Model evaluation and benchmarks",
        "news": "News signal tracking",
        "competition": "Competitor intelligence",
    },
    "outputs": ["validated_findings", "summary", "competitive_analysis",
                "patent_ip_status", "scenarios", "decision_evidence"],
    "execution_authorized": False,
    "status": "DESIGN_ONLY_UNVERIFIED",
}

INTEGRATION_CONDUCTORS = {
    "data": "Data integration and quality",
    "ai_model": "Models, routing and costs",
    "automation": "Workflows and agents",
    "integration": "API and tool compatibility",
    "security": "Identity and risk",
    "compliance": "Policy and evidence",
    "business": "Services, customers and economics",
    "development": "Code, delivery and operations",
}


def crew_catalog() -> dict[str, Any]:
    return {
        "hierarchy": ["owner", "frontier_orchestrator", "department_role", "specialist", "junior", "tool"],
        "orchestration": {"engine": "T3 / World Commander", "model_policy": "qualified-and-replaceable",
                          "always_on_frontier_required": False},
        "groups": {name: list(roles) for name, roles in CREW_GROUPS.items()},
        "integration_conductors": dict(INTEGRATION_CONDUCTORS),
        "research_specialist": dict(RESEARCH_SPECIALIST),
        "juniors": {name: {"group": group, "parent_role": role, "lifecycle": "DRAFT_UNVERIFIED"}
                    for name, (group, role) in JUNIOR_PLACEMENTS.items()},
        "execution_authorized": False,
    }


def validate_placement(family: str) -> tuple[str, str]:
    if family not in JUNIOR_PLACEMENTS:
        raise ValueError("JUNIOR_FAMILY_UNMAPPED")
    group, role = JUNIOR_PLACEMENTS[family]
    if role not in CREW_GROUPS[group]:
        raise ValueError("JUNIOR_PARENT_ROLE_INVALID")
    return group, role
