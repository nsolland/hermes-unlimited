"""Fail-closed host preflight for resource-sensitive harness experiments.

Linux /proc support only. The guard checks resource headroom, not scientific
isolation; passing does not prove other workloads are absent.
"""
import argparse
import json
import os
from pathlib import Path


def inspect_host(load1=None, cpu_count=None, meminfo=None, *, max_load_per_cpu=0.8,
                 max_swap_fraction=0.30, min_available_bytes=1_500_000_000):
    if meminfo is None:
        text = Path("/proc/meminfo").read_text()
        meminfo = {}
        for line in text.splitlines():
            key, _, value = line.partition(":")
            if key in ("MemAvailable", "SwapTotal", "SwapFree"):
                meminfo[key] = int(value.strip().split()[0])*1024
    if load1 is None:
        load1 = os.getloadavg()[0]
    if cpu_count is None:
        cpu_count = os.cpu_count()
    if not cpu_count or cpu_count < 1:
        raise ValueError("cannot determine CPU count")
    for key in ("MemAvailable", "SwapTotal", "SwapFree"):
        if key not in meminfo or meminfo[key] < 0:
            raise ValueError(f"missing or invalid host metric: {key}")
    if meminfo["SwapFree"] > meminfo["SwapTotal"]:
        raise ValueError("swap free cannot exceed total")
    swap_fraction = ((meminfo["SwapTotal"]-meminfo["SwapFree"]) / meminfo["SwapTotal"]
                     if meminfo["SwapTotal"] else 0.0)
    load_per_cpu = load1 / cpu_count
    reasons = []
    if load_per_cpu > max_load_per_cpu:
        reasons.append("HIGH_LOAD")
    if swap_fraction > max_swap_fraction:
        reasons.append("SWAP_PRESSURE")
    if meminfo["MemAvailable"] < min_available_bytes:
        reasons.append("LOW_AVAILABLE_MEMORY")
    return {"admissible": not reasons, "reasons": reasons, "load1": load1,
            "cpu_count": cpu_count, "load_per_cpu": load_per_cpu,
            "swap_fraction": swap_fraction,
            "memory_available_bytes": meminfo["MemAvailable"],
            "check_scope": "Linux host resource guard, not workload isolation"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = inspect_host()
    except (OSError, ValueError) as e:
        result = {"admissible": False, "reasons": ["PREFLIGHT_ERROR"], "error": str(e)}
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2))
    return 0 if result["admissible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
