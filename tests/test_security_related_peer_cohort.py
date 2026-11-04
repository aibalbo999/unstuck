"""Publisher related companies remain leads, never numeric comparability proof."""
from copy import deepcopy
from datetime import date,timedelta
from pathlib import Path
import json,time

import pytest


def page(day=None):
    day=day or date.today();stamp=day.strftime('%Y/%m/%d')
    rows=''.join(f"<tr><td><a href=\"javascript:Link2Stk('AS{code}');\">{code}{name}</a></td><td>{stamp}</td>"+'<td>1</td>'*8+'</tr>'for code,name in [('2891','中信金'),('6721','信實'),('9917','中保科'),('9925','新保')])
    return ('<html><head><title>同業股價表現-傳產其他-保全業-台股-MoneyDJ理財網</title></head><body>'
        '<table id="oMainTable"><tr id="oScrollHead"><td id="oHeadTitle">相關公司股價表現</td></tr>'
        '<tr id="oScrollMenu">'+''.join('<td>'+v+'</td>'for v in ['股票名稱','最後交易 日期','收盤價','漲跌','漲跌幅','近一週 報酬','近一個月 報酬','近二個月 報酬','近三個月 報酬','今年以來 報酬'])+'</tr>'+rows+'</table></body></html>').encode('big5')


def master(day=None):
    day=day or date.today()
    return [{'stock_id':c,'stock_name':n,'type':m,'industry_category':category,'date':day.isoformat()}for c,n,m,category in [('9917','中保科','twse','其他'),('9925','新保','twse','其他'),('6721','信實','tpex','其他'),('2891','中信金','twse','金融保險')]]


def test_dated_related_cohort_excludes_bank_and_keeps_unranked_leads_only():
    from data_fetch.market_sources.security_related_peer_cohort import parse_page
    value=parse_page(page(),master(),today=date.today())
    assert [r['ticker']for r in value['candidates']]==['6721.TWO','9925.TW']
    assert value['rejected_reason_counts']=={'different_exchange_category':1}
    for r in value['candidates']:
        assert r['comparison_status']=='industry_candidate_only'
        assert r['business_comparability_verified_current']is False
        assert r['numeric_comparability_verified']is False
        assert not any(k in r for k in('pe_ttm','roe_pct','ranking_position','price'))


@pytest.mark.parametrize('damage',['wrong_title','truncated','target_missing','target_name','foreign_link','duplicate_row','stale_day','future_day','master_name','master_market','master_stale'])
def test_incomplete_stale_or_wrong_identity_is_rejected(damage):
    from data_fetch.market_sources.security_related_peer_cohort import parse_page
    raw=page();rows=master();today=date.today()
    if damage=='wrong_title':raw=raw.replace('保全業'.encode('big5'),'其他業'.encode('big5'))
    elif damage=='truncated':raw=raw.replace(b'</html>',b'')
    elif damage=='target_missing':raw=raw.replace(b'AS9917',b'AS9918')
    elif damage=='target_name':raw=raw.replace('9917中保科'.encode('big5'),'9917錯公司'.encode('big5'))
    elif damage=='foreign_link':raw=raw.replace(b"javascript:Link2Stk('AS9925');",b'https://example.com/9925')
    elif damage=='duplicate_row':raw=raw.replace(b'</table>',raw[raw.rfind(b'<tr>'):raw.rfind(b'</table>')]+b'</table>')
    elif damage=='stale_day':raw=page(today-timedelta(days=8))
    elif damage=='future_day':raw=page(today+timedelta(days=1))
    elif damage=='master_name':rows[0]['stock_name']='錯公司'
    elif damage=='master_market':rows[0]['type']='tpex'
    else:rows=master(today-timedelta(days=8))
    with pytest.raises(ValueError):parse_page(raw,rows,today=today)


def test_actual_native_original_keeps_2891_out_of_the_candidate_list():
    from data_fetch.market_sources.security_related_peer_cohort import parse_page
    d=Path('/Volumes/X10 Pro Mac/stock-agent-archives/continuation-20261104-independent-gap-triage/security-cohort-research')
    if not(d/'identity-original.bin').is_file():pytest.skip('private preserved native originals unavailable')
    from data_fetch.market_sources.stock_identity_master import parse_master
    value=parse_page((d/'observed-response-1.bin').read_bytes(),parse_master((d/'identity-original.bin').read_bytes()),today=date(2026,11,4))
    assert [r['ticker']for r in value['candidates']]==['6721.TWO','9925.TW']
    assert value['raw_count']==4


def bound_master():
    from official_response_evidence import archive_response
    from data_fetch.market_sources.stock_identity_master import MasterRows,URL,parse_master
    rows=[{'stock_id':str(1000+i),'stock_name':'Synthetic'+str(i),'industry_category':'其他','type':'twse','date':date.today().isoformat()}for i in range(800)]+master()
    raw=json.dumps({'status':200,'data':rows}).encode();receipt=archive_response(raw,source_url=URL,retrieved_at=time.time(),http_status=200)
    return MasterRows(parse_master(raw),{'raw_receipt':receipt})


class ReplayHttp:
    def __init__(self,*,cached=False,stamp=None):self.components=[];self.cached=cached;self.stamp=time.time()if stamp is None else stamp
    def get(self,url):
        self.components.append({'url':url,'http_request_sent':not self.cached,'cache_hit':self.cached,'fetched_at_epoch':self.stamp})
        return page()


