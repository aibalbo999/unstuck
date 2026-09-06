"""Install a pre-connect guard on a loaded psycopg-compatible driver."""

from __future__ import annotations

import os
from typing import Any

from .policy import Endpoint, REJECTION_REASON


def _reject() -> None:
    raise ValueError(REJECTION_REASON)


_LIBPQ_ENV_KEYS = frozenset(
    {
        "PGHOSTADDR",
        "PGSERVICE",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGPASSFILE",
        "PGSERVICEFILE",
        "PGOPTIONS",
        "PGSSLMODE",
    }
)


def install(
    driver: Any,
    endpoints: Any = (),
) -> Any:
    """Patch sync, async, and top-level driver entrypoints before connecting.

    An empty endpoint policy means default deny. The guard only parses and
    compares conninfo; it never probes the database for availability.
    """

    policy_state = getattr(driver, "__pg_validation_policy_state__", None)
    if not isinstance(policy_state, dict):
        policy_state = {"endpoints": ()}
        setattr(driver, "__pg_validation_policy_state__", policy_state)
    policy_state["endpoints"] = tuple(endpoints or ())

    sync_connect = driver.Connection.connect.__func__
    async_connect = driver.AsyncConnection.connect.__func__
    top_connect = getattr(driver, "connect", None)
    while getattr(sync_connect, "__pg_validation_wrapper__", False):
        sync_connect = sync_connect.__pg_validation_original__
    while getattr(async_connect, "__pg_validation_wrapper__", False):
        async_connect = async_connect.__pg_validation_original__
    while getattr(top_connect, "__pg_validation_wrapper__", False):
        top_connect = top_connect.__pg_validation_original__

    def check(conninfo: Any, kwargs: dict[str, Any]) -> None:
        if any(name in os.environ for name in _LIBPQ_ENV_KEYS):
            _reject()
        for endpoint in policy_state["endpoints"]:
            try:
                endpoint.validate(conninfo, kwargs)
                return
            except (TypeError, ValueError):
                pass
        _reject()

    def checked_sync(cls: Any, conninfo: Any = "", **kwargs: Any) -> Any:
        check(conninfo, kwargs)
        return sync_connect(cls, conninfo, **kwargs)

    async def checked_async(cls: Any, conninfo: Any = "", **kwargs: Any) -> Any:
        check(conninfo, kwargs)
        return await async_connect(cls, conninfo, **kwargs)

    def checked_top(conninfo: Any = "", **kwargs: Any) -> Any:
        check(conninfo, kwargs)
        return top_connect(conninfo, **kwargs)

    checked_sync.__pg_validation_wrapper__ = True
    checked_sync.__pg_validation_original__ = sync_connect
    checked_async.__pg_validation_wrapper__ = True
    checked_async.__pg_validation_original__ = async_connect
    checked_top.__pg_validation_wrapper__ = True
    checked_top.__pg_validation_original__ = top_connect

    driver.Connection.connect = classmethod(checked_sync)
    driver.AsyncConnection.connect = classmethod(checked_async)
    driver.connect = checked_top
    return driver


install_connection_guard = install

__all__ = ["install", "install_connection_guard"]
