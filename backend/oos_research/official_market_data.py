"""Build a cutoff-bounded OOS dataset from captured official exchange responses."""

from __future__ import annotations

from datetime import date, datetime, time
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .calendar import validate_sessions
from .canonical import content_hash
from .dataset import validate_dataset
from .inventory import validate_inventory
from .official_market_endpoints import TICKER_RE, official_url


_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_OFFICIAL_HOSTS = {"www.twse.com.tw", "www.tpex.org.tw"}
_DATA_READY_LOCAL_TIME = time(15, 0)


def _read_relative_regular(base: Path, relative: Path) -> bytes:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directory_fds: list[int] = []
    descriptor: int | None = None
    try:
        directory_fds.append(os.open(base, directory_flags))
        for component in relative.parts[:-1]:
            directory_fds.append(os.open(component, directory_flags, dir_fd=directory_fds[-1]))
        descriptor = os.open(relative.parts[-1], file_flags, dir_fd=directory_fds[-1])
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0 or metadata.st_size > 8 * 1024 * 1024:
            raise ValueError("official dataset raw capture size is invalid")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


def verify_official_market_dataset(
    dataset: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    session_calendar: Mapping[str, Any],
    dataset_path: str,
) -> str:
    dataset_hash = validate_dataset(dataset)
    authoritative_sessions, session_calendar_hash = validate_session_calendar(session_calendar)
    if dataset.get("session_calendar_sha256") != session_calendar_hash:
        raise ValueError("official dataset session calendar hash mismatch")
    if dataset.get("calendar_definition_sha256") != session_calendar.get("calendar_definition_sha256"):
        raise ValueError("official dataset calendar definition hash mismatch")
    cutoff_session = dataset.get("cutoff_session")
    try:
        cutoff = date.fromisoformat(str(cutoff_session))
    except ValueError:
        raise ValueError("official dataset cutoff session is invalid") from None
    if cutoff not in authoritative_sessions:
        raise ValueError("official dataset cutoff session is not in the fixed calendar")
    expected_sessions = [session.isoformat() for session in authoritative_sessions if session <= cutoff]
    if dataset.get("calendar") != expected_sessions:
        raise ValueError("official dataset calendar does not match fixed session calendar")
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
        try:
            raw = _read_relative_regular(base, raw_file)
        except (OSError, RuntimeError, IndexError):
            raise ValueError("official dataset raw capture is unavailable") from None
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
        session_calendar=session_calendar,
        cutoff_session=str(cutoff_session),
        as_of=str(dataset["as_of"]),
        fetch_month=fetch_month,
        builder_identity=dataset.get("builder_identity"),
    )
    if by_key or rebuilt != dict(dataset):
        raise ValueError("official dataset does not match raw captures")
    return dataset_hash


def validate_session_calendar(session_calendar: Mapping[str, Any]) -> tuple[tuple[date, ...], str]:
    if not isinstance(session_calendar, Mapping):
        raise ValueError("session calendar must be an object")
    if (
        session_calendar.get("schema_version") != "oos.exchange-sessions.v1"
        or session_calendar.get("market") != "tw"
        or session_calendar.get("timezone") != "Asia/Taipei"
        or session_calendar.get("session_open_local_time") != "09:00:00"
    ):
        raise ValueError("session calendar identity is invalid")
    definition_hash = session_calendar.get("calendar_definition_sha256")
    if not isinstance(definition_hash, str) or not _SHA256_RE.fullmatch(definition_hash):
        raise ValueError("session calendar definition hash is invalid")
    date_range = session_calendar.get("range")
    if not isinstance(date_range, Mapping):
        raise ValueError("session calendar range is invalid")
    try:
        range_start = date.fromisoformat(str(date_range.get("start")))
        range_end = date.fromisoformat(str(date_range.get("end")))
        sessions = validate_sessions(session_calendar.get("sessions"))
    except (TypeError, ValueError):
        raise ValueError("session calendar range or sessions are invalid") from None
    if not sessions or range_start > sessions[0] or range_end < sessions[-1]:
        raise ValueError("session calendar range does not cover its sessions")
    return sessions, content_hash(session_calendar)


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
    if str(source_url) != official_url(ticker, month):
        raise ValueError("official response source URL does not match ticker or month")
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
    if captured_at is None:
        raise ValueError("official response capture time is required")
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
    session_calendar: Mapping[str, Any],
    cutoff_session: str,
    fetch_month: Callable[[str, str], Mapping[str, Any]],
    as_of: str | None = None,
    builder_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    inventory_sha256 = validate_inventory(inventory)
    if inventory.get("coverage_status") != "closed":
        raise ValueError("candidate inventory must be closed")
    candidates = inventory.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidate inventory is empty")
    tickers = sorted({str(candidate.get("ticker", "")) for candidate in candidates if isinstance(candidate, Mapping)})
    if not tickers or any(not TICKER_RE.fullmatch(ticker) for ticker in tickers):
        raise ValueError("candidate ticker is invalid")
    if not _SHA256_RE.fullmatch(inventory_sha256):
        raise ValueError("candidate inventory SHA-256 is invalid")

    validated_sessions, session_calendar_hash = validate_session_calendar(session_calendar)
    try:
        cutoff = date.fromisoformat(cutoff_session)
        observed = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of is not None else None
    except (AttributeError, ValueError):
        raise ValueError("dataset cutoff is invalid") from None
    if observed is not None and (observed.tzinfo is None or observed.utcoffset() is None):
        raise ValueError("dataset as_of must include timezone")
    if cutoff not in validated_sessions:
        raise ValueError("cutoff session is not in the official calendar")
    cutoff_ready_at = datetime.combine(cutoff, _DATA_READY_LOCAL_TIME, ZoneInfo("Asia/Taipei"))
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
                captured = datetime.fromisoformat(capture_value.replace("Z", "+00:00"))
                if captured < cutoff_ready_at:
                    raise ValueError("official response predates the cutoff data-ready boundary")
                capture_times.append(captured)
            completed_at = capture_value
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

    if not capture_times:
        raise ValueError("official response capture time is required")
    latest_capture = max(capture_times)
    if observed is not None and observed != latest_capture:
        raise ValueError("dataset as_of must equal the latest capture time")
    if as_of is None:
        as_of = latest_capture.isoformat().replace("+00:00", "Z")

    dataset: dict[str, Any] = {
        "schema_version": "oos.dataset.v1",
        "provider": "TWSE_STOCK_DAY+TPEx_tradingStock",
        "timezone": "Asia/Taipei",
        "as_of": as_of,
        "price_policy": "raw",
        "corporate_action_policy": "explicit_unprocessed_allowed",
        "calendar": [session.isoformat() for session in bounded_sessions],
        "cutoff_session": cutoff_session,
        "session_calendar_sha256": session_calendar_hash,
        "calendar_definition_sha256": session_calendar["calendar_definition_sha256"],
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
