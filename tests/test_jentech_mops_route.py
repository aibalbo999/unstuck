import pytest

def test_profile_requires_exact_issuer_and_registered_aliases():
 from data_fetch.market_sources import mops_presentation as m
 d={'ticker':'3653.TW','instrument_type':'EQUITY','company_name':'健策 / Jentech Precision Industrial Co., Ltd','company_identity':{'ticker':'3653.TW','official_name':'健策','english_names':['JENTECH PRECISION INDUSTRIAL CO'],'official_ubn':'22415854'}}
 assert m.supports('3653.TW') and m.validate_context(d,'3653.TW')
 d['company_identity']['official_ubn']='11111111'
 assert not m.validate_context(d,'3653.TW')

@pytest.mark.parametrize('ticker',['3653.TW',' 3653.tw '])
def test_qualified_mops_primary_does_not_attempt_issuer_route(monkeypatch,ticker):
 from data_fetch import earnings_call_fetcher as f
 from data_fetch.market_sources import mops_presentation as m,jentech_conference as j
 calls=[]
 monkeypatch.setattr(m,'fetch_presentation_context',lambda t,**kw:calls.append((t,kw))or {'ok':True})
 def forbidden(*a,**kw):raise AssertionError('Issuer route must not run before or after MOPS primary')
 monkeypatch.setattr(j,'fetch_jentech_context',forbidden)
 assert f.fetch_free_earnings_call_context(ticker,use_cache=True,force_refresh=False)=={'ok':True}
 assert calls[0][0]=='3653.TW' and calls[0][1]['force_refresh'] is False and calls[0][1]['use_cache'] is True

@pytest.mark.parametrize('kind',['timeout','single_flight_busy','context_unverified'])
def test_primary_failure_keeps_guard_no_issuer_retry(monkeypatch,kind):
 from data_fetch import earnings_call_fetcher as f
 from data_fetch.market_sources import mops_presentation as m,jentech_conference as j
 from search_provider_runtime import SourceResponseError
 def primary(*a,**kw):raise SourceResponseError(kind)
 monkeypatch.setattr(m,'fetch_presentation_context',primary)
 monkeypatch.setattr(j,'fetch_jentech_context',lambda *a,**kw:pytest.fail('No issuer retry on primary block'))
 with pytest.raises(SourceResponseError) as e:f.fetch_free_earnings_call_context('3653.TW')
 assert e.value.error_kind==kind
