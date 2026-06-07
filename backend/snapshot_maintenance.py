"""Maintenance helpers for data snapshot integrity hashes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR
from data_trust_snapshot import set_snapshot_integrity, verify_data_snapshot_integrity


def verify_snapshots(output_dir: Optional[str] = None, write: bool = False) -> dict:
    root = Path(output_dir or OUTPUT_DIR)
    files = sorted(root.glob("*.data.json")) if root.exists() else []
    results = []
    for path in files:
        results.append(_verify_one(path, write=write))
    return {
        "output_dir": str(root),
        "checked": len(results),
        "missing_hash": sum(1 for item in results if item["status"] == "missing_hash"),
        "backfilled": sum(1 for item in results if item["status"] == "backfilled"),
        "mismatch": sum(1 for item in results if item["status"] == "mismatch"),
        "invalid": sum(1 for item in results if item["status"] == "invalid_json"),
        "results": results,
    }


def _verify_one(path: Path, write: bool = False) -> dict:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"file": path.name, "status": "invalid_json", "message": str(exc)[:180]}
    if not isinstance(snapshot, dict):
        return {"file": path.name, "status": "invalid_json", "message": "snapshot is not an object"}

    has_hash = bool(snapshot.get("snapshot_hash") or snapshot.get("content_hash"))
    integrity = verify_data_snapshot_integrity(snapshot)
    if has_hash and not integrity["valid"]:
        return {
            "file": path.name,
            "status": "mismatch",
            "hash": integrity.get("hash", ""),
            "expected_hash": integrity.get("expected_hash", ""),
        }
    if has_hash:
        return {"file": path.name, "status": "ok", "hash": integrity.get("hash") or snapshot.get("snapshot_hash", "")}

    if not write:
        return {"file": path.name, "status": "missing_hash"}
    set_snapshot_integrity(snapshot)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"file": path.name, "status": "backfilled", "hash": snapshot.get("snapshot_hash", "")}
