#!/usr/bin/env python3
"""Inspect one OOS cutoff before any official market capture or evidence write."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "backend"))

from oos_research.checkpoint_preflight import inspect_checkpoint_cutoff
from oos_research.store import StoreError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only OOS maturity checkpoint preflight")
    parser.add_argument("--checkpoints-root", required=True)
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--cutoff-session", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_checkpoint_cutoff(
            checkpoints_root=args.checkpoints_root,
            study_root=args.study_root,
            study_id=args.study_id,
            cutoff_session=args.cutoff_session,
        )
    except (OSError, StoreError, ValueError):
        error = {
            "schema_version": "oos.checkpoint-preflight.v1",
            "status": "error",
            "should_capture": False,
            "error_code": "preflight_configuration_or_evidence_error",
        }
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["status"] == "conflict" else 0


if __name__ == "__main__":
    raise SystemExit(main())
