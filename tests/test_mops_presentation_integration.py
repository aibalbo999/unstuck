"""New published-original bodies keep identity, audit and report boundaries."""
from copy import deepcopy
import sys
from types import SimpleNamespace
import pytest


@pytest.mark.parametrize('ticker', ['2330.TW'])
def test_public_free_path_uses_qualified_published_body(monkeypatch, ticker):
    from data_fetch import earnings_call_fetcher as fetcher
    value = {'ticker': ticker, 'documents': [{'document_kind': 'presentation'}]}
    seen = []
    def fetch(ticker, **options):
        seen.append((ticker, options))
        return value
    monkeypatch.setitem(sys.modules, 'data_fetch.market_sources.mops_presentation', SimpleNamespace(
        supports=lambda s: s in {'2330.TW', '1229.TW'}, fetch_presentation_context=fetch))
    monkeypatch.setattr(fetcher, '_fetch_official_index_context', lambda *a, **kw: {'materials': []})
    actual = fetcher.fetch_free_earnings_call_context(ticker, force_refresh=True, use_cache=False)
    assert actual == value, 'published full original must reach the normal free provider'
    assert len(seen) == 1 and seen[0][1]['force_refresh'] and not seen[0][1]['use_cache']


def test_shared_presentation_role_preserves_format_and_missing_hidden_limits():
    from conference_presentation_prompt import presentation_prompt_context
    doc = {'source': 'MOPS published presentation', 'document_kind': 'presentation',
           'ticker': '1229.TW', 'language': 'en', 'file_format': 'pptx',
           'page_count': 30, 'total_slide_count': 32, 'hidden_pages': [31, 32],
           'event_date': '2026-09-30', 'material_file_date': '2026-09-30',
           'content_period': '2026Q2', 'missing_text_pages': [2, 3, 21, 29],
           'coverage_status': 'partial', 'native_text_coverage': 'partial',
           'forward_looking_caution': 'Forecasts are not realized facts.',
           'financial_scope_caution': 'Parent, subsidiary, quarter and year-to-date scopes differ.',
           'known_native_text_omissions': [{'page_number': 2, 'issue': 'image_only_disclaimer'}],
           'q_and_a_transcript_available': False,
           'period_scope_caution': 'H1 is cumulative half-year, not standalone Q2.',
           'embedded_object_count': 4, 'external_relationship_count': 0,
           'financial_statement_complete': False,
           'pages': [{'page_number': 4, 'text': 'Revenue cash operating outlook'}]}
    context = {'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': ['Image omissions remain.']}
    before = deepcopy(context)
    for role in (3, 5, 12):
        result = presentation_prompt_context(context, role)['documents'][0]
        for key in ('file_format', 'hidden_pages', 'total_slide_count', 'material_file_date',
                    'content_period', 'financial_scope_caution', 'forward_looking_caution',
                    'known_native_text_omissions', 'q_and_a_transcript_available',
                    'period_scope_caution','embedded_object_count','external_relationship_count','financial_statement_complete'):
            assert result.get(key) == doc[key]
    assert context == before


def test_internal_post_receipt_is_not_in_role_prompt():
    from prompt_evidence import prompt_evidence_copy
    assert prompt_evidence_copy({'mops_material_receipt': {'request_body': 'private-proof'}, 'title': 'public'}) == {'title': 'public'}


@pytest.mark.parametrize('cached', [False, True])
def test_acquisition_audit_counts_one_body_and_no_new_warm_success(cached):
    from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
    result = {'value': {'documents': [{}]}, 'audit': {'status': 'success', 'record_count': 3}}
    diagnostic = {'mops_material_workflow': True, 'mops_material_originals_verified': True,
                  'cache_hit': cached, 'http_request_sent': True, 'http_request_count': 2,
                  'actual_provider': 'MOPS published presentation', 'coverage_status': 'native_presentation_text_partial'}
    apply_earnings_call_audit(result, diagnostic)
    assert result['audit']['record_count'] == 1
    if cached:
        assert result['audit']['status'] == 'skipped_fresh_cache'


from test_mops_presentation import harness, valid_data, otc_harness, halfyear_harness, electronics_harness


def use_legacy_1229_collector(monkeypatch, ticker):
    """Replay the still-supported MOPS receipt through public save boundaries.

    New 1229 requests prefer the issuer PDF; that routing is tested separately.
    Keep old MOPS originals and their tamper checks usable without asserting
    that the old endpoint remains the preferred production route.
    """
    if ticker != '1229.TW':
        return
    from data_fetch import enrichment_providers
    from data_fetch.market_sources import mops_presentation
    monkeypatch.setattr(enrichment_providers, 'fetch_free_earnings_call_context',
                        mops_presentation.fetch_presentation_context)


