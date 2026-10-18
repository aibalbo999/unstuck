"""Official quotes include ETF identifiers; strategy gates remain independent."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from data_fetch.market_sources import twse_session_observation as source
from report_source_admission import price_admission
from maturity_source_admission import assess_maturity_source

BODY=gzip.decompress((Path(__file__).parent/'fixtures/twse_oct8_official_quotes.json.gz').read_bytes())
PAYLOAD=json.loads(BODY)
HASH='ba55492dbf86f5acb728e6d0fafa5fa5a1a0e47ad8641bc696849362b977cfb9'

@pytest.mark.parametrize('code',['2330','0050','0056','00636','006208','00632R','00400A'])
def test_saved_quote_identifiers_remain_exact_in_official_table(code):
    assert hashlib.sha256(BODY).hexdigest()==HASH
    before=copy.deepcopy(PAYLOAD)
    parsed=source.parse_session(PAYLOAD,'2026-10-08')
    assert code in parsed and PAYLOAD==before
    assert parsed[code]['date']=='2026-10-08'
    assert parsed[code]['volume_scope_verified'] is True
    if code=='0050':
        assert [parsed[code][field] for field in ['open','high','low','close']]==[115.35,115.55,114.9,114.95]
        assert parsed[code]['volume']==99877876  # shares, never lots

@pytest.fixture
def official_call(monkeypatch,tmp_path):
    from cache_backends import InMemoryCache
    import cache_store
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr('runtime_paths.current_runtime_paths',lambda:SimpleNamespace(cache_dir=tmp_path))
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(content=BODY,status_code=200,json=lambda:copy.deepcopy(PAYLOAD))
    monkeypatch.setattr(source,'sync_get',get)
    monkeypatch.setattr('market_evidence_policy.acquisition_phase',lambda *a:'post_cutoff')
    yield calls
    cache_store.reset_cache_store_for_tests()


def test_stock_and_etf_share_new_cache_with_exact_raw_receipt_and_maturity_gate(official_call):
    stock=source.official_observation('2330.TW','2026-10-08')
    etf=source.official_observation('0050.TW','2026-10-08')
    assert len(official_call)==1 and stock['status']==etf['status']=='observed'
    assert etf['ticker']=='0050.TW' and etf['volume_unit']=='shares'
    assert etf['cache_hit'] is True and ':v4:' in etf['cache_key']
    assert etf['raw_evidence']['raw_response_sha256']==HASH
    assert etf['raw_evidence']['evidence_kind']=='raw_http_response_bytes'
    assert etf['price_basis']=='unadjusted_exchange_ohlc'
    assert etf['historical_point_in_time_verified'] is False
    assert price_admission({'as_of':'2026-10-08','official_observation':etf},'0050.TW')['eligible'] is True
    bar={field:etf[field] for field in ['date','open','high','low','close']}
    bar['observation_provenance']={'official_observation':etf}
    assert assess_maturity_source([bar],'0050.TW','2026-10-08')['eligible'] is True
    bar['close']=114.8
    assert assess_maturity_source([bar],'0050.TW','2026-10-08')['reason']=='maturity_provider_official_price_mismatch'
    # A cross-market ticker cannot borrow the TWSE archived quote.
    assert not price_admission({'as_of':'2026-10-08','official_observation':etf},'0050.TWO')['eligible']

@pytest.mark.parametrize('ticker',['0050.TWO','2330.TWO','0050.US','50.TW','００５０.TW','0050.TW.extra','0050','ABC.TW'])
def test_wrong_market_or_nonexact_identity_never_queries_official_source(monkeypatch,ticker):
    monkeypatch.setattr(source,'sync_get',lambda *a,**k:pytest.fail('unexpected HTTP'))
    monkeypatch.setattr(source,'shared_fetch',lambda *a,**k:pytest.fail('unexpected cache lookup'))
    assert source.official_observation(ticker,'2026-10-08')['status']=='not_applicable'

@pytest.mark.parametrize('change',['date','unit','corrupt_raw'])
def test_date_share_unit_and_raw_integrity_are_not_relaxed(official_call,change):
    if change=='date':
        with pytest.raises(ValueError):source.parse_session(PAYLOAD,'2026-10-07')
    elif change=='unit':
        payload=copy.deepcopy(PAYLOAD)
        for table in payload['tables']:
            if '成交股數' in table.get('fields',[]):
                table['fields'][table['fields'].index('成交股數')]='成交張數'
        with pytest.raises(ValueError):source.parse_session(payload,'2026-10-08')
    else:
        etf=source.official_observation('0050.TW','2026-10-08')
        Path(etf['raw_evidence']['raw_response_path']).write_bytes(gzip.compress(b'changed'))
        result=price_admission({'as_of':'2026-10-08','official_observation':etf},'0050.TW')
        assert result['eligible'] is False and result['reason']=='official_price_raw_evidence_invalid'
