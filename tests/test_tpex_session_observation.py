import copy,json
from datetime import date,datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import pytest
from data_fetch.market_sources import tpex_session_observation as t
from report_source_admission import price_admission
from maturity_source_admission import assess_maturity_source
F=Path(__file__).parent/'fixtures';RAW=(F/'tpex_3324_202610_raw.json').read_bytes();PAYLOAD=json.loads(RAW);META=json.loads((F/'tpex_3324_202610_metadata.json').read_text())

@pytest.fixture
def observation(monkeypatch,tmp_path):
    import runtime_paths
    from official_response_evidence import archive_response
    isolated_paths=runtime_paths.RuntimePaths.from_values(output_dir=tmp_path/'output',cache_dir=tmp_path)
    monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:isolated_paths)
    proof=archive_response(RAW,source_url=META['source_url'],retrieved_at=META['retrieved_at'],http_status=200)
    row=t.parse_observation(PAYLOAD,'3324.TWO','2026-10-07')
    return {**row,'ticker':'3324.TWO','raw_evidence':proof}

def test_real_monthly_response_selects_exact_daily_row_not_month_date():
    row=t.parse_observation(PAYLOAD,'3324.TWO','2026-10-07')
    assert row['date']=='2026-10-07' and PAYLOAD['date']=='20261001'
    assert (row['open'],row['high'],row['low'],row['close'])==(1540,1550,1485,1525)
    assert row['volume']==2721 and row['volume_unit']=='lots'
    assert row['volume_scope']=='tpex_stock_monthly_excluding_block_trades'
    assert 'quote_type' not in row and 'instrument_type_source' not in row
    assert t.source_url('3324.TWO','2026-10-07')==META['source_url']

@pytest.mark.parametrize('change',[lambda x:x.update(code='9999'),lambda x:x.update(date='20260901'),lambda x:x.update(flagField='股數'),lambda x:x['tables'][0]['data'].append(copy.deepcopy(x['tables'][0]['data'][-1])),lambda x:x['tables'][0]['data'].pop()])
def test_wrong_symbol_month_unit_duplicate_or_missing_day_rejected(change):
    value=copy.deepcopy(PAYLOAD);change(value)
    with pytest.raises(ValueError):t.parse_observation(value,'3324.TWO','2026-10-07')

@pytest.mark.parametrize('ticker',['3324.TW','3324','3324.TWO.EXTRA','0000.TWO'])
def test_no_cross_market_or_approximate_symbol_mapping(ticker):
    with pytest.raises(ValueError):t.parse_observation(PAYLOAD,ticker,'2026-10-07')

def test_archived_tpex_source_admission_and_maturity_keep_pit_finality_false(observation):
    raw=price_admission({'as_of':'2026-10-07','official_observation':observation},'3324.TWO')
    assert raw['eligible'], raw.get('reason')
    assert raw['historical_point_in_time_verified'] is False and raw['finality_guaranteed'] is False
    bar={'date':'2026-10-07',**{k:observation[k] for k in ['open','high','low','close']},'observation_provenance':{'official_observation':observation}}
    r=assess_maturity_source([bar],'3324.TWO','2026-10-07')
    assert r['eligible'] and r['finality_guaranteed'] is False and r['all_historical_bars_verified'] is False
    bar['close']+=1
    assert assess_maturity_source([bar],'3324.TWO','2026-10-07')['reason']=='maturity_provider_official_price_mismatch'

@pytest.mark.parametrize('field,value',[('date','2026-10-06'),('ticker','3324.TW'),('close',999),('volume_unit','shares'),('volume_scope','twse_general_odd_fixed_block_excluding_auction_tender')])
def test_official_excerpt_date_symbol_price_unit_scope_cannot_be_swapped(observation,field,value):
    observation[field]=value
    assert not price_admission({'as_of':'2026-10-07','official_observation':observation},'3324.TWO')['eligible']

def test_provisional_or_corrupt_raw_not_admitted(observation):
    proof=observation['raw_evidence'];proof['retrieved_at']='2026-10-07T13:00:00+00:00'
    assert price_admission({'as_of':'2026-10-07','official_observation':observation},'3324.TWO')['reason']=='official_price_observation_is_provisional'
    proof['retrieved_at']=META['retrieved_at'];Path(proof['raw_response_path']).write_bytes(b'corrupt')
    assert not price_admission({'as_of':'2026-10-07','official_observation':observation},'3324.TWO')['eligible']

@pytest.mark.parametrize('market',['TW','TWO'])
def test_fetcher_dispatch_attaches_only_exact_latest_market(monkeypatch,market):
    from market_price_history import fetch_backtest_bars
    from data_fetch.market_sources import twse_session_observation as tw
    calls=[]
    monkeypatch.setattr(t,'official_observation',lambda ticker,day:calls.append(('TWO',ticker,day)) or {'test':'tpex'})
    monkeypatch.setattr(tw,'official_observation',lambda ticker,day:calls.append(('TW',ticker,day)) or {'test':'twse'})
    frame=pd.DataFrame({'Open':[1540.0],'High':[1550.0],'Low':[1485.0],'Close':[1525.0]},index=pd.to_datetime(['2026-10-07']))
    def history(**kwargs):
        assert kwargs['auto_adjust'] is False and kwargs['actions'] is True
        return frame
    rows=fetch_backtest_bars('3324.'+market,date(2026,9,21),date(2026,10,7),ticker_factory=lambda ticker:SimpleNamespace(history=history),moment=datetime(2026,10,7,15,tzinfo=timezone.utc))
    assert calls==[(market,'3324.'+market,'2026-10-07')]
    assert rows[-1]['observation_provenance']['raw_http_retained'] is False

@pytest.mark.parametrize('meta',[{'stale':True},{'error_kind':'single_flight_busy'}])
def test_stale_or_busy_not_promoted_to_official_observation(monkeypatch,meta):
    monkeypatch.setattr(t,'shared_fetch',lambda *a,**k:({'row':{},'raw_evidence':{'status':'archived'}},meta))
    result=t.official_observation('3324.TWO','2026-10-07')
    assert result['status']=='unavailable' and 'raw_evidence' not in result and result['retrieved_at'] is None

def test_adapter_archives_actual_response_bytes_in_isolated_cache(monkeypatch,tmp_path):
    import runtime_paths,market_evidence_policy
    from official_response_evidence import read_response
    isolated_paths=runtime_paths.RuntimePaths.from_values(output_dir=tmp_path/'output',cache_dir=tmp_path)
    monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:isolated_paths)
    monkeypatch.setattr(market_evidence_policy,'acquisition_phase',lambda *a:'post_cutoff')
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs));return SimpleNamespace(content=RAW,status_code=200,json=lambda:json.loads(RAW))
    monkeypatch.setattr(t,'sync_get',get)
    monkeypatch.setattr(t,'shared_fetch',lambda key,fn,**kwargs:(fn(),{'cache_hit':False}))
    result=t.official_observation('3324.TWO','2026-10-07')
    assert calls[0][0]==t.DATED_URL and calls[0][1]['params']=={'code':'3324','date':'2026/10/01','response':'json'}
    assert calls[0][1]['timeout']==15
    assert read_response(result['raw_evidence'])==RAW
    assert result['price_basis']=='unadjusted_exchange_ohlc' and result['volume_unit']=='lots'
    assert result['historical_point_in_time_verified'] is False and result['finality_verified'] is False
    assert not {'quote_type','instrument_type_source'} & result.keys()
    assert result['raw_evidence']['retrieved_at']==result['retrieved_at']
