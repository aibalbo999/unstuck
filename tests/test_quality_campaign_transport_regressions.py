"""No-network HTTPX/Google SDK adversarial checks of actual wire boundaries."""
import json
import asyncio


import httpx
import pytest

from quality_campaign_budget import CampaignBudget
from quality_campaign_transport import CampaignTransport, ReplayAbort

MODEL='gemini-test-route'
URL=f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'
HASHES={'code_sha256':'a'*64,'source_sha256':'b'*64,'route_sha256':'c'*64}
POLICY={'billing_status':'verified_paid','billing_identity_sha256':'d'*64,
        'reservation_basis_sha256':'e'*64,'maximum_total_tokens':100,
        'maximum_output_tokens':10,'maximum_request_bytes':10000,
        'maximum_microusd_per_million_tokens':1000000}
BODY={'contents':[{'parts':[{'text':'frozen input'}]}],
      'generationConfig':{'maxOutputTokens':10}}


def setup(tmp_path, secrets=()):
    ledger=CampaignBudget(tmp_path/'campaign.sqlite3',{'campaign_id':'independent-wire',**HASHES})
    ledger.start_stage('S1'); ledger.start_batch('batch','S1'); ledger.reserve_job('job','batch')
    guard=CampaignTransport(ledger,'job',{MODEL:POLICY},actual_hashes=HASHES,
                            verify_frozen=lambda:HASHES,secrets=secrets)
    return ledger,guard


def send(client, model_id):
    return client.post(URL,json=BODY)


@pytest.mark.parametrize('invalid_usage',[
    {'promptTokenCount':-1,'candidatesTokenCount':2,'totalTokenCount':7},
    {'promptTokenCount':'invalid','candidatesTokenCount':2,'totalTokenCount':7},
    {'promptTokenCount':True,'candidatesTokenCount':2,'totalTokenCount':7},
])
def test_malformed_explicit_usage_never_releases_reservation(tmp_path,invalid_usage):
    ledger,guard=setup(tmp_path)
    payload={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'answer'}]}}],
             'usageMetadata':invalid_usage}
    with guard,httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))) as client:
        try:
            guard.wrap_sync(send)(client,MODEL)
        except ReplayAbort:
            pass
    assert ledger.snapshot()['spent']['tokens']==100
    assert ledger.snapshot()['spent']['cost_microusd']==100


def test_unknown_finish_reason_is_not_a_trusted_terminal_receipt(tmp_path):
    ledger,guard=setup(tmp_path)
    payload={'candidates':[{'finishReason':'UNRECOGNIZED_REASON','content':{'parts':[{'text':'answer'}]}}],
             'usageMetadata':{'promptTokenCount':5,'candidatesTokenCount':2,'totalTokenCount':7}}
    with guard,httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))) as client:
        try:
            guard.wrap_sync(send)(client,MODEL)
        except ReplayAbort:
            pass
    assert ledger.snapshot()['spent']['tokens']==100


def test_sdk_function_response_inline_modality_is_blocked_before_http(tmp_path):
    from google import genai
    from google.genai import types
    ledger,guard=setup(tmp_path)
    dispatched=[]
    def handler(request):
        dispatched.append(request.content)
        return httpx.Response(200,json={})
    client=genai.Client(api_key='independent-dummy-key',http_options=types.HttpOptions(
        client_args={'transport':httpx.MockTransport(handler),'trust_env':False}))
    content=types.Content(role='tool',parts=[types.Part(function_response=types.FunctionResponse(
        name='frozen_lookup',response={'result':'image'},parts=[
            types.FunctionResponsePart.from_bytes(data=b'not-frozen-image',mime_type='image/png')]))])
    def original(client,model_id):
        return client.models.generate_content(model=model_id,contents=[content],
            config=types.GenerateContentConfig(max_output_tokens=10))
    try:
        with guard:
            try:
                guard.wrap_sync(original)(client,MODEL)
            except ReplayAbort:
                pass
    finally:
        client.close()
    assert not dispatched, 'Supported SDK functionResponse.parts.inlineData bypassed the modality guard'


