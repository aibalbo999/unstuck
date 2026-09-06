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

from pg_validation.cases import PgCase, deny_draft_write, pg_builder
from workflow_checkpoints import open_postgres_checkpointer
from workflow_quality_draft_test_support import (
    initial_state,
    intermediate_quality_runtime,
    quality_runtime,
)

from agent_runtime import audit_repair, quality_gates, step_cache
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


def test_pg05_threads_agents_and_completed_sibling_are_isolated(
    pg_case, quality_runtime, monkeypatch,
):
    """A deferred agent resumes only in its own thread after its sibling commits."""

    calls, control, _events = quality_runtime
    control.update(deferred_agents={4}, wait_for_sibling=True)
    generate = quality_gates.run_single_agent_async

    async def tagged(agent, data, context, rotator):
        return (await generate(agent, data, context, rotator)) + "|" + context["ticker"]

    monkeypatch.setattr(quality_gates, "run_single_agent_async", tagged)
    states = {}
    for name in ("first", "second"):
        state = initial_state()
        state["ticker"] = name
        state["normalized_financials"]["ticker"] = name
        states[name] = state
        with pytest.raises(AgentDeferredError):
            pg_case.execute(state, calls, thread=name, agents=(4, 14))
        assert pg_case.snapshot(calls, thread=name, agents=(4, 14)).next == ("agent_4",)
        for row in pg_case.drafts(name):
            assert row.config["configurable"]["thread_id"] == pg_case.thread(name)
            assert row.checkpoint["channel_values"]["quality_draft"]["text"].endswith(
                "|" + name
            )

    control["deferred"] = False
    for name, state in states.items():
        result = pg_case.execute(state, calls, thread=name, agents=(4, 14))
        assert all(text.endswith("|" + name) for text in result["analyses"].values())
    assert calls["initial"].count(4) == 2 and calls["initial"].count(14) == 2
    assert calls["nodes_returned"].count(14) == 2
    assert calls["nodes_returned"].count(4) == 2 and calls["published"] == 2


def test_pg06_draft_restoration_tracks_upstream_fingerprint(pg_case):
    """Only a real upstream context change creates a new draft namespace."""

    from test_repair_dependencies import _context
    from workflow_quality_drafts import (
        checkpoint_draft_scope,
        initial_or_checkpointed_draft,
        quality_draft_node,
    )

    generated = []
    fixed_graph_state = {"analyses": {"4": "unchanged-graph"}}

    async def generate(agent, data, context, rotator):
        value = context["analyses"][4]
        generated.append(value)
        context.setdefault("rag_context", {})[7] = value
        context.setdefault("context_digests", {})[7] = value
        context.setdefault("market_context_manifests", {})[7] = {"value": value}
        return value

    async def run():
        for value in ("old", "new", "old"):
            context = _context()
            context["analyses"][4] = value
            async with open_postgres_checkpointer(pg_case.app_endpoint.conninfo()) as saver:
                with checkpoint_draft_scope(saver, pg_case.thread()):
                    async with quality_draft_node(7, fixed_graph_state, context):
                        text = await initial_or_checkpointed_draft(
                            7, {}, context, object(), generate
                        )
                        assert text == value
                        assert context["rag_context"][7] == value
                        assert context["context_digests"][7] == value
                        assert context["market_context_manifests"][7] == {"value": value}

    asyncio.run(run())
    assert generated == ["old", "new"]
    assert len({
        row.config["configurable"]["checkpoint_ns"]
        for row in pg_case.drafts()
    }) == 2


