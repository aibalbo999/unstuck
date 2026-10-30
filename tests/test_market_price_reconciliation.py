from datetime import date
from copy import deepcopy
import pandas as pd
import pytest
from market_price_reconciliation import CONTRACT,reconcile
from short_term_market_data import build_short_term_market_context
from data_fetch.yfinance_enrichment_extractors import extract_market_history_bundle
from data_fetch.market_sources import twse_session_observation as source


def daily(volume=1000):
    bar={'date':'2026-10-02','open':67.,'high':69.6,'low':66.8,'close':68.3,'volume':1000.}
    return {'bars':[bar],'volume_unit':'shares','source':'provider','price_basis_contract':CONTRACT,'price_adjustment_basis':'adjusted analysis','volume_basis':'provider shares','provider_raw_observation':{**bar,'ticker':'1301.TW','volume_unit':'shares','retrieved_at':'2026-10-02T15:46:00+00:00'},'official_observation':{**bar,'ticker':'1301.TW','volume':volume,'status':'observed','volume_unit':'shares','retrieved_at':'2026-10-02T13:17:00+00:00'}}


def test_float_noise_matches_but_one_legal_tick_does_not():
    data=daily();data['provider_raw_observation']['close']=68.30000305175781
    assert reconcile(data)['price_status']=='matched_sample_session'
    data['provider_raw_observation']['close']=68.4
    assert reconcile(data)['price_status']=='different'


def test_same_units_but_different_volumes_disable_cross_provider_normalization():
    result=reconcile(daily(1001))
    assert result['price_status']=='matched_sample_session'
    assert result['volume']['delta']==-1 and result['volume']['status']=='different'
    assert result['cross_provider_flow_normalization_allowed'] is False
    assert result['actionable'] is False and result['strategy_results_verified'] is False


@pytest.mark.parametrize('key,value',[('date','2026-10-01'),('ticker','6456.TW'),('status','unavailable')])
def test_other_session_symbol_or_missing_official_response_never_matches(key,value):
    data=daily();data['official_observation'][key]=value
    result=reconcile(data);assert result['session_aligned'] is False and result['price_status']=='unverified'


def test_unknown_volume_is_not_zero_and_adjusted_prices_are_not_raw_execution():
    data=daily();data['provider_raw_observation']['volume']=None;data['bars'][0]['close']=34.15
    result=reconcile(data);assert result['volume']['status']=='unverified' and result['volume']['delta'] is None
    assert result['adjustments']['close']['factor']==pytest.approx(.5) and result['actionable'] is False


def test_prompt_recalculation_preserves_basis_without_mutation_and_excludes_future_observation():
    data=daily();original=deepcopy(data)
    context=build_short_term_market_context({'daily_market_data':data},as_of=date(2026,10,2))
    assert context['daily_market_data']['price_adjustment_basis']=='adjusted analysis'
    assert context['technical_indicators']['price_adjustment_basis']=='adjusted analysis'
    assert context['technical_indicators']['volume_basis']=='provider shares'
    assert len(context['technical_indicators']['input_window']['bars_sha256'])==64
    assert data==original
    earlier=build_short_term_market_context({'daily_market_data':data},as_of=date(2026,10,1))
    assert 'official_observation' not in earlier['daily_market_data']
    assert earlier['daily_market_data']['price_reconciliation']['price_status']=='unverified'


def test_single_raw_fetch_supplies_adjusted_analysis_and_exact_raw_observation(monkeypatch):
    monkeypatch.setattr(source,'official_observation',lambda ticker,day:{**daily()['official_observation'],'date':day,'ticker':ticker})
    class Stock:
        ticker='1301.TW'
        calls=[]
        def history(self,period,*,auto_adjust,end=None):
            self.calls.append((period,auto_adjust))
            return pd.DataFrame({'Open':[100,50],'High':[102,52],'Low':[98,48],'Close':[100,50],'Adj Close':[50,50],'Volume':[1000,2000]},index=pd.to_datetime(['2026-10-01','2026-10-02']))
    stock=Stock();bundle=extract_market_history_bundle(stock,as_of=date(2026,10,2));data=bundle['daily_market_data']
    assert stock.calls==[('5y',False)]
    assert [x['close'] for x in data['bars']]==[50,50]
    assert [x['volume'] for x in data['bars']]==[1000,2000]
    assert data['provider_raw_observation']['close']==50
    assert data['price_basis_contract']==CONTRACT


def test_missing_adjustment_factor_not_assumed_one(monkeypatch):
    monkeypatch.setattr(source,'official_observation',lambda *args:{'status':'unavailable'})
    class Stock:
        ticker='1301.TW'
        def history(self,**kwargs):return pd.DataFrame({'Close':[100]},index=pd.to_datetime(['2026-10-02']))
    result=extract_market_history_bundle(Stock(),as_of=date(2026,10,2))
    assert result['daily_market_data']['bars']==[]
    assert result['daily_market_data']['provider_raw_observation']['close']==100
    assert result['technical_indicators']['sma_5'] is None


