"""Independent public regressions for normal/forced annual-source cache boundaries."""
import time
from copy import deepcopy
import pytest
import cache_store
from cache_backends import InMemoryCache
from test_normal_annual_source_reuse import CountingStock
from test_data_fetch_fixtures import FakeProvider,_patch_common_fetch_dependencies
from test_financial_statement_observation import StatementStock
from data_fetch import yfinance_core_fetch as core
from data_fetch.yfinance_extractors import extract_financial_histories

def setup(monkeypatch):
    _patch_common_fetch_dependencies(monkeypatch,resolved_ticker='AAPL',country='United States')
    now=[1791632500.0];monkeypatch.setattr(core.time_module,'time',lambda:now[0]);cache_store.set_cache_backend(InMemoryCache())
    stock=CountingStock(False);base=FakeProvider('AAPL',country='United States');price=[120.]
    class Provider:
        name='fixture-yfinance'
        def resolve_stock(self,ticker):
            _,info,valid,resolved,attempts=base.resolve_stock(ticker)
            info.update(currentPrice=price[0],quoteType='EQUITY')
            return stock,info,valid,resolved,attempts
    return now,stock,price,Provider()

def test_forced_new_annual_result_cannot_regress_to_previous_normal_cache(monkeypatch):
    now,stock,price,provider=setup(monkeypatch)
    try:
        first=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider)
        stock.stock.financials.loc['Total Revenue',stock.stock.financials.columns[0]]=3_000_000_000
        now[0]+=120;price[0]=125.
        forced=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider,force_refresh=True)
        assert forced['revenue_history'][-1]==3.0 and first['revenue_history'][-1]!=3.0
        now[0]+=120;price[0]=130.
        normal=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider)
        assert normal['current_price']==130.
        assert normal['revenue_history']==forced['revenue_history'],(first['revenue_history'],forced['revenue_history'],normal['revenue_history'])
    finally:cache_store.reset_cache_store_for_tests()


def test_force_refresh_keeps_the_finmind_provider_refresh_contract(monkeypatch):
    import data_fetch.yfinance_extractors as extractor
    seen=[]
    histories={key:[] for key in ('years','revenue_history','net_income_history','gross_profit_history',
        'operating_income_history','fcf_history','total_assets_history','total_equity_history')}
    def acquire(*a,**kwargs):seen.append(kwargs['finmind_use_cache']);return deepcopy(histories)
    monkeypatch.setattr(extractor,'_extract_financial_histories_uncached',acquire)
    cache_store.set_cache_backend(InMemoryCache())
    try:
        extractor.extract_financial_histories(object(),'5314.TWO',[],force_refresh=True)
        extractor.extract_financial_histories(object(),'5314.TWO',[],finmind_use_cache=True)
        assert seen==[False]
    finally:cache_store.reset_cache_store_for_tests()

def test_warm_wrapper_preserves_explicit_stale_child_observation(monkeypatch):
    histories=extract_financial_histories(StatementStock(),'AAPL',[],data_loader_cls=None)
    histories['finmind_financial_fallback_audit']={'source':'financial_statements','provider':'FinMind annual financial statements','status':'degraded_enrichment','record_count':2,'cache_hit':True,'stale':True,'fetched_at':'2026-10-10T10:00:00+00:00','fetched_at_epoch':1791626400.0}
    import shared_provider_cache
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:({'histories':deepcopy(histories),'notes':[]},{'cache_hit':True,'stale':False,'fetched_at_epoch':time.time()}))
    warmed=extract_financial_histories(object(),'AAPL',[],data_loader_cls=None,finmind_use_cache=True)
    assert warmed['finmind_financial_fallback_audit']['stale'] is True,warmed['finmind_financial_fallback_audit']

def test_bad_cached_history_shape_does_not_poison_current_quote_or_block_legacy_provider(monkeypatch):
    now,stock,price,provider=setup(monkeypatch)
    try:
        import shared_provider_cache
        monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:({'histories':{},'notes':[]},{'cache_hit':True,'stale':False,'fetched_at_epoch':now[0]-120}))
        result=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider)
        assert 'error' not in result and result['current_price']==120. and result['revenue_history'],result
    finally:cache_store.reset_cache_store_for_tests()

def test_single_raw_balance_value_tamper_cannot_change_capital_notes_while_rounding_and_audit_hash_match():
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    stock=StatementStock();histories=extract_financial_histories(stock,'AAPL',[],data_loader_cls=None)
    row=histories['primary_balance_snapshot'];row['assets']+=4_000_000
    assert round(row['assets']/1e9,2)==histories['total_assets_history'][-1]
    assert row['data_fingerprint']==histories['primary_financial_audit']['data_fingerprint']
    notes=build_capital_structure_notes(stock,{'returnOnAssets':0.1},
        revenue_history=histories['revenue_history'],net_income_history=histories['net_income_history'],
        total_assets_history=histories['total_assets_history'],total_equity_history=histories['total_equity_history'],
        market_cap=1_000_000_000,total_debt=100_000_000,financial_history_data={**histories,'ticker':'AAPL'})
    assert notes['equity_multiplier']=='2.000x',notes

def test_overflow_original_annual_epoch_is_unknown_not_a_core_fetch_exception(monkeypatch):
    now,stock,price,provider=setup(monkeypatch)
    try:
        histories=extract_financial_histories(StatementStock(),'AAPL',[],data_loader_cls=None)
        histories['primary_financial_audit']['fetched_at_epoch']=10**400
        import shared_provider_cache
        monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:({'histories':deepcopy(histories),'notes':[]},{'cache_hit':True,'stale':False,'fetched_at_epoch':now[0]-120}))
        result=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider)
        assert 'error' not in result and result['current_price']==120.,result
        assert result['source_freshness']['financial_statements']['fetched_at_epoch'] is None
    finally:cache_store.reset_cache_store_for_tests()
