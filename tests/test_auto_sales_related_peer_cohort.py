"""Publisher related companies remain leads, never numeric comparability proof."""
from copy import deepcopy
from datetime import date,timedelta
from pathlib import Path
import json,time

import pytest


def page(day=None):
    day=day or date.today();stamp=day.strftime('%Y/%m/%d')
    rows=''.join(f"<tr><td><a href=\"javascript:Link2Stk('AS{code}');\">{code}{name}</a></td><td>{stamp}</td>"+'<td>1</td>'*8+'</tr>'for code,name in [('2891','中信金'),('2201','裕隆'),('2207','和泰車'),('2247','汎德永業')])
    return ('<html><head><title>同業股價表現-車輛相關-汽車銷售-台股-MoneyDJ理財網</title></head><body>'
        '<link rel="canonical" href="https://www.moneydj.com/Z/ZH/ZH0/ZH00/ZH00.djhtm?A=C022010"><table id="oMainTable"><tr id="oScrollHead"><td id="oHeadTitle">相關公司股價表現<div>報酬計算日期：'+day.strftime('%m/%d')+'</div></td></tr>'
        '<tr id="oScrollMenu">'+''.join('<td>'+v+'</td>'for v in ['股票名稱','最後交易 日期','收盤價','漲跌','漲跌幅','近一週 報酬','近一個月 報酬','近二個月 報酬','近三個月 報酬','今年以來 報酬'])+'</tr>'+rows+'</table></body></html>').encode('big5')


def master(day=None):
    day=day or date.today()
    return [{'stock_id':c,'stock_name':n,'type':m,'industry_category':category,'date':day.isoformat()}for c,n,m,category in [('2207','和泰車','twse','汽車工業'),('2247','汎德永業','twse','汽車工業'),('2201','裕隆','twse','汽車工業'),('2891','中信金','twse','金融保險')]]


def test_dated_related_cohort_excludes_bank_and_keeps_unranked_leads_only():
    from data_fetch.market_sources.auto_sales_related_peer_cohort import parse_page
    value=parse_page(page(),master(),today=date.today())
    assert [r['ticker']for r in value['candidates']]==['2201.TW','2247.TW']
    assert value['rejected_reason_counts']=={'different_exchange_category':1}
    for r in value['candidates']:
        assert r['comparison_status']=='industry_candidate_only'
        assert r['business_comparability_verified_current']is False
        assert r['numeric_comparability_verified']is False
        assert not any(k in r for k in('pe_ttm','roe_pct','ranking_position','price'))


@pytest.mark.parametrize('damage',['wrong_title','truncated','target_missing','target_name','foreign_link','duplicate_row','stale_day','future_day','master_name','master_market','master_stale'])
def test_incomplete_stale_or_wrong_identity_is_rejected(damage):
    from data_fetch.market_sources.auto_sales_related_peer_cohort import parse_page
    raw=page();rows=master();today=date.today()
    if damage=='wrong_title':raw=raw.replace('汽車銷售'.encode('big5'),'其他業'.encode('big5'))
    elif damage=='truncated':raw=raw.replace(b'</html>',b'')
    elif damage=='target_missing':raw=raw.replace(b'AS2207',b'AS9918')
    elif damage=='target_name':raw=raw.replace('2207和泰車'.encode('big5'),'2207錯公司'.encode('big5'))
    elif damage=='foreign_link':raw=raw.replace(b"javascript:Link2Stk('AS2247');",b'https://example.com/2247')
    elif damage=='duplicate_row':raw=raw.replace(b'</table>',raw[raw.rfind(b'<tr>'):raw.rfind(b'</table>')]+b'</table>')
    elif damage=='stale_day':raw=page(today-timedelta(days=8))
    elif damage=='future_day':raw=page(today+timedelta(days=1))
    elif damage=='master_name':rows[0]['stock_name']='錯公司'
    elif damage=='master_market':rows[0]['type']='tpex'
    else:rows=master(today-timedelta(days=8))
    with pytest.raises(ValueError):parse_page(raw,rows,today=today)


def test_complete_real_native_page_replays_six_identities_without_using_page_prices():
    from data_fetch.market_sources.auto_sales_related_peer_cohort import parse_page
    d=Path('/Volumes/X10 Pro Mac/stock-agent-archives/continuation-20261104-auto-sales-peer-research')
    if not(d/'identity-original.bin').is_file():pytest.skip('private preserved native originals unavailable')
    from data_fetch.market_sources.stock_identity_master import parse_master
    value=parse_page((d/'native-auto-cohort.body').read_bytes(),parse_master((d/'identity-original.bin').read_bytes()),today=date(2026,11,4))
    assert [r['ticker']for r in value['candidates']]==['2201.TW','2204.TW','2206.TW','2227.TW','2247.TW']
    assert value['raw_count']==6
    assert {r['publisher_observed_at']for r in value['candidates']}=={'2026-11-03'}