def official_payload(day='20261002'):
    return {'stat':'OK','date':day,'tables':[{'fields':['證券代號','開盤價','最高價','最低價','收盤價','成交股數'],'data':[['1301','67','69.6','66.8','68.3','33,115,055']]}]}


def test_official_parser_validates_exact_date_and_named_ohlcv_fields():
    parsed=source.parse_session(official_payload(),'2026-10-02');assert parsed['1301']['volume']==33115055
    with pytest.raises(ValueError):source.parse_session(official_payload('20261001'),'2026-10-02')
    with pytest.raises(ValueError):source.parse_session({'stat':'OK','date':'20261002','tables':[]},'2026-10-02')


def test_official_cache_preserves_true_acquisition_time_and_symbol_scope(monkeypatch):
    seen=[]
    value={'rows':source.parse_session(official_payload(),'2026-10-02'),'retrieved_at':'2026-10-02T13:17:00+00:00','response_sha256':'x'}
    monkeypatch.setattr(source,'shared_fetch',lambda key,fetch,**kwargs:(seen.append(key) or value,{'cache_hit':True,'stale':False}))
    first=source.official_observation('1301.TW','2026-10-02');second=source.official_observation('1301.TW','2026-10-02')
    assert first['retrieved_at']==second['retrieved_at']==value['retrieved_at'] and first['cache_hit'] is True
    assert source.official_observation('1301.TWO','2026-10-02')['status']=='not_applicable'
    assert source.official_observation('9999.TW','2026-10-02')['status']=='symbol_missing'


def test_old_cache_without_basis_contract_is_rejected_without_overwrite():
    from data_fetch.constants import DATA_SCHEMA_VERSION,REQUIRED_DATA_SCHEMA_FIELDS
    from data_fetch.yfinance_cache_gate import build_fresh_cache_payload
    cached={field:{} for field in REQUIRED_DATA_SCHEMA_FIELDS};cached.update(data_schema_version=DATA_SCHEMA_VERSION,ticker='1301.TW',daily_market_data=daily());cached['daily_market_data'].pop('price_basis_contract');before=deepcopy(cached)
    result=build_fresh_cache_payload('1301.TW',cached,assess_cached=lambda *_:(True,{}),append_cache_audit=lambda *_:None,now_epoch=0)
    assert result==(None,['market_data'],True) and cached==before


def test_official_failed_or_stale_cache_cannot_become_observed(monkeypatch):
    value={'rows':source.parse_session(official_payload(),'2026-10-02'),'retrieved_at':'2026-10-02T13:17:00+00:00'}
    monkeypatch.setattr(source,'shared_fetch',lambda *a,**kw:(value,{'cache_hit':True,'stale':True,'error_kind':'timeout'}))
    result=source.official_observation('1301.TW','2026-10-02')
    assert result['status']=='unavailable' and result['retrieved_at'] is None


def test_raw_ohlc_mismatch_blocks_new_report_observation_gate():
    from reporting.content_credibility_observations import evaluate_observation_credibility
    data=daily();data['as_of']='2026-10-02';data['requested_as_of']='2026-10-02';data['provider_raw_observation']['close']=68.4
    result=evaluate_observation_credibility({'parsed':{}},{'generated_at':'2026-10-02T18:00:00+08:00'},{'ticker':'1301.TW','current_price':68.3,'daily_market_data':data},'v4')
    assert 'v4_official_raw_price_mismatch' in {x['id'] for x in result['blocking_issues']}
    assert result['checks'][0]['details']['price_reconciliation']['price_status']=='different'


def test_indicator_volume_mean_never_splices_official_latest_volume(monkeypatch):
    monkeypatch.setattr(source,'official_observation',lambda ticker,day:{**daily(2000)['official_observation'],'date':day,'ticker':ticker})
    class Stock:
        ticker='1301.TW'
        def history(self,**kwargs):
            from market_calendar_store import load_market_calendar
            holidays = set(load_market_calendar('tw', 2026)['holidays'])
            days = [day for day in pd.bdate_range(end='2026-10-02',periods=30)
                    if day.date().isoformat() not in holidays][-20:]
            return pd.DataFrame({'Close':[68.3]*20,'Adj Close':[68.3]*20,'Open':[67]*20,'High':[69.6]*20,'Low':[66.8]*20,'Volume':[1000]*20},index=days)
    bundle=extract_market_history_bundle(Stock(),as_of=date(2026,10,2))
    assert bundle['technical_indicators']['volume_latest']==1000
    assert bundle['technical_indicators']['volume_sma_20']==1000
    assert bundle['technical_indicators']['volume_ratio_20']==1
    assert bundle['daily_market_data']['price_reconciliation']['cross_provider_flow_normalization_allowed'] is False


