"""Run prompt tests with isolated databases and no network access."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit


def _import_psycopg():
    try:
        import psycopg
    except ImportError:
        return None
    return psycopg


def _install_pg_guard(driver, endpoints):
    from pg_validation.guard import install

    install(driver, endpoints)


def _load_pg_policy(path):
    from pg_validation.guard import load_policy

    return load_policy(path)


def configure_postgres_boundary() -> bool:
    """Clear libpq inheritance and install default-deny or live policy guard."""

    policy_path = os.environ.get("STOCK_AGENT_PG_VALIDATION_POLICY")
    for name in tuple(os.environ):
        if name.startswith("PG"):
            os.environ.pop(name, None)
    driver = _import_psycopg()
    if driver is None:
        return policy_path is None
    endpoints = ()
    if policy_path is not None:
        try:
            endpoints = _load_pg_policy(policy_path)
        except (OSError, TypeError, ValueError):
            return False
    _install_pg_guard(driver, endpoints)
    return True


def external_test_sandbox_base(archive: Path, volume: Path) -> Path:
    """Keep tests external, but outside the production/cache namespace."""
    volume = volume.resolve(strict=True)
    archive = archive.resolve(strict=True)
    if (not os.path.ismount(volume) or not archive.is_relative_to(volume)
            or archive.stat().st_dev != volume.stat().st_dev):
        raise RuntimeError('隔離測試稽核區不在已掛載外接碟，停止寫入')
    base = (archive / 'test-sandboxes').resolve()
    if not base.is_relative_to(archive):
        raise RuntimeError('隔離測試暫存路徑離開稽核區，停止寫入')
    if base.exists() and base.stat().st_dev != volume.stat().st_dev:
        raise RuntimeError('隔離測試暫存位於其他檔案系統，停止寫入')
    base.mkdir(parents=False, exist_ok=True, mode=0o700)
    if base.stat().st_dev != volume.stat().st_dev:
        raise RuntimeError('隔離測試暫存位於其他檔案系統，停止寫入')
    return base


def main() -> int:
    if sys.platform == "darwin":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from project_storage import VOLUME, external_environment

        try:
            os.environ.update(external_environment())
        except (OSError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
        # Never put isolated studies inside a production/cache namespace.
        # Explicit external tempdir also prevents implicit macOS /tmp fallback.
        try:
            base = external_test_sandbox_base(Path(os.environ['STOCK_AGENT_ARCHIVE_DIR']), VOLUME)
        except (OSError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
        tempfile.tempdir = str(base)
        os.environ.update(TMPDIR=str(base), TMP=str(base), TEMP=str(base))
    with tempfile.TemporaryDirectory(prefix="prompt-boundary-tests-") as directory:
        root = Path(directory).resolve()
        os.environ.update({
            "STOCK_AGENT_TEST_NO_NETWORK": "1",
            "CACHE_DIR": str(root / "cache"),
            "CACHE_DB_PATH": str(root / "stock_agent_cache.sqlite3"),
            # Keep legacy-compatible test fixtures in this sandbox; never inherit
            # the production dedicated cache path from project_exec/start_mac.
            "JSON_CACHE_DB_PATH": "",
            "OPERATIONAL_DB_PATH": str(root / "operational.sqlite3"),
            "TASK_DB_PATH": str(root / "operational.sqlite3"),
            "LANGGRAPH_CHECKPOINT_PATH": str(root / "checkpoints.sqlite3"),
            "CACHE_BACKEND": "memory",
            "OUTPUT_DIR": str(root / "output"),
            "LANGGRAPH_CHECKPOINT_BACKEND": "sqlite",
            "LANGGRAPH_CHECKPOINT_POSTGRES_DSN": "isolated-postgres-disabled",
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
        if not configure_postgres_boundary():
            print("PostgreSQL validation policy unavailable", flush=True)
            return 2
        import pytest

        print(f"Isolated CACHE/OPERATIONAL/CHECKPOINT databases: {root}; network disabled", flush=True)
        return pytest.main(["--basetemp", str(root / "pytest"), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
