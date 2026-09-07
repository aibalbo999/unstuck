#!/usr/bin/env python3
"""Create an explicit, read-only report refresh candidate inventory."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import requests


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def collect(base_url: str, *, timeout: int = 30) -> dict:
    session = requests.Session()
    pages: list[dict] = []
    page = 1
    total: int | None = None
    seen: set[str] = set()
    while True:
        response = session.get(f"{base_url.rstrip('/')}/api/reports", params={"page": page, "limit": 100, "include_versions": "true"}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("reports"), list) or not isinstance(payload.get("pagination"), dict):
            raise ValueError("report API returned malformed pagination payload")
        pagination = payload["pagination"]
        current_total = pagination.get("total")
        if isinstance(current_total, bool) or not isinstance(current_total, int) or current_total < 0:
            raise ValueError("report API returned invalid total")
        if total is None:
            total = current_total
        elif total != current_total:
            raise ValueError("report total changed during inventory")
        for report in payload["reports"]:
            if not isinstance(report, dict) or not isinstance(report.get("filename"), str) or not report["filename"]:
                raise ValueError("report API returned an invalid report identity")
            if report["filename"] in seen:
                raise ValueError("report API returned duplicate report identity")
            seen.add(report["filename"])
        pages.append(payload)
        if not pagination.get("has_next"):
            break
        page += 1
        if page > 1000:
            raise ValueError("report API pagination exceeded safety bound")
    reports = [report for payload in pages for report in payload["reports"]]
    if total != len(reports):
        raise ValueError("report API total does not match returned inventory")
    entries = []
    for report in sorted(reports, key=lambda item: (str(item.get("ticker", "")), str(item.get("pipeline_id", "")), item["filename"])):
        freshness = report.get("decision_freshness") if isinstance(report.get("decision_freshness"), dict) else {}
        entries.append({
            "filename": report["filename"], "ticker": report.get("ticker"), "pipeline_id": report.get("pipeline_id"),
            "html_hash": report.get("html_hash"), "markdown_hash": report.get("markdown_hash"),
            "data_snapshot_hash": report.get("data_snapshot_hash"),
            "freshness_status": freshness.get("status"), "requires_rerun": freshness.get("requires_rerun"),
            "conclusion_generated_at": freshness.get("conclusion_generated_at"),
            "snapshot_refreshed_at": freshness.get("snapshot_refreshed_at"),
        })
    return {
        "schema_version": "stock-agent.report-update-candidates.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url.rstrip("/"), "total": total, "returned": len(entries),
        "status_counts": dict(Counter(entry["freshness_status"] for entry in entries)),
        "candidates": [entry for entry in entries if entry["requires_rerun"] is True],
        "all_reports_sha256": hashlib.sha256(_canonical(entries)).hexdigest(),
    }


def write_exclusive(path: Path, payload: dict) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("inventory output must be a new absolute path")
    encoded = (_canonical(payload) + b"\n")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short inventory write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = collect(args.base_url)
    write_exclusive(args.output, payload)
    print(json.dumps({key: payload[key] for key in ("schema_version", "generated_at", "total", "returned", "status_counts", "all_reports_sha256")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