def test_httpx_authentication_roundtrip_has_separate_physical_reservations(tmp_path):
    ledger,guard=setup(tmp_path)
    calls=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(401,headers={'www-authenticate':'Digest realm="fixture", nonce="abc", algorithm=MD5, qop="auth"'})
        return httpx.Response(200,json={})
    with guard,httpx.Client(auth=httpx.DigestAuth('fixture-user','fixture-password'),
            transport=httpx.MockTransport(handler)) as client:
        try:
            guard.wrap_sync(send)(client,MODEL)
        except ReplayAbort:
            pass
    assert len(calls)==ledger.snapshot()['spent']['http'], 'An internal HTTPX auth resend was not reserved'


def test_httpx_request_hook_cannot_add_secret_after_preflight_check(tmp_path):
    secret='independent-secret-never-send'
    ledger,guard=setup(tmp_path,secrets=(secret,))
    calls=[]
    def mutate(request):
        request._content=json.dumps(BODY | {'systemInstruction':{'parts':[{'text':secret}]}}).encode()
        request.stream=httpx.ByteStream(request._content)
        request.headers['content-length']=str(len(request._content))
    with guard,httpx.Client(event_hooks={'request':[mutate]},transport=httpx.MockTransport(
            lambda request:calls.append(request) or httpx.Response(200,json={}))) as client:
        try:
            guard.wrap_sync(send)(client,MODEL)
        except ReplayAbort:
            pass
    assert not calls, 'HTTPX request hook mutated the dispatched body after the credential check'


def test_cached_count_greater_than_prompt_is_not_a_trusted_final_receipt(tmp_path):
    ledger,guard=setup(tmp_path)
    payload={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'answer'}]}}],
             'usageMetadata':{'promptTokenCount':5,'cachedContentTokenCount':6,
                              'candidatesTokenCount':2,'totalTokenCount':7}}
    with guard,httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))) as client:
        try:
            guard.wrap_sync(send)(client,MODEL)
        except ReplayAbort:
            pass
    assert ledger.snapshot()['spent']['tokens']==100


def test_decreasing_cumulative_stream_usage_stops_without_releasing_reservation(tmp_path):
    ledger,guard=setup(tmp_path)
    first={'candidates':[{'content':{'parts':[{'text':'part'}]}}],
           'usageMetadata':{'promptTokenCount':5,'candidatesTokenCount':2,'totalTokenCount':7}}
    last={'candidates':[{'finishReason':'STOP'}],
          'usageMetadata':{'promptTokenCount':2,'candidatesTokenCount':2,'totalTokenCount':4}}
    wire=b''.join(('data: '+json.dumps(row)+'\n\n').encode() for row in [first,last])
    with guard,httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200,content=wire,headers={'content-type':'text/event-stream'}))) as client:
        with pytest.raises(ReplayAbort):
            guard.wrap_sync(send)(client,MODEL)
    assert ledger.snapshot()['spent']['tokens']==100
    attempt=next(row for row in ledger.snapshot()['attempts'].values() if row['http'])
    assert attempt['actual_tokens']==7 and attempt['final_tokens'] is False


def test_sync_physical_response_is_closed_when_wire_setup_aborts(tmp_path):
    ledger,guard=setup(tmp_path)
    closed=[]
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'wire'
        def close(self):
            closed.append(True)
    with guard,httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200,stream=Stream(),headers={'content-encoding':'unsupported-fixture'}))) as client:
        with pytest.raises(ReplayAbort,match='Unsupported HTTP content encoding'):
            guard.wrap_sync(send)(client,MODEL)
    assert closed==[True], 'Physical response leaked when receive() aborted before returning to HTTPX'
    assert ledger.snapshot()['spent']['tokens']==100


def test_async_physical_response_is_closed_when_wire_setup_aborts(tmp_path):
    ledger,guard=setup(tmp_path)
    closed=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'wire'
        async def aclose(self):
            closed.append(True)
    async def original(client,model_id):
        return await client.post(URL,json=BODY)
    async def run():
        with guard:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                    httpx.Response(200,stream=Stream(),headers={'content-encoding':'unsupported-fixture'}))) as client:
                with pytest.raises(ReplayAbort,match='Unsupported HTTP content encoding'):
                    await guard.wrap_async(original)(client,MODEL)
    asyncio.run(run())
    assert closed==[True], 'Async physical response leaked when receive() aborted before returning to HTTPX'
    assert ledger.snapshot()['spent']['tokens']==100
