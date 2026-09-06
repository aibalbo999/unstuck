"""PG-01 bootstrap evidence for the opt-in isolated PostgreSQL live suite.

This task intentionally contains only PG-01.  It is not evidence that the
eventual complete PostgreSQL case registry has passed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from uuid import uuid4

import pytest

from pg_validation.guard import POLICY_ENV, load_policy


_POLICY_PATH = os.environ.get(POLICY_ENV)
if _POLICY_PATH is None:
    pytest.skip(
        "isolated PostgreSQL live suite not enabled",
        allow_module_level=True,
    )
if os.environ.get("PYTEST_XDIST_WORKER") is not None:
    raise RuntimeError("isolated PostgreSQL live suite does not support xdist")

_OWNER_ENDPOINT, _APP_ENDPOINT = load_policy(_POLICY_PATH)

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import sql

from pg_validation.cases import PgCase
from workflow_checkpoints import open_postgres_checkpointer


@dataclass(frozen=True, slots=True)
class PgSetupEvidence:
    owner_endpoint: object
    app_endpoint: object
    tables_before: tuple[str, ...]
    tables_after: tuple[str, ...]
    migrations_after: tuple[int, ...]


async def _public_tables(conn) -> tuple[str, ...]:
    result = await conn.execute(
        "SELECT tablename FROM pg_catalog.pg_tables "
        "WHERE schemaname = 'public' ORDER BY tablename"
    )
    return tuple(row[0] for row in await result.fetchall())


async def _migration_rows(conn) -> tuple[int, ...]:
    result = await conn.execute("SELECT v FROM checkpoint_migrations ORDER BY v")
    return tuple(row[0] for row in await result.fetchall())


@pytest.fixture(scope="session")
def pg_setup_evidence() -> PgSetupEvidence:
    async def prepare() -> PgSetupEvidence:
        async with await psycopg.AsyncConnection.connect(
            _OWNER_ENDPOINT.conninfo(), autocommit=True
        ) as owner_conn:
            tables_before = await _public_tables(owner_conn)

        async with AsyncPostgresSaver.from_conn_string(
            _OWNER_ENDPOINT.conninfo()
        ) as saver:
            await saver.setup()

        async with await psycopg.AsyncConnection.connect(
            _OWNER_ENDPOINT.conninfo(), autocommit=True
        ) as owner_conn:
            tables_after = await _public_tables(owner_conn)
            migrations_after = await _migration_rows(owner_conn)
            await owner_conn.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(_APP_ENDPOINT.user)
                )
            )
            await owner_conn.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON ALL TABLES IN SCHEMA public TO {}"
                ).format(sql.Identifier(_APP_ENDPOINT.user))
            )

        return PgSetupEvidence(
            owner_endpoint=_OWNER_ENDPOINT,
            app_endpoint=_APP_ENDPOINT,
            tables_before=tables_before,
            tables_after=tables_after,
            migrations_after=migrations_after,
        )

    return asyncio.run(prepare())


@pytest.fixture
def pg_case(tmp_path, pg_setup_evidence) -> PgCase:
    return PgCase(
        app_endpoint=pg_setup_evidence.app_endpoint,
        owner_endpoint=pg_setup_evidence.owner_endpoint,
        sqlite_path=tmp_path / "unused.sqlite3",
        prefix=uuid4().hex,
    )


def test_pg01_empty_setup_and_reopen_are_idempotent(
    pg_case,
    pg_setup_evidence,
):
    async def reopen_migrations(endpoint) -> tuple[int, ...]:
        async with open_postgres_checkpointer(endpoint.conninfo()) as saver:
            result = await saver.conn.execute(
                "SELECT v FROM checkpoint_migrations ORDER BY v"
            )
            rows = await result.fetchall()
            return tuple(row["v"] for row in rows)

    async def app_identity_and_owners():
        async with open_postgres_checkpointer(
            pg_setup_evidence.app_endpoint.conninfo()
        ) as saver:
            identity_result = await saver.conn.execute(
                "SELECT current_database() AS database_name, "
                "current_user AS user_name, "
                "(SELECT rolsuper FROM pg_catalog.pg_roles "
                "WHERE rolname = current_user) AS rolsuper"
            )
            identity = await identity_result.fetchone()
            owners_result = await saver.conn.execute(
                "SELECT tablename, tableowner FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
            owners = {
                row["tablename"]: row["tableowner"]
                for row in await owners_result.fetchall()
            }
            return identity, owners

    first_reopen = asyncio.run(reopen_migrations(pg_setup_evidence.owner_endpoint))
    second_reopen = asyncio.run(reopen_migrations(pg_setup_evidence.owner_endpoint))
    identity, table_owners = asyncio.run(app_identity_and_owners())

    assert pg_setup_evidence.tables_before == ()
    assert pg_setup_evidence.tables_after
    assert len(pg_setup_evidence.tables_after) == len(set(pg_setup_evidence.tables_after))
    assert pg_setup_evidence.migrations_after
    assert len(pg_setup_evidence.migrations_after) == len(set(pg_setup_evidence.migrations_after))
    assert first_reopen == pg_setup_evidence.migrations_after == second_reopen
    assert identity["database_name"] == pg_setup_evidence.app_endpoint.dbname
    assert identity["user_name"] == pg_setup_evidence.app_endpoint.user
    assert identity["user_name"] != pg_setup_evidence.owner_endpoint.user
    assert identity["rolsuper"] is False
    assert set(table_owners) == set(pg_setup_evidence.tables_after)
    assert all(
        owner != pg_setup_evidence.app_endpoint.user
        for owner in table_owners.values()
    )
    assert not pg_case.sqlite_path.exists()
