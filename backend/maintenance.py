"""Local maintenance command entrypoints."""

from __future__ import annotations

import argparse
import json

from storage.legacy_reports import migrate_legacy_reports


def main() -> int:
    parser = argparse.ArgumentParser(description="Stock Agent maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate-legacy-reports")
    migrate_parser.add_argument("--output-dir", default=None)
    migrate_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.command == "migrate-legacy-reports":
        result = migrate_legacy_reports(output_dir=args.output_dir, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
