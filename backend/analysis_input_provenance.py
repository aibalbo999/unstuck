"""Freeze the complete per-mode input boundary before LLM analysis starts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from data_trust_snapshot_sanitizer import sanitize_for_snapshot


def freeze_analysis_inputs(data: dict[str, Any], *, cutoff: str | None = None) -> dict[str, str]:
    payload = {
        key: value
        for key, value in data.items()
        if key not in {"analysis_input_cutoff", "analysis_input_hash"}
    }
    encoded = json.dumps(
        sanitize_for_snapshot(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    receipt = {
        "analysis_input_cutoff": cutoff or datetime.now(timezone.utc).isoformat(),
        "analysis_input_hash": hashlib.sha256(encoded).hexdigest(),
    }
    data.update(receipt)
    return receipt