def bound_master():
    from official_response_evidence import archive_response
    from data_fetch.market_sources.stock_identity_master import MasterRows,URL,parse_master
    rows=[{'stock_id':str(1000+i),'stock_name':'Synthetic'+str(i),'industry_category':'其他','type':'twse','date':date.today().isoformat()}for i in range(800)]+[{'stock_id':str(i),'stock_name':'Parts'+str(i),'industry_category':'汽車工業','type':'twse','date':date.today().isoformat()}for i in range(2208,2219)]+master()
    raw=json.dumps({'status':200,'data':rows}).encode();receipt=archive_response(raw,source_url=URL,retrieved_at=time.time(),http_status=200)
    return MasterRows(parse_master(raw),{'raw_receipt':receipt})


class ReplayHttp:
    def __init__(self,*,cached=False,stamp=None):self.components=[];self.cached=cached;self.stamp=time.time()if stamp is None else stamp
    def get(self,url):
        self.components.append({'url':url,'http_request_sent':not self.cached,'cache_hit':self.cached,'fetched_at_epoch':self.stamp})
        return page()


def test_source_consumer_replays_both_originals_and_keeps_cache_epoch_and_zero_http():
    from data_fetch.market_sources.auto_sales_related_peer_cohort import get_candidates,verified_candidates
    from prompt_evidence import prompt_evidence_copy
    master_rows=bound_master();http=ReplayHttp(cached=True,stamp=time.time()-10)
    result=get_candidates('2207.TW',master_rows,today=date.today(),transport=http)
    assert result['status']=='skipped_fresh_cache'and result['source_audit']['http_request_count']==0
    records=deepcopy(result['candidates'])
    assert len(records)==2 and not verified_candidates(records,'2207.TW',today=date.today())
    for row in records:row['comparison_status']='business_industry_matched'
    assert verified_candidates(records,'2207.TW',today=date.today())
    assert records[0]['auto_sales_related_originals']['publication_receipt']['retrieved_at']==http.stamp
    before=deepcopy(records);assert 'raw_response_path'not in json.dumps(prompt_evidence_copy(records))and records==before


@pytest.mark.parametrize('damage',['master_body','publisher_body','publisher_epoch','manifest','peer_name','peer_ticker','policy','bank','false_industry'])
def test_unbound_candidate_or_original_cannot_survive_final_numeric_handoff(damage):
    from data_fetch.market_sources.auto_sales_related_peer_cohort import get_candidates,verified_candidates
    result=get_candidates('2207.TW',bound_master(),today=date.today(),transport=ReplayHttp())
    row=deepcopy(result['candidates'][0]);row['comparison_status']='business_industry_matched';p=row['auto_sales_related_originals']
    if damage=='master_body':p['master_receipt']['raw_response_sha256']='0'*64
    elif damage=='publisher_body':p['publication_receipt']['raw_response_sha256']='0'*64
    elif damage=='publisher_epoch':p['publication_receipt']['retrieved_at']+=1
    elif damage=='manifest':p['receipt_manifest']['raw_response_sha256']='0'*64
    elif damage=='peer_name':row['name']='錯公司'
    elif damage=='peer_ticker':row['ticker']='2330.TW'
    elif damage=='policy':p['policy']='unqualified'
    elif damage=='bank':row['ticker']='2891.TW';row['name']='中信金'
    else:row['comparison_status']='industry_candidate_only'
    assert not verified_candidates([row],'2207.TW',today=date.today())


@pytest.mark.parametrize('stamp',[None,True,float('nan'),-1])
def test_missing_or_invalid_publication_epoch_is_not_renewed(stamp):
    from data_fetch.market_sources.auto_sales_related_peer_cohort import get_candidates
    http=ReplayHttp();http.stamp=stamp
    result=get_candidates('2207.TW',bound_master(),today=date.today(),transport=http)
    assert result['status']=='error'and result['candidates']==[]


def test_unbound_master_cannot_trigger_publisher_request():
    from data_fetch.market_sources.auto_sales_related_peer_cohort import get_candidates
    http=ReplayHttp();result=get_candidates('2207.TW',master(),today=date.today(),transport=http)
    assert result['status']=='error'and not http.components


def pipeline(monkeypatch,*,quote_change=None,annual=True):
    import pandas as pd
    from data_fetch.market_sources import peers,auto_sales_related_peer_cohort as source
    rows=bound_master();monkeypatch.setattr(peers,'load_peer_stock_master',lambda:rows)
    native=source.get_candidates
    monkeypatch.setattr(peers,'get_auto_sales_related_candidates',lambda ticker,rows,**kw:native(ticker,rows,transport=ReplayHttp(),**kw))
    class Stock:
        def __init__(self,ticker):
            self.info={'symbol':ticker,'quoteType':'EQUITY','industry':'Auto & Truck Dealerships'if ticker=='2247.TW'else'Auto Parts',
                'grossMargins':.4,'operatingMargins':.2,'profitMargins':.1,'returnOnEquity':.1,'trailingPE':15,'priceToBook':2,'priceToSalesTrailing12Months':3,'totalRevenue':500,'totalAssets':1000}
            if ticker=='2247.TW'and quote_change:self.info.update(quote_change)
        @property
        def financials(self):return pd.DataFrame([[500]],index=['Total Revenue'],columns=pd.to_datetime(['2025-12-31']))if annual else pd.DataFrame()
        @property
        def balance_sheet(self):return pd.DataFrame([[1000]],index=['Total Assets'],columns=pd.to_datetime(['2025-12-31']))if annual else pd.DataFrame()
    monkeypatch.setattr(peers.yf,'Ticker',Stock)
    monkeypatch.setattr(peers,'fetch_peer_valuation_fallback',lambda *a,**kw:pytest.fail('no redundant valuation call'))
    return peers.fetch_dynamic_peer_metrics_with_diagnostics('2207.TW','和泰車','Industrials','Auto & Truck Dealerships',{})


