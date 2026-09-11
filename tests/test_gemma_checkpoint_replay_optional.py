"""Opt-in replay: copy the checkpoint first; never execute its workflow."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest


@pytest.mark.skipif(not os.getenv('PROMPT_REPLAY_CHECKPOINT_DB'), reason='requires an explicit offline checkpoint copy')
def test_gemma_saved_macro_prompt_admission():
    from agent_runtime.prompting import build_prompt
    from agent_runtime.generation_config import estimate_agent_input_tokens
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from workflow_context import input_data_from_state, legacy_context_from_graph
    from workflow_state import rag_index_to_payload

    path = Path(os.environ['PROMPT_REPLAY_CHECKPOINT_DB']).resolve()
    assert not Path(str(path) + '-wal').exists()
    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        row = db.execute('select type,checkpoint from checkpoints where thread_id=? order by checkpoint_id desc limit 1',
                         (os.environ['PROMPT_REPLAY_THREAD_ID'],)).fetchone()
    graph = JsonPlusSerializer().loads_typed(row)['channel_values']
    graph_before = copy.deepcopy(graph)
    data = input_data_from_state(graph)
    context = legacy_context_from_graph(graph, SimpleNamespace(progress_callback=None, cancel_check=None))
    context['_primary_probe_prompt'] = True
    data_before = copy.deepcopy(data)
    state_before = copy.deepcopy(context['agent_state'])
    rag_before = copy.deepcopy(rag_index_to_payload(context.get('rag_index')))
    old = build_prompt(11, data, context)
    new = build_prompt(11, data, {**context, '_prompt_model_id': 'gemma-4-31b-it'})
    before, after = [estimate_agent_input_tokens(11, 'gemma-4-31b-it',text) for text in (old,new)]
    assert before > 12000
    assert after <= 12000
    assert data == data_before and context['agent_state'] == state_before
    assert rag_index_to_payload(context.get('rag_index')) == rag_before
    assert graph == graph_before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
    print(json.dumps({'before_input_tokens': before, 'after_input_tokens': after, 'checkpoint_unchanged': True}))
