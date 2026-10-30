"""Preview reviewed unscored dispositions; apply only after separate approval.

No environment-derived DB default. Preview opens the explicit existing DB with
mode=ro and never imports or runs a scanner, evaluator, provider, or scheduler.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from legacy76_dispositions import apply, preview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "apply"):
        sub = commands.add_parser(command)
        sub.add_argument("--db", type=Path, required=True, help="explicit existing operational database")
        sub.add_argument("--request", type=Path, required=command == "apply", help="explicit reviewer decisions; never generated as approved")
        if command == "apply":
            sub.add_argument("--confirm-preview-sha256", required=True, help="fingerprint of the separately reviewed preview")
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text()) if args.request else None
        result = preview(args.db, request=request) if args.command == "preview" else apply(
            args.db, request, expected_preview_sha256=args.confirm_preview_sha256)
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"success": False, "applied": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