def test_dynamic_peer_pipeline_acquires_a_true_matching_lead_without_promoting_bank_or_other_service(monkeypatch):
    value=pipeline(monkeypatch)
    assert [r['ticker']for r in value['peers']]==['2247.TW']
    r=value['peers'][0];assert r['metrics_status']=='complete'and r['asset_turnover']==.5
    assert r['business_comparability_verified_current']is False and r['numeric_comparability_verified']is False
    assert value['audit']['candidate_attempt_count']<=10 and value['audit']['business_industry_rejected_count']>=1


@pytest.mark.parametrize('change',[{'symbol':'2330.TW'},{'symbol':None},{'quoteType':'ETF'},{'quoteType':None},{'industry':None},{'industry':'Banks - Regional'}])
def test_publisher_membership_does_not_bypass_quote_identity_or_fine_industry(monkeypatch,change):
    assert pipeline(monkeypatch,quote_change=change)['peers']==[]


def test_quote_totals_do_not_replace_same_period_annual_asset_turnover(monkeypatch):
    value=pipeline(monkeypatch,annual=False);r=value['peers'][0]
    assert r['asset_turnover']is None and r['metrics_status']=='partial'


@pytest.mark.parametrize('damage',['canonical','calculation_day','duplicate_canonical','header','missing_cell','wrong_target_category','receipt_url','master_without_manifest'])
def test_published_identity_and_complete_table_contract_cannot_be_substituted(damage):
    from data_fetch.market_sources.auto_sales_related_peer_cohort import parse_page,get_candidates,verified_candidates
    raw=page();rows=master()
    if damage in ('receipt_url','master_without_manifest'):
        bound=bound_master();http=ReplayHttp()
        if damage=='master_without_manifest':
            bound.identity_master_metadata['raw_receipt']['source_url']='https://example.com/master'
            assert get_candidates('2207.TW',bound,today=date.today(),transport=http)['status']=='error'
            assert not http.components
        else:
            v=get_candidates('2207.TW',bound,today=date.today(),transport=http)
            row=deepcopy(v['candidates'][0]);row['comparison_status']='business_industry_matched'
            row['auto_sales_related_originals']['publication_receipt']['source_url']='https://www.moneydj.com/z/zh/zha/zh00_C099040.djhtm'
            assert not verified_candidates([row],'2207.TW',today=date.today())
        return
    if damage=='canonical':raw=raw.replace(b'C022010',b'C099040')
    elif damage=='calculation_day':raw=raw.replace(('報酬計算日期：'+date.today().strftime('%m/%d')).encode('big5'),'報酬計算日期：01/01'.encode('big5'))
    elif damage=='duplicate_canonical':raw=raw.replace(b'<table',b'<link rel="canonical" href="other"><table')
    elif damage=='header':raw=raw.replace('收盤價'.encode('big5'),'開盤價'.encode('big5'))
    elif damage=='missing_cell':raw=raw.replace(b'<td>1</td>',b'',1)
    else:rows[0]['industry_category']='其他'
    with pytest.raises(ValueError):parse_page(raw,rows,today=date.today())


def test_old_attempt_cap_omits_dealership_but_published_lead_enters_same_cap(monkeypatch):
    from data_fetch.market_sources.peer_recovery import resolve_legacy_peer_candidates
    from data_fetch.market_sources.peers import _prioritize_legacy_candidates
    rows=bound_master();old,_=resolve_legacy_peer_candidates('2207.TW',{},rows,today=date.today())
    assert '2247.TW' not in [r['ticker']for r in _prioritize_legacy_candidates('2207.TW',old)[:10]]
    value=pipeline(monkeypatch)
    assert [r['ticker']for r in value['peers']]==['2247.TW']
    assert value['audit']['candidate_attempt_count']<=10


def test_expired_publication_during_metrics_rejects_handoff(monkeypatch):
    from data_fetch.market_sources import peers
    import data_fetch.market_sources.auto_sales_related_peer_cohort as source
    original=source.replay_context
    calls=[]
    def expiry(context,**kw):
        calls.append(True)
        if len(calls)>1:raise ValueError('publisher expired during SDK work')
        return original(context,**kw)
    monkeypatch.setattr(source,'replay_context',expiry)
    value=pipeline(monkeypatch)
    assert value['peers']==[]
    assert value['audit']['published_auto_sales_related_status']=='originals_expired_or_unverified_after_metrics'
