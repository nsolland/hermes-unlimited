"""ADI v2026.1 delegability evidence (advisory only).

Implements a bounded slice of ADI v2026.1 for Hermes Unlimited: task-level
delegability signal (L0-L3, four barriers, explicit unmapped/unknown), with
provenance (source/version plus dataset hash) and fail-closed handling.

HARD BOUNDARY:
- Every outcome returned by this module carries advisory_only=True.
- No ADI signal may issue an execution permit, bypass JustYou/REHT, or authorize
  an external effect. Callers must use this only for advice/routing rationale.
- The provider refuses to fabricate an occupation; unmapped tasks stay unmapped.
"""

import hashlib
import json
import re

ADI_VERSION = "2026.1"
ADI_SOURCE = "ADI v2026.1"

ADI_LEVELS = ("L0", "L1", "L2", "L3")
ADI_BARRIERS = ("physical", "accountability", "trust", "access")

# Version-pinned dataset (bounded slice). Each row is advisory; confidence is
# between 0 and 1. Absence from this table => unmapped, never silently guessed.
CODEBOOK = [
    {
        "code": "routine-administrative",
        "label": "routine administrative",
        "level": "L0",
        "confidence": 0.90,
        "uncertainty": "low",
        "barriers": {"physical": False, "accountability": False, "trust": False, "access": False},
        "source": ADI_SOURCE,
    },
    {
        "code": "research-analyst",
        "label": "research analyst",
        "level": "L1",
        "confidence": 0.84,
        "uncertainty": "low",
        "barriers": {"physical": False, "accountability": False, "trust": False, "access": False},
        "source": ADI_SOURCE,
    },
    {
        "code": "builder-developer",
        "label": "builder / developer",
        "level": "L2",
        "confidence": 0.73,
        "uncertainty": "low",
        "barriers": {"physical": False, "accountability": True, "trust": True, "access": False},
        "source": ADI_SOURCE,
    },
    {
        "code": "verifier-auditor",
        "label": "verifier / auditor",
        "level": "L2",
        "confidence": 0.70,
        "uncertainty": "low",
        "barriers": {"physical": False, "accountability": False, "trust": False, "access": False},
        "source": ADI_SOURCE,
    },
    {
        "code": "field-operator",
        "label": "field operator",
        "level": "L2",
        "confidence": 0.62,
        "uncertainty": "medium",
        "barriers": {"physical": True, "accountability": False, "trust": True, "access": True},
        "source": ADI_SOURCE,
    },
    {
        "code": "remote-executor",
        "label": "remote executor",
        "level": "L3",
        "confidence": 0.56,
        "uncertainty": "high",
        "barriers": {"physical": False, "accountability": True, "trust": True, "access": True},
        "source": ADI_SOURCE,
    },
]

_CODEBOOK_JSON = json.dumps(CODEBOOK, sort_keys=True)
_DATASET_HASH = hashlib.sha256(_CODEBOOK_JSON.encode("utf-8")).hexdigest()


def dataset_hash():
    """Version-pinned SHA-256 of the codebook table for provenance."""
    return _DATASET_HASH


def _match_occupation(text, dataset=None):
    tn = _normalize(text)
    table = dataset if dataset is not None else CODEBOOK
    for entry in table:
        if _normalize(entry["code"]) in tn or _normalize(entry["label"]) in tn:
            return entry
    return None


def _normalize(value):
    """Lowercase and strip non-alphanumeric so matching is token-flexible."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


class AdiOutcome:
    """Advisory-only result; never carries an execution permit."""

    def __init__(self, level, barriers, confidence, uncertainty, unmapped, reason,
                 source=ADI_SOURCE, version=ADI_VERSION, dataset_hash=None):
        self.level = level
        self.barriers = barriers
        self.confidence = confidence
        self.uncertainty = uncertainty
        self.unmapped = unmapped
        self.reason = reason
        self.source = source
        self.version = version
        self.dataset_hash = dataset_hash

    @property
    def advisory_only(self):
        return True

    def as_dict(self):
        return {
            "advisory_only": self.advisory_only,
            "level": self.level,
            "barriers": dict(self.barriers),
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "unmapped": self.unmapped,
            "reason": self.reason,
            "source": self.source,
            "version": self.version,
            "dataset_hash": self.dataset_hash,
        }


class AdiProvider:
    """Version-pinned ADI v2026.1 provider with fail-closed behavior."""

    def __init__(self, dataset=None, version=ADI_VERSION, offline=False):
        self.dataset = CODEBOOK if dataset is None else dataset
        self.version = version
        self.offline = offline

    def score(self, task_text):
        """Compute the advisory ADI signal for the given task text."""
        result = {
            "level": None,
            "barriers": {b: False for b in ADI_BARRIERS},
            "confidence": None,
            "uncertainty": "unknown",
            "unmapped": True,
            "reason": "no occupation matched; task remains unmapped and NOT silently assigned",
            "source": ADI_SOURCE,
            "version": self.version,
            "dataset_hash": dataset_hash(),
        }
        if self.offline:
            return AdiOutcome(**result)
        if self.dataset is None:
            return AdiOutcome(**result)
        entry = _match_occupation(task_text, self.dataset)
        if entry is None:
            return AdiOutcome(**result)
        return AdiOutcome(
            level=entry.get("level", None),
            barriers=entry.get("barriers", {b: False for b in ADI_BARRIERS}),
            confidence=entry.get("confidence"),
            uncertainty=entry.get("uncertainty", "unknown"),
            unmapped=False,
            reason=result["reason"] if entry.get("code") is None else f"matched {entry.get('code')}",
            dataset_hash=dataset_hash(),
        )

    @property
    def advisory_only(self):
        return True

    def require_permit(self):
        """Deliberately raises: this module never issues execution permits."""
        raise PermissionError("ADI delegability evidence is advisory only; no permit issued")
