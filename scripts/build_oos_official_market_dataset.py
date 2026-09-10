#!/usr/bin/env python3
"""Capture official TWSE/TPEx OHLC and build one immutable OOS cutoff dataset."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from oos_research.canonical import canonical_bytes, content_hash, require_sha256_pin
from oos_research.inventory import validate_inventory
from oos_research.official_market_data import build_official_market_dataset, validate_session_calendar
from oos_research.official_market_endpoints import official_url


MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def builder_identity() -> dict:
    source_paths = (
        Path(__file__).resolve(),
        ROOT / "backend/oos_research/calendar.py",
        ROOT / "backend/oos_research/canonical.py",
        ROOT / "backend/oos_research/dataset.py",
        ROOT / "backend/oos_research/official_market_data.py",
        ROOT / "backend/oos_research/official_market_endpoints.py",
    )
    files = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    return {
        "schema_version": "oos.dataset-builder-identity.v1",
        "source_sha256": content_hash({"files": files}),
        "files": files,
    }


def _load_json(path: Path):
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("input must be an absolute regular non-symlink file")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input file size is invalid")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("input JSON is invalid") from None
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def _write_exclusive(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(temporary, flags, 0o600)
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short official evidence write")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(temporary, path, follow_symlinks=False)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _new_output(path: Path) -> Path:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("output must be a new absolute file in an existing directory")
    return path.parent.resolve() / path.name


def _new_raw_dir(path: Path) -> Path:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("raw output must be a new absolute directory in an existing directory")
    resolved = path.parent.resolve() / path.name
    os.mkdir(resolved, 0o700)
    return resolved


def official_ssl_context() -> ssl.SSLContext:
    """Keep Web PKI verification while tolerating TPEx's missing legacy SKI."""
    context = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def _default_open(request, *, timeout):
    return urllib.request.urlopen(request, timeout=timeout, context=official_ssl_context())


def _capture_fetcher(*, raw_dir: Path, raw_prefix: str, opener, clock):
    def fetch_month(ticker: str, month: str):
        url = official_url(ticker, month)
        request = urllib.request.Request(url, headers={"User-Agent": "stock-agent-oos/1.0"})
        with opener(request, timeout=30) as response:
            final_url = response.geturl()
            if urllib.parse.urlparse(final_url).hostname != urllib.parse.urlparse(url).hostname:
                raise ValueError("official response redirected outside exchange host")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if not raw or len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("official response size is invalid")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("official response JSON is invalid") from None
        if not isinstance(payload, dict):
            raise ValueError("official response JSON must be an object")
        digest = hashlib.sha256(raw).hexdigest()
        filename = f"{ticker.replace('.', '-')}-{month}-{digest[:16]}.json"
        _write_exclusive(raw_dir / filename, raw)
        captured = clock()
        if not isinstance(captured, datetime) or captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError("capture clock must return a timezone-aware datetime")
        return {
            "payload": payload,
            "source_url": final_url,
            "raw_sha256": digest,
            "raw_file": f"{raw_prefix}/{filename}",
            "captured_at": captured.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    return fetch_month


def main(argv=None, *, opener=None, clock=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--expected-inventory-sha256", required=True)
    parser.add_argument("--sessions", type=Path, required=True)
    parser.add_argument("--expected-session-calendar-sha256", required=True)
    parser.add_argument("--cutoff-session", required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = _new_output(args.output)
    if args.raw_dir.parent.resolve() != output.parent:
        raise ValueError("raw output directory and dataset must share one parent")
    inventory = _load_json(args.inventory)
    sessions_payload = _load_json(args.sessions)
    inventory_hash = validate_inventory(inventory)
    _, session_calendar_hash = validate_session_calendar(sessions_payload)
    require_sha256_pin(inventory_hash, args.expected_inventory_sha256, label="inventory")
    require_sha256_pin(
        session_calendar_hash,
        args.expected_session_calendar_sha256,
        label="session calendar",
    )
    sessions = sessions_payload.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("session calendar is invalid")
    raw_dir = _new_raw_dir(args.raw_dir)
    fetch_month = _capture_fetcher(
        raw_dir=raw_dir,
        raw_prefix=raw_dir.name,
        opener=opener or _default_open,
        clock=clock or (lambda: datetime.now(timezone.utc)),
    )
    dataset = build_official_market_dataset(
        inventory=inventory,
        session_calendar=sessions_payload,
        cutoff_session=args.cutoff_session,
        fetch_month=fetch_month,
        builder_identity=builder_identity(),
    )
    _write_exclusive(output, canonical_bytes(dataset) + b"\n")
    print(json.dumps({
        "dataset_sha256": dataset["dataset_sha256"],
        "cutoff_session": args.cutoff_session,
        "ticker_count": len(dataset["bars"]),
        "raw_capture_count": len(dataset["source_captures"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
