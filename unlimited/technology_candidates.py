"""Discovery register for podcast candidates: candidates are not approved integrations."""

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Candidate:
    name: str
    project: str
    priority: str
    decision_area: str
    repository: Optional[str] = None
    stage: str = "DISCOVERY_UNVERIFIED"

CANDIDATES = (
    Candidate("Ember Cloudflare", "Communications", "P0", "managed chat TCO", "https://github.com/NYLLON-SOFTWARE/ember-cloudflare"),
    Candidate("REA Video", "Creative", "P1", "video analysis adapter", "https://github.com/JuneYaooo/rea-video"),
    Candidate("OpenGenjutsu", "Creative", "P2", "optional video effect", "https://github.com/Anil-matcha/open-genjutsu"),
    Candidate("Sherlock", "Intelligence", "P2", "OSINT", "https://github.com/sherlock-project/sherlock"),
    Candidate("Anthropic Skills", "Agent skills", "P0", "skill compatibility", "https://github.com/anthropics/skills"),
    Candidate("OpenMausBot", "Agent operations", "P0", "Hermes competitor benchmark", "https://github.com/milind-soni/OpenMausBot"),
    Candidate("Agent Browser", "Browser", "P0", "browser session adapter", "https://github.com/vercel-labs/agent-browser"),
    Candidate("Daily Stock Analysis", "Finance", "P2", "optional vertical research", "https://github.com/ZhuLinsen/daily_stock_analysis"),
    Candidate("NVIDIA AutoOntology", "Company intelligence", "P0", "semantic data access", "https://github.com/NVIDIA/auto-ontology"),
    Candidate("MuJoCo", "Simulation", "P1", "physical simulation", "https://github.com/google-deepmind/mujoco"),
    Candidate("Matt Pocock Skills", "Agent skills", "P1", "development agent skills", "https://github.com/mattpocock/skills"),
    Candidate("Addy Osmani Agent Skills", "Agent skills", "P1", "development agent skills", "https://github.com/addyosmani/agent-skills"),
    Candidate("Cloudflare Security Audit Skill", "Assurance", "P0", "independent security verification", "https://github.com/cloudflare/security-audit-skill"),
    Candidate("Atlas", "Memory", "P0", "The Thread competitor benchmark", "https://github.com/tryatlas/atlas"),
    Candidate("Bomby", "Voice UI", "P1", "voice agent interface", "https://github.com/bomby-app/bomby"),
    Candidate("Sprint Wake Projects", "Unknown", "P2", "resolve exact repository"),
    Candidate("Rightsize", "Economics", "P0", "JevRouter outcome-cost benchmark", "https://github.com/archid21/rightsize"),
)

def summary() -> dict:
    return {
        "count": len(CANDIDATES),
        "unresolved_repositories": [x.name for x in CANDIDATES if not x.repository],
        "ready_for_production": [x.name for x in CANDIDATES if x.stage == "PRODUCTION_VERIFIED"],
        "priorities": {p: sum(c.priority == p for c in CANDIDATES) for p in ("P0", "P1", "P2")},
    }
