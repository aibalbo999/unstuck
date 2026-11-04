"""Offline observations distinguish absent headers from partial HTTP bodies."""
import json
import time
import pytest
from search_provider_runtime import SourceResponseError
from data_fetch.market_sources import gce_conference_transport as csv
from data_fetch.market_sources import official_issuer_master_json as js

URLS = [csv.MASTER_URL, js.URL]


@pytest.mark.parametrize('url', URLS)
@pytest.mark.parametrize('status,rc,kind', [(200,28,'timeout'), (None,28,'timeout'),
                                         (429,0,'rate_limited'), (503,0,'server_error')])
def test_failure_keeps_native_timings_and_actual_status(monkeypatch,url,status,rc,kind):
    module = csv if url == csv.MASTER_URL else js
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in module.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
    failures = []
    monkeypatch.setattr(module, 'remember_failure', lambda key,exc: failures.append(exc))
    body = b'partial' if status == 200 else b''
    meta = {'http_code':status or 0, 'url_effective':url, 'http_version':'2',
            'time_namelookup':0.01, 'time_connect':0.04, 'time_appconnect':0.08,
            'time_starttransfer':0.2 if status else 0, 'time_total':4.99,
            'headers':'secret', 'url':'https://example.com/?secret=1'}
    def collect(args,deadline,**kw):
        assert args[-1] == url and args[args.index('--retry')+1] == '0'
        assert args[args.index('--max-redirs')+1] == '0'
        headers = b'' if status is None else f'HTTP/2 {status}\r\nRetry-After: 90\r\n\r\n'.encode()
        return {'process_started':True, 'body':body,'headers':headers,
                'metadata':json.dumps(meta).encode()},rc,None
    monkeypatch.setattr(module, 'collect_capped_process', collect)
    http = csv.ConferenceHttp(time.monotonic()+25)
    monkeypatch.setattr(http, '_external_guards', lambda *a: None)
    diag = {'url':url, 'cache_hit':False}
    with pytest.raises(SourceResponseError) as caught:
        http.download_original(url,diag)
    assert caught.value.error_kind == kind
    assert caught.value.status_code == status and diag['http_status'] == status
    assert diag['http_status_observed'] is (status is not None)
    obs = diag['transfer_observation']
    assert obs['process_exit_code'] == rc and obs['response_bytes'] == len(body)
    assert obs['time_total'] == 4.99 and obs['http_version'] == '2'
    assert 'secret' not in json.dumps(obs) and 'headers' not in obs
    if status in (429,503):
        assert len(failures) == 1 and caught.value.response.headers['retry-after'] == '90'
    else:
        assert not failures


def test_only_bounded_typed_fields_survive_canonical_details():
    from provider_observation_details import observation_details
    item = {'url':URLS[0], 'request_method':'GET', 'http_request_sent':True,
            'cache_hit':False, 'transfer_observation':{
                'process_exit_code':28, 'response_bytes':7, 'time_total':5.0,
                'time_connect':float('nan'), 'time_appconnect':True,
                'time_starttransfer':-1, 'time_namelookup':10**400,
                'http_version':'2', 'headers':'secret', 'env':{'TOKEN':'secret'}}}
    # Use the public adapter so SQLite event payloads get the same sanitization.
    value = observation_details({'component_statuses':[item]})
    obs = value['component_statuses'][0]['transfer_observation']
    assert obs == {'process_exit_code':28,'response_bytes':7,'time_total':5.0,'http_version':'2'}
    assert 'secret' not in json.dumps(value)
    for change in ({'url':'https://example.com/?secret=1'}, {'url':[]}, {'cache_hit':True},
                   {'http_request_sent':False}, {'request_method':'POST'}):
        value = observation_details({'component_statuses':[{**item,**change}]})
        assert 'transfer_observation' not in value['component_statuses'][0]


@pytest.mark.parametrize('url', URLS)
def test_complete_200_keeps_existing_body_validation_and_observation(monkeypatch,url):
    module = csv if url == csv.MASTER_URL else js
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in module.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
    body = b'[]'  # transport-only; this is not a complete identity master.
    mime = 'text/csv' if url == csv.MASTER_URL else 'application/json'
    meta = {'http_code':200, 'url_effective':url, 'num_redirects':0,
            'size_download':len(body), 'content_type':mime, 'method':'GET',
            'proxy_used':0, 'time_total':0.7, 'http_version':'1.1'}
    parts = {'process_started':True, 'body':body,
             'headers':f'HTTP/1.1 200 OK\r\nContent-Type: {mime}\r\n\r\n'.encode(),
             'metadata':json.dumps(meta).encode()}
    monkeypatch.setattr(module, 'collect_capped_process', lambda *a,**kw:(parts,0,None))
    http = csv.ConferenceHttp(time.monotonic()+25)
    monkeypatch.setattr(http, '_external_guards', lambda *a: None)
    diag = {'url':url}
    value = http.download_original(url,diag)
    assert value['response_metadata']['http_status'] == 200 and diag['http_status_observed'] is True
    assert diag['transfer_observation'] == {
        'time_total':0.7, 'http_version':'1.1', 'process_exit_code':0, 'response_bytes':2}
    # A timing observation cannot make this transport body a qualified master.
    from data_fetch.market_sources import official_issuer_master as master
    with pytest.raises(ValueError):
        (master.validate_csv(body,time.time()) if url == csv.MASTER_URL else js.parse_rows(body,time.time()))
    meta['num_redirects'] = 1
    parts['metadata'] = json.dumps(meta).encode()
    with pytest.raises(SourceResponseError) as exc:
        http.download_original(url,{})
    assert exc.value.error_kind == 'transport_metadata_invalid'


@pytest.mark.parametrize('value', [None, [], 'secret', {'time_total':float('inf')},
                                 {'http_version':'HTTP/2 secret'}, {'process_exit_code':True}])
def test_invalid_observations_do_not_invent_timings_or_store_text(value):
    from official_master_transport_observation import sanitize_observation, observe_transfer
    assert sanitize_observation(value) == {}
    assert observe_transfer(URLS[0], {'process_started':False},None,{}) == {}
    assert observe_transfer('https://example.com', {'process_started':True},0,{}) == {}


def test_killed_child_with_no_metadata_preserves_only_actual_exit_and_bytes():
    from official_master_transport_observation import observe_transfer
    value = observe_transfer(URLS[1], {'process_started':True,'body':b'part'},-9,{})
    assert value == {'process_exit_code':-9,'response_bytes':4}
