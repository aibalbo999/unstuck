"""True PostgreSQL workflow helpers for the isolated live validation suite."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from pg_validation.policy import Endpoint
from workflow_checkpoints import execute_persistent_graph, open_postgres_checkpointer
from workflow_quality_draft_test_support import builder_for
from workflow_services import create_default_workflow_services
from workflow_state import AgentGraphState


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
        query = sql.SQL(
            action
            + " INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            + direction
            + " {}"
        ).format(sql.Identifier(self.app_endpoint.user))
        async with await psycopg.AsyncConnection.connect(
            self.owner_endpoint.conninfo(), autocommit=True
        ) as conn:
            await conn.execute(query)


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


__all__ = ["PgCase", "pg_builder"]
