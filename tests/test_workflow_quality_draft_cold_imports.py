"""Cold imports must work without warming up agent_runtime first."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["workflow_quality_drafts", "workflow_checkpoints", "agent_runtime.quality_gates"])
def test_workflow_draft_cold_imports_in_isolated_process(tmp_path, module):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, CACHE_DIR=str(tmp_path / "cache"), CACHE_BACKEND="memory",
               CACHE_DB_PATH=str(tmp_path / "cache.sqlite3"),
               OPERATIONAL_DB_PATH=str(tmp_path / "operational.sqlite3"),
               TASK_DB_PATH=str(tmp_path / "operational.sqlite3"),
               LANGGRAPH_CHECKPOINT_PATH=str(tmp_path / "checkpoints.sqlite3"))
    code = """
import importlib
from pathlib import Path
import socket
import sqlite3
import sys
from urllib.parse import unquote, urlsplit

root = Path(sys.argv[1]).resolve()
connect = sqlite3.connect

def isolated_connect(database, *args, **kwargs):
    name = str(database)
    if name != ':memory:':
        path = Path(unquote(urlsplit(name).path) if name.startswith('file:') else name).resolve()
        assert path.is_relative_to(root), f'Nonisolated database access: {path}'
    return connect(database, *args, **kwargs)

def no_network(*args, **kwargs):
    raise AssertionError('Cold imports must not contact runtime, Redis, or providers')

sqlite3.connect = isolated_connect
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = no_network
assert 'agent_runtime' not in sys.modules
sys.path.insert(0, sys.argv[2])
importlib.import_module(sys.argv[3])
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(tmp_path), str(root / "backend"), module],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
