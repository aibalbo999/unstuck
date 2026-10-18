from copy import deepcopy
import asyncio,json,base64,time
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from test_medtecs_medical_peer_recovery import boundaries,DATA,F,TODAY
from data_fetch.types import FetchRequest,ProviderResult


def acquired(monkeypatch):
    from data_fetch.market_sources import peer_recovery
    from data_fetch.market_sources import moneydj_medical_peer_cohort as source
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    boundaries(monkeypatch)
    original_get=IssuerNewsHttp.get
    def dated_original(http,url):
        raw=original_get(http,url)
        http.components[-1]['fetched_at_epoch']=datetime(2026,10,10,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        return raw
    monkeypatch.setattr(IssuerNewsHttp,'get',dated_original)
    monkeypatch.setattr(source,'_today',lambda:TODAY)
    monkeypatch.setattr(peer_recovery,'load_peer_stock_master',lambda:deepcopy(F['master_rows']))
    from data_fetch.enrichment_search_providers import MedicalPublishedPeerCohortProvider
    return MedicalPublishedPeerCohortProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':deepcopy(DATA)})


def test_public_discovery_provider_is_registered_for_one_issuer_and_preserves_candidate_limits(monkeypatch):
    from data_fetch.provider_registry import ProviderRegistry
    result=acquired(monkeypatch)
    matching=[p for p in ProviderRegistry().for_request(FetchRequest.from_ticker('9103.TW'),source='peer_discovery') if p.name==result.provider]
    assert len(matching)==1
    assert not matching[0].supports(FetchRequest.from_ticker('5314.TWO'))
    assert len(result.value)==5 and result.audit['record_count']==5
    assert result.audit['raw_count']==10
    assert all(r['business_comparability_verified'] is False and r['numeric_comparability_verified'] is False and r['business_comparability_verified_current'] is False for r in result.value)


@pytest.mark.parametrize('enough',[True,False])
def test_workflow_uses_two_verified_publisher_leads_before_falling_back_to_search(monkeypatch,enough):
    from types import SimpleNamespace
    from data_fetch import workflow
    published=acquired(monkeypatch)
    if not enough:published.value=published.value[:1]
    providers=[SimpleNamespace(source='peer_discovery',name=n) for n in ('Alternative Search','Yahoo Taiwan published industry ranking',published.provider)]
    monkeypatch.setattr(workflow,'collect_optional_providers',lambda *a,**k:(providers,{'peer_discovery':True}))
    monkeypatch.setattr(workflow,'_merge_optional_http_bundle',lambda data,bundle,**k:data)
    monkeypatch.setattr(workflow,'finalize_data_trust',lambda data:None)
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *a:None)
    calls=[]
    async def fetch(request,batch,context):
        calls.extend(p.name for p in batch)
        return [published if p.name==published.provider else ProviderResult('peer_discovery',p.name,'unavailable',value=[],audit={'source':'peer_discovery','provider':p.name,'status':'unavailable','record_count':0}) for p in batch]
    monkeypatch.setattr(workflow,'fetch_provider_results',fetch)
    asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker('9103.TW'),None,deepcopy(DATA)))
    assert ('Alternative Search' in calls) is not enough
    assert calls.count(published.provider)==1


def test_saved_discovery_round_trip_survives_merge_with_original_epoch_and_stays_candidate_only(monkeypatch):
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources.moneydj_medical_peer_cohort import is_medical_peer_record
    from prompt_builder import format_data_for_prompt
    result=acquired(monkeypatch);data={**deepcopy(DATA),'source_audit':[result.audit],'peer_discovery_results':[{'title':'unverified legacy','link':'https://example.com/old'}]}
    merged=_merge_optional_http_bundle(data,{'medical_peer_discovery':result.value},refreshed_sources=['peer_discovery'])
    saved=json.loads(json.dumps(merged));rows=saved['peer_discovery_results']
    assert len(rows)==5 and all(is_medical_peer_record(r,'9103.TW',today=TODAY)for r in rows)
    assert any(x['reason']=='legacy_peer_relationship_unverified'for x in saved['source_record_archive'])
    assert all(r['business_comparability_verified_current'] is False for r in rows)
    prompt=format_data_for_prompt(saved)
    assert 'raw_response_path' not in prompt and 'accepted_medical_publisher_originals' not in prompt


@pytest.mark.parametrize('change',['business','numeric','current_business','issuer','counterparty','name','date','future','hash','policy','link','missing_original','original_epoch','original_url'])
def test_discovery_requires_original_publisher_and_official_identity_receipts_after_snapshot_round_trip(monkeypatch,change):
    from data_fetch.market_sources.moneydj_medical_peer_cohort import is_medical_peer_record
    row=json.loads(json.dumps(acquired(monkeypatch).value[0]))
    if change=='business':row['business_comparability_verified']=True
    elif change=='numeric':row['numeric_comparability_verified']=True
    elif change=='current_business':row['business_comparability_verified_current']=True
    elif change=='issuer':row['issuer']['ticker']='5314.TWO'
    elif change=='counterparty':row['counterparty']['ticker']='2330.TW'
    elif change=='name':row['counterparty']['official_name']='其他公司'
    elif change=='date':row['observed_at']='2026-09-01'
    elif change=='future':row['observed_at']='2026-10-11'
    elif change=='hash':row['response_sha256']='0'*64
    elif change=='policy':row['selection_policy']='unverified_legacy'
    elif change=='link':row['link']='https://example.com/unknown'
    elif change=='missing_original':row.pop('source_record_archive')
    elif change=='original_epoch':row['source_record_archive'][0]['medical_originals']['publisher']['retrieved_at']=True
    elif change=='original_url':row['source_record_archive'][0]['medical_originals']['issuer']['source_url']='https://example.com/wrong'
    assert not is_medical_peer_record(row,'9103.TW',today=TODAY)