@pytest.mark.parametrize('ticker',['2330.TW','1229.TW','1104.TW'])
def test_provider_cold_and_warm_have_one_qualified_body(harness,ticker,monkeypatch):
    use_legacy_1229_collector(monkeypatch, ticker)
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    request=FetchRequest.from_ticker(ticker)
    cold=EarningsCallProvider().fetch(request,{'data':valid_data(ticker)})
    warm=EarningsCallProvider().fetch(request,{'data':valid_data(ticker)})
    assert cold.provider==warm.provider=='MOPS published presentation'
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
    result=enrichment_providers.EarningsCallProvider().fetch(FetchRequest.from_ticker('1229.TW'),{'data':data})
    assert result.status=='unavailable' and result.audit['http_request_count']==0 and not result.audit['http_request_sent']


@pytest.mark.parametrize('ticker',['2330.TW','1229.TW','2838.TW','2845.TW','3703.TW','2023.TW','1104.TW','3531.TWO','1102.TW','1216.TW','1301.TW','2353.TW','2382.TW'])
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
    context={'data':valid_data(ticker),'original_ticker':ticker}
    asyncio.run(StockDataService(registry=ProviderRegistry([Provider()])).fetch_source_async(FetchRequest.from_ticker(ticker),'earnings_call',context=context))
    assert seen==[context]


@pytest.mark.parametrize('ticker',['2838.TW','2845.TW','3703.TW','2023.TW','1104.TW','3531.TWO','1102.TW','1216.TW','1301.TW','2353.TW','2382.TW'])
def test_expanded_profiles_reject_wrong_report_identity_before_fetch(ticker):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*args,**kwargs):
            pytest.fail('conflicting report identity reached provider')
    data=valid_data(ticker)
    data['company_identity']['official_ubn']='11111111'
    snapshot={'ticker':ticker,'data':data,'source_audit':[{'source':'earnings_call','status':'unavailable'}]}
    with pytest.raises(HTTPException)as exc:
        asyncio.run(fetch_report_source_data(snapshot,'earnings_call',Service()))
    assert exc.value.status_code==400


@pytest.mark.parametrize('ticker',['2838.TW','2845.TW','3703.TW','2023.TW','1104.TW','3531.TWO','1102.TW','1216.TW','1301.TW','2353.TW','2382.TW'])
def test_report_source_route_preserves_expanded_profile_identity(ticker):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    seen=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,request,source,*,context=None):
            seen.append(context)
            return SimpleNamespace(data={'ticker':ticker,'earnings_call':{}},source_audit=[])
    data=valid_data(ticker)
    snapshot={'ticker':ticker,'data':data,'source_audit':[{'source':'earnings_call','status':'unavailable'}]}
    with pytest.raises(HTTPException):
        asyncio.run(fetch_report_source_data(snapshot,'earnings_call',Service()))
    assert seen==[{'data':data}]


def test_transport_failure_is_reported_before_attempting_material_replay(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    from data_fetch.market_sources import mops_presentation as source
    monkeypatch.setattr(source,'verify_context',lambda *a,**k:pytest.fail('failed acquisition has no original to replay'))
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*args,**kwargs):
            return SimpleNamespace(data={'ticker':'2023.TW','earnings_call':{}},source_audit=[{
                'source':'earnings_call','provider':source.PROVIDER,'status':'error',
                'error_kind':'timeout','record_count':0,'http_request_sent':True}])
    snapshot={'ticker':'2023.TW','data':valid_data('2023.TW'),
              'source_audit':[{'source':'earnings_call','status':'unavailable'}]}
    with pytest.raises(HTTPException)as exc:
        asyncio.run(fetch_report_source_data(snapshot,'earnings_call',Service()))
    assert exc.value.status_code==502 and '逾時'in exc.value.detail


@pytest.mark.parametrize('ticker',['2330.TW','1229.TW','2838.TW','3703.TW','2023.TW'])
@pytest.mark.parametrize('tamper',[False,True])
def test_public_source_only_preserves_report_and_checks_native_proof(harness,tmp_path,monkeypatch,ticker,tamper):
    use_legacy_1229_collector(monkeypatch, ticker)
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
    filename,keys,before=saved_target(storage,ticker,valid_data(ticker)['company_identity']['official_name'])
    before['data'].update(valid_data(ticker))
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
        assert doc['page_count']==len(doc['pages'])=={'2330.TW':12,'1229.TW':30,'2838.TW':20,'3703.TW':16,'2023.TW':27}[ticker]
        assert not doc['q_and_a_transcript_available']
        assert after['data']['recent_catalysts']==before['data']['recent_catalysts']
        assert result['analysis_text_stale'] is True
        assert_preserved(storage,keys,before,after)
    observed=events()
    assert len(observed)==1 and observed[0]['source']=='earnings_call'
    assert len(harness[1])==3


from test_mops_presentation_shared_master import fallback


