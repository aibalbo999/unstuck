"""Local maintenance command entrypoints."""

from __future__ import annotations

import argparse
import json

from storage.legacy_reports import migrate_legacy_reports
from market_calendar_store import update_market_calendars
from provider_sla_maintenance import cleanup_provider_sla_events
from snapshot_maintenance import verify_snapshots
from storage_inventory import build_storage_summary, clear_runtime_storage


def main() -> int:
    parser = argparse.ArgumentParser(description="Stock Agent maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate-legacy-reports")
    migrate_parser.add_argument("--output-dir", default=None)
    migrate_parser.add_argument("--dry-run", action="store_true")
    calendar_parser = subparsers.add_parser("update-market-calendars")
    calendar_parser.add_argument("--calendar-dir", default=None)
    calendar_parser.add_argument("--market", action="append", choices=["us", "tw"])
    calendar_parser.add_argument("--year", action="append", type=int)
    calendar_parser.add_argument("--overwrite", action="store_true")
    snapshot_parser = subparsers.add_parser("verify-snapshots")
    snapshot_parser.add_argument("--output-dir", default=None)
    snapshot_parser.add_argument("--write", action="store_true")
    sla_parser = subparsers.add_parser("cleanup-provider-sla")
    sla_parser.add_argument("--retention-days", type=int, default=None)
    storage_parser = subparsers.add_parser("storage-summary")
    storage_parser.add_argument("--output-dir", default=None)
    storage_parser.add_argument("--cache-dir", default=None)
    storage_parser.add_argument("--cache-db-path", default=None)
    storage_parser.add_argument("--task-db-path", default=None)
    storage_parser.add_argument("--market-calendar-dir", default=None)
    clear_parser = subparsers.add_parser("clear-runtime-storage")
    clear_parser.add_argument("--output-dir", default=None)
    clear_parser.add_argument("--cache-dir", default=None)
    clear_parser.add_argument("--cache-db-path", default=None)
    clear_parser.add_argument("--task-db-path", default=None)
    clear_parser.add_argument("--market-calendar-dir", default=None)
    clear_parser.add_argument("--confirm-delete", action="store_true")

    args = parser.parse_args()
    if args.command == "migrate-legacy-reports":
        result = migrate_legacy_reports(output_dir=args.output_dir, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "update-market-calendars":
        result = update_market_calendars(
            years=args.year,
            markets=args.market,
            calendar_dir=args.calendar_dir,
            overwrite=args.overwrite,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "verify-snapshots":
        result = verify_snapshots(output_dir=args.output_dir, write=args.write)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "cleanup-provider-sla":
        result = cleanup_provider_sla_events(retention_days=args.retention_days)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "storage-summary":
        result = build_storage_summary(
            output_dir=args.output_dir,
            cache_dir=args.cache_dir,
            cache_db_path=args.cache_db_path,
            task_db_path=args.task_db_path,
            market_calendar_dir=args.market_calendar_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "clear-runtime-storage":
        result = clear_runtime_storage(
            output_dir=args.output_dir,
            cache_dir=args.cache_dir,
            cache_db_path=args.cache_db_path,
            task_db_path=args.task_db_path,
            market_calendar_dir=args.market_calendar_dir,
            confirm_delete=args.confirm_delete,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
