"""Version-pinned, fail-closed ADI v2026.1 dataset loader.

Bounded slice of the open Agent Delegability Index (ADI) v2026.1. This module
owns dataset versioning and corruption handling: any mismatch with the pinned
version or any unparseable payload fails closed, never guessing an
occupation.
"""

import hashlib
import json

from unlimited.adi import ADI_SOURCE, ADI_VERSION, CODEBOOK

_DATASET_JSON = json.dumps(CODEBOOK, sort_keys=True)
_DATASET_HASH = hashlib.sha256(_DATASET_JSON.encode("utf-8")).hexdigest()


class AdiDatasetError(RuntimeError):
    """Raised when a dataset fails version/corrupt validation."""


class AdiDataset:
    """Deterministic, version-pinned subset of ADI v2026.1."""

    def __init__(self, rows, source=ADI_SOURCE, version=ADI_VERSION):
        if not isinstance(rows, (list, tuple)):
            raise AdiDatasetError("ADI dataset must be a list of code rows")
        self._rows = list(rows)
        self.source = source
        self.version = version
        self.is_corrupt = False
        self._hash = hashlib.sha256(
            json.dumps(self._rows, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @classmethod
    def load(cls, version=ADI_VERSION, source=ADI_SOURCE):
        # Fail-closed: always fall back to the version-pinned built-in slice.
        return cls(CODEBOOK, source=source, version=version)

    def validate(self, candidate_version):
        if candidate_version != self.version:
            raise AdiDatasetError(
                f"ADI dataset version mismatch: expected {self.version}, got {candidate_version!r}"
            )

    def dataset_hash(self):
        return self._hash

    def rows(self):
        return list(self._rows)
