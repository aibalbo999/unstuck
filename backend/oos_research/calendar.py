"""Explicit offline exchange-session calendar."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .canonical import content_hash


def validate_sessions(sessions: Iterable[str]) -> tuple[date, ...]:
    values: list[date] = []
    for raw in sessions:
        try:
            values.append(date.fromisoformat(str(raw)))
        except ValueError as exc:
            raise ValueError("invalid session date") from exc
    if len(set(values)) != len(values):
        raise ValueError("duplicate session date")
    if values != sorted(values):
        raise ValueError("sessions must be sorted")
    return tuple(values)


def calendar_digest(sessions: Iterable[str]) -> str:
    return content_hash({"sessions": [d.isoformat() for d in validate_sessions(sessions)]})


def first_session_after(sessions: Iterable[str], anchor: date) -> date | None:
    validated = validate_sessions(sessions)
    return next((session for session in validated if session > anchor), None)


def first_session_after_timestamp(
    sessions: Iterable[str], report_available_at: str, *, timezone_name: str,
    session_open: str = "09:00:00",
) -> date | None:
    try:
        zone = ZoneInfo(timezone_name)
        opened = time.fromisoformat(session_open)
        available = datetime.fromisoformat(report_available_at.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError("exchange session policy is invalid") from None
    if opened.tzinfo is not None or available.tzinfo is None or available.utcoffset() is None:
        raise ValueError("exchange session policy is invalid")
    available = available.astimezone(zone)
    return next((session for session in validate_sessions(sessions)
                 if datetime.combine(session, opened, tzinfo=zone) > available), None)


def sessions_between(sessions: Iterable[str], start: date, end: date) -> tuple[date, ...]:
    validated = validate_sessions(sessions)
    return tuple(session for session in validated if start <= session <= end)
