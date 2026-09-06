"""Pure, deterministic policy for the isolated PostgreSQL test boundary.

This module deliberately does not import psycopg or attempt a connection.  It
only accepts the two run-scoped identities supplied by the test harness.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
from typing import Any


REJECTION_REASON = "isolated_pg_connection_rejected"
_HOST_RE = re.compile(r"^/tmp/pg-validation-[0-9a-f]{16}/socket$")
_DB_RE = re.compile(r"^db_[0-9a-f]{16}$")
_USER_RE = re.compile(r"^(?:app|owner)_[0-9a-f]{16}$")
_CANONICAL_KEYS = ("host", "port", "dbname", "user", "connect_timeout", "sslmode")
_CLIENT_OPTIONS = frozenset(
    {"autocommit", "row_factory", "cursor_factory", "prepare_threshold", "context"}
)
CLIENT_OPTIONS = _CLIENT_OPTIONS


def _reject() -> None:
    raise ValueError(REJECTION_REASON)


def _identity_reject() -> None:
    raise ValueError("isolated_pg_identity_invalid")


def _safe_text(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        _reject()
    return str(value)


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One fixed endpoint identity permitted by an isolated test run."""

    host: str
    port: str
    dbname: str
    user: str

    def _validated_identity(self) -> dict[str, str]:
        host = _safe_text(self.host)
        port = _safe_text(self.port)
        dbname = _safe_text(self.dbname)
        user = _safe_text(self.user)
        if not (
            _HOST_RE.fullmatch(host)
            and port == "5432"
            and _DB_RE.fullmatch(dbname)
            and _USER_RE.fullmatch(user)
        ):
            _identity_reject()
        return {"host": host, "port": port, "dbname": dbname, "user": user}

    def values(self) -> dict[str, str]:
        """Return all canonical endpoint values in the policy's fixed shape."""

        values = self._validated_identity()
        values.update({"connect_timeout": "5", "sslmode": "disable"})
        return values

    def conninfo(self) -> str:
        values = self.values()
        return (
            " ".join(f"{key}={value}" for key, value in values.items())
        )

    def validate(self, conninfo: Any, kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate conninfo against this endpoint and client-only options."""

        values = self.values()
        options = {} if kwargs is None else kwargs
        if not isinstance(options, dict) or not set(options) <= _CLIENT_OPTIONS:
            _reject()
        parsed = _parse_conninfo(conninfo)
        if parsed != values:
            _reject()
        result: dict[str, Any] = dict(values)
        result.update(options)
        return result


def _parse_conninfo(conninfo: Any) -> dict[str, str]:
    if not isinstance(conninfo, str) or not conninfo.strip() or "://" in conninfo:
        _reject()
    try:
        tokens = shlex.split(conninfo, posix=True)
    except (ValueError, TypeError):
        _reject()
    parsed: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            _reject()
        key, value = token.split("=", 1)
        if not key or key in parsed or key not in _CANONICAL_KEYS:
            _reject()
        if not value:
            _reject()
        parsed[key] = value
    if tuple(parsed) != _CANONICAL_KEYS:
        _reject()
    if parsed["connect_timeout"] != "5" or parsed["sslmode"] != "disable":
        _reject()
    return parsed


def validate(
    conninfo: Any,
    kwargs: dict[str, Any] | None = None,
    /,
    **options: Any,
) -> dict[str, Any]:
    """Validate conninfo and client-only options, returning canonical fields.

    The parser intentionally does not consult environment variables.  libpq
    defaults such as ``PGSERVICE`` and ``PGHOSTADDR`` therefore cannot alter a
    complete, explicit conninfo accepted by this boundary.
    """

    merged = {} if kwargs is None else kwargs
    if options:
        if merged:
            _reject()
        merged = options
    parsed = _parse_conninfo(conninfo)
    if set(merged) - _CLIENT_OPTIONS:
        _reject()
    if not (
        _HOST_RE.fullmatch(parsed["host"])
        and parsed["port"] == "5432"
        and _DB_RE.fullmatch(parsed["dbname"])
        and _USER_RE.fullmatch(parsed["user"])
    ):
        _reject()
    result: dict[str, Any] = {key: parsed[key] for key in _CANONICAL_KEYS}
    result.update(merged)
    return result


__all__ = ["Endpoint", "REJECTION_REASON", "validate"]
