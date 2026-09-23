"""Source meanings stay intact across fallback and partial acquisition."""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from datetime import datetime, timezone

MACRO_NOW = datetime(2026, 9, 23, 12, tzinfo=timezone.utc).timestamp()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def test_fx_spot_is_not_bank_bid_ask(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(fx, '_fetch_bot_exchange_rates', lambda: (_ for _ in ()).throw(ValueError('HTML')))
    monkeypatch.setattr(fx, '_fetch_er_api_usd_twd_rate', lambda: {'rate':'31.93','date':'2026-09-22'})
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    usd = result.value['rates']['USD']
    assert usd['spot'] == '31.93'
    assert usd.get('buy') is None and usd.get('sell') is None
    assert usd['rate_kind'] == 'spot'
    assert result.provider == result.audit['provider'] == result.value['actual_provider'] == 'open.er-api.com'
    assert result.status == 'degraded_enrichment'
    assert result.value['coverage']['EUR'] == 'unsupported'


def test_fx_shared_across_tickers_preserves_observation_date(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    calls=[]
    monkeypatch.setattr(fx, '_fetch_bot_exchange_rates', lambda: calls.append('BOT') or {'USD':{'buy':'31','sell':'32'}})
    first=fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    second=fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2305.TW'))
    assert calls == ['BOT']
    assert second.audit['cache_hit'] is True
    assert first.value['rates']['USD']['rate_kind'] == 'bank_quote'
    assert first.value['rates']['USD'].get('as_of') is None


def test_macro_one_failure_preserves_other_series(monkeypatch):
    import macro_fetcher as macro
    monkeypatch.setattr(macro, '_latest_observation', lambda s,k,name,**kw: {'value':4.2 if name=='DGS10' else 18.4,'date':'2026-09-22'})
    monkeypatch.setattr(macro, '_cpi_yoy_observation', lambda *a,**kw: (_ for _ in ()).throw(TimeoutError('unavailable')))
    result=macro.fetch_key_macro_indicators(api_key='test',use_cache=False,now_epoch=MACRO_NOW)
    assert result['status'] == 'partial'
    assert set(result['indicators']) == {'us_10y_yield','vix'}
    assert result['component_statuses']['us_cpi_yoy']['status'] == 'unavailable'
    assert '資料不足' in result['summary_text']


def test_macro_cpi_requires_same_month_last_year(monkeypatch):
    import macro_fetcher as macro
    monkeypatch.setattr(macro, '_fred_observations', lambda *a,**k: [{'date':'2026-07-01','value':'320'},{'date':'2026-08-01','value':'329'}])
    with pytest.raises(ValueError):
        macro._cpi_yoy_observation(None,'test',timeout=1)


def test_macro_rejects_nonfinite_or_undated_values():
    import macro_fetcher as macro
    assert macro._parse_observation({'date':'2026-09-22','value':'NaN'}) is None
    assert macro._parse_observation({'date':'','value':'4.2'}) is None


def test_chip_partial_does_not_hide_missing_borrowed(monkeypatch):
    import chip_data_fetcher as chip
    from data_fetch.agent_context_providers import ChipDataProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(chip,'fetch_tdcc_shareholder_distribution',lambda *a: {'status':'success','as_of_date':'2026-09-18'})
    monkeypatch.setattr(chip,'fetch_twse_margin_short_sales',lambda *a: {'status':'unavailable'})
    result=ChipDataProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.value['status'] == 'partial'
    assert result.value['component_statuses']['borrowed_short']['status'] == 'unknown'
    assert result.audit['coverage_status'] == 'partial'


def test_jobs_news_only_never_counts_as_numeric_coverage(monkeypatch):
    import alternative_data_fetcher as jobs
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    payload={'status':'success','job_count':None,'recent_recruitment_news':[{'title':'Hiring'}]}
    monkeypatch.setattr(jobs,'fetch_104_job_openings_count',lambda *a: dict(payload))
    monkeypatch.setattr(jobs,'fetch_1111_job_openings_count',lambda *a: dict(payload))
    result=AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'degraded_enrichment'
    assert result.value['numeric_count_coverage'] == 0
    assert result.value['recruitment_news_count'] == 2
    assert result.value['status'] == 'qualitative_only'


def test_jobs_zero_is_valid_empty_not_failure(monkeypatch):
    import alternative_data_fetcher as jobs
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(jobs,'fetch_104_job_openings_count',lambda *a: {'status':'success','job_count':0})
    monkeypatch.setattr(jobs,'fetch_1111_job_openings_count',lambda *a: {'status':'success','job_count':0})
    result=AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status == 'success'
    assert result.value['status'] == 'valid_empty'
    assert result.value['numeric_count_coverage'] == 2


def test_1111_parse_failure_is_not_transport_failure(monkeypatch):
    import alternative_data_fetcher as jobs
    monkeypatch.setattr(jobs,'_get_job_search_response',lambda *a,**k: type('R',(),{'text':'<html></html>'})())
    monkeypatch.setattr(jobs,'_google_news_fallback',lambda *a,**k: pytest.fail('parse errors must stay distinct'))
    result=jobs.fetch_1111_job_openings_count('Company','engineer')
    assert result['reason_code'] == 'parse_failure'


def test_pe_default_is_assumption_in_compact_prompt(monkeypatch):
    from data_fetch.market_sources import valuation
    from prompt_builder_helpers import _compact_pe_river
    monkeypatch.setattr(valuation,'DataLoader',None)
    result=valuation.build_pe_river_chart_data('AAPL',['2025'],[1],1e9)
    assert result['valuation_basis'] == 'scenario_assumption'
    assert result['historical_quantiles_available'] is False
    compact=_compact_pe_river(result)
    assert compact['valuation_basis'] == 'scenario_assumption'
    assert compact['historical_quantiles_available'] is False


def test_stale_macro_not_used_as_current_market_wacc():
    from quant_input_contract import wacc_policy
    result=wacc_policy({'macro_indicators':{'indicators':{'us_10y_yield':{'value':4.2,'stale':True}}}})
    assert result['uses_market_rate'] is False


def test_stale_vix_does_not_trigger_alert():
    from watchlist_triggers import _vix_above
    matched, message, metrics = _vix_above({'threshold':30}, {'macro_indicators':{'indicators':{'vix':{'value':50,'stale':True}}}})
    assert matched is False
    assert metrics['vix'] is None
    assert '過期' in message


def test_pe_default_snapshot_and_chart_identify_assumption():
    from stock_snapshot.peers_valuation import _valuation_range
    from reporting.chart_payload import chart_pe_river
    from reporting.html_chart_context import build_html_chart_context
    chart={'source':'default multiples','years':['2025'],'multiples':[10,15], 'bands':{'10x':[100],'15x':[150]},
           'valuation_basis':'scenario_assumption','historical_quantiles_available':False}
    snapshot=_valuation_range({'pe_river_chart':chart},current_price=120)
    assert snapshot['valuation_basis'] == 'scenario_assumption'
    assert snapshot['label'] == '情境假設區間'
    assert chart_pe_river(chart)['valuation_basis'] == 'scenario_assumption'
    assert '假設' in build_html_chart_context({'pe_river_chart':chart},{})['pe_river_title']


def test_jobs_cache_reuses_same_company_keywords(monkeypatch):
    import alternative_data_fetcher as jobs
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    calls=[]
    def count(*args):
        calls.append(args)
        return {'status':'success','job_count':5}
    monkeypatch.setattr(jobs,'fetch_104_job_openings_count',count)
    monkeypatch.setattr(jobs,'fetch_1111_job_openings_count',count)
    provider=AlternativeJobOpeningsProvider()
    request=FetchRequest.from_ticker('2330.TW')
    context={'data':{'company_name':'Company','job_opening_keywords':['engineering']}}
    provider.fetch(request,context)
    hit=provider.fetch(request,context)
    assert len(calls) == 2
    assert hit.audit['cache_hit'] is True
    provider.fetch(request,{'data':{'company_name':'Company','job_opening_keywords':['sales']}})
    assert len(calls) == 4


def test_social_empty_unknown_is_cached_without_claiming_no_discussions(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.types import FetchRequest
    calls=[]
    monkeypatch.setattr(news_fetchers,'fetch_google_news_rss',lambda *a,**k: calls.append('rss') or [])
    monkeypatch.setattr(news_fetchers,'fetch_ptt_stock_sentiment',lambda *a,**k: calls.append('ptt') or [])
    provider=SocialSentimentProvider()
    request=FetchRequest.from_ticker('2330.TW')
    provider.fetch(request)
    hit=provider.fetch(request)
    assert len(calls) == 4
    assert hit.value['status'] == 'empty_unknown'
    assert hit.audit['cache_hit'] is True
    assert '可接受空結果' not in hit.audit['message']


def test_macro_stale_series_retains_original_date_and_recovers_independently(monkeypatch):
    import macro_fetcher as macro
    import shared_provider_cache as shared
    now=[1000.]
    monkeypatch.setattr(shared.time,'time',lambda:now[0])
    failing=[False]
    def latest(session,key,name,**kwargs):
        if name=='DGS10' and failing[0]:
            raise TimeoutError('provider busy')
        return {'value':4.2 if name=='DGS10' else 18.4,'date':'2026-09-22'}
    monkeypatch.setattr(macro,'_latest_observation',latest)
    monkeypatch.setattr(macro,'_cpi_yoy_observation',lambda *a,**k: {'value':3.,'date':'2026-08-01'})
    initial=macro.fetch_key_macro_indicators(api_key='test',cache_ttl_seconds=10,now_epoch=MACRO_NOW)
    now[0]=1011
    failing[0]=True
    result=macro.fetch_key_macro_indicators(api_key='test',cache_ttl_seconds=10,now_epoch=MACRO_NOW)
    assert initial['status'] == 'success' and result['status'] == 'partial'
    assert result['indicators']['us_10y_yield']['date'] == '2026-09-22'
    assert result['indicators']['us_10y_yield']['stale'] is True
    assert result['indicators']['vix']['stale'] is False
    assert '過期備援' in result['summary_text']
    now[0]=1072
    failing[0]=False
    assert macro.fetch_key_macro_indicators(api_key='test',cache_ttl_seconds=10,now_epoch=MACRO_NOW)['status'] == 'success'


def test_fx_spot_survives_prompt_agent_context_without_bid_ask(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    from prompt_builder_helpers import _agent_context
    monkeypatch.setattr(fx,'_fetch_bot_exchange_rates',lambda:(_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(fx,'_fetch_er_api_usd_twd_rate',lambda:{'rate':'31.93','date':'2026-09-22'})
    result=fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    context=_agent_context({'taiwan_open_data':result.value})
    quote=context['taiwan_open_data']['rates']['USD']
    assert quote['spot'] == '31.93' and quote['buy'] is None and quote['sell'] is None
    assert context['taiwan_open_data']['actual_provider'] == 'open.er-api.com'


def test_jobs_one_zero_and_one_failure_is_partial_not_empty(monkeypatch):
    import alternative_data_fetcher as jobs
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(jobs,'fetch_104_job_openings_count',lambda *a: {'status':'success','job_count':0})
    monkeypatch.setattr(jobs,'fetch_1111_job_openings_count',lambda *a: {'status':'unavailable','job_count':None,'reason_code':'parse_failure'})
    result=AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.value['status'] == 'partial'
    assert result.status == 'degraded_enrichment'
    assert result.value['numeric_count_coverage'] == 1


def test_er_spot_date_is_normalized_from_provider_timestamp(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    class Response:
        def json(self):
            return {'result':'success','rates':{'TWD':31.93},'time_last_update_utc':'Fri, 03 Jul 2026 00:00:01 +0000'}
    monkeypatch.setattr(fx,'sync_get',lambda *a,**k:Response())
    result=fx._fetch_er_api_usd_twd_rate()
    assert result['date'].startswith('2026-07-03')


def test_bot_partial_quote_has_no_invalid_numeric_placeholder(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    monkeypatch.setattr(fx,'_fetch_bot_exchange_rates',lambda:{'USD':{'buy':'-','sell':'32'}})
    payload=fx._fetch_exchange_rates()
    assert payload['rates']['USD']['buy'] is None
    assert payload['coverage']['USD'] == 'partial'


def test_historical_pe_quantiles_remain_historical_not_assumed(monkeypatch):
    import pandas as pd
    from data_fetch.market_sources import valuation
    from reporting.html_chart_context import build_html_chart_context
    class Loader:
        def taiwan_stock_per_pbr(self,**kwargs):
            return pd.DataFrame({'PER':range(10,50)})
    monkeypatch.setattr(valuation,'DataLoader',Loader)
    chart=valuation.build_pe_river_chart_data('2330.TW',['2025'],[1],1e9)
    assert chart['valuation_basis'] == 'historical_quantiles'
    assert chart['historical_quantiles_available'] is True
    assert chart['historical_sample_count'] == 40
    assert '歷史本益比' in build_html_chart_context({'pe_river_chart':chart},{})['pe_river_title']
