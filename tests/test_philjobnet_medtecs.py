from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import time
from zoneinfo import ZoneInfo
from dataclasses import asdict

import httpx
import pytest

from data_trust import source_record_count
from data_fetch.market_sources.tdr_mops_history import _master_anchor
from official_response_evidence import archive_response
from data_fetch.market_sources import philjobnet_medtecs as source

FIXTURES=Path(__file__).parent/'fixtures/source_acquisition'
PROFILE='https://philjobnet.gov.ph/job-vacancies/company/medtecs-intl-corp-ltd-2912'
CONTACT='https://www.medtecs.com/contact/'
DATA={'ticker':'9103.TW','company_name':'美德醫療-DR','company_identity':{'ticker':'9103.TW','official_name':'美德醫療-DR'}}
PROVIDER='PhilJobNet exact employer portal observation'
NOTE='取得當時該菲律賓政府入口的雇主清單明示未列職缺；只代表此入口，全球職缺數未知，不能推定招募縮減。'


def originals():
    now=datetime.now(ZoneInfo('Asia/Taipei'))
    f=json.loads((FIXTURES/'tdr_mops_9103_20261010.json').read_text())
    master=f['selected_master']
    # Unit identity slice, with the test's publication date; never live proof.
    master[0]['出表日期']=f'{now.year-1911:03d}{now.month:02d}{now.day:02d}'
    return json.dumps(master,ensure_ascii=False).encode(),(FIXTURES/'medtecs_contact_20261010_public_fixture.html').read_bytes(),(FIXTURES/'philjobnet_medtecs_20261010_complete.html').read_bytes()


def observation():
    raw,contact,profile=originals();stamp=time.time()-60
    anchor=_master_anchor(raw,stamp,datetime.now(ZoneInfo('Asia/Taipei')),require_fresh=True)
    for body,url in [(raw,anchor['master_source_url']),(contact,CONTACT),(profile,PROFILE)]:
        assert archive_response(body,source_url=url,retrieved_at=stamp,http_status=200)['status']=='archived'
    return {'status':'success','ticker':'9103.TW','source':PROVIDER,'source_url':PROFILE,
            'employer_id':'2912','employer_legal_name':'Medtecs International Corporation Limited',
            'query_scope':'single_philjobnet_employer_listing','portal_job_count':0,'global_job_count':None,
            'job_postings':[],'coverage_status':'single_portal_numeric_observation','coverage_note':NOTE,
            'fetched_at_epoch':stamp,'philjobnet_employer_receipt':{
                'policy':'medtecs-philjobnet-portal-count-v1','issuer_master':anchor,
                'contact_response_sha256':sha256(contact).hexdigest(),'contact_fetched_at_epoch':stamp,
                'profile_response_sha256':sha256(profile).hexdigest(),'profile_fetched_at_epoch':stamp}}


def test_explicit_zero_portal_count_is_one_observation_and_not_unknown_empty():
    value=observation()
    assert source_record_count('alternative_data',{**DATA,'alternative_data':{'job_openings_philjobnet':value}})==1
    assert value['portal_job_count']==0 and value['global_job_count'] is None


@pytest.mark.parametrize('key,value',[('status','error'),('portal_job_count',False),('portal_job_count',1),
    ('portal_job_count',None),('global_job_count',0),('job_postings',[{'title':'invented'}]),
    ('ticker','1301.TW'),('employer_id','9999'),('source_url','https://example.org'),
    ('query_scope','global_employer'),('coverage_note','全球沒有招募'),('fetched_at_epoch',True)])
def test_mutable_zero_or_scope_fields_cannot_replace_originals(key,value):
    item=observation();item[key]=value
    assert source_record_count('alternative_data',{**DATA,'alternative_data':{'job_openings_philjobnet':item}})==0


@pytest.mark.parametrize('identity',[False,0,[],'',{'ticker':'1301.TW'},{'official_name':'美德醫療'},
    {'legal_name':'Medtecs Taiwan Corporation'},{'forbidden_aliases':['美德醫療-DR']},
    {'forbidden_aliases':['<b>美德醫療-DR</b>']},{'forbidden_aliases':['<b>* 美德醫療-DR *</b>']}])
def test_conflicting_company_context_is_rejected(identity):
    assert not source.verified_philjobnet_observation(observation(),{**DATA,'company_identity':identity})


@pytest.mark.parametrize('change',[
    lambda s:s.replace('No job vacancies',''),
    lambda s:s.replace('No job vacancies','Loading'),
    lambda s:s.replace('No job vacancies','Coming soon'),
    lambda s:s.replace('value="2912"','value="9999"'),
    lambda s:s.replace('Medtecs International Corporation Limited is','Universal Weavers Corporation is'),
    lambda s:s.replace('</html>',''),
    lambda s:s.replace('No job vacancies','No job vacancies</td></tr><tr><td>other row'),
    lambda s:s.replace('No job vacancies','No job vacancies<a href="?page=2">Next</a>'),
    lambda s:s.replace('No job vacancies','No job vacancies<script>fetch("jobs")</script>'),
    lambda s:s.replace('</table>','</table><div class="job-card">1 job vacancy: Textile Technologist</div>'),
    lambda s:s.replace('id="jobs"','id="jobs" data-removed="jobs"',1).replace('</html>','<div id="jobs"></div></html>'),
])
def test_incomplete_loading_subsidiary_or_duplicate_profile_cannot_be_numeric_zero(change):
    _,_,raw=originals()
    with pytest.raises(ValueError):source._profile(change(raw.decode()).encode())


