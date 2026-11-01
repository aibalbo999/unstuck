"""Exercise actual HTTPX/SDK boundaries with local mock HTTP, never a provider."""
import asyncio
import copy
import gzip
import json
import time
import httpx
import pytest

from quality_campaign_budget import CampaignBudget
from quality_campaign_transport import CampaignTransport, ReplayAbort


IDENTITY = {'campaign_id': 'wire-budget', 'code_sha256': 'a' * 64,
            'source_sha256': 'b' * 64, 'route_sha256': 'c' * 64}
HASHES = {key: value for key, value in IDENTITY.items() if key != 'campaign_id'}
MODEL = 'gemini-test-route'
URL = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'
POLICY = {'billing_status': 'verified_paid', 'billing_identity_sha256': 'd' * 64,
          'reservation_basis_sha256': 'e' * 64, 'maximum_total_tokens': 100,
          'maximum_output_tokens': 10, 'maximum_request_bytes': 10000,
          'maximum_microusd_per_million_tokens': 1000000}


def active(tmp_path, *, limits=None, clock=None):
    ledger = CampaignBudget(tmp_path / 'campaign.sqlite3', IDENTITY, limits=limits, clock=clock)
    ledger.start_stage('S1')
    ledger.start_batch('batch', 'S1')
    ledger.reserve_job('job', 'batch')
    return ledger


def test_http_without_enclosing_reserved_transport_never_reaches_mock_handler(tmp_path):
    calls = []
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: None)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json={}))) as client:
        with pytest.raises(ReplayAbort, match='transport'):
            client.post(URL, json={'contents': []})
    assert calls == []
    assert ledger.snapshot()['spent']['http'] == 0


def result_payload(total=7):
    return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'public answer'}]}}],
            'usageMetadata': {'promptTokenCount': total - 2, 'candidatesTokenCount': 2,
                              'totalTokenCount': total, 'cachedContentTokenCount': 3}}


def send_once(client, model_id):
    return client.post(URL, json={'contents': [{'parts': [{'text': 'frozen source'}]}],
                                 'generationConfig': {'maxOutputTokens': 10}})


def test_http_and_transport_are_separate_but_usage_is_charged_only_once(tmp_path):
    calls = []
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json=result_payload()))) as client:
        assert guard.wrap_sync(send_once)(client, MODEL).status_code == 200
    assert len(calls) == 1
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': 1,
                                         'tokens': 7, 'cost_microusd': 7}


def test_http_limit_is_reserved_before_dispatch_and_persists_on_reopen(tmp_path):
    calls = []
    limits = {'S1': {'http': 0}}
    ledger = active(tmp_path, limits=limits)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json=result_payload()))) as client:
        with pytest.raises(ReplayAbort, match='http budget'):
            guard.wrap_sync(send_once)(client, MODEL)
    assert calls == []
    resumed = CampaignBudget(ledger.path, IDENTITY, limits=limits)
    assert resumed.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': 0,
                                           'tokens': 0, 'cost_microusd': 0}


@pytest.mark.parametrize('change', [
    {'billing_status': 'unknown'}, {'billing_identity_sha256': None},
    {'maximum_total_tokens': 0}, {'maximum_microusd_per_million_tokens': 0},
    {'reservation_basis_sha256': ''},
])
def test_unknown_billing_or_unproven_bounds_block_before_any_dispatch(tmp_path, change):
    calls = []
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY | change}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json=result_payload()))) as client:
        with pytest.raises(ReplayAbort):
            guard.wrap_sync(send_once)(client, MODEL)
    assert calls == []
    assert ledger.snapshot()['spent']['http'] == 0


@pytest.mark.parametrize('mutation', ['no_terminal', 'missing_total', 'invalid_total', 'missing_usage'])
def test_partial_or_unreliable_usage_cannot_release_reservation(tmp_path, mutation):
    payload = result_payload()
    if mutation == 'no_terminal':
        payload['candidates'][0].pop('finishReason')
    elif mutation == 'missing_total':
        payload['usageMetadata'].pop('totalTokenCount')
        payload['usageMetadata'].update(thoughtsTokenCount=4, toolUsePromptTokenCount=6)
    elif mutation == 'invalid_total':
        payload['usageMetadata']['totalTokenCount'] = 1
    else:
        payload.pop('usageMetadata')
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json=payload))) as client:
        guard.wrap_sync(send_once)(client, MODEL)
    assert ledger.snapshot()['spent']['tokens'] == 100
    assert ledger.snapshot()['spent']['cost_microusd'] == 100
    if mutation == 'missing_total':
        http = next(row for row in ledger.snapshot()['attempts'].values() if row['http'])
        assert http['actual_tokens'] == 17  # 5 prompt + 2 output + 4 thought + 6 tool; cached not extra.


