"""Annual provider must preserve the caller's explicit cache policy."""
from copy import deepcopy
import pytest
from data_fetch.types import FetchRequest
from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
import data_fetch.market_sources.tcfhc_annual_financial as annual

class StopBeforeTransport(Exception):
    pass

@pytest.mark.parametrize('force', [False, True])
def test_tcfhc_provider_forwards_request_cache_policy(monkeypatch, force):
    data = {'ticker':'5880.TW', 'quote_type':'EQUITY', 'currency':'TWD',
            'financial_currency':'TWD', 'sector':'Financial Services',
            'industry':'Banks - Regional', 'company_identity':{
                'ticker':'5880.TW','stock_id':'5880','official_name':'合庫金',
                'legal_name':'合作金庫金融控股股份有限公司','official_ubn':'53021433',
                'instrument_type':'EQUITY'}}
    before=deepcopy(data)
    calls=[]
    def capture(ticker, *, force_refresh=False):
        calls.append((ticker,force_refresh))
        raise StopBeforeTransport
    monkeypatch.setattr(annual,'fetch_annual_result',capture)
    monkeypatch.setattr(annual,'supports_annual',lambda t:t=='5880.TW')
    with pytest.raises(StopBeforeTransport):
        AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('5880.TW',force_refresh=force),{'data':data})
    assert calls==[('5880.TW',force)]
    assert data==before

@pytest.mark.parametrize('field,value', [('currency','USD'),('ticker','2883.TW'),('quote_type','ETF')])
def test_invalid_annual_context_never_reaches_transport(monkeypatch,field,value):
    data={'ticker':'5880.TW','quote_type':'EQUITY','currency':'TWD','financial_currency':'TWD'}
    data[field]=value
    def forbidden(*args,**kwargs):
        pytest.fail('invalid context reached annual transport')
    monkeypatch.setattr(annual,'fetch_annual_result',forbidden)
    with pytest.raises(ValueError):
        AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('5880.TW'),{'data':data})
