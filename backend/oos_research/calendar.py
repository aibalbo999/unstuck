"""Explicit offline exchange-session calendar."""

from __future__ import annotations

from datetime import date
from typing import Iterable

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


def sessions_between(sessions: Iterable[str], start: date, end: date) -> tuple[date, ...]:
    validated = validate_sessions(sessions)
    return tuple(session for session in validated if start <= session <= end)