def test_request_and_response_bytes_are_not_rewritten_or_duplicated_in_budget_journal(tmp_path):
    ledger = active(tmp_path)
    payload = result_payload()
    response_raw = json.dumps(payload, separators=(',', ':')).encode()
    requests = []
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            requests.append(request.content) or httpx.Response(200, content=response_raw))) as client:
        response = guard.wrap_sync(send_once)(client, MODEL)
    assert response.content == response_raw
    assert json.loads(requests[0])['contents'][0]['parts'][0]['text'] == 'frozen source'
    journal = guard.evidence.path.read_text()
    assert 'public answer' not in journal and 'frozen source' not in journal
    assert 'request_sha256' in journal and 'usage_observation' in journal


def test_every_inner_retry_http_is_charged_without_double_charging_transport(tmp_path):
    ledger = active(tmp_path)
    calls = []
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={}) if len(calls) == 1 else httpx.Response(200, json=result_payload())
    def retrying(client, model_id):
        send_once(client, model_id)
        return send_once(client, model_id)
    with guard, httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert guard.wrap_sync(retrying)(client, MODEL).status_code == 200
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': 2,
                                         'tokens': 107, 'cost_microusd': 107}


def test_stream_interruption_retains_partial_usage_and_reservation(tmp_path):
    ledger = active(tmp_path)
    payload = result_payload()
    payload['candidates'][0].pop('finishReason')
    class Interrupted(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield ('data: ' + json.dumps(payload) + '\n\n').encode()
            raise asyncio.CancelledError()
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    async def original(client, model_id):
        request = client.build_request('POST', URL, json={'contents': [], 'generationConfig': {'maxOutputTokens': 10}})
        response = await client.send(request, stream=True)
        try:
            async for data in response.aiter_bytes():
                pass
        finally:
            await response.aclose()
    async def run():
        with guard:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                    httpx.Response(200, stream=Interrupted(), headers={'content-type': 'text/event-stream'}))) as client:
                with pytest.raises(asyncio.CancelledError):
                    await guard.wrap_async(original)(client, MODEL)
    asyncio.run(run())
    assert ledger.snapshot()['spent']['tokens'] == 100
    http = next(row for row in ledger.snapshot()['attempts'].values() if row['http'])
    assert http['actual_tokens'] == 7 and http['final_tokens'] is False


def test_explicit_usage_overrun_stops_later_calls_but_preserves_true_usage(tmp_path):
    ledger = active(tmp_path)
    calls = []
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json=result_payload(101)))) as client:
        with pytest.raises(ReplayAbort, match='exceeded'):
            guard.wrap_sync(send_once)(client, MODEL)
        with pytest.raises(ReplayAbort, match='exceeded'):
            guard.wrap_sync(send_once)(client, MODEL)
    assert len(calls) == 1
    assert ledger.snapshot()['spent']['tokens'] == 101


@pytest.mark.parametrize('drift', ['deadline', 'source'])
def test_reservation_fsync_drift_blocks_dispatch_without_refund(tmp_path, monkeypatch, drift):
    now = [1000.0]
    frozen = [HASHES]
    ledger = active(tmp_path, clock=lambda: now[0])
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: frozen[0])
    calls = []
    record = guard.evidence.record
    def record_and_drift(row):
        receipt = record(row)
        if row['type'] == 'http_reserved':
            if drift == 'deadline':
                now[0] += 3601
            else:
                frozen[0] = HASHES | {'source_sha256': 'f' * 64}
        return receipt
    monkeypatch.setattr(guard.evidence, 'record', record_and_drift)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json=result_payload()))) as client:
        with pytest.raises(ReplayAbort):
            guard.wrap_sync(send_once)(client, MODEL)
    assert calls == []
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': 1,
                                         'tokens': 100, 'cost_microusd': 100}