def test_pg06_dependency_repair_resumes_atomic_invalidated_round(
    pg_case, monkeypatch,
):
    """A real graph resumes only the uncommitted repair round after reopen."""

    from langgraph.graph import END, START, StateGraph
    from state_memory import initialize_agent_state as initialize_domain_state
    from workflow_services import create_default_workflow_services
    from workflow_state import AgentGraphState, agent_state_to_graph
    from test_repair_dependencies import _context

    visits, prior = [], []
    allow_finish = False

    async def complete(agent, data, candidate, rotator, issues):
        visits.append(agent)
        if agent == 21 and not allow_finish:
            raise AgentDeferredError(
                agent,
                [{"model_id": "test-model", "retry_wait_seconds": 1}],
            )
        candidate["analyses"][agent] = f"repaired {agent}"
        candidate["structured_outputs"][agent] = {"value": f"repaired {agent}"}
        return True, "accepted"

    def audit(context, **kwargs):
        issues = {4: ["valuation"]} if context["analyses"].get(4) == "original 4" else {}
        return {
            "critical": ["old valuation"] if issues else [],
            "repair_agent_issues": issues,
        }

    monkeypatch.setattr(audit_repair, "_repair_agent_output_async", complete)
    monkeypatch.setattr(audit_repair, "run_final_report_audit", audit)

    async def execute():
        nonlocal allow_finish
        services = create_default_workflow_services(rotator=object())
        builder = StateGraph(AgentGraphState)

        async def previous_node(state):
            prior.append("already successful")
            return {}

        builder.add_node("previous", previous_node)
        builder.add_node("final_audit", services.final_audit)
        builder.add_edge(START, "previous")
        builder.add_edge("previous", "final_audit")
        builder.add_edge("final_audit", END)
        state = {
            **agent_state_to_graph(
                initialize_domain_state({"ticker": "TEST"}), pipeline_id="v1"
            ),
            **_context(),
        }
        config = {
            "configurable": {
                "thread_id": pg_case.thread("repair-deferred"),
                "checkpoint_ns": "",
            }
        }

        async with open_postgres_checkpointer(pg_case.app_endpoint.conninfo()) as saver:
            graph = builder.compile(checkpointer=saver)
            with pytest.raises(AgentDeferredError):
                await graph.ainvoke(state, config)
            snapshot = await graph.aget_state(config)
            assert snapshot.next == ("final_audit",)
            assert snapshot.values["analyses"][4] == "original 4"
            assert snapshot.values["analyses"][7] == "original 7"

        allow_finish = True
        async with open_postgres_checkpointer(pg_case.app_endpoint.conninfo()) as saver:
            graph = builder.compile(checkpointer=saver)
            result = await graph.ainvoke(None, config)
            assert result["analyses"]["4"] == "repaired 4"
            assert result["analyses"]["7"] == "repaired 7"
            assert result["invalidated_agents"] == []

    asyncio.run(execute())
    assert prior == ["already successful"]
    assert visits == [4, 6, 21, 4, 6, 21, 7]


def test_pg07_original_draft_permission_denied_fails_closed(
    pg_case, quality_runtime, monkeypatch,
):
    calls, control, _events = quality_runtime
    state = initial_state()
    asyncio.run(_save_draft(pg_case, state, "old-other-thread", thread="baseline"))
    before = [row.checkpoint for row in pg_case.drafts("baseline")]

    evidence = deny_draft_write(
        monkeypatch,
        pg_case,
        target_thread=pg_case.thread(),
        matches=lambda record: record.get("text", "").startswith("unvalidated-draft-4:"),
    )
    with pytest.raises(psycopg.Error) as denied:
        pg_case.execute(state, calls, builder=pg_builder(calls))

    assert denied.value.sqlstate == "42501"
    assert evidence and all(item["sqlstate"] == "42501" for item in evidence)
    assert all(item["thread_id"] == pg_case.thread() for item in evidence)
    assert all(item["namespace"].startswith("quality_draft/") for item in evidence)
    assert not pg_case.drafts()
    assert [row.checkpoint for row in pg_case.drafts("baseline")] == before
    assert calls["initial"] == [4]
    assert not calls["parsed"] and not calls["validated"] and not calls["rewrite"]
    assert calls["published"] == 0 and calls["prerequisite"] == 1
    assert pg_case.snapshot(calls, builder=pg_builder(calls)).next == ("agent_4",)


def test_pg07_intermediate_draft_permission_denied_preserves_original(
    pg_case, intermediate_quality_runtime, monkeypatch,
):
    calls, control, generated = intermediate_quality_runtime
    control["deferred"] = False
    barrier_counts = []

    def matches(record):
        selected = record.get("text") == "repaired-draft-1"
        if selected:
            barrier_counts.append((len(calls["validated"]), len(calls["parsed"])))
        return selected

    evidence = deny_draft_write(
        monkeypatch,
        pg_case,
        target_thread=pg_case.thread(),
        matches=matches,
    )
    with pytest.raises(psycopg.Error) as denied:
        pg_case.execute(initial_state(), calls, builder=pg_builder(calls))

    assert denied.value.sqlstate == "42501"
    assert len(evidence) == 1 and evidence[0]["sqlstate"] == "42501"
    assert evidence[0]["thread_id"] == pg_case.thread()
    assert evidence[0]["namespace"].startswith("quality_draft/")
    assert generated == ["bad-json", "repaired-draft-1"]
    rows = pg_case.drafts()
    assert len(rows) == 1
    original = rows[0].checkpoint["channel_values"]["quality_draft"]
    assert original["text"] == "bad-json"
    assert original["structured_output"] == {"draft": "bad-json"}
    assert barrier_counts == [(len(calls["validated"]), len(calls["parsed"]))]
    assert not calls["rewrite"] and calls["published"] == 0
    snapshot = pg_case.snapshot(calls, builder=pg_builder(calls))
    assert snapshot.next == ("agent_4",)
    assert not snapshot.values.get("analyses") and not snapshot.values.get("agent_reports")


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
