"""Captured OTC originals admit an unknown report without inferring its type."""
from copy import deepcopy
import json,time
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from fastapi import HTTPException
import pytest

import data_fetch.market_sources.twse_security_identity as source
from data_fetch.market_sources.official_company_legal_name import URLS
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
from test_report_security_identity_source_refresh import unknown_report,refresh
from test_report_refresh_acquisition_audit import init_db,events

FIXTURES=Path(__file__).parent/'fixtures/source_acquisition'
EPOCH=1791701709.0  # Captured 2026-10-11; master publication is 2026-10-10.


@pytest.fixture(autouse=True)
def isolated_circuit(monkeypatch):
    import os
    from provider_resilience import clear_provider_circuits,clear_provider_throttles
    assert os.environ.get('STOCK_AGENT_TEST_NO_NETWORK')=='1'
    clear_provider_circuits(source.PROVIDER);clear_provider_throttles(source.PROVIDER)
    monkeypatch.setattr(source,'time',SimpleNamespace(time=lambda:EPOCH+60,monotonic=time.monotonic))
    yield
    clear_provider_circuits(source.PROVIDER);clear_provider_throttles(source.PROVIDER)


def report():
    storage,name,keys,old=unknown_report('8069.TWO')
    old['data']['company_name']='元太'
    old['data']['company_identity']={'ticker':'8069.TWO','stock_id':'8069','official_name':'元太','instrument_type':'unknown'}
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    return storage,name,keys,old


def native(monkeypatch,*,change=None,cached=False):
    calls=[]
    identity=(FIXTURES/'eink8069_isin_native_20261011.html').read_bytes()
    master=(FIXTURES/'tpex_complete_company_master_native_20261011.json').read_bytes()
    def get(self,url):
        calls.append(url)
        assert url in {source.query_url('8069.TWO'),URLS['.TWO']}
        raw=master if url==URLS['.TWO']else identity
        if change:raw=change(url,raw)
        self.components.append({'url':url,'cache_hit':cached,'http_request_sent':not cached,'http_request_count':0 if cached else 1,'fetched_at_epoch':EPOCH})
        self.http_request_count+=0 if cached else 1
        return raw
    monkeypatch.setattr(IssuerNewsHttp,'get',get)
    return calls


def test_two_complete_official_originals_repair_unknown_OTC_context_and_admit_financial_refresh(tmp_path,monkeypatch):
    from annual_financial_source_refresh import validate_annual_refresh_context
    init_db();storage,name,keys,old=report();calls=native(monkeypatch)
    refresh(storage,name,tmp_path);saved=json.loads(storage.get_report(keys.data_key).content);data=saved['data']
    identity=data['security_identity']
    assert (identity['market'],identity['security_type'],identity['cfi_code'],data['instrument_type'])==('上櫃','股票','ESVUFR','EQUITY')
    assert identity['isin']=='TW0008069006'and identity['listed_company_legal_name']=='元太科技工業股份有限公司'
    assert set(identity['source_record_archive'])=={'identity','otc_master'}
    assert len(calls)==2 and calls[-1]==URLS['.TWO']
    assert source.verified_security_identity(identity,'8069.TWO')
    validate_annual_refresh_context(data,'8069.TWO',saved['source_audit'])
    for field in ['company_identity','current_price','revenue_ttm_raw','years','fcf_history']:assert data[field]==old['data'][field]
    assert data['taiwan_open_data']['other_original']is True and data['source_audit'][:-1]==old['source_audit']
    assert data['source_freshness']['taiwan_open_data']['fetched_at_epoch']<=old['source_audit'][-1]['fetched_at_epoch']
    assert saved['analysis_evidence']==old['analysis_evidence']
    for gate in ['report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:assert saved[gate]==old[gate]
    assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
    assert saved['decision_validity_status']=='needs_rerun'
    assert len(events())==1 and events()[0]['status']=='success'and events()[0]['record_count']==1


def test_OTC_full_raw_cache_is_usable_but_keeps_epoch_and_zero_new_acquisition(tmp_path,monkeypatch):
    init_db();storage,name,keys,_=report();native(monkeypatch,cached=True);refresh(storage,name,tmp_path)
    data=json.loads(storage.get_report(keys.data_key).content)['data'];identity=data['security_identity']
    assert identity['observed_at_epoch']==EPOCH
    assert all(v['retrieved_at']==EPOCH for v in identity['source_record_archive'].values())
    row=events()[0];assert row['status']=='skipped_fresh_cache'
    details=json.loads(row['details_json']);assert details['http_request_sent']is False
    assert data['source_audit'][-1]['http_request_count']==0


@pytest.mark.parametrize('ticker,fixture',[('8069.TW','eink8069_isin_native_20261011.html'),('6669.TWO','twse_isin_6669_captured_20261011.html')])
def test_suffix_must_match_explicit_native_market(ticker,fixture):
    with pytest.raises(ValueError):source.parse_security((FIXTURES/fixture).read_bytes(),ticker,EPOCH)


@pytest.mark.parametrize('bad',['CFI','security_type','duplicate','wrong_legal','wrong_schema','partial_master'])
def test_OTC_ambiguity_wrong_type_or_incomplete_master_cannot_change_report(tmp_path,monkeypatch,bad):
    init_db();storage,name,keys,_=report();before=storage.get_report(keys.data_key).content
    def change(url,raw):
        if url==URLS['.TWO']:
            rows=json.loads(raw)
            if bad=='wrong_legal':next(r for r in rows if r['SecuritiesCompanyCode']=='8069')['CompanyAbbreviation']='其他公司'
            elif bad=='wrong_schema':rows=[{'公司代號':r['SecuritiesCompanyCode'],'公司簡稱':r['CompanyAbbreviation'],'公司名稱':r['CompanyName'],'出表日期':r['Date']}for r in rows]
            elif bad=='partial_master':rows=[r for r in rows if r['SecuritiesCompanyCode']=='8069']
            return json.dumps(rows,ensure_ascii=False).encode()
        soup=BeautifulSoup(raw.decode('big5',errors='strict'),'html.parser')
        table=next(t for t in soup.find_all('table')if len(t.find_all('tr'))==2);row=table.find_all('tr')[-1]
        if bad=='CFI':row.find_all('td',recursive=False)[8].string='CEOGEU'
        elif bad=='security_type':row.find_all('td',recursive=False)[5].string='ETF'
        elif bad=='duplicate':table.append(deepcopy(row))
        return str(soup).encode('big5')
    native(monkeypatch,change=change)
    with pytest.raises(HTTPException)as err:refresh(storage,name,tmp_path)
    assert err.value.status_code==502 and storage.get_report(keys.data_key).content==before
    assert len(events())==1 and events()[0]['record_count']==0


def test_OTC_receipt_cannot_substitute_listed_master_or_market_suffix(monkeypatch):
    native(monkeypatch);value=source.fetch_security_identity('8069.TWO',diagnostics={})
    assert source.verified_security_identity(value,'8069.TWO')
    changed=deepcopy(value);changed['source_record_archive']['otc_master']['source_url']=URLS['.TW']
    assert not source.verified_security_identity(changed,'8069.TWO')
    changed=deepcopy(value);changed['source_record_archive']['listed_master']=changed['source_record_archive'].pop('otc_master')
    assert not source.verified_security_identity(changed,'8069.TWO')
    assert not source.verified_security_identity(value,'8069.TW')
