"""Opt-in, read-only replay of an existing checkpoint; no workflow is executed."""

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from types import ModuleType, SimpleNamespace

import pytest


@pytest.mark.skipif(not os.getenv("PROMPT_REPLAY_CHECKPOINT_DB"), reason="requires an explicit offline checkpoint DB")
def test_existing_checkpoint_prompt_reduction(monkeypatch):
    from agent_runtime import prompting
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from llm_rate_limits import estimate_text_tokens
    from workflow_context import input_data_from_state, legacy_context_from_graph
    from workflow_state import rag_index_to_payload

    root = Path(__file__).resolve().parents[1]
    path = Path(os.environ["PROMPT_REPLAY_CHECKPOINT_DB"]).resolve()
    thread_id = os.environ["PROMPT_REPLAY_THREAD_ID"]
    assert not Path(str(path) + "-wal").exists(), "Replay requires a quiescent offline DB without a WAL"
    before_stat = (path.stat().st_size, path.stat().st_mtime_ns)
    uri = path.as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as db:
        row = db.execute(
            "SELECT checkpoint_id, type, checkpoint FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
    assert row is not None
    checkpoint_id, kind, blob = row
    graph = JsonPlusSerializer().loads_typed((kind, blob))["channel_values"]
    before_graph = copy.deepcopy(graph)
    data = input_data_from_state(graph)
    context = legacy_context_from_graph(graph, SimpleNamespace(progress_callback=None, cancel_check=None))
    before_inputs = copy.deepcopy((data, {key: value for key, value in context.items() if key != "rag_index"}))
    before_index = rag_index_to_payload(context.get("rag_index"))
    chunks = graph["tool_results"]["rag_index"]["chunks"]
    embedded = [chunk for chunk in chunks if chunk.get("embedding")]

    old_state = ModuleType("_pre_boundary_state_memory")
    old_prompting = ModuleType("agent_runtime._pre_boundary_prompting")
    for module, source_path in ((old_state, "backend/state_memory.py"), (old_prompting, "backend/agent_runtime/prompting.py")):
        source = subprocess.check_output(["git", "show", f"HEAD:{source_path}"], cwd=root, text=True)
        exec(compile(source, source_path, "exec"), module.__dict__)
    old_prompting.state_view_for = old_state.state_view_for
    # Measure pre-guard input so legacy character clipping cannot conceal leakage.
    old_prompting._enforce_prompt_token_budget = lambda prompt, *args, **kwargs: prompt
    monkeypatch.setattr(prompting, "_enforce_prompt_token_budget", lambda prompt, *args, **kwargs: prompt)
    results = []
    for role in (4, 14, 21, 7, 16, 19):
        old = old_prompting.build_prompt(role, data, context)
        new = prompting.build_prompt(role, data, context)
        without_index = copy.deepcopy(context)
        without_index["agent_state"].tool_results.pop("rag_index")
        assert new == prompting.build_prompt(role, data, without_index)
        assert '"rag_index"' not in new and '"embedding"' not in new
        assert new.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
        old_tokens, new_tokens = (estimate_text_tokens(text, response_budget=8192) for text in (old, new))
        assert new_tokens < old_tokens * 0.2
        results.append({"role": role, "before_tokens_with_8192_reserve": old_tokens,
                        "after_tokens_with_8192_reserve": new_tokens, "reduction_pct": round((1 - new_tokens / old_tokens) * 100, 2)})
    assert graph == before_graph
    assert (data, {key: value for key, value in context.items() if key != "rag_index"}) == before_inputs
    assert rag_index_to_payload(context.get("rag_index")) == before_index
    with sqlite3.connect(uri, uri=True) as db:
        after_blob = db.execute("SELECT checkpoint FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?", (thread_id, checkpoint_id)).fetchone()[0]
    assert hashlib.sha256(blob).digest() == hashlib.sha256(after_blob).digest()
    assert before_stat == (path.stat().st_size, path.stat().st_mtime_ns)
    print(json.dumps({"checkpoint_id": checkpoint_id, "chunks": len(chunks), "embedded": len(embedded),
                      "dimensions": sorted({len(chunk["embedding"]) for chunk in embedded}),
                      "checkpoint_unchanged": True, "results": results}, indent=2))
