"""Official backup acquisition preserves source dates, units and missing records."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from chip_data_fetcher import fetch_twse_margin_short_sales
from data_fetch.taiwan_providers import InstitutionalTradingProvider
from data_fetch.types import FetchRequest


class Response:
    status_code = 200
    def __init__(self, value): self.value = value
    def json(self): return self.value
    def raise_for_status(self): pass


SBL = {'Date': '1150924', 'SecuritiesCompanyCode': '6488', 'CompanyName': '環球晶',
       'SecuritiesBorrowingBalancePreviousDay': '37797000', 'SecuritiesBorrowingSale': '742000',
       'SecuritiesBorrowingReturn': '0', 'SecuritiesBorrowingAdjustment': '0',
       'SecuritiesBorrowingBalanceOfTheMarketDay': '38539000', 'AvailableVolumesForSBLShortSale': '3155909', 'Note': ''}


class Session:
    def __init__(self, sbl=None): self.calls = []; self.sbl = [deepcopy(SBL)] if sbl is None else sbl
    def get(self, url, **kwargs):
        self.calls.append(url)
        if 'tpex_margin_sbl' in url: return Response(self.sbl)
        return Response([{'Date':'1150923','SecuritiesCompanyCode':'6488','CompanyName':'環球晶',
                          'MarginPurchaseBalance':'6961','ShortSaleBalance':'136'}])


def test_otc_borrowed_short_recovered_without_borrowing_margin_date():
    result = fetch_twse_margin_short_sales('6488.TWO', session=Session())
    assert result['borrowed_short_status'] == 'success'
    assert result['borrowed_short_as_of_date'] == '2026-09-24'
    assert result['margin_as_of_date'] == '2026-09-23'
    assert result['borrowed_short_unit'] == 'shares'
    assert result['borrowed_short_sale_balance'] == 38539000
    assert result['borrowed_short_sale_today'] == 742000
    assert result['borrowed_short_return_today'] == 0
    assert result['borrowed_short_source'] == 'TPEx OpenAPI tpex_margin_sbl'
    assert result['borrowed_short_reason_code'] == 'reported_balance'


def test_otc_missing_row_does_not_become_zero():
    result = fetch_twse_margin_short_sales('6488.TWO', session=Session([]))
    assert result['borrowed_short_status'] == 'unavailable'
    assert result['borrowed_short_reason_code'] == 'record_not_found'
    assert 'borrowed_short_sale_balance' not in result


@pytest.mark.parametrize('field,value', [('Date','1151399'),('SecuritiesBorrowingBalanceOfTheMarketDay','--'),
                                        ('SecuritiesBorrowingBalanceOfTheMarketDay','-3')])
def test_otc_bad_borrowed_row_cannot_be_success(field, value):
    row = {**SBL, field: value}
    result = fetch_twse_margin_short_sales('6488.TWO', session=Session([row]))
    assert result['borrowed_short_status'] != 'success'
    assert result['margin_as_of_date'] == '2026-09-23'

T86_FIELDS = ['證券代號', '證券名稱', '外陸資買進股數(不含外資自營商)', '外陸資賣出股數(不含外資自營商)',
              '外陸資買賣超股數(不含外資自營商)', '外資自營商買進股數', '外資自營商賣出股數', '外資自營商買賣超股數',
              '投信買進股數', '投信賣出股數', '投信買賣超股數', '自營商買賣超股數', '自營商買進股數(自行買賣)',
              '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)', '自營商買進股數(避險)', '自營商賣出股數(避險)',
              '自營商買賣超股數(避險)', '三大法人買賣超股數']


def t86(day, code='2321', foreign=1200):
    row = [code, '測試公司', str(foreign), '0', str(foreign), '0', '0', '0', '0', '100', '-100',
           '30', '30', '0', '30', '0', '0', '0', str(foreign-100+30)]
    return {'stat':'OK','date':day.replace('-',''),'hints':'單位：股','fields':T86_FIELDS,'data':[row]}


def primary_old():
    return {'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell','latest_date':'2026-09-08',
            'observation_dates':['2026-09-08'], 'window_coverage_status':'missing_sessions',
            'lookback_trading_days':1, 'net_buy_shares_by_category':{'foreign':0,'investment_trust':0,'dealer':-89},
            'total_net_buy_shares':-89, 'daily_category_observations':[
                {'date':'2026-09-08','category':cat,'net_buy_shares':val,'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell'}
                for cat,val in [('foreign',0),('investment_trust',0),('dealer',-89)]]}


@pytest.fixture
def institutional_http(monkeypatch):
    import cache_store, external_http_client, provider_resilience, shared_provider_cache
    from cache_backends import InMemoryCache
    from urllib.parse import urlparse, parse_qs
    cache_store.set_cache_backend(InMemoryCache())
    now = datetime(2026,9,25,2,tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(shared_provider_cache.time,'time',lambda:now)
    monkeypatch.setattr(provider_resilience,'_check_provider_state',lambda *_:None)
    monkeypatch.setattr(provider_resilience,'enforce_provider_throttle',lambda *_:None)
    monkeypatch.setattr(provider_resilience,'_record_provider_success',lambda *_:None)
    calls=[]
    def fetch(url, **kw):
        calls.append(url)
        day=parse_qs(urlparse(url).query)['date'][0]
        return Response(t86(day))
    monkeypatch.setattr(external_http_client,'sync_get',fetch)
    yield calls
    cache_store.reset_cache_store_for_tests()


def test_stale_institutional_acquisition_recovers_through_official_provider(monkeypatch, institutional_http):
    from data_fetch.institutional_provider import fetch_institutional_result
    result=fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:primary_old())
    assert result.value['latest_date']=='2026-09-24'
    assert result.value['lookback_trading_days']==6
    assert result.value['total_net_buy_shares']==5*1130-89
    assert result.value['official_recovery']['added_observation_count']==15
    assert result.audit['coverage_status']=='partial'  # Still not a complete 30-session window.
    assert 'TWSE T86' in result.audit['actual_provider']
    assert len(institutional_http)==5


def test_official_missing_security_preserves_stale_date_and_no_zero(monkeypatch, institutional_http):
    import external_http_client
    from data_fetch.institutional_provider import fetch_institutional_result
    from urllib.parse import urlparse,parse_qs
    def get(url,**kw):
        day=parse_qs(urlparse(url).query)['date'][0]
        return Response(t86(day,code='2330'))
    monkeypatch.setattr(external_http_client,'sync_get',get)
    result=fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:primary_old())
    assert result.value['latest_date']=='2026-09-08'
    assert result.value['total_net_buy_shares']==-89
    assert result.value['official_recovery']['status']=='security_absent'
    assert result.audit['stale'] is True
    assert result.value['official_recovery']['checked_dates']==['2026-09-24','2026-09-23','2026-09-22','2026-09-21','2026-09-18']


def test_claimed_complete_primary_without_raw_evidence_still_checks_official(institutional_http):
    from data_fetch.institutional_provider import fetch_institutional_result
    value={**primary_old(),'latest_date':'2026-09-24','window_coverage_status':'complete'}
    result=fetch_institutional_result(FetchRequest.from_ticker('2330.TW'),fetch=lambda _:value)
    assert len(institutional_http)==5
    assert result.value['latest_date']=='2026-09-24'
    assert result.audit['official_recovery']['status']=='security_absent'
    assert result.audit['latest_session_admission']['eligible'] is False


def test_dated_report_does_not_accept_provider_ignoring_requested_date(monkeypatch, institutional_http):
    import external_http_client
    from data_fetch.institutional_provider import fetch_institutional_result
    monkeypatch.setattr(external_http_client,'sync_get',lambda *a,**kw:Response(t86('2026-08-01')))
    result=fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:primary_old())
    assert result.value['latest_date']=='2026-09-08'
    assert result.value['official_recovery']['status']=='unavailable'


def test_market_reports_are_shared_between_tickers(institutional_http):
    from data_fetch.institutional_provider import fetch_institutional_result
    fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:primary_old())
    second=fetch_institutional_result(FetchRequest.from_ticker('2330.TW'),fetch=lambda _:primary_old())
    assert len(institutional_http)==5
    assert all(row['cache_hit'] for row in second.audit['official_recovery']['reports'])


def test_twse_t86_timeout_uses_official_mirror_for_same_exact_report(monkeypatch, institutional_http):
    from requests.exceptions import Timeout
    import external_http_client
    from official_institutional_source import _fetch_report
    from search_provider_runtime import cooldown_state, scope_key

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs['timeout']))
        if len(calls) == 1:
            raise Timeout('primary T86 timed out')
        return Response(t86('2026-09-24'))

    monkeypatch.setattr(external_http_client, 'sync_get', get)
    report = _fetch_report('TWSE', '2026-09-24', 8)

    assert report['report_status'] == 'available'
    assert report['rows']['2321']['foreign'] == 1200
    assert [url.split('/')[2] for url, _ in calls] == ['www.twse.com.tw', 'wwwc.twse.com.tw']
    assert all('20260924' in url for url, _ in calls)
    assert calls[0][1] <= 5 and 0 < calls[1][1] <= 3
    assert report['source_url'].startswith('https://wwwc.twse.com.tw/')
    assert report['fallback_reason'] == 'timeout'
    assert cooldown_state(scope_key('TWSE T86', endpoint='institutional_daily')) == {}


def test_twse_t86_mirror_does_not_bypass_access_denial_or_wrong_date(monkeypatch, institutional_http):
    from requests.exceptions import HTTPError, Timeout
    from types import SimpleNamespace
    import external_http_client
    from official_institutional_source import _fetch_report

    calls = []

    def forbidden(url, **kwargs):
        calls.append(url)
        error = HTTPError('forbidden')
        error.response = SimpleNamespace(status_code=403, headers={})
        raise error

    monkeypatch.setattr(external_http_client, 'sync_get', forbidden)
    with pytest.raises(HTTPError):
        _fetch_report('TWSE', '2026-09-24', 8)
    assert len(calls) == 1 and 'www.twse.com.tw' in calls[0]

    from cache_store import set_cache_json
    from search_provider_runtime import scope_key
    set_cache_json(scope_key('TWSE T86', endpoint='institutional_daily'), {}, 1)
    calls.clear()

    def wrong_date(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise Timeout('primary timeout')
        return Response(t86('2026-09-23'))

    monkeypatch.setattr(external_http_client, 'sync_get', wrong_date)
    with pytest.raises(ValueError, match='date does not match'):
        _fetch_report('TWSE', '2026-09-24', 8)
    assert len(calls) == 2 and 'wwwc.twse.com.tw' in calls[1]


def test_institutional_workflow_recovers_latest_day_through_twse_mirror(monkeypatch, institutional_http):
    from requests.exceptions import Timeout
    from urllib.parse import parse_qs, urlparse
    import external_http_client
    from data_fetch.institutional_provider import fetch_institutional_result

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        day = parse_qs(urlparse(url).query)['date'][0]
        if len(calls) == 1:
            raise Timeout('primary latest day timeout')
        return Response(t86(day))

    monkeypatch.setattr(external_http_client, 'sync_get', get)
    result = fetch_institutional_result(FetchRequest.from_ticker('2321.TW'), fetch=lambda _: primary_old())

    assert result.value['latest_date'] == '2026-09-24'
    assert result.value['official_recovery']['reports'][0]['source_url'].startswith('https://wwwc.twse.com.tw/')
    assert len(calls) >= 2 and calls[0].startswith('https://www.twse.com.tw/')
    assert calls[1].startswith('https://wwwc.twse.com.tw/')


def test_conflicting_date_category_is_preserved_not_double_counted(institutional_http):
    from data_fetch.institutional_provider import fetch_institutional_result
    value=primary_old()
    value['latest_date']='2026-09-24'
    value['daily_category_observations']=[{'date':'2026-09-24','category':cat,'net_buy_shares':val,'source':value['source']}
                                         for cat,val in [('foreign',999),('investment_trust',-100),('dealer',30)]]
    result=fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:value)
    assert result.value['total_net_buy_shares']==929+4*1130
    conflict=result.value['official_recovery']['conflicts'][0]
    assert conflict['primary']['net_buy_shares']==999
    assert conflict['official']['net_buy_shares']==1200
    assert conflict['selected']=='primary'
    assert result.audit['coverage_status']=='partial'


def test_primary_empty_can_recover_actual_provider_and_acquisition_time(institutional_http):
    from data_fetch.institutional_provider import fetch_institutional_result
    result=fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:{})
    assert result.value['actual_provider']=='TWSE T86'
    assert result.value['latest_date']=='2026-09-24'
    assert result.audit['fetched_at_epoch'] is not None
    assert result.value['lookback_trading_days']==5


def test_tpex_institutional_category_contract_is_not_twse_column_mapping(monkeypatch,institutional_http):
    import external_http_client
    from data_fetch.institutional_provider import fetch_institutional_result
    from official_institutional_source import TPEX_FIELDS
    from urllib.parse import urlparse,parse_qs
    calls=[]
    def get(url,**kw):
        calls.append(url)
        day=parse_qs(urlparse(url).query)['date'][0].replace('/','')
        return Response({'stat':'ok','date':day,'tables':[{'fields':TPEX_FIELDS,'data':[
            ['6488','環球晶','2365104','4727374','-2362270','0','0','0','2365104','4727374','-2362270',
             '0','11000','-11000','9800','131796','-121996','324162','440170','-116008','333962','571966','-238004','-2611274']]}]})
    monkeypatch.setattr(external_http_client,'sync_get',get)
    result=fetch_institutional_result(FetchRequest.from_ticker('6488.TWO'),fetch=lambda _:{})
    assert result.value['total_net_buy_shares']==5*-2611274
    assert result.value['net_buy_shares_by_category']['dealer']==5*-238004
    assert result.value['actual_provider']=='TPEx dailyTrade'
    assert all('tpex.org.tw' in url for url in calls)


def test_missing_calendar_does_not_guess_business_days(monkeypatch,institutional_http):
    import data_freshness_market
    from data_fetch.institutional_provider import fetch_institutional_result
    monkeypatch.setattr(data_freshness_market,'market_calendar',lambda *a,**kw:{'coverage_status':'unknown'})
    result=fetch_institutional_result(FetchRequest.from_ticker('2321.TW'),fetch=lambda _:primary_old())
    assert not institutional_http
    assert result.audit['official_recovery']['status']=='calendar_unknown'
    assert result.value['latest_date']=='2026-09-08'


def test_borrowed_short_all_market_snapshot_is_shared(monkeypatch,institutional_http):
    import chip_data_fetcher
    calls=[]
    def get(url,**kw):
        calls.append(url)
        if 'tpex_margin_sbl' in url:return Response([SBL,{**SBL,'SecuritiesCompanyCode':'3324'}])
        return Response([{'Date':'1150924','SecuritiesCompanyCode':code,'MarginPurchaseBalance':'7'} for code in ('6488','3324')])
    monkeypatch.setattr(chip_data_fetcher,'_http_get',get)
    first=fetch_twse_margin_short_sales('6488.TWO')
    second=fetch_twse_margin_short_sales('3324.TWO')
    assert sum('tpex_margin_sbl' in url for url in calls)==1
    assert sum('tpex_mainboard_margin_balance' in url for url in calls)==1
    assert first['borrowed_short_cache_hit'] is False and second['borrowed_short_cache_hit'] is True


def test_borrowed_balance_must_reconcile_with_its_own_components():
    result=fetch_twse_margin_short_sales('6488.TWO',session=Session([{**SBL,'SecuritiesBorrowingBalanceOfTheMarketDay':'38539001'}]))
    assert result['borrowed_short_status'] != 'success'
