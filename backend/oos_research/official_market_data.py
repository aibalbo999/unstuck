"""Build a cutoff-bounded OOS dataset from captured official exchange responses."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .calendar import validate_sessions
from .canonical import content_hash
from .dataset import validate_dataset


_TICKER_RE = re.compile(r"[0-9A-Z]{4,8}\.(?:TW|TWO)")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_OFFICIAL_HOSTS = {"www.twse.com.tw", "www.tpex.org.tw"}


def verify_official_market_dataset(
    dataset: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    dataset_path: str,
) -> str:
    dataset_hash = validate_dataset(dataset)
    dataset_file = Path(dataset_path)
    if not dataset_file.is_absolute() or dataset_file.is_symlink() or not dataset_file.is_file():
        raise ValueError("official dataset path must be an absolute regular non-symlink file")
    base = dataset_file.parent.resolve(strict=True)
    captures = dataset.get("source_captures")
    if not isinstance(captures, list) or not captures:
        raise ValueError("official dataset source captures are missing")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for capture in captures:
        if not isinstance(capture, Mapping):
            raise ValueError("official dataset source capture is invalid")
        ticker = str(capture.get("ticker", ""))
        month = str(capture.get("month", ""))
        key = (ticker, month)
        if key in by_key:
            raise ValueError("duplicate official dataset source capture")
        raw_file = Path(str(capture.get("raw_file", "")))
        if raw_file.is_absolute() or ".." in raw_file.parts or not raw_file.parts:
            raise ValueError("official dataset raw capture path is unsafe")
        raw_path = base / raw_file
        if any(component.is_symlink() for component in (raw_path, *raw_path.parents) if component != base.parent):
            raise ValueError("official dataset raw capture path is unsafe")
        try:
            resolved = raw_path.resolve(strict=True)
            resolved.relative_to(base)
            descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except (OSError, RuntimeError, ValueError):
            raise ValueError("official dataset raw capture is unavailable") from None
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0 or metadata.st_size > 8 * 1024 * 1024:
                raise ValueError("official dataset raw capture size is invalid")
            chunks = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
        finally:
            os.close(descriptor)
        raw = b"".join(chunks)
        if hashlib.sha256(raw).hexdigest() != capture.get("raw_sha256"):
            raise ValueError("official dataset raw capture hash mismatch")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("official dataset raw capture JSON is invalid") from None
        by_key[key] = {**dict(capture), "payload": payload}

    def fetch_month(ticker: str, month: str) -> Mapping[str, Any]:
        try:
            return by_key.pop((ticker, month))
        except KeyError:
            raise ValueError("official dataset source capture coverage is incomplete") from None

    sessions = dataset.get("calendar")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("official dataset calendar is empty")
    rebuilt = build_official_market_dataset(
        inventory=inventory,
        sessions=sessions,
        cutoff_session=sessions[-1],
        as_of=str(dataset["as_of"]),
        fetch_month=fetch_month,
        builder_identity=dataset.get("builder_identity"),
    )
    if by_key or rebuilt != dict(dataset):
        raise ValueError("official dataset does not match raw captures")
    return dataset_hash


def _roc_date(raw: Any) -> date:
    value = str(raw or "").strip()
    parts = value.split("/")
    if len(parts) == 3:
        year, month, day = (int(part) for part in parts)
    elif len(value) == 7 and value.isdigit():
        year, month, day = int(value[:3]), int(value[3:5]), int(value[5:])
    else:
        raise ValueError("official row date is invalid")
    return date(year + 1911, month, day)


def _price(raw: Any) -> float:
    if isinstance(raw, bool):
        raise ValueError("official OHLC value is invalid")
    try:
        value = float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        raise ValueError("official OHLC value is invalid") from None
    if value <= 0:
        raise ValueError("official OHLC value is invalid")
    return value


def _rows(payload: Mapping[str, Any], *, ticker: str) -> Sequence[Any]:
    if ticker.endswith(".TW"):
        if payload.get("stat") != "OK" or not isinstance(payload.get("data"), list):
            raise ValueError("TWSE official response is invalid")
        return payload["data"]
    tables = payload.get("tables")
    if not isinstance(tables, list) or not tables or not isinstance(tables[0], Mapping):
        raise ValueError("TPEx official response is invalid")
    rows = tables[0].get("data")
    if not isinstance(rows, list):
        raise ValueError("TPEx official response is invalid")
    return rows


def _capture_projection(capture: Mapping[str, Any], *, ticker: str, month: str) -> dict[str, str]:
    source_url = capture.get("source_url")
    raw_sha256 = capture.get("raw_sha256")
    raw_file = capture.get("raw_file")
    parsed = urlparse(str(source_url or ""))
    if parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS:
        raise ValueError("official response source URL is invalid")
    if not isinstance(raw_sha256, str) or not _SHA256_RE.fullmatch(raw_sha256):
        raise ValueError("official response SHA-256 is invalid")
    if not isinstance(raw_file, str) or raw_file.startswith(("/", "../")) or "/../" in raw_file:
        raise ValueError("official response capture path is invalid")
    projection = {
        "ticker": ticker,
        "month": month,
        "source_url": source_url,
        "raw_sha256": raw_sha256,
        "raw_file": raw_file,
    }
    captured_at = capture.get("captured_at")
    if captured_at is not None:
        try:
            captured = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("official response capture time is invalid") from None
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError("official response capture time must include timezone")
        projection["captured_at"] = str(captured_at)
    return projection


def build_official_market_dataset(
    *,
    inventory: Mapping[str, Any],
    sessions: Sequence[str],
    cutoff_session: str,
    fetch_month: Callable[[str, str], Mapping[str, Any]],
    as_of: str | None = None,
    builder_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if inventory.get("coverage_status") != "closed":
        raise ValueError("candidate inventory must be closed")
    candidates = inventory.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidate inventory is empty")
    tickers = sorted({str(candidate.get("ticker", "")) for candidate in candidates if isinstance(candidate, Mapping)})
    if not tickers or any(not _TICKER_RE.fullmatch(ticker) for ticker in tickers):
        raise ValueError("candidate ticker is invalid")
    inventory_sha256 = str(inventory.get("inventory_sha256") or content_hash(inventory))
    if not _SHA256_RE.fullmatch(inventory_sha256):
        raise ValueError("candidate inventory SHA-256 is invalid")

    validated_sessions = validate_sessions(sessions)
    try:
        cutoff = date.fromisoformat(cutoff_session)
        observed = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of is not None else None
    except (AttributeError, ValueError):
        raise ValueError("dataset cutoff is invalid") from None
    if observed is not None and (observed.tzinfo is None or observed.utcoffset() is None):
        raise ValueError("dataset as_of must include timezone")
    if cutoff not in validated_sessions:
        raise ValueError("cutoff session is not in the official calendar")
    bounded_sessions = tuple(session for session in validated_sessions if session <= cutoff)
    months = sorted({session.strftime("%Y-%m") for session in bounded_sessions})
    allowed_dates = {session.isoformat() for session in bounded_sessions}

    bars: dict[str, list[dict[str, Any]]] = {}
    captures: list[dict[str, str]] = []
    capture_times: list[datetime] = []
    missing_sessions: dict[str, list[str]] = {}
    for ticker in tickers:
        by_date: dict[str, dict[str, Any]] = {}
        for month in months:
            capture = fetch_month(ticker, month)
            if not isinstance(capture, Mapping) or not isinstance(capture.get("payload"), Mapping):
                raise ValueError("official response capture is invalid")
            projection = _capture_projection(capture, ticker=ticker, month=month)
            captures.append(projection)
            capture_value = projection.get("captured_at")
            if capture_value is not None:
                capture_times.append(datetime.fromisoformat(capture_value.replace("Z", "+00:00")))
            completed_at = capture_value or as_of
            if completed_at is None:
                raise ValueError("official response capture time is required")
            for raw_row in _rows(capture["payload"], ticker=ticker):
                if not isinstance(raw_row, Sequence) or isinstance(raw_row, (str, bytes)) or len(raw_row) < 7:
                    raise ValueError("official OHLC row is invalid")
                trading_date = _roc_date(raw_row[0]).isoformat()
                if trading_date not in allowed_dates:
                    continue
                if trading_date in by_date:
                    raise ValueError("duplicate official OHLC row")
                row = {
                    "date": trading_date,
                    "open": _price(raw_row[3]),
                    "high": _price(raw_row[4]),
                    "low": _price(raw_row[5]),
                    "close": _price(raw_row[6]),
                    "complete": True,
                    "completed_at": completed_at,
                }
                by_date[trading_date] = row
        if cutoff_session not in by_date:
            raise ValueError(f"cutoff session is not published for {ticker}")
        bars[ticker] = [by_date[session] for session in sorted(by_date)]
        missing_sessions[ticker] = sorted(allowed_dates - set(by_date))

    if as_of is None:
        if not capture_times:
            raise ValueError("official response capture time is required")
        latest_capture = max(capture_times)
        as_of = latest_capture.isoformat().replace("+00:00", "Z")

    dataset: dict[str, Any] = {
        "schema_version": "oos.dataset.v1",
        "provider": "TWSE_STOCK_DAY+TPEx_tradingStock",
        "timezone": "Asia/Taipei",
        "as_of": as_of,
        "price_policy": "raw",
        "corporate_action_policy": "explicit_unprocessed_allowed",
        "calendar": [session.isoformat() for session in bounded_sessions],
        "bars": bars,
        "source_captures": captures,
        "missing_sessions_by_ticker": missing_sessions,
        "candidate_inventory_sha256": inventory_sha256,
    }
    if builder_identity is not None:
        if not isinstance(builder_identity, Mapping):
            raise ValueError("dataset builder identity is invalid")
        dataset["builder_identity"] = dict(builder_identity)
    dataset["dataset_sha256"] = content_hash(dataset)
    validate_dataset(dataset)
    return dataset
