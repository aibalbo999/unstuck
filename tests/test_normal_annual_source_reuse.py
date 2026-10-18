"""Refreshing a quote must not refetch a fresh annual source or renew its age."""
from collections import Counter
from copy import deepcopy
import time

import pytest
import cache_store
from cache_backends import InMemoryCache
from provider_correlation import correlation_scope
from test_data_fetch_fixtures import FakeStock,FakeProvider,_patch_common_fetch_dependencies
from data_fetch import yfinance_core_fetch as core


class CountingStock:
    def __init__(self,partial):
        self.stock=FakeStock();self.calls=Counter()
        if partial:self.stock.cashflow=self.stock.cashflow.drop('Capital Expenditure')

    def __getattr__(self,name):
        if name in {'financials','cashflow','balance_sheet'}:self.calls[name]+=1
        return getattr(self.stock,name)


@pytest.mark.parametrize('partial',[False,True])
def test_normal_quote_refresh_reuses_annual_provider_and_keeps_age_quality_and_force_contract(monkeypatch,partial):
    _patch_common_fetch_dependencies(monkeypatch,resolved_ticker='AAPL',country='United States')
    now=[1791632500.0];monkeypatch.setattr(core.time_module,'time',lambda:now[0])
    cache_store.set_cache_backend(InMemoryCache());stock=CountingStock(partial)
    base=FakeProvider('AAPL',country='United States');price=[120.0]
    class Provider:
        name='fixture-yfinance'
        def resolve_stock(self,ticker):
            _,info,valid,resolved,attempts=base.resolve_stock(ticker)
            info.update(currentPrice=price[0],quoteType='EQUITY')
            return stock,info,valid,resolved,attempts
    provider=Provider()
    try:
        with correlation_scope(replace=True,fetch_id='first-normal'):
            first=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider)
        assert first.get('ticker')=='AAPL' and 'error' not in first
        now[0]+=120;price[0]=125.0
        with correlation_scope(replace=True,fetch_id='second-normal'):
            second=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider)
        assert second['current_price']==125.0 and first['current_price']==120.0
        assert stock.calls=={'financials':1,'cashflow':1,'balance_sheet':1}
        for key in ('years','revenue_history','net_income_history','fcf_history','total_assets_history','total_equity_history'):
            assert second[key]==first[key]
        old=next(a for a in first['source_audit']if a['provider']=='Yahoo annual financial statements')
        new=next(a for a in second['source_audit']if a['provider']=='Yahoo annual financial statements')
        assert new['status']==('degraded_enrichment' if partial else 'skipped_fresh_cache')
        assert new['coverage_status']==old['coverage_status']
        assert new['fetched_at_epoch']==old['fetched_at_epoch'] and new['fetched_at']==old['fetched_at']
        assert new['fetch_id']=='second-normal' and new['cache_hit'] is True
        assert new['http_request_sent'] is False and new['http_request_count']==0
        assert new['provider_attempt_count']==0 and new['provider_attempts']==[]
        fin=second['source_freshness']['financial_statements']
        assert fin['fetched_at_epoch']==old['fetched_at_epoch'] and fin['age_seconds']==120
        assert second['source_freshness']['market_data']['fetched_at_epoch']==now[0]
        if partial:assert second['fcf_history']==[None,None]
        now[0]+=120
        forced=core.fetch_stock_data('AAPL',skip_optional_http=True,market_data_provider=provider,force_refresh=True)
        assert stock.calls=={'financials':2,'cashflow':2,'balance_sheet':2}
        actual=next(a for a in forced['source_audit']if a['provider']=='Yahoo annual financial statements')
        assert actual['cache_hit'] is False and actual['status']==('degraded_enrichment' if partial else 'success')
        assert actual['fetched_at_epoch']==now[0]
    finally:cache_store.reset_cache_store_for_tests()


@pytest.mark.parametrize('change',[lambda a:a.update(fetched_at_epoch=True),
    lambda a:a.update(fetched_at_epoch=float('nan')),lambda a:a.update(fetched_at_epoch=2000),
    lambda a:a.update(fetched_at='1970-01-01T00:16:40'),
    lambda a:a.update(fetched_at_epoch=900),lambda a:(a.pop('fetched_at'),a.pop('fetched_at_epoch'))])
def test_invalid_original_time_never_becomes_fresh_with_the_quote(change):
    from data_fetch.annual_history_cache_freshness import preserve_reused_annual_freshness
    audit={'cache_hit':True,'fetched_at_epoch':1000,'fetched_at':'1970-01-01T00:16:40+00:00'}
    change(audit);old=deepcopy(audit)
    data={'source_freshness':{'market_data':{'fetched_at_epoch':1100}}}
    preserve_reused_annual_freshness(data,'AAPL',[audit],1100)
    assert data['source_freshness']['financial_statements']['fetched_at_epoch'] is None
    assert data['source_freshness']['market_data']['fetched_at_epoch']==1100 and audit==old


def test_failed_refresh_retention_is_not_a_fresh_annual_cache(monkeypatch):
    from data_fetch.yfinance_extractors import extract_financial_histories
    import shared_provider_cache
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:
        ({'histories':{},'notes':[]},{'cache_hit':True,'stale':True,'error_kind':'RuntimeError','fetched_at_epoch':1000}))
    with pytest.raises(RuntimeError):extract_financial_histories(object(),'AAPL',[],finmind_use_cache=True)
