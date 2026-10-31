"""Official security classification admits missing contexts without quote renewal."""
import asyncio,json,time
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import pytest
from fastapi import HTTPException
from data_fetch.service import StockDataService
from report_refresh_service import refresh_report_data_snapshot
from test_report_annual_financial_source_refresh import report
from test_report_refresh_acquisition_audit import init_db,events


@pytest.fixture(autouse=True)
def isolated_identity_circuit():
 import os
 from provider_resilience import clear_provider_circuits,clear_provider_throttles
 from data_fetch.market_sources.twse_security_identity import PROVIDER
 assert os.environ.get('STOCK_AGENT_TEST_NO_NETWORK')=='1'
 clear_provider_circuits(PROVIDER);clear_provider_throttles(PROVIDER)
 yield
 clear_provider_circuits(PROVIDER);clear_provider_throttles(PROVIDER)


def unknown_report(ticker='6669.TW'):
 storage,name,keys,old=report(ticker);data=old['data'];data.pop('quote_type');data['company_identity']={'instrument_type':'unknown','official_name':'緯穎'if ticker=='6669.TW'else'元大台灣50'}
 if ticker=='6669.TW':data['company_name']='緯穎 / Wiwynn Corporation'
 else:data['company_name']='元大台灣50 ETF'
 data['taiwan_open_data']={'other_original':True};epoch=time.time()-3*86400
 open_audit={'ticker':ticker,'source':'taiwan_open_data','provider':'other original data','status':'success','record_count':1,'fetched_at_epoch':epoch,'fetched_at':datetime.fromtimestamp(epoch,timezone.utc).isoformat(),'fetch_id':'original','cache_hit':False,'stale':True};old['source_audit'].append(open_audit);data['source_audit']=deepcopy(old['source_audit']);data['source_freshness']={a['source']:deepcopy(a)for a in old['source_audit']};storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');return storage,name,keys,old


def native(monkeypatch,ticker='6669.TW',change=None):
 from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp as SecurityIdentityHttp
 from data_fetch.market_sources.issuer_news_transport import ROSTER_URL
 calls=[];raw=(Path(__file__).parent/'fixtures/source_acquisition'/('twse_isin_'+ticker.split('.')[0]+'_captured_20261011.html')).read_bytes();today=datetime.now(timezone.utc).strftime('%Y%m%d');stamp=str(int(today[:4])-1911)+today[4:]
 records=[{'公司代號':str(n),'公司簡稱':'測試'+str(n),'公司名稱':'測試'+str(n),'出表日期':stamp}for n in range(1000,2000)]
 records.extend([{'公司代號':'6669','公司簡稱':'緯穎','公司名稱':'緯穎科技股份有限公司','出表日期':stamp},{'公司代號':'6924','公司簡稱':'榮惠-KY創','公司名稱':'榮惠集團(開曼)股份有限公司','出表日期':stamp},{'公司代號':'2353','公司簡稱':'宏碁','公司名稱':'宏碁股份有限公司','出表日期':stamp}]);roster=json.dumps(records,ensure_ascii=False).encode()
 def get(self,url):
  calls.append(url);body=roster if url==ROSTER_URL else raw
  if change and url!=ROSTER_URL:body=change(body)
  self.components.append({'url':url,'cache_hit':False,'http_request_sent':True,'http_request_count':1,'fetched_at_epoch':time.time()});self.http_request_count+=1;return body
 monkeypatch.setattr(SecurityIdentityHttp,'get',get);return calls


def refresh(storage,name,tmp):
 try:return asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp),storage=storage,refresh_service=StockDataService(),source='instrument_identity'))
 except HTTPException as exc:
  exc.add_note(json.dumps([{k:e.get(k)for k in ['status','message','details_json']}for e in events()],ensure_ascii=False));raise


