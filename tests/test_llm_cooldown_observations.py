import json

import pytest
import config
import llm_congestion as guard
from llm_congestion_store import CongestionStore
from llm_observation_context import attempt_scope


def test_cooldown_identity_links_trigger_block_and_recovery_without_policy_change(monkeypatch):
    now,events=[1000.0],[]
    monkeypatch.setattr(config,'LLM_CONGESTION_GUARD_ENABLED',True)
    monkeypatch.setattr(guard,'_store',CongestionStore(clock=lambda:now[0],jitter=lambda:0))
    monkeypatch.setattr('api_usage_store.record_api_usage',lambda **event:events.append(event))
    class Busy(RuntimeError):status_code=503
    with attempt_scope('gemini-fixture','analysis'):
        with pytest.raises(Busy):
            with guard.provider_attempt_scope('gemini-fixture','secret'):
                raise Busy('private-error')
    opened=events[-1]['metadata']
    assert opened['cooldown_id']
    assert opened['guard_scope']=='model'
    assert opened['attempt_id']!=opened['guard_attempt_id']
    assert guard.congestion_wait('gemini-fixture')==60
    fields=guard.current_cooldown_fields('gemini-fixture')
    assert fields['cooldown_id']==opened['cooldown_id']
    now[0]+=61
    with guard.provider_attempt_scope('gemini-fixture','other-secret'):pass
    recovered=events[-1]['metadata']
    assert recovered['transition']=='recovered'
    assert recovered['cooldown_id']==opened['cooldown_id']
    assert recovered['cooldown_elapsed_seconds']==61
    assert guard.congestion_wait('gemini-fixture')==0
    assert 'secret' not in json.dumps(events)
