"""Regression for the real legacy timeout test's process-global fixture ownership."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('body_fails', [False, True])
@pytest.mark.parametrize('checked_state', ['clients', 'timeout', 'sdk_module'])
def test_timeout_fixture_restores_existing_transport_state(monkeypatch, body_fails, checked_state):
    import llm_client
    import llm_transport
    from test_architecture_services import test_genai_client_receives_request_timeout as timeout_case

    closed = []
    foreign = SimpleNamespace(close=lambda: closed.append('foreign client closed'))
    previous_cache = {'unrelated-offline-owner': foreign}
    previous_sdk = SimpleNamespace(Client=None)
    monkeypatch.setattr(llm_transport, '_client_cache', previous_cache)
    monkeypatch.setattr(llm_transport, 'genai', previous_sdk)
    monkeypatch.setattr(llm_transport, 'LLM_AGENT_CALL_TIMEOUT_SECONDS', 37.25)
    original_call = llm_client.generate_content
    primary = RuntimeError('failure after owned fake SDK client was created')
    if body_fails:
        def failed_call(*args, **kwargs):
            original_call(*args, **kwargs)
            raise primary
        monkeypatch.setattr(llm_client, 'generate_content', failed_call)

    def invoke_actual_timeout_test():
        # This is the same MonkeyPatch teardown used by pytest, not a rewritten
        # imitation of the original timeout/cache sequence.
        with pytest.MonkeyPatch.context() as owned:
            timeout_case(owned)
    if body_fails:
        with pytest.raises(RuntimeError) as caught:
            invoke_actual_timeout_test()
        assert caught.value is primary
    else:
        invoke_actual_timeout_test()

    if checked_state == 'clients':
        assert llm_transport._client_cache is previous_cache
        assert previous_cache == {'unrelated-offline-owner': foreign}
        assert closed == []
    elif checked_state == 'timeout':
        assert llm_transport.LLM_AGENT_CALL_TIMEOUT_SECONDS == 37.25
    else:
        assert llm_transport.genai is previous_sdk
