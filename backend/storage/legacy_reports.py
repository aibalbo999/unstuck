"""Legacy report migration utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR
from data_trust import build_legacy_report_snapshot, data_snapshot_filename_for_report
from report_index import build_report_metadata, upsert_report_metadata


def migrate_legacy_reports(output_dir: Optional[str] = None, dry_run: bool = False) -> dict:
    out_dir = Path(output_dir or OUTPUT_DIR).expanduser().resolve()
    result = {
        "output_dir": str(out_dir),
        "dry_run": bool(dry_run),
        "scanned": 0,
        "created": 0,
        "indexed": 0,
        "skipped": 0,
        "files": [],
    }
    if not out_dir.exists():
        return result

    from storage.capacity import reserve_write, sqlite_write_bytes, write_text
    import report_index

    for html_path in sorted(out_dir.glob("*.html")):
        result["scanned"] += 1
        filename = html_path.name
        metadata = build_report_metadata(filename, output_dir=str(out_dir))
        if not metadata:
            result["skipped"] += 1
            continue

        data_filename = data_snapshot_filename_for_report(filename)
        data_path = out_dir / data_filename
        action = "exists"
        snapshot_text = None
        if not data_path.exists():
            action = "create_snapshot"
            snapshot = build_legacy_report_snapshot(
                ticker=metadata["ticker"],
                company_name=metadata["company_name"],
                pipeline=metadata["pipeline_id"],
                recommendation=metadata["recommendation"],
            )
            snapshot_text = json.dumps(snapshot, ensure_ascii=False, indent=2)
            result["created"] += 1
        else:
            result["skipped"] += 1

        if not dry_run:
            new_bytes = len(snapshot_text.encode('utf-8')) if snapshot_text is not None else 0
            source_bytes = new_bytes + sum(p.stat().st_size for p in
                (html_path, html_path.with_suffix('.md'), data_path) if p.is_file())
            known = new_bytes + sqlite_write_bytes(report_index.CACHE_DB_PATH, 8 * source_bytes + 64 * 1024)
            with reserve_write(out_dir, known, 'Legacy snapshot and derived index DB/WAL before either mutation'):
                if snapshot_text is not None:
                    write_text(data_path, snapshot_text)
                upsert_report_metadata(filename, output_dir=str(out_dir))
                result["indexed"] += 1

        result["files"].append({
            "filename": filename,
            "data_snapshot_filename": data_filename,
            "action": action,
        })

    return result
