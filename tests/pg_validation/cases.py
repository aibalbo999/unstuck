"""True PostgreSQL workflow helpers for the isolated live validation suite."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from weakref import WeakKeyDictionary

from langgraph.graph import END, START, StateGraph

from pg_validation.policy import Endpoint
from workflow_checkpoints import execute_persistent_graph, open_postgres_checkpointer
from workflow_quality_draft_test_support import builder_for
from workflow_services import create_default_workflow_services
from workflow_state import AgentGraphState

from .result import EXPECTED_CASES, accepted_result


@dataclass(slots=True)
class PgCase:
    """One UUID-scoped workflow case inside the attested dedicated database."""

    app_endpoint: Endpoint
    owner_endpoint: Endpoint
    sqlite_path: Path
    prefix: str

    def thread(self, name: str = "draft-job") -> str:
        return f"{self.prefix}:{name}"

    def execute(
        self,
        state,
        calls,
        *,
        thread: str = "draft-job",
        agents=(4,),
        builder=None,
    ):
        return asyncio.run(execute_persistent_graph(
            graph_builder=builder if builder is not None else builder_for(calls, agents),
            initial_state=state,
            thread_id=self.thread(thread),
            checkpoint_path=self.sqlite_path,
            checkpoint_backend="postgres",
            checkpoint_postgres_dsn=self.app_endpoint.conninfo(),
        ))

    def tuples(self, thread: str = "draft-job"):
        async def read():
            async with open_postgres_checkpointer(self.app_endpoint.conninfo()) as saver:
                config = {"configurable": {"thread_id": self.thread(thread)}}
                rows = [item async for item in saver.alist(config)]
                return sorted(rows, key=lambda item: item.checkpoint["id"])

        return asyncio.run(read())

    def drafts(self, thread: str = "draft-job"):
        return [
            item for item in self.tuples(thread)
            if item.config["configurable"].get("checkpoint_ns", "").startswith("quality_draft/")
        ]

    def snapshot(
        self,
        calls,
        *,
        thread: str = "draft-job",
        agents=(4,),
        builder=None,
    ):
        async def read():
            async with open_postgres_checkpointer(self.app_endpoint.conninfo()) as saver:
                graph_builder = builder if builder is not None else builder_for(calls, agents)
                graph = graph_builder.compile(checkpointer=saver)
                return await graph.aget_state({"configurable": {
                    "thread_id": self.thread(thread),
                    "checkpoint_ns": "",
                }})

        return asyncio.run(read())

    async def permissions(self, enabled: bool) -> None:
        import psycopg
        from psycopg import sql

        action, direction = ("GRANT", "TO") if enabled else ("REVOKE", "FROM")
        if self.owner_endpoint.user == self.app_endpoint.user:
            raise AssertionError("isolated_pg_owner_and_app_must_differ")
        tables = sql.SQL(", ").join(
            sql.Identifier(name)
            for name in (
                "checkpoint_migrations",
                "checkpoints",
                "checkpoint_blobs",
                "checkpoint_writes",
            )
        )
        query = sql.SQL(action + " INSERT, UPDATE, DELETE ON TABLE " + "{} " + direction + " {}").format(
            tables,
            sql.Identifier(self.app_endpoint.user),
        )
        async with await psycopg.AsyncConnection.connect(
            self.owner_endpoint.conninfo(), autocommit=True
        ) as conn:
            await conn.execute(query)

            result = await conn.execute(
                "SELECT current_database(), current_user, "
                "(SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user)"
            )
            owner_database, owner_user, owner_superuser = await result.fetchone()
            if (
                owner_database != self.app_endpoint.dbname
                or owner_user != self.owner_endpoint.user
                or owner_superuser is not False
            ):
                raise AssertionError("isolated_pg_draft_privileges_invalid")

        async with await psycopg.AsyncConnection.connect(
            self.app_endpoint.conninfo(), autocommit=True
        ) as app_conn:
            result = await app_conn.execute(
                "SELECT current_database(), current_user, "
                "(SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user), "
                "EXISTS (SELECT 1 FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' AND tablename IN "
                "('checkpoint_migrations', 'checkpoints', 'checkpoint_blobs', 'checkpoint_writes') "
                "AND tableowner = current_user), "
                "has_table_privilege(current_user, 'public.checkpoints', 'SELECT'), "
                "has_table_privilege(current_user, 'public.checkpoints', 'INSERT'), "
                "has_table_privilege(current_user, 'public.checkpoints', 'UPDATE'), "
                "has_table_privilege(current_user, 'public.checkpoints', 'DELETE')"
            )
            (
                app_database,
                app_user,
                app_superuser,
                app_owns_table,
                can_select,
                can_insert,
                can_update,
                can_delete,
            ) = await result.fetchone()
            if (
                app_database != self.app_endpoint.dbname
                or app_user != self.app_endpoint.user
                or app_user == self.owner_endpoint.user
                or app_superuser is not False
                or app_owns_table
                or not can_select
                or (enabled and not (can_insert and can_update and can_delete))
                or (not enabled and (can_insert or can_update or can_delete))
            ):
                raise AssertionError("isolated_pg_draft_privileges_invalid")


def deny_draft_write(monkeypatch, case: PgCase, *, target_thread: str, matches):
    """Revoke only for a selected draft write and execute the real saver method.

    The temporary barrier is intentionally test-only.  The lock is shared by
    the current event loop so a graph cannot interleave an unrelated
    ``aput_writes`` call while the app role is denied DML privileges.
    """

    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    put = AsyncPostgresSaver.aput
    put_writes = AsyncPostgresSaver.aput_writes
    locks = WeakKeyDictionary()
    evidence = []

    def lock_for_current_loop():
        loop = asyncio.get_running_loop()
        try:
            return locks[loop]
        except KeyError:
            lock = asyncio.Lock()
            locks[loop] = lock
            return lock

    async def guarded_put(self, config, checkpoint, metadata, new_versions):
        async with lock_for_current_loop():
            configurable = config["configurable"]
            record = checkpoint.get("channel_values", {}).get("quality_draft", {})
            selected = (
                configurable.get("thread_id") == target_thread
                and configurable.get("checkpoint_ns", "").startswith("quality_draft/")
                and isinstance(record, dict)
                and matches(record)
            )
            if not selected:
                return await put(self, config, checkpoint, metadata, new_versions)

            revoke_attempted = False
            try:
                # permissions(False) also verifies the app role after REVOKE;
                # if that verification fails, restoration is still required.
                revoke_attempted = True
                await case.permissions(False)
                try:
                    result = await put(self, config, checkpoint, metadata, new_versions)
                except psycopg.Error as exc:
                    evidence.append(
                        {
                            "thread_id": configurable["thread_id"],
                            "namespace": configurable["checkpoint_ns"],
                            "sqlstate": exc.sqlstate,
                            "target_reached": True,
                        }
                    )
                    raise
                else:
                    raise AssertionError("isolated_pg_draft_write_not_denied")
            finally:
                # Do not swallow a restore failure: it must fail the live case.
                if revoke_attempted:
                    await case.permissions(True)

    async def guarded_writes(self, *args, **kwargs):
        async with lock_for_current_loop():
            return await put_writes(self, *args, **kwargs)

    monkeypatch.setattr(AsyncPostgresSaver, "aput", guarded_put)
    monkeypatch.setattr(AsyncPostgresSaver, "aput_writes", guarded_writes)
    return evidence


def pg_builder(calls, agents=(4,)):
    """Build a deterministic graph with a durable prerequisite before agents."""

    services = create_default_workflow_services(rotator=object())
    builder = StateGraph(AgentGraphState)

    async def prerequisite(state):
        calls["prerequisite"] = calls.get("prerequisite", 0) + 1
        return {"execution_trace": [{"id": "pg-prerequisite"}]}

    builder.add_node("prerequisite", prerequisite)
    builder.add_edge(START, "prerequisite")
    names = []
    for agent in agents:
        name = f"agent_{agent}"
        names.append(name)

        async def run(state, agent=agent):
            result = await services.run_agent(agent, state)
            calls["nodes_returned"].append(agent)
            return result

        builder.add_node(name, run)
        builder.add_edge("prerequisite", name)

    async def publish(state):
        calls["published"] += 1
        return {"status": "done"}

    builder.add_node("publish", publish)
    builder.add_edge(names, "publish")
    builder.add_edge("publish", END)
    return builder


__all__ = [
    "EXPECTED_CASES",
    "PgCase",
    "accepted_result",
    "deny_draft_write",
    "pg_builder",
]
