"""Read-only, credential-free installation diagnostics for the public plugin."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def diagnose(*, root: str | Path | None = None, binaries=("hermes",), min_python=(3, 10)):
    """Check locally available prerequisites; do not connect or claim live readiness."""
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    checks = [
        Check("python", "ok" if sys.version_info[:2] >= min_python else "fail",
              f"{sys.version_info.major}.{sys.version_info.minor}"),
        Check("plugin_manifest", "ok" if (base / "plugin.yaml").is_file() else "fail",
              "plugin.yaml present" if (base / "plugin.yaml").is_file() else "plugin.yaml missing"),
        Check("plugin_entry", "ok" if (base / "__init__.py").is_file() else "fail",
              "entrypoint present" if (base / "__init__.py").is_file() else "entrypoint missing"),
    ]
    for name in binaries:
        resolved = shutil.which(name)
        checks.append(Check(f"binary:{name}", "ok" if resolved else "unavailable",
                            "on PATH" if resolved else "not found on PATH"))
    return {"checks": [asdict(c) for c in checks],
            "ready_for_local_plugin_inspection": all(c.status == "ok" for c in checks[:3]),
            "live_host_verified": False, "customer_execution_verified": False}


def main():
    print(json.dumps(diagnose(), sort_keys=True, indent=2))
    return 0 if diagnose()["ready_for_local_plugin_inspection"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