def test_source_consumer_replays_both_originals_and_keeps_cache_epoch_and_zero_http():
    from data_fetch.market_sources.security_related_peer_cohort import get_candidates,verified_candidates
    from prompt_evidence import prompt_evidence_copy
    master_rows=bound_master();http=ReplayHttp(cached=True,stamp=time.time()-10)
    result=get_candidates('9917.TW',master_rows,today=date.today(),transport=http)
    assert result['status']=='skipped_fresh_cache'and result['source_audit']['http_request_count']==0
    records=deepcopy(result['candidates'])
    assert len(records)==2 and not verified_candidates(records,'9917.TW',today=date.today())
    for row in records:row['comparison_status']='business_industry_matched'
    assert verified_candidates(records,'9917.TW',today=date.today())
    assert records[0]['security_related_originals']['publication_receipt']['retrieved_at']==http.stamp
    before=deepcopy(records);assert 'raw_response_path'not in json.dumps(prompt_evidence_copy(records))and records==before


@pytest.mark.parametrize('damage',['master_body','publisher_body','publisher_epoch','manifest','peer_name','peer_ticker','policy','bank','false_industry'])
def test_unbound_candidate_or_original_cannot_survive_final_numeric_handoff(damage):
    from data_fetch.market_sources.security_related_peer_cohort import get_candidates,verified_candidates
    result=get_candidates('9917.TW',bound_master(),today=date.today(),transport=ReplayHttp())
    row=deepcopy(result['candidates'][0]);row['comparison_status']='business_industry_matched';p=row['security_related_originals']
    if damage=='master_body':p['master_receipt']['raw_response_sha256']='0'*64
    elif damage=='publisher_body':p['publication_receipt']['raw_response_sha256']='0'*64
    elif damage=='publisher_epoch':p['publication_receipt']['retrieved_at']+=1
    elif damage=='manifest':p['receipt_manifest']['raw_response_sha256']='0'*64
    elif damage=='peer_name':row['name']='錯公司'
    elif damage=='peer_ticker':row['ticker']='2330.TW'
    elif damage=='policy':p['policy']='unqualified'
    elif damage=='bank':row['ticker']='2891.TW';row['name']='中信金'
    else:row['comparison_status']='industry_candidate_only'
    assert not verified_candidates([row],'9917.TW',today=date.today())


@pytest.mark.parametrize('stamp',[None,True,float('nan'),-1])
def test_missing_or_invalid_publication_epoch_is_not_renewed(stamp):
    from data_fetch.market_sources.security_related_peer_cohort import get_candidates
    http=ReplayHttp();http.stamp=stamp
    result=get_candidates('9917.TW',bound_master(),today=date.today(),transport=http)
    assert result['status']=='error'and result['candidates']==[]


def test_unbound_master_cannot_trigger_publisher_request():
    from data_fetch.market_sources.security_related_peer_cohort import get_candidates
    http=ReplayHttp();result=get_candidates('9917.TW',master(),today=date.today(),transport=http)
    assert result['status']=='error'and not http.components


def pipeline(monkeypatch,*,quote_change=None,annual=True):
    import pandas as pd
    from data_fetch.market_sources import peers,security_related_peer_cohort as source
    rows=bound_master();monkeypatch.setattr(peers,'load_peer_stock_master',lambda:rows)
    native=source.get_candidates
    monkeypatch.setattr(peers,'get_security_related_candidates',lambda ticker,rows,**kw:native(ticker,rows,transport=ReplayHttp(),**kw))
    class Stock:
        def __init__(self,ticker):
            self.info={'symbol':ticker,'quoteType':'EQUITY','industry':'Security & Protection Services'if ticker=='9925.TW'else'Specialty Business Services',
                'grossMargins':.4,'operatingMargins':.2,'profitMargins':.1,'returnOnEquity':.1,'trailingPE':15,'priceToBook':2,'priceToSalesTrailing12Months':3,'totalRevenue':500,'totalAssets':1000}
            if ticker=='9925.TW'and quote_change:self.info.update(quote_change)
        @property
        def financials(self):return pd.DataFrame([[500]],index=['Total Revenue'],columns=pd.to_datetime(['2025-12-31']))if annual else pd.DataFrame()
        @property
        def balance_sheet(self):return pd.DataFrame([[1000]],index=['Total Assets'],columns=pd.to_datetime(['2025-12-31']))if annual else pd.DataFrame()
    monkeypatch.setattr(peers.yf,'Ticker',Stock)
    monkeypatch.setattr(peers,'fetch_peer_valuation_fallback',lambda *a,**kw:pytest.fail('no redundant valuation call'))
    return peers.fetch_dynamic_peer_metrics_with_diagnostics('9917.TW','中保科','Industrials','Security & Protection Services',{})


def test_dynamic_peer_pipeline_acquires_a_true_matching_lead_without_promoting_bank_or_other_service(monkeypatch):
    value=pipeline(monkeypatch)
    assert [r['ticker']for r in value['peers']]==['9925.TW']
    r=value['peers'][0];assert r['metrics_status']=='complete'and r['asset_turnover']==.5
    assert r['business_comparability_verified_current']is False and r['numeric_comparability_verified']is False
    assert value['audit']['candidate_attempt_count']==2 and value['audit']['business_industry_rejected_count']==1


@pytest.mark.parametrize('change',[{'symbol':'2330.TW'},{'symbol':None},{'quoteType':'ETF'},{'quoteType':None},{'industry':None},{'industry':'Banks - Regional'}])
def test_publisher_membership_does_not_bypass_quote_identity_or_fine_industry(monkeypatch,change):
    assert pipeline(monkeypatch,quote_change=change)['peers']==[]


def test_quote_totals_do_not_replace_same_period_annual_asset_turnover(monkeypatch):
    value=pipeline(monkeypatch,annual=False);r=value['peers'][0]
    assert r['asset_turnover']is None and r['metrics_status']=='partial'
