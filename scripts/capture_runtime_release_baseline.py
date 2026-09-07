#!/usr/bin/env python3
"""Capture a secret-safe, read-only baseline before a runtime release action."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import requests


ROOT = Path(__file__).resolve().parents[1]
REPORT_API_PAGE_SIZE = 100
MAX_FILE_BYTES = 512 * 1024 * 1024
PROCESS_PATTERNS = ("uvicorn", "worker_main.py", "redis-server")
OBSERVED_ENV_KEYS = (
    "GIT_COMMIT",
    "GIT_DIRTY",
    "TASK_QUEUE_BACKEND",
    "TASK_QUEUE_NAME",
    "REDIS_URL",
    "GEMINI_API_KEYS",
    "GOOGLE_API_KEYS",
)


def _run(command: list[str], *, timeout: int = 5) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def _git_baseline() -> dict:
    code, head, _ = _run(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    status_code, status, _ = _run(["git", "-C", str(ROOT), "status", "--porcelain=v1", "--untracked-files=normal"])
    return {
        "head": head.strip() if code == 0 and re.fullmatch(r"[0-9a-f]{40}", head.strip()) else None,
        "dirty": bool(status.strip()) if status_code == 0 else None,
        "status_available": status_code == 0,
    }


def _process_baseline() -> list[dict]:
    code, output, _ = _run(["ps", "-axo", "pid,lstart,command"])
    if code != 0:
        return []
    records = []
    for line in output.splitlines():
        match = re.match(r"^\s*(\d+)\s+(.*)$", line)
        if not match:
            continue
        pid, command = int(match.group(1)), match.group(2).strip()
        if not any(pattern in command for pattern in PROCESS_PATTERNS):
            continue
        cwd = None
        cwd_code, cwd_output, _ = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
        if cwd_code == 0:
            for cwd_line in cwd_output.splitlines():
                if cwd_line.startswith("n"):
                    cwd = cwd_line[1:]
                    break
        records.append({"pid": pid, "command": command, "cwd": cwd})
    return sorted(records, key=lambda item: item["pid"])


def _response_summary(response: requests.Response) -> dict:
    result = {"status_code": response.status_code}
    try:
        payload = response.json()
    except ValueError:
        return result
    if isinstance(payload, dict):
        for key in ("status", "schema_version", "commit", "dirty", "active_count", "enabled_count"):
            if key in payload:
                value = payload[key]
                if key == "commit" and not (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value)):
                    value = None
                if key == "dirty" and not isinstance(value, bool):
                    value = None
                if key in {"active_count", "enabled_count"} and (isinstance(value, bool) or not isinstance(value, int)):
                    value = None
                result[key] = value
    return result


def _report_inventory(session: requests.Session, base_url: str, *, timeout: int) -> dict:
    reports = []
    seen: set[str] = set()
    total: int | None = None
    page = 1
    while True:
        response = session.get(
            f"{base_url.rstrip('/')}/api/reports",
            params={"page": page, "limit": REPORT_API_PAGE_SIZE, "include_versions": "true"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("reports"), list) or not isinstance(payload.get("pagination"), dict):
            raise ValueError("report API returned malformed inventory")
        pagination = payload["pagination"]
        current_total = pagination.get("total")
        if isinstance(current_total, bool) or not isinstance(current_total, int) or current_total < 0:
            raise ValueError("report API returned invalid total")
        if total is None:
            total = current_total
        elif total != current_total:
            raise ValueError("report index changed during baseline")
        for report in payload["reports"]:
            if not isinstance(report, dict) or not isinstance(report.get("filename"), str) or not report["filename"]:
                raise ValueError("report API returned invalid identity")
            if report["filename"] in seen:
                raise ValueError("report API returned duplicate identity")
            seen.add(report["filename"])
            freshness = report.get("decision_freshness") if isinstance(report.get("decision_freshness"), dict) else {}
            reports.append({
                "filename": report["filename"],
                "ticker": report.get("ticker"),
                "pipeline_id": report.get("pipeline_id"),
                "timestamp": report.get("timestamp") if isinstance(report.get("timestamp"), (int, float)) and not isinstance(report.get("timestamp"), bool) and math.isfinite(report.get("timestamp")) else None,
                "html_hash": report.get("html_hash"),
                "markdown_hash": report.get("markdown_hash"),
                "data_snapshot_hash": report.get("data_snapshot_hash"),
                "freshness_status": freshness.get("status"),
                "requires_rerun": freshness.get("requires_rerun"),
            })
        if not pagination.get("has_next"):
            break
        page += 1
        if page > 1000:
            raise ValueError("report API pagination exceeded safety bound")
    if total != len(reports):
        raise ValueError("report API total does not match baseline")
    canonical = json.dumps(sorted(reports, key=lambda item: (str(item.get("ticker", "")), str(item.get("pipeline_id", "")), item["filename"])), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "total": total,
        "status_counts": dict(Counter(item.get("freshness_status") for item in reports)),
        "requires_rerun_count": sum(item.get("requires_rerun") is True for item in reports),
        "all_reports_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _file_baseline(path: Path) -> dict:
    item = {"path": str(path), "present": path.exists(), "is_symlink": path.is_symlink()}
    if not path.exists() or path.is_symlink() or not path.is_file():
        return item
    stat = path.stat()
    item["size_bytes"] = stat.st_size
    if stat.st_size > MAX_FILE_BYTES:
        item["sha256"] = None
        item["hash_status"] = "too_large"
        return item
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    item["sha256"] = digest.hexdigest()
    item["hash_status"] = "ok"
    return item


def _database_baseline() -> list[dict]:
    return [_file_baseline(ROOT / relative) for relative in (
        "backend/cache/stock_agent_cache.sqlite3",
        "backend/cache/operational.sqlite3",
    )]


def capture(base_url: str = "http://127.0.0.1:8080", *, timeout: int = 10) -> dict:
    session = requests.Session()
    endpoints = {}
    for path in ("/healthz", "/readyz", "/api/runtime-identity", "/api/observability/active-jobs", "/api/decision-tracking"):
        try:
            endpoints[path] = _response_summary(session.get(base_url.rstrip("/") + path, timeout=timeout))
        except requests.RequestException as exc:
            endpoints[path] = {"status_code": None, "error": type(exc).__name__}
    try:
        reports = _report_inventory(session, base_url, timeout=timeout)
    except (requests.RequestException, ValueError) as exc:
        reports = {"error": type(exc).__name__}
    return {
        "schema_version": "stock-agent.runtime-release-baseline.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url.rstrip("/"),
        "git": _git_baseline(),
        "processes": _process_baseline(),
        "environment_presence": {key: bool(os.environ.get(key)) for key in OBSERVED_ENV_KEYS},
        "endpoints": endpoints,
        "reports": reports,
        "databases": _database_baseline(),
    }


def write_exclusive(path: Path, payload: dict) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("baseline output must be a new absolute path")
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short baseline write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = capture(args.base_url)
    write_exclusive(args.output, payload)
    print(json.dumps({
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "git": payload["git"],
        "process_count": len(payload["processes"]),
        "reports": payload["reports"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
