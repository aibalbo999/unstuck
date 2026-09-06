"""Opt-in true-PostgreSQL workflow persistence and recovery checks.

The module is deliberately skipped unless the validated isolated PostgreSQL
policy is present.  A skipped module is therefore not evidence that the live
suite passed; the offline test suite covers only collection and contract
boundaries.
"""

from __future__ import annotations

import asyncio
import copy
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

from pg_validation.cases import PgCase, pg_builder
from workflow_checkpoints import open_postgres_checkpointer
from workflow_quality_draft_test_support import (
    initial_state,
    intermediate_quality_runtime,
    quality_runtime,
)

from agent_runtime import quality_gates, step_cache
from agent_runtime.deferred import AgentDeferredError
from langgraph.errors import NodeCancelledError


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


async def _save_draft(case, state, text, *, thread="draft-job"):
    """Write one quality-draft checkpoint through a fresh PostgreSQL saver."""

    from workflow_quality_drafts import (
        checkpoint_draft_scope,
        checkpoint_unvalidated_draft,
        quality_draft_node,
    )

    context = {
        "pipeline_id": "v1",
        "analyses": {},
        "structured_outputs": {},
        "rag_context": {},
        "context_digests": {},
    }
    async with open_postgres_checkpointer(case.app_endpoint.conninfo()) as saver:
        with checkpoint_draft_scope(saver, case.thread(thread)):
            async with quality_draft_node(4, state, context):
                context["structured_outputs"][4] = {"draft": text}
                context["market_context_manifests"] = {4: {"source": text}}
                context["rag_context"][4] = f"rag:{text}"
                context["context_digests"][4] = f"digest:{text}"
                await checkpoint_unvalidated_draft(4, text, context)


def test_pg02_original_and_intermediate_drafts_roundtrip(pg_case):
    state = initial_state()
    for text in ("original", "intermediate"):
        asyncio.run(_save_draft(pg_case, state, text))

    rows = pg_case.drafts()
    assert len(rows) == 2
    versions = [row.checkpoint["channel_versions"]["quality_draft"] for row in rows]
    assert versions[1] > versions[0]
    fingerprints = set()
    for row, text in zip(rows, ("original", "intermediate"), strict=True):
        record = row.checkpoint["channel_values"]["quality_draft"]
        assert record["text"] == text and record["status"] == "unvalidated"
        assert record["structured_output"] == {"draft": text}
        assert record["market_context_manifest"] == {"source": text}
        assert record["rag_context"] == f"rag:{text}"
        assert record["context_digest"] == f"digest:{text}"
        fingerprints.add(record["input_fingerprint"])
    assert len(fingerprints) == 1
    assert not pg_case.sqlite_path.exists()


@pytest.mark.parametrize(
    "cache_enabled,ttl",
    [(False, 3600), (True, 0), (False, 0)],
    ids=["disabled", "expired", "disabled-expired"],
)
def test_pg03_deferred_draft_resumes_gate_once(
    pg_case, quality_runtime, monkeypatch, cache_enabled, ttl,
):
    calls, control, _events = quality_runtime
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_ENABLED", cache_enabled)
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_SECONDS", ttl)
    control["raw_size"] = 110_000
    state = initial_state()

    with pytest.raises(AgentDeferredError):
        pg_case.execute(state, calls, builder=pg_builder(calls))

    saved = pg_case.drafts()[0].checkpoint["channel_values"]["quality_draft"]
    assert saved["status"] == "unvalidated"
    assert saved["text"] == "unvalidated-draft-4:" + "x" * 110_000
    assert saved["structured_output"] == {"unvalidated_value": 4}
    assert saved["rag_context"] == "retrieved-evidence-4"
    assert saved["context_digest"] == "digest-4"
    pending = pg_case.snapshot(calls, builder=pg_builder(calls))
    assert pending.next == ("agent_4",)
    assert not pending.values.get("analyses")
    assert not pending.values.get("agent_reports")
    assert calls["published"] == 0

    control["deferred"] = False
    result = pg_case.execute(state, calls, builder=pg_builder(calls))
    assert result["analyses"]["4"] == "validated-result-4"
    assert result["agent_reports"]["4"]["markdown"] == "validated-result-4"
    assert result["status"] == "done"
    assert calls["initial"] == [4] and calls["published"] == 1
    assert len(calls["rewrite"]) == 2
    assert calls["prerequisite"] == 1
    assert [text for _, text in calls["validated"]].count(saved["text"]) == 2
    assert calls["parsed"][-2][2] == {"unvalidated_value": 4}
    assert not pg_case.sqlite_path.exists()