@pytest.mark.parametrize('body', [
    b'{"generationConfig":{"maxOutputTokens":10},"contents":[],"contents":[]}',
    b'{"generationConfig":{"maxOutputTokens":10},"contents":[{"parts":[{"text":"s\\u0065cret-value"}]}]}',
    b'{"generationConfig":{"maxOutputTokens":10},"contents":[{"parts":[{"fileData":{"fileUri":"https://example.com"}}]}]}',
    b'{"generationConfig":{"maxOutputTokens":10},"tools":[{"googleSearch":{}}]}',
])
def test_ambiguous_secret_or_external_input_rejected_without_http(tmp_path, body):
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES, secrets=('secret-value',))
    calls = []
    def sending(client, model_id):
        return client.post(URL, content=body)
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            calls.append(request) or httpx.Response(200, json={}))) as client:
        with pytest.raises(ReplayAbort):
            guard.wrap_sync(sending)(client, MODEL)
    assert not calls and ledger.snapshot()['spent']['http'] == 0


def test_redirect_is_not_followed_even_when_client_enabled_it(tmp_path):
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    calls = []
    with guard, httpx.Client(follow_redirects=True, transport=httpx.MockTransport(lambda request:
            calls.append(str(request.url)) or httpx.Response(307, headers={'location': URL}))) as client:
        assert guard.wrap_sync(send_once)(client, MODEL).status_code == 307
    assert calls == [URL]
    assert ledger.snapshot()['spent']['http'] == 1
    assert ledger.snapshot()['spent']['tokens'] == 100


def test_http_hooks_restored_after_unretryable_abort(tmp_path):
    sync, asynchronous = httpx.Client.send, httpx.AsyncClient.send
    ledger = active(tmp_path)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: {})
    with pytest.raises(ReplayAbort):
        with guard:
            guard.wrap_sync(send_once)(None, MODEL)
    assert httpx.Client.send is sync and httpx.AsyncClient.send is asynchronous


@pytest.mark.parametrize('compressed', [False, True])
def test_real_google_sdk_stream_uses_the_same_http_ledger(tmp_path, monkeypatch, compressed):
    from google import genai
    from google.genai import types, _api_client
    import llm_transport
    ledger = active(tmp_path)
    payload = result_payload()
    requests = []
    def handler(request):
        requests.append(request.content)
        raw = ('data: ' + json.dumps(payload) + '\n\n').encode()
        headers = {'content-type': 'text/event-stream'}
        if compressed:
            raw = gzip.compress(raw)
            headers['content-encoding'] = 'gzip'
        return httpx.Response(200, stream=httpx.ByteStream(raw), headers=headers)
    client = genai.Client(api_key='isolated-dummy-key', http_options=types.HttpOptions(
        client_args={'transport': httpx.MockTransport(handler), 'trust_env': False},
        async_client_args={'transport': httpx.MockTransport(handler), 'trust_env': False}))
    monkeypatch.setattr(_api_client.BaseApiClient, '_use_aiohttp', lambda self: False)
    monkeypatch.setattr(llm_transport, '_get_client', lambda key: client)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES, secrets=('isolated-dummy-key',))
    async def run():
        try:
            with guard:
                return await guard.wrap_async(llm_transport.generate_content_stream_async)(
                    'isolated-dummy-key', MODEL, 'frozen source', types.GenerateContentConfig(max_output_tokens=10))
        finally:
            await client.aio.aclose()
            client.close()
    response = asyncio.run(run())
    assert response.text == 'public answer'
    assert len(requests) == 1
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': 1,
                                         'tokens': 7, 'cost_microusd': 7}
    assert 'isolated-dummy-key' not in guard.evidence.path.read_text()


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('scenario', ['retry', 'afc', 'retry_budget_stop'])
def test_real_sdk_retry_and_afc_each_reserve_a_physical_http(tmp_path, monkeypatch, asynchronous, scenario):
    from google import genai
    from google.genai import types, _api_client
    ledger = active(tmp_path, limits={'S1': {'http': 1}} if scenario == 'retry_budget_stop' else None)
    requests, tool_calls = [], []
    def frozen_lookup() -> str:
        """Read the already frozen local test fact without external fetches."""
        tool_calls.append(True)
        return 'frozen local fact'
    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1 and scenario.startswith('retry'):
            return httpx.Response(503, json={'error': {'code': 503, 'status': 'UNAVAILABLE', 'message': 'synthetic'}})
        payload = result_payload()
        if len(requests) == 1 and scenario == 'afc':
            payload['candidates'][0]['content'] = {'role': 'model', 'parts': [
                {'functionCall': {'name': 'frozen_lookup', 'args': {}}}]}
        return httpx.Response(200, json=payload)
    client = genai.Client(api_key='isolated-dummy-key', http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=3, initial_delay=0.001, max_delay=0.001, jitter=0),
        client_args={'transport': httpx.MockTransport(handler), 'trust_env': False},
        async_client_args={'transport': httpx.MockTransport(handler), 'trust_env': False}))
    monkeypatch.setattr(_api_client.BaseApiClient, '_use_aiohttp', lambda self: False)
    config = types.GenerateContentConfig(max_output_tokens=10, tools=[frozen_lookup] if scenario == 'afc' else None)
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES, secrets=('isolated-dummy-key',))
    def original(key, model_id):
        return client.models.generate_content(model=model_id, contents='frozen source', config=config)
    async def original_async(key, model_id):
        return await client.aio.models.generate_content(model=model_id, contents='frozen source', config=config)
    async def run():
        try:
            with guard:
                if scenario == 'retry_budget_stop':
                    with pytest.raises(ReplayAbort, match='http budget'):
                        if asynchronous:
                            await guard.wrap_async(original_async)('isolated-dummy-key', MODEL)
                        else:
                            guard.wrap_sync(original)('isolated-dummy-key', MODEL)
                    return None
                if asynchronous:
                    return await guard.wrap_async(original_async)('isolated-dummy-key', MODEL)
                return guard.wrap_sync(original)('isolated-dummy-key', MODEL)
        finally:
            await client.aio.aclose()
            client.close()
    response = asyncio.run(run())
    if scenario == 'retry_budget_stop':
        assert len(requests) == 1
        expected_tokens = 100
    else:
        assert response.text == 'public answer' and len(requests) == 2
        expected_tokens = 14 if scenario == 'afc' else 107
    assert ledger.snapshot()['spent'] == {'jobs': 1, 'transport': 1, 'http': len(requests),
        'tokens': expected_tokens, 'cost_microusd': expected_tokens}
    if scenario == 'afc':
        assert tool_calls == [True]
        assert any('functionResponse' in part for content in requests[1]['contents'] for part in content['parts'])
    assert 'isolated-dummy-key' not in guard.evidence.path.read_text()


