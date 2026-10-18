import base64
from hashlib import sha256
import json
import time

import pytest

from test_shared_provider_cache import memory_cache


@pytest.fixture
def network(monkeypatch):
    from data_fetch.market_sources import kgi_careers_transport as transport
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in transport.PROXY_ENV:monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(transport, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(transport, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(transport, 'observe_http_response', lambda *a: None)
    errors=[]
    monkeypatch.setattr(transport, 'remember_failure', lambda key, exc: errors.append(exc.error_kind))
    return transport, errors


def response(argv, status=200, body=b'{"example":true}'):
    return {'body':body,'headers':f'HTTP/2 {status}\r\nContent-Type: application/json\r\n\r\n'.encode(),
            'metadata':json.dumps({'http_code':status,'url_effective':argv[-1],'num_redirects':0}).encode(),
            'process_started':True},0,''


def test_anonymous_request_and_cross_reader_original_epoch(network, monkeypatch):
    t,_=network;calls=[]
    def run(argv,*a,**k):calls.append(argv);return response(argv)
    monkeypatch.setattr(t,'collect_capped_process',run)
    first=t.KgiCareersHttp(time.monotonic()+12);a=first.get_receipt()
    second=t.KgiCareersHttp(time.monotonic()+12);b=second.get_receipt()
    assert a==b and len(calls)==1 and first.http_request_count==1 and second.http_request_count==0
    assert a['method']=='POST' and a['fetched_at_epoch']>0
    assert not any('cookie' in part.lower() or 'authorization' in part.lower() for part in calls[0])
    assert '--retry' in calls[0] and calls[0][calls[0].index('--retry')+1]=='0'


@pytest.mark.parametrize('status', [401,403,429,500,503])
def test_refusal_records_cooldown_and_stops_repeated_request(network,monkeypatch,status):
    t,errors=network;calls=[]
    def run(argv,*a,**k):calls.append(argv);return response(argv,status)
    monkeypatch.setattr(t,'collect_capped_process',run)
    for _ in range(2):
        with pytest.raises(t.SourceResponseError):t.KgiCareersHttp(time.monotonic()+12).get_receipt()
    assert len(calls)==1 and len(errors)==1


def test_expired_deadline_never_starts_transport(network,monkeypatch):
    t,_=network
    monkeypatch.setattr(t,'collect_capped_process',lambda *a,**k:pytest.fail('unexpected request'))
    with pytest.raises(t.SourceResponseError):t.KgiCareersHttp(time.monotonic()-1).get_receipt()


def test_corrupt_cached_body_is_not_used_as_original(network,monkeypatch):
    t,_=network
    monkeypatch.setattr(t,'shared_fetch',lambda *a,**k:({'url':t.API_URL,'method':'POST','request_json':t.REQUEST,
                    'body_b64':base64.b64encode(b'bad').decode(),'sha256':'0'*64},
                    {'fetched_at_epoch':time.time(),'cache_hit':True,'stale':False}))
    with pytest.raises(t.SourceResponseError):t.KgiCareersHttp(time.monotonic()+12).get_receipt()
