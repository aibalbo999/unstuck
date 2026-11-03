"""A complete native response and a qualified public issuer result are distinct."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json,time

import pytest

from test_railway_peer_sources import isolated,native_boundary,body


def test_gateway_replays_all_qualified_originals_without_new_requests_or_nonce_exposure(monkeypatch):
    from data_fetch.market_sources.jpx_company_transport import JpxCompanyGateway,verify_bundle
    from runtime_paths import current_runtime_paths
    calls=native_boundary(monkeypatch);gateway=JpxCompanyGateway(time.monotonic()+20)
    first=gateway.get('90200',details=True)
    assert first['listing']['legal_name']=='East Japan Railway Company'
    assert len(calls)==3 and gateway.http_request_count==3
    stamps=[p['retrieved_at']for p in first['originals']]
    assert all(p['response_complete']is True for p in first['originals'])
    assert 'jsessionid='not in json.dumps(first)and'cookies.txt'not in json.dumps(first)
    second=gateway.get('90200',details=True)
    assert second==first and len(calls)==3 and gateway.http_request_count==3
    assert [p['retrieved_at']for p in second['originals']]==stamps
    assert verify_bundle(second,'90200',details=True)==first
    assert not list((current_runtime_paths().cache_dir/'tmp').glob('jpx-anonymous-*'))


@pytest.mark.parametrize('change',['search_form','code','hidden_name','market','industry','year_end','alert','duplicate','headers'])
def test_http200_without_consistent_current_listing_is_rejected(change):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.jpx_company_schema import parse_listing
    raw=body('search9022.html')
    if change=='search_form':raw=body('search-reset.html')
    elif change=='code':raw=raw.replace(b'90220',b'90230')
    elif change=='market':raw=raw.replace(b'Prime',b'Standard')
    elif change=='year_end':raw=raw.replace(b'March',b'NotAMonth')
    elif change=='headers':raw=raw.replace(b'Issue name',b'Other label')
    else:
        soup=BeautifulSoup(raw,'html.parser');row=soup.find('input',attrs={'name':'ccJjCrpSelKekkLst_st[0].eqMgrCd'}).find_parent('tr')
        if change=='hidden_name':row.find('input',attrs={'name':'ccJjCrpSelKekkLst_st[0].eqMgrNm'})['value']='Another Company'
        elif change=='industry':row.find('input',attrs={'name':'ccJjCrpSelKekkLst_st[0].gyshDspNm'})['value']='Another Industry'
        elif change=='alert':row.find_all('td',recursive=False)[5].append('Unverified listing alert')
        elif change=='duplicate':row.parent.append(deepcopy(row))
        raw=str(soup).encode()
    with pytest.raises(ValueError):parse_listing(raw,'90220')


@pytest.mark.parametrize('change',['expired','future','digest','request_binding','method','complete','wrong_company','canonical_url'])
def test_retained_or_tampered_original_cannot_validate_gateway_identity(monkeypatch,change):
    from data_fetch.market_sources.jpx_company_transport import JpxCompanyGateway,verify_bundle
    native_boundary(monkeypatch);value=JpxCompanyGateway(time.monotonic()+20).get('90200',details=True);value=deepcopy(value)
    proof=value['originals'][1]
    if change=='expired':proof['retrieved_at']=time.time()-1801
    elif change=='future':proof['retrieved_at']=time.time()+1
    elif change=='digest':proof['raw_response_sha256']='0'*64
    elif change=='request_binding':proof['request_body_sha256']='0'*64
    elif change=='method':proof['request_method']='GET'
    elif change=='complete':proof['response_complete']=False
    elif change=='wrong_company':value['listing']['legal_name']='Another Company'
    elif change=='canonical_url':proof['source_url']='https://example.com/search'
    with pytest.raises((ValueError,OSError)):verify_bundle(value,'90200',details=True)


@pytest.mark.parametrize('status,kind',[(401,'authentication'),(403,'access_denied'),(429,'rate_limited'),(504,'server_error')])
def test_native_failure_is_retained_and_does_not_automatically_resubmit(monkeypatch,status,kind):
    from data_fetch.market_sources import jpx_company_transport as module
    from search_provider_runtime import SourceResponseError
    calls=native_boundary(monkeypatch);mock=module._run_curl
    def fail_post(argv,*a,**kw):
        parts,rc,error=mock(argv,*a,**kw)
        if '--data-raw'in argv:
            parts['headers']=('HTTP/2 '+str(status)+'\r\nContent-Type: text/html\r\n\r\n').encode();meta=json.loads(parts['metadata']);meta['http_code']=status;parts['metadata']=json.dumps(meta).encode()
        return parts,rc,error
    monkeypatch.setattr(module,'_run_curl',fail_post);gateway=module.JpxCompanyGateway(time.monotonic()+20)
    with pytest.raises(SourceResponseError)as e:gateway.get('90200')
    assert e.value.error_kind==kind and gateway.components[-1]['http_status']==status
    assert len(calls)==2
    with pytest.raises(SourceResponseError):gateway.get('90200')
    assert len(calls)==2


@pytest.mark.parametrize('change',['redirect','download_size','mime','partial_timeout'])
def test_incomplete_or_unqualified_native_transport_never_becomes_an_original(monkeypatch,change):
    from data_fetch.market_sources import jpx_company_transport as module
    from search_provider_runtime import SourceResponseError
    native_boundary(monkeypatch);mock=module._run_curl
    def mutate(argv,*a,**kw):
        parts,rc,error=mock(argv,*a,**kw);meta=json.loads(parts['metadata'])
        if change=='redirect':meta['num_redirects']=1
        elif change=='download_size':meta['size_download']+=1
        elif change=='mime':parts['headers']=b'HTTP/2 200\r\nContent-Type: application/pdf\r\n\r\n'
        elif change=='partial_timeout':rc=28
        parts['metadata']=json.dumps(meta).encode();return parts,rc,error
    monkeypatch.setattr(module,'_run_curl',mutate)
    gateway=module.JpxCompanyGateway(time.monotonic()+20)
    with pytest.raises(SourceResponseError):gateway.get('90200')
    assert len(gateway.components)==1 and'original_receipt'not in gateway.components[0]


def test_bad_declared_form_action_is_rejected_before_any_cross_host_post():
    from data_fetch.market_sources.jpx_company_schema import search_form
    raw=body('entry.html')
    url,fields=search_form(raw,'90200')
    assert len(url.split('jsessionid=')[1])==33 and fields['eqMgrCd']=='90200'
    wrong=raw.replace(b'/tseHpFront/JJK020010Action.do;',b'https://example.com/JJK020010Action.do;')
    with pytest.raises(ValueError):search_form(wrong,'90200')


def test_unavailable_admission_storage_stops_before_native_io(monkeypatch):
    from data_fetch.market_sources.jpx_company_transport import JpxCompanyGateway
    import cache_store
    calls=native_boundary(monkeypatch)
    def unavailable(*a,**k):raise OSError('isolated store unavailable')
    monkeypatch.setattr(cache_store,'set_cache_json',unavailable)
    with pytest.raises(OSError):JpxCompanyGateway(time.monotonic()+20).get('90200')
    assert calls==[]
