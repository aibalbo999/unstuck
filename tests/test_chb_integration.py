"""CHB QA routing and full-answer boundaries, not synthetic transcript success."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import pytest
from test_chb_conference import harness,valid_data
from data_fetch.market_sources.chb_conference_transport import PDF_URL
PROVIDER='CHB official investor QA summary'

def test_public_routing_uses_chb_qa_without_mops_retry(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    calls=[];expected={'source':PROVIDER,'documents':[{'page_count':7}]}
    def fetch(ticker,**options):calls.append((ticker,options));return expected
    monkeypatch.setitem(sys.modules,'data_fetch.market_sources.chb_conference',SimpleNamespace(supports_chb=lambda t:t=='2801.TW',fetch_chb_context=fetch))
    assert fetcher.fetch_free_earnings_call_context('2801.TW',force_refresh=True,use_cache=False)==expected
    assert calls==[('2801.TW',{'diagnostics':{},'force_refresh':True,'use_cache':False})]

@pytest.mark.parametrize('kind',['timeout','cooldown','single_flight_busy','guard_storage_unavailable','lease_lost'])
def test_selected_source_failure_does_not_retry_mops(monkeypatch,kind):
    from data_fetch import earnings_call_fetcher as fetcher
    from search_provider_runtime import SourceResponseError
    def fetch(*a,**kw):raise SourceResponseError(kind)
    monkeypatch.setitem(sys.modules,'data_fetch.market_sources.chb_conference',SimpleNamespace(supports_chb=lambda t:t=='2801.TW',fetch_chb_context=fetch))
    with pytest.raises(SourceResponseError)as caught:fetcher.fetch_free_earnings_call_context('2801.TW')
    assert caught.value.error_kind==kind

@pytest.mark.parametrize('role',[3,5,12])
def test_whole_qa_fits_role_budget_without_cutting_cross_page_answers(harness,role):
    from data_fetch.market_sources.chb_conference import fetch_chb_context
    from conference_presentation_prompt import presentation_prompt_context,without_presentation_documents
    v=fetch_chb_context('2801.TW');before=deepcopy(v);p=presentation_prompt_context(v,role)
    assert p['transcript_available']is False and p['coverage_status']=='partial'
    d=p['documents'][0]
    assert d['document_kind']=='issuer_qa_summary' and d['selection_policy']=='complete_qa_original_page_order'
    assert [x['page_number']for x in d['pages']]==list(range(1,8))
    assert all(x['content_truncated']is False for x in d['pages'])
    assert [x['text']for x in d['pages']]==[x['text']for x in before['documents'][0]['pages']]
    assert d['cross_page_questions']=={'2':[1,2],'4':[2,3],'6':[3,4],'12':[6,7]}
    assert d['question_count']==12 and d['q_and_a_transcript_available']is False
    assert d['forward_looking_caution']==v['documents'][0]['forward_looking_caution']
    assert 'documents'not in without_presentation_documents(v) and v==before

@pytest.mark.parametrize('change',['text','missing_answer','boolean_page','question','event','kind','claim_complete'])
def test_roles_reject_unverified_qa_edits_even_with_same_digest_label(harness,change):
    from data_fetch.market_sources.chb_conference import fetch_chb_context
    from conference_presentation_prompt import presentation_prompt_context
    v=fetch_chb_context('2801.TW');d=v['documents'][0]
    if change=='text':d['pages'][5]['text']='本行已完成併購'
    elif change=='missing_answer':d['pages'].pop()
    elif change=='boolean_page':d['pages'][0]['page_number']=True
    elif change=='question':d['cross_page_questions']={}
    elif change=='event':d['event_date']='2026-10-15'
    elif change=='kind':d['document_kind']='presentation'
    else:d['q_and_a_transcript_available']=True
    for role in (3,5,12):assert not presentation_prompt_context(v,role).get('documents')

@pytest.mark.parametrize('marker',[{'chb_qa_receipt':None},{'source':PROVIDER},{'projection_policy':'chb-qa-role-v1'},{'url':PDF_URL}])
def test_archived_qa_cannot_become_reusable_financial_payload(monkeypatch,marker):
    from data_fetch import cache_helpers
    calls=[];monkeypatch.setattr(cache_helpers,'set_cache_json',lambda *a,**k:calls.append(a))
    v={'ticker':'2801.TW','earnings_call':{'documents':[marker]}};before=deepcopy(v)
    cache_helpers._cache_financial_data(v,'2801.TW');assert calls==[] and v==before

def test_private_receipt_does_not_enter_prompts():
    from prompt_evidence import prompt_evidence_copy
    assert prompt_evidence_copy({'chb_qa_receipt':{'private':'archive'},'text':'回答'})=={'text':'回答'}

def test_invalid_context_is_local_block_for_the_selected_issuer(monkeypatch):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers,'fetch_free_earnings_call_context',lambda *a,**kw:pytest.fail('invalid identity reached HTTP'))
    result=enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('2801.TW'),{'data':{'ticker':'2801.TW','company_name':'彰銀','quote_type':'ETF'}})
    assert result.provider==PROVIDER and result.audit['event_kind']=='local_block'
    assert result.audit['record_count']==result.audit['http_request_count']==0

def test_one_qa_summary_does_not_count_pages_or_questions_as_successes():
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result={'value':{'source':PROVIDER,'documents':[{'page_count':7,'question_count':12}]},'audit':{'status':'success','record_count':12}}
    apply_earnings_call_audit(result,{'chb_qa_workflow':True,'chb_originals_verified':True,'actual_provider':PROVIDER,'http_request_count':3,'http_request_sent':True,'cache_hit':False})
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
    filename, keys, before = saved_target(storage, '2801.TW', '彰銀')
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
                del value['chb_qa_receipt']
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
        assert doc['page_count'] == len(doc['pages']) == 7
        assert doc['native_text_coverage'] == 'complete'
        assert doc['missing_text_pages'] == []
        assert doc['q_and_a_transcript_available'] is False
        assert result['analysis_text_stale'] is True
        assert_preserved(storage, keys, before, after)
    ledger = events()
    assert len(ledger) == 1 and ledger[0]['source'] == 'earnings_call'
    assert len(harness[1]) == 3