def test_unknown_equity_gets_official_type_and_keeps_original_quote_other_data_and_gates(tmp_path,monkeypatch):
 init_db();storage,name,keys,old=unknown_report();calls=native(monkeypatch);refresh(storage,name,tmp_path);saved=json.loads(storage.get_report(keys.data_key).content);data=saved['data']
 assert data['instrument_type']=='EQUITY'and data['security_identity']['security_type']=='股票'and data['security_identity']['cfi_code']=='ESVUFR'
 assert 'quote_type'not in data and data['company_identity']==old['data']['company_identity']
 assert data['current_price']==old['data']['current_price']and data['revenue_ttm_raw']==old['data']['revenue_ttm_raw']and data['years']==old['data']['years']
 assert data['taiwan_open_data']['other_original']is True and data['source_freshness']['taiwan_open_data']['fetched_at_epoch']<=old['source_audit'][-1]['fetched_at_epoch']
 assert data['source_audit'][:-1]==old['source_audit']and saved['analysis_evidence']==old['analysis_evidence']
 for gate in ['report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:assert saved[gate]==old[gate]
 assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
 assert saved['decision_validity_status']=='needs_rerun';observed=events();assert len(observed)==1 and observed[0]['source']=='taiwan_open_data'and observed[0]['record_count']==1
 assert len(calls)==2


def test_real_etf_classification_is_explicit_and_never_pretends_to_acquire_company_financials(tmp_path,monkeypatch):
 init_db();storage,name,keys,old=unknown_report('0050.TW');calls=native(monkeypatch,'0050.TW');refresh(storage,name,tmp_path);data=json.loads(storage.get_report(keys.data_key).content)['data']
 assert data['instrument_type']=='ETF'and data['security_identity']['security_type']=='ETF'and data['security_identity']['cfi_code']=='CEOGEU';assert len(calls)==1
 assert data['years']==old['data']['years']and data['revenue_ttm_raw']==old['data']['revenue_ttm_raw'];observed=events();assert len(observed)==1 and observed[0]['source']=='taiwan_open_data'


@pytest.mark.parametrize('change',[lambda raw:raw.replace(b'6669',b'2330'),lambda raw:raw.replace(b'ESVUFR',b'CEOGEU'),lambda raw:raw.replace(b'TW0006669005',b'TW0006669006')])
def test_wrong_issuer_type_or_isin_check_digit_rejected_without_report_mutation(tmp_path,monkeypatch,change):
 init_db();storage,name,keys,old=unknown_report();before=storage.get_report(keys.data_key).content;native(monkeypatch,change=change)
 with pytest.raises(HTTPException)as error:refresh(storage,name,tmp_path)
 assert error.value.status_code==502 and storage.get_report(keys.data_key).content==before;observed=events();assert len(observed)==1 and observed[0]['status']!='success'and observed[0]['record_count']==0


def test_already_declared_instrument_is_not_requeried_or_changed(tmp_path,monkeypatch):
 init_db();storage,name,keys,old=report('6669.TW');calls=native(monkeypatch)
 with pytest.raises(HTTPException)as error:refresh(storage,name,tmp_path)
 assert error.value.status_code==400 and calls==[]and events()==[]


def test_identity_adds_open_data_slot_when_original_slot_is_none(tmp_path,monkeypatch):
 init_db();storage,name,keys,old=unknown_report();old['data']['taiwan_open_data']=None;storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');native(monkeypatch);refresh(storage,name,tmp_path)
 data=json.loads(storage.get_report(keys.data_key).content)['data'];assert data['instrument_type']=='EQUITY'and data['taiwan_open_data']['security_identity']['security_code']=='6669'


def test_equivalent_quote_and_official_type_representations_do_not_force_another_analysis():
 from report_refresh_diff import refresh_data_diff,refresh_requires_analysis_rerun
 before={'data':{'quote_type':'EQUITY','instrument_type':'EQUITY'},'data_trust':{'status':'fresh'}};after={'data':{'quote_type':'EQUITY'},'data_trust':{'status':'fresh'}}
 assert not refresh_requires_analysis_rerun(before,after,refresh_data_diff(before,after))


def test_retained_other_issuer_quote_rejects_identity_work_before_network(tmp_path,monkeypatch):
 init_db();storage,name,keys,old=unknown_report();old['source_audit'][0]['ticker']='2330.TW';storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');calls=native(monkeypatch)
 with pytest.raises(HTTPException)as err:refresh(storage,name,tmp_path)
 assert err.value.status_code==400 and calls==[]and events()==[]


def test_refresh_timestamp_overflow_is_unknown_not_an_exception():
 from report_source_refresh import _timestamp
 assert _timestamp({'fetched_at_epoch':10**400,'fetched_at':datetime.now(timezone.utc).isoformat()})is None


def test_cached_identity_keeps_original_epoch_and_is_not_new_acquisition(tmp_path,monkeypatch):
 import data_fetch.market_sources.twse_security_identity as source
 from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
 init_db();storage,name,keys,old=unknown_report();native(monkeypatch);real=IssuerNewsHttp.get;epoch=time.time()-60
 def cached(self,url):
  raw=real(self,url);self.http_request_count-=1;self.components[-1].update(cache_hit=True,http_request_sent=False,http_request_count=0,fetched_at_epoch=epoch);return raw
 monkeypatch.setattr(IssuerNewsHttp,'get',cached);refresh(storage,name,tmp_path);data=json.loads(storage.get_report(keys.data_key).content)['data'];assert data['security_identity']['observed_at_epoch']==epoch
 observed=events();assert len(observed)==1 and observed[0]['status']=='skipped_fresh_cache'
 audit=data['source_audit'][-1];assert audit['http_request_count']==0 and audit['http_request_sent']is False


def test_new_master_with_cached_identity_does_not_renew_classification_time(tmp_path,monkeypatch):
 from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL
 init_db();storage,name,keys,old=unknown_report();native(monkeypatch);real=IssuerNewsHttp.get;epoch=time.time()-60
 def mixed(self,url):
  raw=real(self,url)
  if url!=ROSTER_URL:self.http_request_count-=1;self.components[-1].update(cache_hit=True,http_request_sent=False,http_request_count=0,fetched_at_epoch=epoch)
  return raw
 monkeypatch.setattr(IssuerNewsHttp,'get',mixed);refresh(storage,name,tmp_path);data=json.loads(storage.get_report(keys.data_key).content)['data'];assert data['security_identity']['observed_at_epoch']==epoch
 observed=events();assert len(observed)==1 and observed[0]['status']=='degraded_enrichment';audit=data['source_audit'][-1];assert audit['acquisition_status']=='partial_acquisition_with_cached_records'and audit['fetched_at_epoch']==epoch


@pytest.mark.parametrize('field,value',[('ticker','2330.TW'),('stock_id','2330')])
def test_explicit_conflicting_original_company_binding_rejects_identity_work(tmp_path,monkeypatch,field,value):
 init_db();storage,name,keys,old=unknown_report();old['data']['company_identity'][field]=value;storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');calls=native(monkeypatch)
 with pytest.raises(HTTPException)as err:refresh(storage,name,tmp_path)
 assert err.value.status_code==400 and calls==[]and events()==[]


def test_corrupt_archived_original_rejects_verified_identity(monkeypatch,tmp_path):
 from data_fetch.market_sources.twse_security_identity import fetch_security_identity,verified_security_identity
 from official_response_evidence import read_response
 import gzip
 native(monkeypatch);diagnostics={};value=fetch_security_identity('6669.TW',diagnostics=diagnostics);assert verified_security_identity(value,'6669.TW')
 proof=value['source_record_archive']['identity'];p=Path(proof['raw_response_path']);before=p.read_bytes()
 try:
  p.write_bytes(gzip.compress(b'incomplete source'))
  assert not verified_security_identity(value,'6669.TW')
 finally:p.write_bytes(before)


@pytest.mark.parametrize('bad',['duplicate_empty_owner','wrong_host','http_boolean','wrong_epoch'])
def test_contradictory_saved_identity_receipt_is_rejected(monkeypatch,bad):
 from data_fetch.market_sources.twse_security_identity import fetch_security_identity,verified_security_identity
 native(monkeypatch);value=fetch_security_identity('6669.TW',diagnostics={});copy=deepcopy(value)
 if bad=='duplicate_empty_owner':copy['source_record_archive']['identity']['source_url']+='&owncode='
 elif bad=='wrong_host':copy['source_record_archive']['identity']['source_url']=copy['source_url'].replace('isin.twse.com.tw','invalid.example')
 elif bad=='http_boolean':copy['source_record_archive']['identity']['http_status']=True
 else:copy['source_record_archive']['identity']['retrieved_at']-=60
 assert not verified_security_identity(copy,'6669.TW')


# Independent public counterexamples retained as regression checks.
from types import SimpleNamespace
from bs4 import BeautifulSoup
import data_fetch.market_sources.twse_security_identity as source


def test_conflicting_original_legal_name_cannot_be_admitted_by_correct_code_alone(tmp_path,monkeypatch):
    init_db();storage,name,keys,old=unknown_report();old['data']['company_identity']['legal_name']='台積電股份有限公司'
    before=json.dumps(old).encode();storage.save_report(keys.data_key,before,content_type='application/json');native(monkeypatch)
    with pytest.raises(HTTPException):refresh(storage,name,tmp_path)
    assert storage.get_report(keys.data_key).content==before


def test_non_raw_evidence_kind_cannot_substantiate_full_original_classification(monkeypatch):
    native(monkeypatch);value=source.fetch_security_identity('6669.TW',diagnostics={})
    value['source_record_archive']['identity']['evidence_kind']='selected_decoded_fields'
    assert not source.verified_security_identity(value,'6669.TW')


def test_conflicting_target_row_with_missing_column_is_not_silently_ignored(tmp_path,monkeypatch):
    init_db();storage,name,keys,_=unknown_report();before=storage.get_report(keys.data_key).content
    def ambiguous(raw):
        soup=BeautifulSoup(raw.decode('big5'),'html.parser')
        table=next(t for t in soup.find_all('table') if len(t.find_all('tr'))==2)
        duplicate=deepcopy(table.find_all('tr')[1]);cells=duplicate.find_all('td',recursive=False)
        cells[5].string='ETF';cells[8].string='CEOGEU';cells[-1].decompose();table.append(duplicate)
        return str(soup).encode('big5')
    native(monkeypatch,change=ambiguous)
    with pytest.raises(HTTPException):refresh(storage,name,tmp_path)
    assert storage.get_report(keys.data_key).content==before


def test_completion_after_whole_source_deadline_does_not_publish_classification(tmp_path,monkeypatch):
    init_db();storage,name,keys,_=unknown_report();before=storage.get_report(keys.data_key).content;native(monkeypatch)
    clock=[0.];proof_calls=[0];original=source._proof
    monkeypatch.setattr(source,'time',SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    def delayed_last_archive(*a,**k):
        receipt=original(*a,**k);proof_calls[0]+=1
        if proof_calls[0]==2:clock[0]=16.
        return receipt
    monkeypatch.setattr(source,'_proof',delayed_last_archive)
    with pytest.raises(HTTPException):refresh(storage,name,tmp_path)
    assert storage.get_report(keys.data_key).content==before


def test_first_actual_http_parse_failure_is_not_erased_by_warm_retry_diagnostics(tmp_path,monkeypatch):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from tenacity import wait_fixed
    import provider_resilience
    init_db();storage,name,keys,_=unknown_report();before=storage.get_report(keys.data_key).content
    native(monkeypatch,change=lambda raw:raw.replace(b'ESVUFR',b'CEOGEU'))
    original=IssuerNewsHttp.get;epochs={}
    def simulate_real_raw_cache(self,url):
        raw=original(self,url)
        if url in epochs:
            self.http_request_count-=1
            self.components[-1].update(cache_hit=True,http_request_sent=False,http_request_count=0,fetched_at_epoch=epochs[url])
        else:epochs[url]=self.components[-1]['fetched_at_epoch']
        return raw
    monkeypatch.setattr(IssuerNewsHttp,'get',simulate_real_raw_cache)
    monkeypatch.setenv('PROVIDER_RETRY_ATTEMPTS','3')
    monkeypatch.setattr(provider_resilience,'_retry_wait_strategy',lambda:wait_fixed(0))
    with pytest.raises(HTTPException):refresh(storage,name,tmp_path)
    assert storage.get_report(keys.data_key).content==before
    observed=events();assert len(observed)==1 and observed[0]['status']=='error'and observed[0]['record_count']==0
    details=json.loads(observed[0]['details_json'])
    assert details['http_request_sent'] is True and details['cache_hit'] is False,details
    from provider_acquisition import get_provider_acquisition_summary
    summary=next(s for s in get_provider_acquisition_summary()['sources']if s['source']=='taiwan_open_data')
    assert summary['fetch_attempts']==summary['failed_count']==summary['http_attempt_count']==1,summary


def test_matching_original_legal_name_remains_eligible(tmp_path,monkeypatch):
 init_db();storage,name,keys,old=unknown_report();old['data']['company_identity']['legal_name']='緯穎科技股份有限公司';storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');native(monkeypatch);refresh(storage,name,tmp_path)
 data=json.loads(storage.get_report(keys.data_key).content)['data'];assert data['instrument_type']=='EQUITY'and data['company_identity']==old['data']['company_identity']


@pytest.mark.parametrize('ticker,name',[('6924.TW','榮惠-KY創'),('2353.TW','宏碁')])
def test_captured_native_variant_uses_explicit_board_or_strict_extension_decode(tmp_path,monkeypatch,ticker,name):
 init_db();storage,filename,keys,old=unknown_report(ticker);old['data']['company_name']=name;old['data']['company_identity']['official_name']=name;storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');calls=native(monkeypatch,ticker);refresh(storage,filename,tmp_path);snapshot=json.loads(storage.get_report(keys.data_key).content);data=snapshot['data'];value=data['security_identity']
 assert value['instrument_type']=='EQUITY'and value['security_name']==name and value['cfi_code']=='ESVUFR'and len(calls)==2
 assert value['market']==('上市臺灣創新板'if ticker=='6924.TW'else'上市')and value['security_type']==('創新板'if ticker=='6924.TW'else'股票')
 assert value['encoding_policy']==('strict_big5_fixed_table.v1'if ticker=='6924.TW'else'strict_cp950_extension_fixed_table.v1')
 assert data['company_identity']==old['data']['company_identity']and data['current_price']==old['data']['current_price']and data['years']==old['data']['years']
 assert snapshot['analysis_evidence']==old['analysis_evidence']and snapshot['decision_validity_status']=='needs_rerun'
 assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
 assert len(events())==1 and events()[0]['record_count']==1


@pytest.mark.parametrize('field,new', [(4,'上市'),(5,'股票'),(8,'CEOGEU'),(4,'上櫃')])
def test_board_market_type_and_cfi_must_remain_exact_observed_triple(tmp_path,monkeypatch,field,new):
 init_db();storage,name,keys,_=unknown_report('6924.TW');before=storage.get_report(keys.data_key).content
 def alter(raw):
  soup=BeautifulSoup(raw.decode('big5',errors='strict'),'html.parser');table=next(t for t in soup.find_all('table')if len(t.find_all('tr'))==2);table.find_all('tr')[-1].find_all('td',recursive=False)[field].string=new;return str(soup).encode('big5')
 native(monkeypatch,'6924.TW',change=alter)
 with pytest.raises(HTTPException):refresh(storage,name,tmp_path)
 assert storage.get_report(keys.data_key).content==before and events()[0]['record_count']==0


def test_extension_decoder_does_not_replace_invalid_bytes_or_freshen_original(tmp_path,monkeypatch):
 init_db();storage,name,keys,_=unknown_report('2353.TW');before=storage.get_report(keys.data_key).content
 native(monkeypatch,'2353.TW',change=lambda raw:raw.replace('碁'.encode('cp950'),b'\x81\x7f'))
 with pytest.raises(HTTPException):refresh(storage,name,tmp_path)
 assert storage.get_report(keys.data_key).content==before and events()[0]['record_count']==0
