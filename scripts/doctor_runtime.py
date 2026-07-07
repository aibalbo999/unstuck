#!/usr/bin/env python3
"""Print the canonical local runtime map and basic storage checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _path_status(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }


def build_doctor_payload() -> dict[str, object]:
    from runtime_paths import current_runtime_paths

    paths = current_runtime_paths()
    return {
        "runtime_paths": paths.as_dict(),
        "checks": {
            "output_dir": _path_status(paths.output_dir),
            "cache_dir": _path_status(paths.cache_dir),
            "report_index_db": _path_status(paths.report_index_db),
            "operational_db": _path_status(paths.operational_db),
            "legacy_decision_tracking_db": {
                **_path_status(paths.legacy_decision_tracking_db),
                "canonical": False,
                "message": "legacy migration only; do not use this file to verify current tracking state",
            },
        },
    }


def _print_text(payload: dict[str, object]) -> None:
    runtime_paths = payload["runtime_paths"]
    checks = payload["checks"]
    assert isinstance(runtime_paths, dict)
    assert isinstance(checks, dict)
    print("Runtime Truth Map")
    print("=================")
    for key in (
        "output_dir",
        "cache_dir",
        "report_index_db",
        "operational_db",
        "task_db",
        "decision_tracking_db",
        "legacy_decision_tracking_db",
        "langgraph_checkpoint_path",
        "cache_backend",
        "redis_url",
        "task_queue_backend",
        "task_queue_name",
    ):
        value = runtime_paths.get(key)
        if isinstance(value, dict):
            marker = "canonical" if value.get("canonical") else "legacy"
            print(f"{key}: {value.get('path')} ({marker}, owner={value.get('owner')})")
        else:
            print(f"{key}: {value}")
    print("")
    print("Storage Checks")
    print("==============")
    for key, value in checks.items():
        if not isinstance(value, dict):
            continue
        status = "exists" if value.get("exists") else "missing"
        print(f"{key}: {value.get('path')} [{status}]")
        message = value.get("message")
        if message:
            print(f"  note: {message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print canonical stock-agent runtime paths.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)
    payload = build_doctor_payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
