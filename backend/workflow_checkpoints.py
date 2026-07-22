"""Checkpoint backend adapters for LangGraph workflow execution."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph

from workflow_state import AgentGraphState


@asynccontextmanager
async def open_sqlite_checkpointer(path: str | Path):
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(target)) as saver:
        await saver.conn.execute("PRAGMA journal_mode=WAL")
        await saver.conn.execute("PRAGMA busy_timeout=30000")
        await saver.conn.execute("PRAGMA synchronous=NORMAL")
        await saver.setup()
        yield saver


def _load_async_postgres_saver():
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:
        raise RuntimeError(
            "LANGGRAPH_CHECKPOINT_BACKEND=postgres requires langgraph-checkpoint-postgres. "
            "Install backend requirements before enabling PostgreSQL checkpoints."
        ) from exc
    return AsyncPostgresSaver


@asynccontextmanager
async def open_postgres_checkpointer(dsn: str):
    normalized_dsn = str(dsn or "").strip()
    if not normalized_dsn:
        raise ValueError("LANGGRAPH_CHECKPOINT_POSTGRES_DSN must be set when checkpoint backend is postgres")
    saver_cls = _load_async_postgres_saver()
    async with saver_cls.from_conn_string(normalized_dsn) as saver:
        await saver.setup()
        yield saver


@asynccontextmanager
async def open_checkpointer(
    *,
    checkpoint_backend: str = "sqlite",
    checkpoint_path: str | Path | None = None,
    postgres_dsn: str | None = None,
):
    backend = str(checkpoint_backend or "sqlite").strip().lower()
    if backend == "sqlite":
        if checkpoint_path is None:
            raise ValueError("checkpoint_path must be set when checkpoint backend is sqlite")
        async with open_sqlite_checkpointer(checkpoint_path) as saver:
            yield saver
        return
    if backend == "postgres":
        async with open_postgres_checkpointer(postgres_dsn or "") as saver:
            yield saver
        return
    raise ValueError(f"Unsupported LangGraph checkpoint backend: {checkpoint_backend}")


async def execute_persistent_graph(
    *,
    graph_builder: StateGraph,
    initial_state: AgentGraphState,
    thread_id: str,
    checkpoint_path: str | Path,
    checkpoint_backend: str = "sqlite",
    checkpoint_postgres_dsn: str | None = None,
) -> AgentGraphState:
    config = {"configurable": {"thread_id": thread_id}}
    async with open_checkpointer(
        checkpoint_backend=checkpoint_backend,
        checkpoint_path=checkpoint_path,
        postgres_dsn=checkpoint_postgres_dsn,
    ) as saver:
        graph = graph_builder.compile(checkpointer=saver)
        snapshot = await graph.aget_state(config)
        if snapshot.values and not snapshot.next:
            return dict(snapshot.values)
        graph_input = None if snapshot.values else initial_state
        return dict(await graph.ainvoke(graph_input, config=config))


__all__ = [
    "execute_persistent_graph",
    "open_checkpointer",
    "open_postgres_checkpointer",
    "open_sqlite_checkpointer",
]