@pytest.mark.parametrize('mode',['cold','warm','http_failure','local_block'])
def test_public_discovery_audit_retains_transport_cache_and_source_failure_modes(monkeypatch,mode):
    acquired(monkeypatch)
    from data_fetch.enrichment_search_providers import MedicalPublishedPeerCohortProvider
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL
    from search_provider_runtime import SourceResponseError
    from provider_observation_details import observation_details
    stamp=datetime(2026,10,10,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    def get(http,url):
        sent=mode in {'cold','http_failure'};cached=mode=='warm'
        c={'url':url,'fetched_at_epoch':stamp,'http_request_sent':sent,'cache_hit':cached}
        http.components.append(c);http.http_request_count+=int(sent)
        if mode in {'http_failure','local_block'}:
            c['error_kind']='server_error' if sent else 'cooldown';raise SourceResponseError(c['error_kind'])
        return json.dumps(F['selected_official_roster_rows'],ensure_ascii=False).encode() if url==ROSTER_URL else base64.b64decode(F['raw_html_base64'])
    monkeypatch.setattr(IssuerNewsHttp,'get',get)
    result=MedicalPublishedPeerCohortProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':deepcopy(DATA)})
    audit=result.audit;detail=observation_details(audit)
    assert audit['http_request_sent']==(mode in {'cold','http_failure'})
    assert result.status==('success' if mode=='cold' else 'skipped_fresh_cache' if mode=='warm' else 'error')
    assert audit['record_count']==(5 if mode in {'cold','warm'} else 0)
    assert detail['component_statuses']['official_issuer_identity']['fetched_at_epoch']==stamp


def test_invalid_candidate_cannot_enter_merge_without_a_policy_audit(monkeypatch):
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    row=deepcopy(acquired(monkeypatch).value[0]);row['business_comparability_verified_current']=True
    merged=_merge_optional_http_bundle(deepcopy(DATA),{'medical_peer_discovery':[row]},refreshed_sources=['peer_discovery'])
    assert not merged.get('peer_discovery_results')
    assert merged['source_record_archive'][0]['reason']=='incoming_peer_relationship_unverified'


@pytest.mark.parametrize('field',['business_comparability_verified','numeric_comparability_verified','business_comparability_verified_current'])
def test_zero_is_not_the_explicit_boolean_candidate_contract(monkeypatch,field):
    from data_fetch.market_sources.moneydj_medical_peer_cohort import is_medical_peer_record
    row=deepcopy(acquired(monkeypatch).value[0]);row[field]=0
    assert not is_medical_peer_record(row,'9103.TW',today=TODAY)


@pytest.mark.parametrize('component',['issuer','publisher'])
def test_selected_field_receipt_is_not_a_complete_original_http_response(monkeypatch,component):
    from data_fetch.market_sources.moneydj_medical_peer_cohort import is_medical_peer_record
    row=deepcopy(acquired(monkeypatch).value[0])
    row['source_record_archive'][0]['medical_originals'][component]['evidence_kind']='selected_payload_fields_not_full_http_bytes'
    assert not is_medical_peer_record(row,'9103.TW',today=TODAY)


def test_medical_marked_generic_record_cannot_bypass_its_original_receipt_contract(monkeypatch):
    from peer_relationship_evidence import POLICY,is_reported_peer_record
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources.moneydj_medical_peer_cohort import DISCOVERY_TYPE
    now=time.time();title='美德醫療(9103) 與 邦特(4107)醫療業務比較'
    record={'selection_policy':POLICY,'relationship_kind':'reported_business_peer_comparison',
        'relationship_basis':'headline_or_snippet','numeric_comparability_verified':False,
        'issuer':{'ticker':'9103.TW'},'counterparty':{'ticker':'4107.TWO','stock_id':'4107','exchange':'TWO',
            'official_name':'邦特','market_data_fetched_at_epoch':now-60,'cache_generated_at_epoch':now-30,
            'identity_basis':'existing_cached_self_identity','instrument_type':'EQUITY'},
        'published_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),'link':'https://example.com/reported-peer',
        'title':title,'evidence_span':title,'reported_scope':'醫療業務','source':'test publisher',
        'source_type':DISCOVERY_TYPE}
    assert is_reported_peer_record(record,'9103.TW')
    merged=_merge_optional_http_bundle(deepcopy(DATA),{'medical_peer_discovery':[record]},refreshed_sources=['peer_discovery'])
    assert not merged.get('peer_discovery_results')


def test_original_acquisition_date_cannot_precede_the_issuer_row_observation(monkeypatch):
    acquired(monkeypatch)
    from data_fetch.enrichment_search_providers import MedicalPublishedPeerCohortProvider
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(base64.b64decode(F['raw_html_base64']).decode('big5'),'html.parser')
    link=next(a for a in soup.find('table',id='oMainTable').find_all('a',href=True)if 'AS9103' in a['href'])
    node=next(t for t in link.find_parent('tr').find_all(string=True)if '2026/10/08' in t)
    node.replace_with(str(node).replace('2026/10/08','2026/10/10'))
    raw=str(soup).encode('big5',errors='xmlcharrefreplace')
    def get(http,url):
        http.components.append({'url':url,'cache_hit':True,'http_request_sent':False,
            'fetched_at_epoch':datetime(2026,10,9,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()})
        return json.dumps(F['selected_official_roster_rows'],ensure_ascii=False).encode() if url==ROSTER_URL else raw
    monkeypatch.setattr(IssuerNewsHttp,'get',get)
    result=MedicalPublishedPeerCohortProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':deepcopy(DATA)})
    assert not result.value and result.audit['record_count']==0