def test_history_request_has_explicit_exclusive_end_after_verified_session(monkeypatch):
    monkeypatch.setattr(source,'official_observation',lambda *args:{'status':'unavailable'})
    class Stock:
        ticker='1301.TW'
        query=None
        def history(self,**kwargs):
            self.query=kwargs
            return pd.DataFrame({'Close':[100],'Adj Close':[100]},index=pd.to_datetime(['2026-10-02']))
    stock=Stock();bundle=extract_market_history_bundle(stock,as_of=date(2026,10,3))
    assert stock.query=={'period':'5y','auto_adjust':False,'end':'2026-10-03'}
    assert bundle['daily_market_data']['history_query']['expected_completed_session']=='2026-10-02'
    assert bundle['daily_market_data']['as_of']=='2026-10-02'


def test_us_default_query_does_not_apply_taiwan_session_calendar(monkeypatch):
    monkeypatch.setattr(source,'official_observation',lambda *args:{'status':'not_applicable'})
    class Stock:
        ticker='AAPL'
        query=None
        def history(self,**kwargs):
            self.query=kwargs
            return pd.DataFrame({'Close':[100],'Adj Close':[100]},index=pd.to_datetime(['2026-10-01']))
    stock=Stock();bundle=extract_market_history_bundle(stock)
    assert stock.query=={'period':'5y','auto_adjust':False}
    assert bundle['daily_market_data']['history_query']['calendar_verified'] is False


def test_missing_provider_latest_close_is_recovered_only_from_exact_compatible_session(monkeypatch):
    from data_fetch.market_sources import yfinance_session_recovery as recovery
    monkeypatch.setattr(source,'official_observation',lambda ticker,day:{**daily()['official_observation'],'ticker':ticker,'date':day})
    monkeypatch.setattr(recovery,'shared_fetch',lambda key,fetch,**kw:(fetch(),{'cache_hit':False}))
    class Stock:
        ticker='1301.TW'
        calls=[]
        def history(self,**query):
            self.calls.append(query)
            if 'start' in query:return pd.DataFrame({'Open':[67],'High':[69.6],'Low':[66.8],'Close':[68.3],'Adj Close':[68.3],'Volume':[1000]},index=pd.to_datetime(['2026-10-02']))
            return pd.DataFrame({'Open':[67,67],'High':[69.6,69.6],'Low':[66.8,66.8],'Close':[68.3,float('nan')],'Adj Close':[68.3,float('nan')],'Volume':[1000,1000]},index=pd.to_datetime(['2026-10-01','2026-10-02']))
    stock=Stock();bundle=extract_market_history_bundle(stock,as_of=date(2026,10,3))
    assert len(stock.calls)==2 and stock.calls[1]['start']=='2026-10-02'
    assert bundle['daily_market_data']['as_of']=='2026-10-02'
    assert bundle['daily_market_data']['session_recovery']['adopted'] is True
    assert bundle['daily_market_data']['provider_raw_observation']['retrieved_at']==bundle['daily_market_data']['session_recovery']['retrieved_at']


@pytest.mark.parametrize('bad',['wrong_date','conflict','missing_adj','unavailable'])
def test_short_session_recovery_failure_never_fills_or_redates_original(bad,monkeypatch):
    from data_fetch.market_sources import yfinance_session_recovery as recovery
    raw=pd.DataFrame({'Open':[67],'High':[69.6],'Low':[66.8],'Close':[float('nan')],'Adj Close':[float('nan')],'Volume':[1000]},index=pd.to_datetime(['2026-10-02']))
    class Stock:
        ticker='1301.TW'
        def history(self,**kwargs):
            if bad=='unavailable':return pd.DataFrame()
            return pd.DataFrame({'Open':[68 if bad=='conflict' else 67],'High':[69.6],'Low':[66.8],'Close':[68.3],'Adj Close':[float('nan') if bad=='missing_adj' else 68.3],'Volume':[1000]},index=pd.to_datetime(['2026-10-01' if bad=='wrong_date' else '2026-10-02']))
    def fake_cache(key,fetch,**kw):
        try:return fetch(),{'cache_hit':False}
        except ValueError:return None,{'error_kind':'ValueError'}
    monkeypatch.setattr(recovery,'shared_fetch',fake_cache)
    frame,receipt=recovery.recover_session(Stock(),raw,'2026-10-02',as_of=date(2026,10,3))
    assert receipt['adopted'] is False and pd.isna(frame.iloc[-1]['Close'])
    pd.testing.assert_frame_equal(raw,frame)