def test_contact_bridge_must_use_both_exact_country_panels():
    _,contact,_=originals()
    changed=contact.decode().replace('id="elementor-tab-content-1313"','id="wrong-panel"')
    with pytest.raises(ValueError):source._contact(changed.encode())
    item=observation()
    proof=archive_response(changed.encode(),source_url=CONTACT,retrieved_at=time.time(),http_status=200)
    item['philjobnet_employer_receipt']['contact_response_sha256']=proof['raw_response_sha256']
    assert not source.verified_philjobnet_observation(item,DATA)


def test_missing_archive_and_future_epoch_do_not_count():
    item=observation();item['philjobnet_employer_receipt']['profile_response_sha256']='0'*64
    assert not source.verified_philjobnet_observation(item,DATA)
    item=observation();item['philjobnet_employer_receipt']['profile_fetched_at_epoch']=time.time()+3600
    assert not source.verified_philjobnet_observation(item,DATA)


def mock_get(monkeypatch, *, fail=False):
    from data_fetch.market_sources import tdr_mops_history as master
    raw,contact,profile=originals();stamp=time.time()-60;calls=[]
    monkeypatch.setattr(master,'read_cached_listed_roster_bytes',lambda:(raw,{
        'fetched_at_epoch':stamp,'stale':False,'source_url':master.URLS['.TW'],
        'source_payload_sha256':sha256(raw).hexdigest()}))
    def get(url,**kwargs):
        calls.append(url)
        return httpx.Response(403 if fail else 200,content=contact if url==CONTACT else profile,
                              request=httpx.Request('GET',url))
    return get,calls


def test_fetch_archives_complete_originals_and_rebuilds_saved_zero(monkeypatch):
    get,calls=mock_get(monkeypatch)
    value,audit=source.fetch_philjobnet_observation('9103.TW',get=get)
    assert calls==[CONTACT,PROFILE] and audit['status']=='success' and audit['record_count']==1
    assert source.verified_philjobnet_observation(value,DATA,require_fresh=True)
    assert value['global_job_count'] is None and value['portal_job_count']==0


def test_refusal_is_unknown_and_stops_before_profile(monkeypatch):
    get,calls=mock_get(monkeypatch,fail=True)
    value,audit=source.fetch_philjobnet_observation('9103.TW',get=get)
    assert value is None and audit['record_count']==0 and calls==[CONTACT]


def test_other_ticker_makes_no_request():
    value,audit=source.fetch_philjobnet_observation('1301.TW',get=lambda *a:pytest.fail('wrong issuer request'))
    assert value is None and audit['record_count']==0 and audit['http_request_sent'] is False


def test_cache_retains_original_epoch_and_has_zero_native_requests_on_warm_read(monkeypatch):
    from data_fetch.agent_context_providers import PhilJobNetJobObservationProvider
    from data_fetch.types import FetchRequest,ProviderResult
    import shared_provider_cache
    item=observation();stamp=item['fetched_at_epoch']
    saved=ProviderResult('alternative_data',PROVIDER,'success',{'job_openings_philjobnet':item},
                         {'source':'alternative_data','provider':PROVIDER,'status':'success',
                          'record_count':1,'fetched_at_epoch':stamp,'http_request_count':2})
    def cache(key,acquire,**kwargs):
        assert key.startswith('optional-context:philjobnet-v1:')
        return asdict(saved),{'cache_hit':True,'stale':False,'fetched_at_epoch':stamp+10}
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cache)
    provider=PhilJobNetJobObservationProvider()
    monkeypatch.setattr(provider,'_fetch_uncached',lambda *a:pytest.fail('warm cache reacquired'))
    got=provider.fetch(FetchRequest('9103.TW'),{'data':DATA})
    assert got.audit['fetched_at_epoch']==stamp and got.audit['http_request_count']==0
    assert got.audit['http_request_sent'] is False and got.audit['event_kind']=='cache_hit'
    saved.value['job_openings_philjobnet']['global_job_count']=0
    bad=provider.fetch(FetchRequest('9103.TW'),{'data':DATA})
    assert bad.status=='error' and bad.value is None and bad.audit['record_count']==0
    assert bad.audit['http_request_count']==0 and bad.audit['http_request_sent'] is False


def test_prompt_keeps_scope_and_unknown_global_but_excludes_internal_receipt():
    from prompt_evidence import prompt_evidence_copy
    got=prompt_evidence_copy({'alternative_data':{'job_openings_philjobnet':observation()}})
    item=got['alternative_data']['job_openings_philjobnet']
    assert 'philjobnet_employer_receipt' not in item
    assert item['portal_job_count']==0 and item['global_job_count'] is None and item['coverage_note']==NOTE


