"""Run prompt tests with isolated databases and no network access."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="prompt-boundary-tests-") as directory:
        root = Path(directory).resolve()
        os.environ.update({
            "CACHE_DIR": str(root / "cache"),
            "CACHE_DB_PATH": str(root / "stock_agent_cache.sqlite3"),
            "OPERATIONAL_DB_PATH": str(root / "operational.sqlite3"),
            "TASK_DB_PATH": str(root / "operational.sqlite3"),
            "LANGGRAPH_CHECKPOINT_PATH": str(root / "checkpoints.sqlite3"),
            "CACHE_BACKEND": "memory",
        })
        connect = sqlite3.connect

        def isolated_connect(database, *args, **kwargs):
            name = os.fspath(database)
            if name != ":memory:":
                uri = urlsplit(name) if name.startswith("file:") else None
                path = Path(unquote(uri.path) if uri else name).resolve()
                if not path.is_relative_to(root):
                    query = parse_qs(uri.query) if uri else {}
                    replay = os.environ.get("PROMPT_REPLAY_CHECKPOINT_DB")
                    allowed_replay = (
                        replay and path == Path(replay).resolve() and kwargs.get("uri")
                        and query.get("mode") == ["ro"] and query.get("immutable") == ["1"]
                    )
                    if not allowed_replay:
                        raise AssertionError(f"Database access outside isolated test directory: {path}")
            return connect(database, *args, **kwargs)

        def no_network(*args, **kwargs):
            # Optional live suites recognize an unavailable socket and skip normally.
            raise OSError("Isolated tests cannot contact runtime, Redis, or providers")

        sqlite3.connect = isolated_connect
        socket.socket.connect = no_network
        socket.socket.connect_ex = no_network
        socket.create_connection = no_network
        import pytest

        print(f"Isolated CACHE/OPERATIONAL/CHECKPOINT databases: {root}; network disabled", flush=True)
        return pytest.main(["--basetemp", str(root / "pytest"), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
