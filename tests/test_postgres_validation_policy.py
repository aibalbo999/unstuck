"""TDD coverage for the isolated PostgreSQL connection boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from pg_validation.guard import install
from pg_validation.policy import Endpoint


RUN_ID = "0123456789abcdef"
HOST = f"/tmp/pg-validation-{RUN_ID}/socket"
APP = Endpoint(HOST, "5432", f"db_{RUN_ID}", f"app_{RUN_ID}")
OWNER = Endpoint(HOST, "5432", f"db_{RUN_ID}", f"owner_{RUN_ID}")
OTHER_HOST = "/tmp/pg-validation-fedcba9876543210/socket"


def test_endpoint_values_validate_the_fixed_isolated_identity():
    assert APP.values() == {
        "host": HOST,
        "port": "5432",
        "dbname": f"db_{RUN_ID}",
        "user": f"app_{RUN_ID}",
        "connect_timeout": "5",
        "sslmode": "disable",
    }
    assert APP.conninfo() == (
        f"host={HOST} port=5432 dbname=db_{RUN_ID} user=app_{RUN_ID} "
        "connect_timeout=5 sslmode=disable"
    )


@pytest.mark.parametrize(
    "suffix",
    [
        "hostaddr=127.0.0.1",
        "service=production",
        "host=other",
        "options=-csearch_path=public",
        "port=5433",
        "dbname=other",
        "user=postgres",
        "host=/tmp/other",
        "connect_timeout=0",
    ],
)
def test_endpoint_rejects_conninfo_suffix_overrides_without_leaking_input(suffix):
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$") as exc:
        APP.validate(APP.conninfo() + " " + suffix, {})
    assert suffix not in str(exc.value)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "postgresql://user:secret@production/db",
        "host=/tmp/pg-validation-0123456789abcdef/socket dbname=db_0123456789abcdef",
        "host=/tmp/pg-validation-0123456789abcdef/socket port=5432 dbname=db_0123456789abcdef user=app_0123456789abcdef user=postgres",
    ],
)
def test_validate_rejects_uri_missing_identity_and_duplicate_keys(bad):
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$") as exc:
        APP.validate(bad, {})
    if bad:
        assert bad not in str(exc.value)


def test_validate_accepts_canonical_conninfo_and_client_option():
    assert APP.validate(APP.conninfo(), {"autocommit": True})["autocommit"] is True
    assert APP.validate(APP.conninfo(), {"autocommit": True}) == {
        "host": HOST,
        "port": "5432",
        "dbname": f"db_{RUN_ID}",
        "user": f"app_{RUN_ID}",
        "connect_timeout": "5",
        "sslmode": "disable",
        "autocommit": True,
    }


def test_explicit_conninfo_ignores_libpq_host_environment(monkeypatch):
    monkeypatch.setenv("PGHOSTADDR", "127.0.0.1")
    monkeypatch.setenv("PGSERVICE", "production")
    assert APP.validate(APP.conninfo(), {})["host"] == HOST
    assert APP.validate(APP.conninfo(), {})["sslmode"] == "disable"


def test_validate_rejects_hostaddr_kwarg():
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        APP.validate(APP.conninfo(), {"hostaddr": "127.0.0.1"})


@pytest.mark.parametrize(
    "host,dbname,user",
    [
        (OTHER_HOST, f"db_{RUN_ID}", f"app_{RUN_ID}"),
        (OTHER_HOST, "db_fedcba9876543210", f"app_{RUN_ID}"),
        (OTHER_HOST, "db_fedcba9876543210", f"owner_{RUN_ID}"),
    ],
)
def test_endpoint_binds_run_id_across_host_database_and_user(host, dbname, user):
    with pytest.raises(ValueError, match="^isolated_pg_identity_invalid$"):
        Endpoint(host, "5432", dbname, user).values()


@dataclass
class _FakeConnection:
    dsn: str
    kwargs: dict


class _FakeConnectionClass:
    calls = []

    @classmethod
    def connect(cls, conninfo="", **kwargs):
        cls.calls.append((conninfo, kwargs))
        return _FakeConnection(conninfo, kwargs)


class _FakeAsyncConnectionClass:
    calls = []

    @classmethod
    async def connect(cls, conninfo="", **kwargs):
        cls.calls.append((conninfo, kwargs))
        return _FakeConnection(conninfo, kwargs)


class _FakeDriver:
    Connection = _FakeConnectionClass
    AsyncConnection = _FakeAsyncConnectionClass

    @staticmethod
    def connect(conninfo="", **kwargs):
        _FakeDriver.top_calls.append((conninfo, kwargs))
        return _FakeConnection(conninfo, kwargs)

    top_calls = []


def _fresh_driver():
    _FakeConnectionClass.calls = []
    _FakeAsyncConnectionClass.calls = []
    _FakeDriver.top_calls = []
    return _FakeDriver


def _evil_dsn():
    return APP.conninfo() + " hostaddr=127.0.0.1"


def test_guard_default_denies_without_policy_and_does_not_call_driver():
    driver = _fresh_driver()
    install(driver)
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        driver.connect(APP.conninfo())
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        driver.Connection.connect(APP.conninfo())
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        asyncio.run(driver.AsyncConnection.connect(APP.conninfo()))
    assert driver.top_calls == []
    assert driver.Connection.calls == []
    assert driver.AsyncConnection.calls == []


def test_guard_allows_only_the_two_loaded_endpoints_for_all_entrypoints():
    driver = _fresh_driver()
    install(driver, endpoints=(APP, OWNER))
    alias = driver.connect
    driver.connect(APP.conninfo(), autocommit=True)
    driver.Connection.connect(OWNER.conninfo())
    asyncio.run(driver.AsyncConnection.connect(APP.conninfo()))
    alias(APP.conninfo())
    assert len(driver.top_calls) == 2
    assert len(driver.Connection.calls) == 1
    assert len(driver.AsyncConnection.calls) == 1

    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        alias(_evil_dsn())
    assert len(driver.top_calls) == 2
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        driver.Connection.connect(_evil_dsn())
    assert len(driver.Connection.calls) == 1
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        asyncio.run(driver.AsyncConnection.connect(_evil_dsn()))
    assert len(driver.AsyncConnection.calls) == 1


@pytest.mark.parametrize(
    "env_name",
    [
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
    ],
)
def test_guard_fails_closed_when_libpq_env_source_exists(monkeypatch, env_name):
    monkeypatch.setenv(env_name, "production")
    driver = _fresh_driver()
    install(driver, endpoints=(APP, OWNER))
    alias = driver.connect
    for entrypoint in (
        lambda: alias(APP.conninfo()),
        lambda: driver.Connection.connect(APP.conninfo()),
        lambda: asyncio.run(driver.AsyncConnection.connect(APP.conninfo())),
    ):
        with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
            entrypoint()
    assert len(driver.top_calls) == 0
    assert len(driver.Connection.calls) == 0
    assert len(driver.AsyncConnection.calls) == 0


def test_stale_alias_uses_latest_reinstalled_policy():
    driver = _fresh_driver()
    install(driver, endpoints=(APP,))
    stale = driver.connect
    install(driver, endpoints=(OWNER,))
    with pytest.raises(ValueError, match="^isolated_pg_connection_rejected$"):
        stale(APP.conninfo())
    assert len(driver.top_calls) == 0
    driver.connect(OWNER.conninfo())
    assert len(driver.top_calls) == 1


def test_guard_preserves_stable_reason_for_malformed_endpoint():
    with pytest.raises(ValueError, match="^isolated_pg_identity_invalid$"):
        Endpoint("/tmp/other", "5432", "db_other", "postgres").values()
