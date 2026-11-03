"""Complete saved mixed-scope indices qualify only a failed C-history gap."""
from pathlib import Path
from copy import deepcopy
import pytest
import time
from contextlib import contextmanager
from hashlib import sha256
from datetime import datetime
from test_public_annual_gap_cache import isolated_cache_and_provider

F=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261103/mixed-annual-gap'

@pytest.mark.parametrize('issuer,years,other',[('6994',[2023,2024,2025],[2022]),('7711',[2024,2025],[2023])])
def test_real_complete_mixed_index_preserves_both_scopes_without_joining_them(issuer,years,other):
    from data_fetch.market_sources.annual_filing_index_gap import confirmed_short_annual_index,validate_short_annual_index_proof
    raw=(F/(issuer+'-index.html')).read_bytes()
    proof=confirmed_short_annual_index(raw,issuer)
    assert proof is not None
    assert proof['available_consolidated_annual_years']==years
    assert proof['other_annual_filing_years']=={'A':other}
    assert set(proof['filing_urls_by_year'])=={str(y)for y in years}
    assert validate_short_annual_index_proof(proof,issuer,proof['message'])
    wrong=deepcopy(proof);wrong['available_consolidated_annual_years']=sorted(years+other)
    assert not validate_short_annual_index_proof(wrong,issuer,proof['message'])

@pytest.mark.parametrize('damage',['scope','preview_scope','issuer','truncated','extra_query','duplicate'])
def test_mixed_scope_proof_rejects_mismatched_or_incomplete_originals(damage):
    from data_fetch.market_sources.annual_filing_index_gap import confirmed_short_annual_index
    raw=(F/'6994-index.html').read_bytes();text=raw.decode()
    if damage=='scope':text=text.replace('<td>個別</td>','<td>合併</td>',1)
    elif damage=='preview_scope':text=text.replace('ci-ir-6994','ci-cr-6994',1)
    elif damage=='issuer':text=text.replace('co_id=6994','co_id=2330',1)
    elif damage=='truncated':text=text[:4000]
    elif damage=='extra_query':text=text.replace('report_id=A','report_id=A&unexpected=',1)
    else:
        start=text.index('<tr class=');end=text.index('</tr>',start)+5
        text=text[:end]+text[start:end]+text[end:]
    assert confirmed_short_annual_index(text.encode(),'6994')is None

@pytest.mark.parametrize('issuer',['6994','7711'])
def test_mixed_short_index_cache_keeps_failure_and_original_lifetime_without_http(issuer):
    from data_fetch.market_sources import mops_public_gap_cache as cache
    from data_fetch.market_sources.mops_public_annual import fetch_public_financial_result,INDEX_URL
    from official_response_evidence import archive_response
    from provider_correlation import correlation_scope
    from provider_acquisition import observation_kind
    from provider_observation_details import observation_details
    class Captured:
        def __init__(self):
            self.deadline=time.monotonic()+45;self.components=[];self.calls=[]
        @contextmanager
        def batch(self):yield self
        def request(self,url,**kwargs):
            assert url==INDEX_URL and kwargs['request']['co_id']==issuer
            raw=(F/(issuer+'-index.html')).read_bytes();self.calls.append(url)
            self.components.append({'url':url,'http_request_sent':True,'http_status':200,
                'response_complete':True,'response_sha256':sha256(raw).hexdigest(),'response_bytes':len(raw),'status':'complete'})
            return raw,archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200)
    cold_http=Captured();warm_http=Captured();ticker=issuer+'.TW'
    with correlation_scope(replace=True,ticker=ticker,fetch_id='mixed-cold'):
        cold=fetch_public_financial_result(ticker,transport=cold_http)
    with correlation_scope(replace=True,ticker=ticker,fetch_id='mixed-warm'):
        warm=fetch_public_financial_result(ticker,transport=warm_http)
    assert len(cold_http.calls)==1 and not warm_http.calls
    assert cold['value']is warm['value']is None
    assert cold['audit']['status']==warm['audit']['status']=='error'
    assert cold['audit']['record_count']==warm['audit']['record_count']==0
    assert cold['audit']['fetched_at']==warm['audit']['fetched_at']
    assert warm['audit']['retry_at']==datetime.fromisoformat(cold['audit']['fetched_at']).timestamp()+cache.GAP_RETRY_SECONDS
    assert cache.GAP_RETRY_SECONDS==24*60*60
    assert warm['audit']['http_request_count']==0 and warm['audit']['http_request_sent']is False
    assert observation_kind({**warm['audit'],'details':observation_details(warm['audit'])})=='empty_cache_count'
    assert observation_kind({**cold['audit'],'details':observation_details(cold['audit'])})=='failed_count'
