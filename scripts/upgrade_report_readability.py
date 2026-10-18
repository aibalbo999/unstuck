"""Inventory, preview or apply the reversible HTML reader to indexed reports."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from report_reader_assets import inject_reader
from report_reader_migration import migrate_report, sha256
from storage.report_storage import LocalFileStorage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--prepared", type=Path, help="Previously verified dry-run manifest, required for apply")
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and args.prepared is None:
        parser.error("--apply requires --prepared")
    if not args.index.is_file() or not args.output.is_dir():
        parser.error("Existing index and output directory are required")
    storage = LocalFileStorage(args.output)
    with sqlite3.connect(f"{args.index.resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM reports WHERE output_dir=? ORDER BY timestamp DESC", (str(storage._root),))]
    indexed = {row["filename"] for row in rows}
    files = storage.list_reports()
    unindexed = [item.key for item in files if item.key.endswith(".html") and Path(item.key).name not in indexed]
    protected = {item.key: sha256(storage.get_report(item.key).content) for item in files if not item.key.endswith(".html")}
    prepared = json.loads(args.prepared.read_text()) if args.prepared else None
    if prepared and (prepared["output"] != str(storage._root) or prepared["index"] != str(args.index.resolve()) or prepared.get("errors") or prepared.get("unindexed_html")):
        parser.error("Prepared manifest does not describe a clean inventory of this target")
    expected = {item["filename"]: item["before_sha256"] for item in prepared["reports"]} if prepared else {}
    expected_after = {item["filename"]: item["after_sha256"] for item in prepared["reports"]} if prepared else {}
    if prepared and indexed != set(expected):
        parser.error("Report inventory changed; prepare a new dry-run manifest")
    if prepared and protected != prepared["protected_artifacts"]:
        parser.error("Saved non-HTML artifacts changed; prepare a new dry-run manifest")
    result = {"started_at": datetime.now(timezone.utc).isoformat(), "output": str(storage._root), "index": str(args.index.resolve()),
              "apply": args.apply, "reports": [], "errors": [], "unindexed_html": unindexed, "protected_artifacts": protected,
              "index_rows_before": rows}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    if args.manifest.exists():
        parser.error("Manifest already exists; choose a new path")
    preview_modes = set()
    for row in rows:
        try:
            item = migrate_report(args.index, storage, row["filename"], expected_sha256=expected.get(row["filename"]), expected_after_sha256=expected_after.get(row["filename"]), apply=args.apply)
            result["reports"].append(item)
            if args.preview_dir and row["pipeline_id"] not in preview_modes:
                args.preview_dir.mkdir(parents=True, exist_ok=True)
                raw = storage.get_report(item["key"]).content.decode("utf-8")
                preview_html = inject_reader(raw)
                (args.preview_dir / f"{row['pipeline_id']}.html").write_text(preview_html, encoding="utf-8")
                from report_history_downloads import secure_html_response
                headers = dict(secure_html_response(preview_html).headers)
                (args.preview_dir / f"{row['pipeline_id']}.headers.json").write_text(json.dumps(headers), encoding="utf-8")
                preview_modes.add(row["pipeline_id"])
        except Exception as exc:
            result["errors"].append({"filename": row["filename"], "error": str(exc), "type": type(exc).__name__})
            if args.apply:
                break
        if args.apply:
            # Durable progress allows an interrupted run to be reconciled per file.
            args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with sqlite3.connect(f"{args.index.resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        after_rows = [dict(row) for row in conn.execute("SELECT * FROM reports WHERE output_dir=? ORDER BY timestamp DESC", (str(storage._root),))]
    result["index_rows_preserved"] = [{k: v for k, v in row.items() if k != "html_hash"} for row in rows] == [{k: v for k, v in row.items() if k != "html_hash"} for row in after_rows]
    result["protected_artifacts_preserved"] = all(storage.get_report(key) is not None and sha256(storage.get_report(key).content) == digest for key, digest in protected.items())
    result["counts"] = dict(Counter(item["status"] for item in result["reports"]))
    result["modes"] = dict(Counter(item["pipeline_id"] for item in result["reports"]))
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: result[key] for key in ("counts", "modes", "errors", "unindexed_html", "index_rows_preserved", "protected_artifacts_preserved")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(bool(result["errors"] or unindexed or not result["index_rows_preserved"] or not result["protected_artifacts_preserved"]))


if __name__ == "__main__":
    raise SystemExit(main())
