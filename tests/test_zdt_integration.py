"""ZDT presentation routing and whole-page boundaries, not synthetic transcript success."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import pytest
from test_zdt_conference import harness,valid_data
from data_fetch.market_sources.zdt_conference_transport import PDF_URL
PROVIDER='ZDT official conference presentation'

def test_public_routing_uses_zdt_presentation_without_mops_retry(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    calls=[];expected={'source':PROVIDER,'documents':[{'page_count':38}]}
    def fetch(ticker,**options):calls.append((ticker,options));return expected
    monkeypatch.setitem(sys.modules,'data_fetch.market_sources.zdt_conference',SimpleNamespace(supports_zdt=lambda t:t=='4958.TW',fetch_zdt_context=fetch))
    assert fetcher.fetch_free_earnings_call_context('4958.TW',force_refresh=True,use_cache=False)==expected
    assert calls==[('4958.TW',{'diagnostics':{},'force_refresh':True,'use_cache':False})]

@pytest.mark.parametrize('kind',['timeout','cooldown','single_flight_busy','guard_storage_unavailable','lease_lost'])
def test_selected_source_failure_does_not_retry_mops(monkeypatch,kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from search_provider_runtime import SourceResponseError
    def fetch(*a,**kw):raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules,'data_fetch.market_sources.zdt_conference',SimpleNamespace(supports_zdt=lambda t:t=='4958.TW',fetch_zdt_context=fetch))
    with pytest.raises(SourceResponseError)as caught:fetcher.fetch_free_earnings_call_context('4958.TW')
    assert caught.value.error_kind==kind

@pytest.mark.parametrize('role',[3,5,12])
def test_role_pages_keep_complete_financial_rows_dates_and_cautions(harness,role):
    from data_fetch.market_sources.zdt_conference import fetch_zdt_context
    from conference_presentation_prompt import presentation_prompt_context,without_presentation_documents
    v=fetch_zdt_context('4958.TW');before=deepcopy(v);p=presentation_prompt_context(v,role);d=p['documents'][0]
    assert sorted(x['page_number']for x in d['pages'])==[1,2,5,22]
    assert all(x['content_truncated']is False for x in d['pages'])
    for x in d['pages']:assert x['text']==before['documents'][0]['pages'][x['page_number']-1]['text']
    assert d['event_date']=='2026-10-13' and d['material_file_date']==None
    assert d['content_period']=='2026H1 financials and October operational outlook' and d['financial_statement_complete']is False
    for key in ['unit_scope_caution','native_editorial_caution','forward_looking_caution','index_reuse_caution']:assert d[key]==v['documents'][0][key]
    assert 'documents'not in without_presentation_documents(v)and v==before

@pytest.mark.parametrize('change',['text','missing_page','boolean_page','event','document_date','scope','role','claim_complete','title','caution'])
def test_roles_reject_edited_evidence_even_with_original_digest_label(harness,change):
    from data_fetch.market_sources.zdt_conference import fetch_zdt_context
    from conference_presentation_prompt import presentation_prompt_context
    v=fetch_zdt_context('4958.TW');d=v['documents'][0]
    if change=='text':d['pages'][6]['text']='Free cash flow = operating minus capital expenditures'
    elif change=='missing_page':d['pages'].pop()
    elif change=='boolean_page':d['pages'][0]['page_number']=True
    elif change=='event':d['event_date']=None
    elif change=='document_date':d['material_file_date']='2026-10-13'
    elif change=='scope':d['content_period']='2026Q3'
    elif change=='role':d['role_page_allowlist'].append(9)
    elif change=='title':d['title']='2026Q4已查核實績'
    elif change=='caution':d['forward_looking_caution']='Verified completed results'
    else:d['financial_statement_complete']=True
    for role in (3,5,12):assert not presentation_prompt_context(v,role).get('documents')

@pytest.mark.parametrize('marker',[{'zdt_conference_receipt':None},{'source':PROVIDER},{'projection_policy':'zdt-presentation-role-v1'},{'url':PDF_URL}])
def test_archived_presentation_cannot_become_reusable_financial_payload(monkeypatch,marker):
    from data_fetch import cache_helpers
    calls=[];monkeypatch.setattr(cache_helpers,'set_cache_json',lambda *a,**k:calls.append(a))
    v={'ticker':'4958.TW','earnings_call':{'documents':[marker]}};before=deepcopy(v)
    cache_helpers._cache_financial_data(v,'4958.TW');assert calls==[] and v==before

def test_private_receipt_does_not_enter_prompts():
    from prompt_evidence import prompt_evidence_copy
    assert prompt_evidence_copy({'zdt_conference_receipt':{'private':'archive'},'text':'回答'})=={'text':'回答'}

def test_invalid_context_is_local_block_for_the_selected_issuer(monkeypatch):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers,'fetch_free_earnings_call_context',lambda *a,**kw:pytest.fail('invalid identity reached HTTP'))
    result=enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('4958.TW'),{'data':{'ticker':'4958.TW','company_name':'臻鼎-KY','quote_type':'ETF'}})
    assert result.provider==PROVIDER and result.audit['event_kind']=='local_block'
    assert result.audit['record_count']==result.audit['http_request_count']==0

def test_one_presentation_does_not_count_pages_as_successes():
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result={'value':{'source':PROVIDER,'documents':[{'page_count':38}]},'audit':{'status':'success','record_count':12}}
    apply_earnings_call_audit(result,{'zdt_presentation_workflow':True,'zdt_originals_verified':True,'actual_provider':PROVIDER,'http_request_count':3,'http_request_sent':True,'cache_hit':False})
    assert result['audit']['record_count']==1 and result['audit']['http_request_count']==3

@pytest.mark.parametrize('tamper', [None, 'missing_page', 'scope', 'receipt'])
def test_saved_source_preserves_analysis_and_rejects_incomplete_proof(harness, tmp_path, monkeypatch, tamper):
    import asyncio
    import json
    from fastapi import HTTPException
    from data_fetch import enrichment_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from report_analysis_evidence import capture_analysis_evidence
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db, events
    from test_unitech_tcfhc_source_integration import saved_target, assert_preserved
    init_db(); storage = InMemoryStorage()
    filename, keys, before = saved_target(storage, '4958.TW', '臻鼎-KY')
    before['data'].update(valid_data())
    before['analysis_evidence'] = capture_analysis_evidence({'data': before['data']}, generated_at=before['generated_at'])
    storage.save_report(keys.data_key, json.dumps(before).encode(), content_type='application/json')
    original = storage.get_report(keys.data_key).content
    if tamper:
        acquire = enrichment_providers.fetch_free_earnings_call_context
        def corrupted(*args, **kwargs):
            value = acquire(*args, **kwargs)
            if tamper == 'missing_page':
                value['documents'][0]['pages'].pop()
            elif tamper == 'scope':
                value['documents'][0]['financial_statement_complete'] = True
            else:
                del value['zdt_conference_receipt']
            return value
        monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context', corrupted)
    service = StockDataService(registry=ProviderRegistry([enrichment_providers.EarningsCallProvider()]))
    call = refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='earnings_call', return_refreshed_data=True)
    if tamper:
        with pytest.raises(HTTPException) as caught:
            asyncio.run(call)
        assert caught.value.status_code == 502
        assert storage.get_report(keys.data_key).content == original
    else:
        result = asyncio.run(call)
        after = json.loads(storage.get_report(keys.data_key).content)
        doc = after['data']['earnings_call']['documents'][0]
        assert doc['page_count'] == len(doc['pages']) == 38
        assert doc['native_text_coverage'] == 'complete'
        assert doc['missing_text_pages'] == []
        assert doc['q_and_a_transcript_available'] is False
        assert result['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
        # A later transient general refresh retains this newly acquired
        # exact original, explicitly stale, without adding acquisition events.
        from report_conference_retention import retain_verified_conference
        from test_conference_retention_new_profiles import failed_data
        retained=retain_verified_conference(after,failed_data(after,'zdt'),'4958.TW')
        assert retained['earnings_call']==after['data']['earnings_call']
        assert retained['conference_retention']['new_acquisition']is False
        # Replay the persisted service result at its original observation time;
        # the native live TTL remains expired and no acquisition is invented.
        import time
        from test_zdt_conference import NOW
        from data_fetch.market_sources.zdt_conference import verify_context
        from provider_acquisition import project_acquisition_events
        future=NOW+400*86400
        monkeypatch.setattr(time,'time',lambda:future)
        assert not verify_context(after['data']['earnings_call'],'4958.TW',max_age=1800)
        historical=retain_verified_conference(after,failed_data(after,'zdt',now=future),'4958.TW')
        assert historical['earnings_call']==after['data']['earnings_call']
        assert historical['conference_retention']['new_acquisition']is False
        reused=historical['source_audit'][0]
        row=project_acquisition_events([{**reused,'created_at':future,'details_json':json.dumps(reused)}],window='last_24h',now=future)['sources'][0]
        assert row['fetched_count']==row['fetch_attempts']==0 and row['stale_cache_count']==1
    ledger = events()
    assert len(ledger) == 1 and ledger[0]['source'] == 'earnings_call'
    assert len(harness[1]) == 3