def test_pg02_intermediate_repair_survives_repeated_deferral(
    pg_case, intermediate_quality_runtime,
):
    calls, control, generated = intermediate_quality_runtime
    state = initial_state()
    for _ in range(2):
        with pytest.raises(AgentDeferredError):
            pg_case.execute(state, calls, builder=pg_builder(calls))

    assert generated == ["bad-json", "repaired-draft-1"]
    assert calls["rewrite"] == [(4, "repaired-draft-1"), (4, "repaired-draft-1")]
    rows = pg_case.drafts()
    assert len(rows) == 2
    assert rows[1].checkpoint["channel_versions"]["quality_draft"] > rows[0].checkpoint["channel_versions"]["quality_draft"]
    latest = rows[-1].checkpoint["channel_values"]["quality_draft"]
    assert latest["status"] == "unvalidated"
    assert latest["text"] == "repaired-draft-1"
    assert latest["structured_output"] == {"draft": "repaired-draft-1"}
    assert latest["rag_context"] == "retrieved-evidence-4"
    assert latest["context_digest"] == "digest-4"
    assert calls["parsed"][-1][2] == {"draft": "repaired-draft-1"}
    assert calls["published"] == 0
    pending = pg_case.snapshot(calls, builder=pg_builder(calls))
    assert pending.next == ("agent_4",)
    assert not pending.values.get("analyses")
    assert not pending.values.get("agent_reports")

    control["deferred"] = False
    assert pg_case.execute(state, calls, builder=pg_builder(calls))["analyses"]["4"] == "validated-result-4"
    assert generated == ["bad-json", "repaired-draft-1"]


def test_pg03_restored_draft_does_not_refresh_evidence(
    pg_case, quality_runtime, monkeypatch,
):
    calls, control, events = quality_runtime
    state = initial_state()
    with pytest.raises(AgentDeferredError):
        pg_case.execute(state, calls, builder=pg_builder(calls))

    async def forbidden_refresh(*args, **kwargs):
        pytest.fail("resumed draft refreshed its evidence")

    generate = quality_gates.run_single_agent_async

    async def check_inputs(agent, data, context, rotator):
        assert context.get("_audit_retry_instruction")
        assert context["rag_context"][agent] == "retrieved-evidence-4"
        assert context["context_digests"][agent] == "digest-4"
        return await generate(agent, data, context, rotator)

    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", forbidden_refresh)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", forbidden_refresh)
    monkeypatch.setattr(quality_gates, "run_single_agent_async", check_inputs)
    control["deferred"] = False
    assert pg_case.execute(state, calls, builder=pg_builder(calls))["status"] == "done"
    assert calls["initial"] == [4]
    assert any(event.get("phase") == "quality_draft_restored" for event in events)


def test_pg04_cancel_after_draft_resumes_without_partial_adoption(
    pg_case, quality_runtime, monkeypatch,
):
    calls, control, _events = quality_runtime
    original_generate = quality_gates.run_single_agent_async

    async def cancel_retry(agent, data, context, rotator):
        if control["deferred"] and context.get("_audit_retry_instruction"):
            raise asyncio.CancelledError()
        return await original_generate(agent, data, context, rotator)

    monkeypatch.setattr(quality_gates, "run_single_agent_async", cancel_retry)
    state = initial_state()
    with pytest.raises(NodeCancelledError):
        pg_case.execute(state, calls, builder=pg_builder(calls))

    assert len(pg_case.drafts()) == 1
    snapshot = pg_case.snapshot(calls, builder=pg_builder(calls))
    assert snapshot.next == ("agent_4",)
    assert not snapshot.values.get("analyses") and not snapshot.values.get("agent_reports")
    assert calls["published"] == 0

    control["deferred"] = False
    assert pg_case.execute(state, calls, builder=pg_builder(calls))["status"] == "done"
    assert calls["initial"] == [4] and calls["prerequisite"] == 1


def test_pg08_completed_graph_reopen_does_not_repeat_work_or_publish(
    pg_case, quality_runtime,
):
    calls, control, _events = quality_runtime
    control["deferred"] = False
    state = initial_state()
    expected = pg_case.execute(state, calls, builder=pg_builder(calls))
    before = copy.deepcopy(calls)
    actual = pg_case.execute(state, calls, builder=pg_builder(calls))
    assert actual == expected and calls == before
    assert not pg_case.sqlite_path.exists()
