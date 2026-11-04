"""Complete anonymous responses, request admission and cache provenance."""
from copy import deepcopy
import json
import time

import pytest
from test_shared_provider_cache import memory_cache
from data_fetch.market_sources import tigerair_yes123_transport as t
from search_provider_runtime import SourceResponseError


def parts(body=b'<html>public</html>', status=200, url=t.PAGE):
    return {'process_started': True, 'body': body,
        'headers': f'HTTP/2 {status}\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'.encode(),
        'metadata': json.dumps({'http_code': status, 'url_effective': url,
            'ssl_verify_result': 0, 'proxy_used': 0, 'num_redirects': 0, 'size_download': len(body)}).encode()}


def client(monkeypatch):
    monkeypatch.setattr(t, 'verified_issuer', lambda *a: True)
    return t.TigerairCareersHttp({'isolated': 'transport contract only'})


def test_native_original_and_warm_read_do_not_renew_epoch_or_create_http(monkeypatch):
    c=client(monkeypatch);calls=[]
    def download(self,url,d):
        calls.append(url);return self._consume(url,parts(),0,None,d)
    monkeypatch.setattr(t.TigerairCareersHttp,'_download',download)
    first=c.read(t.PAGE);warm=client(monkeypatch);second=warm.read(t.PAGE)
    assert first==second and calls==[t.PAGE]
    assert c.http_request_count==1 and warm.http_request_count==0
    assert warm.components[0]['cache_hit']is True and warm.components[0]['http_request_sent']is False
    assert t.receipt_body(second,t.PAGE,time.time())==b'<html>public</html>'


@pytest.mark.parametrize('status',[401,402,403,429,503,504])
def test_actual_refusal_is_one_request_and_keeps_status(status,monkeypatch):
    c=client(monkeypatch);d={}
    with pytest.raises(SourceResponseError)as err:c._consume(t.PAGE,parts(status=status),0,None,d)
    assert c.http_request_count==1 and d['http_request_sent']is True and d['http_status']==status
    assert err.value.diagnostic['http_status_observed']is True


def test_unobserved_timeout_keeps_unknown_status_after_a_prior_200(monkeypatch):
    c=client(monkeypatch);c._consume(t.PAGE,parts(),0,None,{})
    p=parts(body=b'');p['headers']=b'';p['metadata']=b'{}';d={}
    with pytest.raises(SourceResponseError)as err:c._consume(t.PAGE,p,28,'timeout',d)
    assert c.http_request_count==1 and d['http_request_sent']is None
    assert d['http_status']is None and err.value.diagnostic['http_status_observed']is False


@pytest.mark.parametrize('field,value',[('ssl_verify_result',1),('ssl_verify_result',False),
    ('proxy_used',1),('proxy_used',False),('num_redirects',1),('num_redirects',False),
    ('url_effective','https://example.com/'),('size_download',999),('size_download',True)])
def test_invalid_native_metadata_cannot_become_a_receipt(field,value,monkeypatch):
    c=client(monkeypatch);p=parts();m=json.loads(p['metadata']);m[field]=value;p['metadata']=json.dumps(m).encode()
    with pytest.raises(SourceResponseError):c._consume(t.PAGE,p,0,None,{})


@pytest.mark.parametrize('target',[t.ARTICLE,t.PROFILE,
    'https://www.yes123.com.tw/wk_index/job.asp?p_id=20140325092151_Y201403028&job_id=20261103084009_11555084'])
def test_unpublished_order_cannot_start_transport(target,monkeypatch):
    c=client(monkeypatch)
    monkeypatch.setattr(t,'shared_fetch',lambda *a,**k:pytest.fail('unpublished action reached cache/transport'))
    with pytest.raises(SourceResponseError):c.read(target)


def test_duplicate_target_and_foreign_url_cannot_be_requested(monkeypatch):
    c=client(monkeypatch)
    monkeypatch.setattr(t.TigerairCareersHttp,'_download',lambda self,u,d:self._consume(u,parts(),0,None,d))
    c.read(t.PAGE)
    with pytest.raises(SourceResponseError):c.read(t.PAGE)
    with pytest.raises(ValueError):c.read('https://example.com/')
    assert c.http_request_count==1


def test_live_legacy_raw_cache_blocks_new_namespace_without_network(monkeypatch):
    import cache_store
    c=client(monkeypatch)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    monkeypatch.setattr(t,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(t,'cooldown_state',lambda *a:None)
    for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(cache_store,'get_cache_json',lambda k:{'fresh_until_epoch':time.time()+60})
    monkeypatch.setattr(t,'collect_capped_process',lambda *a,**k:pytest.fail('legacy cache bypassed'))
    with pytest.raises(SourceResponseError)as err:c._download(t.PAGE,{})
    assert err.value.error_kind=='legacy_raw_cache_still_live'


def test_only_exact_source_scope_can_emit_passive_native_receipts(monkeypatch):
    import provider_correlation as correlation,provider_sla
    c=client(monkeypatch);c.record_provider_sla=True;rows=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda x:rows.extend(deepcopy(x)))
    monkeypatch.setattr(correlation,'current_correlation',lambda:{'ticker':t.TICKER,'fetch_id':'isolated','operation_id':'op'})
    monkeypatch.setattr(correlation,'current_source_identity',lambda:('alternative_data','104 & 1111 job openings'))
    c._consume(t.PAGE,parts(),0,None,{})
    assert len(rows)==1 and rows[0]['record_count']==0 and rows[0]['event_kind']=='http_transport_receipt'
    assert rows[0]['selection_policy']=='transport-receipt-only:v1'
    monkeypatch.setattr(correlation,'current_source_identity',lambda:('other','other'))
    c._consume(t.PAGE,parts(),0,None,{})
    assert len(rows)==1