@pytest.mark.parametrize('status,rc,error',[(200,0,None),(429,0,None),(200,63,None),(206,0,None)])
def test_native_transport_caps_refusals_and_never_retries(monkeypatch,status,rc,error):
    from data_fetch.market_sources import philjobnet_medtecs_transport as transport
    from search_provider_runtime import SourceResponseError
    for key in transport.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:None)
    monkeypatch.setattr(transport,'observe_http_response',lambda *a:None)
    failures=[];calls=[]
    monkeypatch.setattr(transport,'remember_failure',lambda *a:failures.append(a))
    def collect(argv,deadline,**kwargs):
        calls.append(argv)
        assert '--retry' in argv and argv[argv.index('--retry')+1]=='0'
        assert '--max-redirs' in argv and argv[argv.index('--max-redirs')+1]=='0'
        assert kwargs['body_limit']==600000 and '--location' not in argv
        return {'headers':f'HTTP/2 {status} OK\r\nContent-Type: text/html\r\n\r\n'.encode(),
                'body':b'<html></html>','process_started':True,
                'metadata':json.dumps({'http_code':status,'url_effective':PROFILE,'num_redirects':0}).encode()},rc,error
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    client=transport.PhilJobNetHttp(time.monotonic()+20)
    if status==200 and not rc:assert client.get(PROFILE).status_code==200
    else:
        with pytest.raises(SourceResponseError):client.get(PROFILE)
    assert len(calls)==1 and client.http_request_count==1
    assert len(failures)==int(status==429)


def test_transport_deadline_and_unknown_urls_send_nothing(monkeypatch):
    from data_fetch.market_sources import philjobnet_medtecs_transport as transport
    from search_provider_runtime import SourceResponseError
    for key in transport.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:None)
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:pytest.fail('deadline sent HTTP'))
    client=transport.PhilJobNetHttp(time.monotonic()-1)
    for url in (PROFILE,'https://philjobnet.gov.ph/job-vacancies/company/other-2912'):
        with pytest.raises(SourceResponseError):client.get(url)
    assert client.http_request_count==0


def test_deleted_typed_slot_cannot_bypass_revalidation_and_warm_http_is_zero(monkeypatch):
    from data_fetch.agent_context_providers import PhilJobNetJobObservationProvider
    from data_fetch.types import FetchRequest,ProviderResult
    import shared_provider_cache
    stamp=observation()['fetched_at_epoch']
    saved=ProviderResult('alternative_data',PROVIDER,'success',{'coverage_status':'single_portal_numeric_observation'},
        {'source':'alternative_data','provider':PROVIDER,'status':'success','record_count':1,
         'fetched_at_epoch':stamp,'http_request_count':2,'http_request_sent':True})
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:
        (asdict(saved),{'cache_hit':True,'stale':False,'fetched_at_epoch':stamp+10}))
    provider=PhilJobNetJobObservationProvider()
    monkeypatch.setattr(provider,'_fetch_uncached',lambda *a:pytest.fail('warm cache reacquired'))
    got=provider.fetch(FetchRequest('9103.TW'),{'data':DATA})
    assert got.status=='error' and got.value is None and got.audit['record_count']==0
    assert got.audit['fetched_at_epoch']==stamp and got.audit['http_request_count']==0
    assert got.audit['http_request_sent'] is False


def test_component_and_general_fallback_have_distinct_cache_identity(monkeypatch):
    from data_fetch.agent_context_providers import PhilJobNetJobObservationProvider,AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest,ProviderResult
    import shared_provider_cache
    saved={};calls=[];item=observation()
    def cache(key,acquire,**kwargs):
        hit=key in saved
        if not hit:saved[key]=acquire()
        return deepcopy(saved[key]),{'cache_hit':hit,'stale':False,'fetched_at_epoch':time.time()}
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',cache)
    general=AlternativeJobOpeningsProvider();typed=PhilJobNetJobObservationProvider()
    def fallback(*a):
        calls.append('104fallback')
        return ProviderResult('alternative_data',general.name,'success',{'job_openings_104':{'status':'success','job_count':5}},
            {'source':'alternative_data','provider':general.name,'status':'success','record_count':1,'fetched_at_epoch':time.time()})
    def portal(*a):
        calls.append('portal')
        return ProviderResult('alternative_data',PROVIDER,'success',{'job_openings_philjobnet':item},
            {'source':'alternative_data','provider':PROVIDER,'status':'success','record_count':1,'fetched_at_epoch':item['fetched_at_epoch']})
    monkeypatch.setattr(general,'_fetch_uncached',fallback);monkeypatch.setattr(typed,'_fetch_uncached',portal)
    general.fetch(FetchRequest('9103.TW'),{'data':DATA})
    got=typed.fetch(FetchRequest('9103.TW'),{'data':DATA})
    assert calls==['104fallback','portal'] and got.provider==PROVIDER and len(saved)==2
