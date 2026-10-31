"""Public CSC source routing and role boundaries; no live provider requests."""
from types import SimpleNamespace
import sys
from copy import deepcopy
import pytest

PROVIDER='CSC official conference presentation'


def test_public_free_context_prefers_csc_original(monkeypatch):
    from data_fetch import earnings_call_fetcher as fetcher
    expected={'ticker':'2002.TW','source':PROVIDER,'documents':[{'page_count':35}]}
    seen=[]
    def fetch(ticker,**options):seen.append((ticker,options));return expected
    monkeypatch.setitem(sys.modules,'data_fetch.market_sources.csc_conference',SimpleNamespace(supports_csc=lambda t:t=='2002.TW',fetch_csc_context=fetch))
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**kw:{'source':'MOPS','materials':[]})
    assert fetcher.fetch_free_earnings_call_context('2002.TW',force_refresh=True,use_cache=False)==expected
    assert len(seen)==1 and seen[0][1]['force_refresh'] and not seen[0][1]['use_cache']


@pytest.mark.parametrize('cached',[False,True])
def test_csc_audit_is_one_native_body_or_zero_new_warm_acquisition(cached):
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result={'value':{'documents':[{}]},'audit':{'status':'success','record_count':4}}
    diagnostic={'actual_provider':PROVIDER,'csc_presentation_workflow':True,'csc_originals_verified':True,
                'cache_hit':cached,'http_request_sent':not cached,'http_request_count':0 if cached else 4,
                'coverage_status':'native_presentation_text_complete'}
    apply_earnings_call_audit(result,diagnostic)
    assert result['audit']['record_count']==1
    assert result['audit']['status']==('skipped_fresh_cache'if cached else'success')


def test_csc_private_receipts_not_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    assert prompt_evidence_copy({'csc_conference_receipt':{'raw':'private'},'csc_glyph_evidence':{'font':'private'},'title':'public'})=={'title':'public'}


def test_csc_role_keeps_mixed_periods_no_transcript_and_financial_limitations():
    from conference_presentation_prompt import presentation_prompt_context
    doc={'source':PROVIDER,'document_kind':'presentation','ticker':'2002.TW','page_count':35,
         'event_date':'2026-09-23','content_periods':['1H26','Jan-Jul2026 self-assessed'],
         'coverage_status':'partial','native_text_coverage':'complete','full_content_coverage_verified':False,
         'financial_scope_caution':'H1 and seven month self-assessed financials are distinct; parent and consolidated differ.',
         'forward_looking_caution':'Targets are not realized results.',
         'unaudited_financial_caution':'Seven month results are preliminary.',
         'period_scope_caution':'Page26 May and August labels remain unreconciled.', 'q_and_a_transcript_available':False,
         'known_native_text_omissions':[{'page_number':8,'issue':'diagram semantics not verified'}],
         'pages':[{'page_number':4,'text':'Revenue capital cash operating outlook strategy '+('sourceword '*1000)}]}
    before=deepcopy(doc)
    for role in (3,5,12):
        projected=presentation_prompt_context({'documents':[doc]},role)['documents'][0]
        for key in ('content_periods','financial_scope_caution','forward_looking_caution','unaudited_financial_caution','period_scope_caution','q_and_a_transcript_available','known_native_text_omissions'):
            assert projected.get(key)==doc[key]
        assert sum(len(p['text'].split())for p in projected['pages'])<=200
    assert doc==before


from test_csc_conference import harness, valid_data



@pytest.mark.parametrize('ticker',['2002.TW'])
def test_provider_cold_and_warm_have_one_qualified_body(harness,ticker):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    request=FetchRequest.from_ticker(ticker)
    cold=EarningsCallProvider().fetch(request,{'data':valid_data()})
    warm=EarningsCallProvider().fetch(request,{'data':valid_data()})
    assert cold.provider==warm.provider==PROVIDER
    assert cold.audit['status']=='success' and cold.audit['record_count']==1
    assert cold.audit['http_request_count']==3 and cold.audit['http_request_sent'] is True
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['cache_hit'] is True
    assert warm.audit['http_request_count']==0 and warm.audit['http_request_sent'] is False
    assert cold.value['documents']==warm.value['documents'] and len(harness[1])==3


@pytest.mark.parametrize('data',[False,[], 'bad', {'ticker':'2330.TW','company_name':'聯華','quoteType':'EQUITY'},
                                     {'ticker':'1229.TW','company_name':'聯華','quoteType':'ETF'}])
def test_provider_invalid_context_stops_before_any_HTTP(monkeypatch,data):
    from data_fetch import enrichment_providers
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(enrichment_providers,'fetch_free_earnings_call_context',lambda *a,**kw:pytest.fail('invalid original reached acquisition'))
    result=enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('2002.TW'),{'data':data})
    assert result.status=='unavailable' and result.audit['http_request_count']==0 and not result.audit['http_request_sent']


@pytest.mark.parametrize('ticker',['2002.TW'])
def test_source_service_passes_original_identity(ticker):
    import asyncio
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest,ProviderResult
    seen=[]
    class Provider(EarningsCallProvider):
        def fetch(self,request,context=None):
            seen.append(context)
            return ProviderResult(self.source,self.name,'unavailable',value={})
    context={'data':valid_data(),'original_ticker':ticker}
    asyncio.run(StockDataService(registry=ProviderRegistry([Provider()])).fetch_source_async(FetchRequest.from_ticker(ticker),'earnings_call',context=context))
    assert seen==[context]


@pytest.mark.parametrize('ticker',['2002.TW'])
@pytest.mark.parametrize('tamper',[False,True])
def test_public_source_only_preserves_report_and_checks_native_proof(harness,tmp_path,monkeypatch,ticker,tamper):
    import asyncio,json
    from fastapi import HTTPException
    from data_fetch import enrichment_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from report_analysis_evidence import capture_analysis_evidence
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db,events
    from test_unitech_tcfhc_source_integration import saved_target,assert_preserved
    init_db();storage=InMemoryStorage()
    filename,keys,before=saved_target(storage,ticker,'中鋼')
    before['data'].update(valid_data())
    before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
    storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
    original=storage.get_report(keys.data_key).content
    if tamper:
        real=enrichment_providers.fetch_free_earnings_call_context
        def acquire(*a,**kw):
            value=real(*a,**kw);value['documents'][0]['q_and_a_transcript_available']=True
            return value
        monkeypatch.setattr(enrichment_providers,'fetch_free_earnings_call_context',acquire)
    provider=enrichment_providers.EarningsCallProvider();real_fetch=provider.fetch
    def fetch(request,context=None):
        assert context['data']==before['data']
        return real_fetch(request,context)
    monkeypatch.setattr(provider,'fetch',fetch)
    service=StockDataService(registry=ProviderRegistry([provider]))
    call=refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,
                                      source='earnings_call',return_refreshed_data=True)
    if tamper:
        with pytest.raises(HTTPException) as e:asyncio.run(call)
        assert e.value.status_code==502 and storage.get_report(keys.data_key).content==original
    else:
        result=asyncio.run(call);after=json.loads(storage.get_report(keys.data_key).content)
        doc=after['data']['earnings_call']['documents'][0]
        assert doc['page_count']==len(doc['pages'])==35
        assert not doc['q_and_a_transcript_available']
        assert after['data']['recent_catalysts']==before['data']['recent_catalysts']
        assert result['analysis_text_stale'] is True
        assert_preserved(storage,keys,before,after)
    observed=events()
    assert len(observed)==1 and observed[0]['source']=='earnings_call'
    assert len(harness[1])==3