def test_many_stream_chunks_do_not_replay_the_shared_ledger_for_every_chunk(tmp_path, monkeypatch):
    now = [1000.0]
    ledger = active(tmp_path, clock=lambda: now[0])
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    monkeypatch.setattr(time, 'monotonic', lambda: 10.0)
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            before = len(ledger.events())
            for _ in range(100):
                yield b': keepalive\n'
            assert len(ledger.events()) - before <= 1, 'Pure stream chunks must not write 100 full-state checks in one instant'
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, stream=Stream(), headers={'content-type': 'text/event-stream'}))) as client:
        guard.wrap_sync(send_once)(client, MODEL)
    assert ledger.snapshot()['spent']['tokens'] == 100


@pytest.mark.parametrize('failure', ['wall_deadline', 'wall_rollback', 'monotonic_deadline', 'external_block'])
def test_chunk_checks_keep_immediate_local_time_and_bounded_external_stop(tmp_path, monkeypatch, failure):
    wall, monotonic = [1000.0], [10.0]
    ledger = active(tmp_path, clock=lambda: wall[0])
    guard = CampaignTransport(ledger, 'job', {MODEL: POLICY}, actual_hashes=HASHES,
                              verify_frozen=lambda: HASHES)
    monkeypatch.setattr(time, 'monotonic', lambda: monotonic[0])
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b': initial\n'
            if failure == 'wall_deadline':
                wall[0] += 2401
            elif failure == 'wall_rollback':
                wall[0] -= 1
            elif failure == 'monotonic_deadline':
                monotonic[0] += 2401
            else:
                other = CampaignBudget(ledger.path, IDENTITY, clock=lambda: wall[0])
                attempt = next(row for row in other.snapshot()['attempts'].values() if row['http'])
                other.settle_attempt(attempt['attempt_id'], actual_tokens=101, usage_evidence_sha256='f' * 64)
                monotonic[0] += 0.251
            yield b': must not reach sdk\n'
            pytest.fail('A stop was ignored beyond the permitted check interval')
    with guard, httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, stream=Stream(), headers={'content-type': 'text/event-stream'}))) as client:
        with pytest.raises(ReplayAbort):
            guard.wrap_sync(send_once)(client, MODEL)
    assert ledger.snapshot()['spent']['http'] == 1
    assert ledger.snapshot()['spent']['tokens'] == (101 if failure == 'external_block' else 100)