@pytest.mark.parametrize('damage',[None,'master_url','master_policy'])
def test_shared_master_fallback_public_source_only_preserves_report(fallback,tmp_path,monkeypatch,damage):
    use_legacy_1229_collector(monkeypatch, "1229.TW")
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
    source,calls,control,base=fallback
    init_db();storage=InMemoryStorage();ticker='1229.TW'
    filename,keys,before=saved_target(storage,ticker,'聯華')
    before['data'].update(valid_data(ticker))
    before['analysis_evidence']=capture_analysis_evidence({'data':before['data']},generated_at=before['generated_at'])
    storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
    original=storage.get_report(keys.data_key).content
    html=storage.get_report(keys.html_key).content;markdown=storage.get_report(keys.md_key).content
    if damage:
        acquire=enrichment_providers.fetch_free_earnings_call_context
        def corrupted(*args,**kwargs):
            value=acquire(*args,**kwargs);master=value['mops_material_receipt']['master']
            if damage=='master_url':master['source_url']=source.MASTER_URL
            else:master['retrieval_policy']='unknown-policy'
            return value
        monkeypatch.setattr(enrichment_providers,'fetch_free_earnings_call_context',corrupted)
    provider=enrichment_providers.EarningsCallProvider()
    service=StockDataService(registry=ProviderRegistry([provider]))
    call=refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,
                                      source='earnings_call',return_refreshed_data=True)
    if damage:
        with pytest.raises(HTTPException) as exc:asyncio.run(call)
        assert exc.value.status_code==502
        assert storage.get_report(keys.data_key).content==original
        assert storage.get_report(keys.html_key).content==html
        assert storage.get_report(keys.md_key).content==markdown
    else:
        result=asyncio.run(call);after=json.loads(storage.get_report(keys.data_key).content)
        doc=after['data']['earnings_call']['documents'][0]
        assert doc['page_count']==30 and doc['hidden_pages']==[31,32]
        assert not doc['q_and_a_transcript_available'] and doc['content_period'] is None
        assert after['data']['recent_catalysts']==before['data']['recent_catalysts']
        assert result['analysis_text_stale'] is True
        assert_preserved(storage,keys,before,after)
    observed=events()
    assert len(observed)==1 and observed[0]['source']=='earnings_call'
    assert len(calls)==2 and base[1]==[ticker+':index',ticker+':material']


def test_shianyih_public_provider_uses_otc_master_and_retains_truth(otc_harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    request=FetchRequest.from_ticker('3531.TWO')
    cold=EarningsCallProvider().fetch(request,{'data':valid_data('3531.TWO')})
    warm=EarningsCallProvider().fetch(request,{'data':valid_data('3531.TWO')})
    assert cold.provider=='MOPS published presentation' and cold.audit['status']=='success'
    assert cold.audit['http_request_count']==3 and cold.audit['record_count']==1
    assert cold.value['documents'][0]['embedded_object_count']==4
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0
    assert warm.value['fetched_at_epoch']==cold.value['fetched_at_epoch']


@pytest.mark.parametrize('ticker',['1102.TW','1216.TW'])
def test_halfyear_provider_preserves_period_and_warm_acquisition_truth(halfyear_harness,ticker):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    req=FetchRequest.from_ticker(ticker)
    cold=EarningsCallProvider().fetch(req,{'data':valid_data(ticker)})
    warm=EarningsCallProvider().fetch(req,{'data':valid_data(ticker)})
    assert cold.provider=='MOPS published presentation' and cold.audit['status']=='success'
    assert cold.value['documents'][0]['content_period']=='2026H1'
    assert cold.audit['http_request_count']==3 and cold.audit['record_count']==1
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0


def test_fpc_public_provider_keeps_glyph_proof_and_acquisition_truth(halfyear_harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_presentation_prompt import presentation_prompt_context
    req=FetchRequest.from_ticker('1301.TW')
    cold=EarningsCallProvider().fetch(req,{'data':valid_data('1301.TW')})
    warm=EarningsCallProvider().fetch(req,{'data':valid_data('1301.TW')})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==3
    doc=cold.value['documents'][0]
    assert doc['native_text_coverage']=='complete' and doc['symbol_mapping_evidence']
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0
    prompt=presentation_prompt_context(cold.value,3)['documents'][0]
    assert prompt['content_period']=='2026Q2' and prompt['period_scope_caution']
    assert not prompt['full_content_coverage_verified'] and not prompt['financial_statement_complete']


@pytest.mark.parametrize('ticker',['2353.TW','2382.TW'])
def test_electronics_provider_keeps_native_truth_and_agent_period(electronics_harness,ticker):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_presentation_prompt import presentation_prompt_context
    request=FetchRequest.from_ticker(ticker)
    cold=EarningsCallProvider().fetch(request,{'data':valid_data(ticker)})
    warm=EarningsCallProvider().fetch(request,{'data':valid_data(ticker)})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==3
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0
    for role in (3,5,12):
        doc=presentation_prompt_context(cold.value,role)['documents'][0]
        assert doc['content_period']=='2026Q2' and 'H1' in doc['period_scope_caution']
        assert not doc['financial_statement_complete'] and not doc['full_content_coverage_verified']
