"""Fresh transport never renews the date of a provider observation."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

NOW = datetime(2026, 9, 23, 12, tzinfo=timezone.utc).timestamp()


@pytest.mark.parametrize('observed,expected', [('2026-09-15','stale'),('2026-09-24','future'),('bad','unknown'),('', 'unknown')])
def test_fresh_http_macro_old_or_invalid_dates_are_not_current(monkeypatch, observed, expected):
    import macro_fetcher as macro
    monkeypatch.setattr(macro, "time", SimpleNamespace(time=lambda: NOW), raising=False)
    from quant_input_contract import wacc_policy
    from watchlist_triggers import _vix_above
    monkeypatch.setattr(macro, '_latest_observation', lambda *a,**k:{'value':50.,'date':observed})
    monkeypatch.setattr(macro, '_cpi_yoy_observation', lambda *a,**k:{'value':3.,'date':'2026-08-01'})
    result=macro.fetch_key_macro_indicators(api_key='test', use_cache=False)
    rate=result['indicators']['us_10y_yield']
    assert rate['stale'] is True
    assert rate['observation_status'] == expected
    assert result['component_statuses']['us_10y_yield']['reason_code'] == f'observation_{expected}'
    assert result['indicators']['us_cpi_yoy']['stale'] is False
    assert wacc_policy({'macro_indicators':result})['uses_market_rate'] is False
    assert _vix_above({'threshold':30},{'macro_indicators':result})[0] is False


@pytest.mark.parametrize('daily,cpi,status', [('2026-09-16','2026-06-25','success'),('2026-09-15','2026-06-24','stale')])
def test_macro_daily_seven_days_and_cpi_ninety_days_boundaries(monkeypatch,daily,cpi,status):
    import macro_fetcher as macro
    monkeypatch.setattr(macro, "time", SimpleNamespace(time=lambda: NOW), raising=False)
    monkeypatch.setattr(macro, '_latest_observation', lambda *a,**k:{'value':4.2,'date':daily})
    monkeypatch.setattr(macro, '_cpi_yoy_observation', lambda *a,**k:{'value':3.,'date':cpi})
    result=macro.fetch_key_macro_indicators(api_key='test',use_cache=False)
    assert result['status'] == status


@pytest.mark.parametrize('observed,expected', [('2026-09-15','stale'),('2026-09-24','future'),(None,'unknown')])
def test_fx_aged_future_or_undated_quotes_never_fresh(monkeypatch,observed,expected):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(fx,'time',SimpleNamespace(time=lambda:NOW),raising=False)
    monkeypatch.setattr(fx,'_fetch_exchange_rates',lambda:{'status':'success','actual_provider':'Bank of Taiwan',
        'rates':{'USD':{'buy':'31','sell':'32','as_of':observed,'rate_kind':'bank_quote'}},'coverage':{'USD':'available'}})
    result=fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker('2330.TW',force_refresh=True))
    assert result.status == 'degraded_enrichment'
    assert result.audit['stale'] is True
    assert result.value['rates']['USD']['observation_status'] == expected
    assert result.audit['component_statuses']['USD']['reason_code'] == f'observation_{expected}'
    assert result.value['rates']['USD']['as_of'] == observed
