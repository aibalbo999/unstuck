"""Mock wire/private-body replay is never new real provider acquisition."""
import base64
from copy import deepcopy
import csv
from datetime import datetime
import io
import json
from hashlib import sha256
import time
from zoneinfo import ZoneInfo

import pytest

from test_shared_provider_cache import memory_cache
from test_mega_annual_catalog import html


@pytest.fixture
def catalogue(memory_cache,monkeypatch):
    from data_fetch.market_sources import mega_catalog_transport as t,official_issuer_master as master
    from data_fetch.market_sources.official_issuer_master_transport import IssuerMasterHttp
    calls=[]
    def download(self,url,diagnostic):
        fields=['公司代號','公司名稱','公司簡稱','營利事業統一編號','英文簡稱','網址','出表日期']
        now=datetime.now(ZoneInfo('Asia/Taipei'));day=f'{now.year-1911:03d}{now.month:02d}{now.day:02d}'
        rows=[dict(zip(fields,[str(1000+i),'合成公司'+str(i),'合成'+str(i),'10000000','Synthetic','https://example.com',day]))for i in range(500)]
        rows.append(dict(zip(fields,['2886','兆豐金融控股股份有限公司','兆豐金','70796754','MEGA','www.megaholdings.com.tw',day])))
        out=io.StringIO();writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader();writer.writerows(rows);raw=out.getvalue().encode()
        meta=master.master_metadata({'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),'content_type':'text/csv','content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'max-age=1800'},raw,{})
        self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'request_method':'GET','request_body':None,'response_metadata':meta}
    monkeypatch.setattr(IssuerMasterHttp,'download_original',download)
    def collect(argv,*a,**kwargs):
        url=argv[-1];calls.append(url);year=int(url.rsplit('=',1)[-1])-100 if '?'in url else 2026;raw=html(year)
        headers=f'HTTP/2 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(raw)}\r\n\r\n'.encode()
        return {'body':raw,'headers':headers,'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,'proxy_used':0,'size_download':len(raw),'method':'GET'}).encode(),'process_started':True,'body_bytes_read':len(raw)},0,None
    monkeypatch.setattr(t,'collect_capped_process',collect);monkeypatch.setattr(t,'cooldown_state',lambda *a:None);monkeypatch.setattr(t,'proxy_url_for_request',lambda *a:None)
    for name in t.PROXY_ENV+('STOCK_AGENT_TEST_NO_NETWORK',):monkeypatch.delenv(name,raising=False)
    from data_fetch.market_sources.mega_annual_catalog import fetch_catalogue
    return fetch_catalogue(time.monotonic()+30),calls


def value_with_catalogue(proof):
    from test_public_holding_annual_source import captured_value
    from data_fetch.market_sources.mega_annual_catalog import POLICY
    value=captured_value();value.pop('published_index_receipt')
    return dict(value,acquisition_protocol=POLICY,publication_catalogue=deepcopy(proof))


def test_new_publication_proof_replays_all_bodies_and_preserves_every_financial_fact(catalogue):
    from data_fetch.market_sources.mega_annual_catalog import replay_catalogue
    from data_fetch.market_sources.mops_public_holding import project_public_holding_statement
    proof,calls=catalogue;assert len(calls)==7
    assert replay_catalogue(proof)['years']==[2021,2022,2023,2024,2025]
    value=value_with_catalogue(proof);before=deepcopy(value)
    assert project_public_holding_statement(value,'2886.TW')==value and value==before
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder_helpers import _prompt_financial_institution_history
    projected=project_source_value(value,'2886.TW')
    assert projected['revenue_history']==projected['gross_profit_history']==projected['operating_income_history']==[None]*5
    prompt=_prompt_financial_institution_history({'ticker':'2886.TW','sector_specific_financials':value})
    assert prompt and 'raw_response_path'not in json.dumps(prompt,ensure_ascii=False)
    assert 'acquisition_manifest'not in json.dumps(prompt,ensure_ascii=False)


@pytest.mark.parametrize('damage',['master','year','delete_year','wrong_URL','raw_SHA','template','fact','missing_policy'])
def test_catalogue_cannot_replace_numeric_bodies_or_allow_unbound_publications(catalogue,damage):
    from data_fetch.market_sources.mops_public_holding import project_public_holding_statement
    value=value_with_catalogue(catalogue[0]);p=value['publication_catalogue']
    if damage=='master':p['master']['raw_response_sha256']='0'*64
    elif damage=='year':p['catalogues'][0]['year']=2025
    elif damage=='delete_year':p['catalogues'].pop()
    elif damage=='wrong_URL':p['catalogues'][0]['receipt']['source_url']='https://example.com'
    elif damage=='raw_SHA':p['catalogues'][0]['receipt']['raw_response_sha256']='0'*64
    elif damage=='template':value['documents'][0]['components'][0]['unit_template_receipt']['raw_response_sha256']='0'*64
    elif damage=='fact':value['raw_twd_by_year']['2021']['net_revenue']+=1
    else:value.pop('acquisition_protocol')
    assert project_public_holding_statement(value,'2886.TW')is None


def test_unknown_year_url_cannot_start_a_native_request(memory_cache):
    from data_fetch.market_sources.mega_catalog_transport import MegaCatalogHttp
    from data_fetch.market_sources.mega_annual_catalog import page_url
    from search_provider_runtime import SourceResponseError
    h=MegaCatalogHttp(time.monotonic()+20)
    with pytest.raises(SourceResponseError):h.get_receipt(page_url('2125'))
    assert not h.components and h.http_request_count==0


def test_fetcher_uses_eighteen_full_numeric_originals_without_old_publication_index(catalogue):
    from test_public_holding_annual_source import CapturedTransport
    from data_fetch.market_sources.mops_public_holding import fetch_public_holding_histories,project_public_holding_statement
    transport=CapturedTransport(fail_at='index')
    value=fetch_public_holding_histories('2886.TW',transport=transport,publication_catalogue=catalogue[0])
    assert value['years']==['2021','2022','2023','2024','2025']and len(transport.components)==18
    assert project_public_holding_statement(value,'2886.TW')is not None


@pytest.mark.parametrize('stage', ['final_body', 'batch_cleanup'])
def test_live_catalogue_expiry_rechecked_at_whole_source_handoff(catalogue,monkeypatch,stage):
    from contextlib import contextmanager
    from test_public_holding_annual_source import CapturedTransport
    from data_fetch.market_sources.mops_public_holding import fetch_public_holding_histories
    from search_provider_runtime import SourceResponseError
    proof=catalogue[0];http=CapturedTransport(fail_at='index');old=http.request
    expired=proof['master']['fresh_until_epoch']+1
    if stage=='final_body':
        def request(*a,**kw):
            value=old(*a,**kw)
            if len(http.components)==18:monkeypatch.setattr(time,'time',lambda:expired)
            return value
        http.request=request
    else:
        @contextmanager
        def batch():
            yield http
            monkeypatch.setattr(time,'time',lambda:expired)
        http.batch=batch
    with pytest.raises((SourceResponseError,ValueError)):
        fetch_public_holding_histories('2886.TW',transport=http,publication_catalogue=proof)
    assert len(http.components)==18


@pytest.mark.parametrize('damage',['marker_only','stale','future','no_request','cached'])
def test_remembered_selection_requires_recent_native_catalogue_provenance(memory_cache,monkeypatch,damage):
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import record_source_audit_entries
    from data_fetch.market_sources import mega_annual_catalog as c
    from data_fetch.market_sources.mops_public_holding import PROVIDER
    init_db();stamp=time.time()
    entry={'source':'financial_statements','provider':PROVIDER,'ticker':'2886.TW',
        'selection_policy':c.POLICY,'status':'success','record_count':5,
        'cache_hit':False,'http_request_sent':True,'component_statuses':{
            '0':{'url':c.ROOT,'request_method':'GET','http_request_sent':True,
                 'response_complete':True,'http_status':200}}}
    if damage=='marker_only':entry['component_statuses']={}
    elif damage=='no_request':entry['http_request_sent']=False
    elif damage=='cached':entry['cache_hit']=True
    record_source_audit_entries([entry])
    if damage=='stale':monkeypatch.setattr(time,'time',lambda:stamp+86401)
    elif damage=='future':monkeypatch.setattr(time,'time',lambda:stamp-60)
    assert c.prefer_catalogue('2886.TW')is False


def test_remembered_current_native_catalogue_selection_is_usable(memory_cache):
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import record_source_audit_entries
    from data_fetch.market_sources import mega_annual_catalog as c
    from data_fetch.market_sources.mops_public_holding import PROVIDER
    init_db();record_source_audit_entries([{'source':'financial_statements','provider':PROVIDER,
        'ticker':'2886.TW','selection_policy':c.POLICY,'status':'success','record_count':5,
        'cache_hit':False,'http_request_sent':True,'component_statuses':{
            '0':{'url':c.ROOT,'request_method':'GET','http_request_sent':True,
                 'response_complete':True,'http_status':200}}}])
    assert c.prefer_catalogue('2886.TW')is True


@pytest.mark.parametrize('kind,status,expected',[
    ('timeout',200,True),('timeout',None,True),('parse_error',200,False),
    ('access_denied',403,False),('rate_limited',429,False)])
def test_only_prior_native_publication_transport_failure_selects_catalogue(memory_cache,kind,status,expected):
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import record_source_audit_entries
    from data_fetch.market_sources.mops_public_holding import PROVIDER
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    from data_fetch.market_sources.mega_annual_catalog import prefer_catalogue
    init_db();record_source_audit_entries([{'source':'financial_statements','provider':PROVIDER,'ticker':'2886.TW',
        'status':'error','record_count':0,'http_request_sent':True,'component_statuses':{'0':{'url':INDEX_URL,
            'request_method':'POST','http_request_sent':True,'response_complete':False,'error_kind':kind,'http_status':status}}}])
    assert prefer_catalogue('2886.TW')is expected


def test_financial_host_cooldown_blocks_before_any_catalogue_download(memory_cache,monkeypatch):
    from data_fetch.market_sources import mega_annual_catalog as catalog,mops_public_holding as holding
    import search_provider_runtime as runtime
    monkeypatch.setattr(catalog,'prefer_catalogue',lambda *a:True)
    def forbidden(*a,**kw):raise AssertionError('metadata request during retained financial host wait')
    monkeypatch.setattr(catalog,'fetch_catalogue',forbidden)
    monkeypatch.setattr(runtime,'cooldown_state',lambda *a:{'retry_at':time.time()+60})
    result=holding.fetch_public_holding_result('2886.TW')
    assert result['value']is None and result['audit']['http_request_count']==0
    assert result['audit']['http_request_sent']is False


@pytest.mark.parametrize('damage',['http_bool','redirect','proxy','truncated','wrong_method','wrong_effective_url','mutated_epoch'])
def test_catalogue_metadata_changes_cannot_reseal_original(catalogue,damage):
    from data_fetch.market_sources.mega_catalog_transport import original_bytes
    from data_fetch.market_sources.mega_annual_catalog import ROOT
    r=deepcopy(catalogue[0]['root']);m=r['response_metadata']
    if damage=='http_bool':m['http_status']=True
    elif damage=='redirect':m['num_redirects']=1
    elif damage=='proxy':m['proxy_used']=1
    elif damage=='truncated':m['size_download']-=1
    elif damage=='wrong_method':m['method']='POST'
    elif damage=='wrong_effective_url':m['effective_url']='https://example.com'
    else:r['retrieved_at']+=1
    with pytest.raises(ValueError):original_bytes(r,ROOT)


@pytest.mark.parametrize('status,rc,error,expected',[(429,0,None,'rate_limited'),(200,28,None,'timeout'),(None,28,None,'timeout')])
def test_failed_transport_retains_actual_status_bytes_and_retry_after(memory_cache,monkeypatch,status,rc,error,expected):
    from data_fetch.market_sources import mega_catalog_transport as t
    from data_fetch.market_sources.mega_annual_catalog import ROOT
    from search_provider_runtime import SourceResponseError
    saved=[];raw=b'incomplete provider response'
    def collect(*a,**kw):
        headers=(f'HTTP/2 {status} test\r\nRetry-After: 90\r\nContent-Type: text/html\r\n\r\n'.encode()if status else b'')
        return {'body':raw,'headers':headers,'metadata':b'{}','process_started':True,'body_bytes_read':len(raw)},rc,error
    monkeypatch.setattr(t,'collect_capped_process',collect)
    monkeypatch.setattr(t,'cooldown_state',lambda *a:None)
    monkeypatch.setattr(t,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(t,'remember_failure',lambda key,exc:saved.append(exc))
    for name in t.PROXY_ENV+('STOCK_AGENT_TEST_NO_NETWORK',):monkeypatch.delenv(name,raising=False)
    h=t.MegaCatalogHttp(time.monotonic()+20)
    with pytest.raises(SourceResponseError)as caught:h.get_receipt(ROOT)
    d=h.components[0]
    assert caught.value.error_kind==expected and d['http_status']==status
    assert d['response_complete']is False and d['http_status_observed']is (status is not None)
    assert d['failure_evidence']['raw_response_sha256']==sha256(raw).hexdigest()
    assert len(saved)==1
    if status==429:assert saved[0].response.headers['retry-after']=='90'


def install_catalogue_route(monkeypatch,proof,*,fail_at='index'):
    from data_fetch.market_sources import mega_annual_catalog as catalog,mops_public_holding as native
    from test_public_holding_annual_source import CapturedTransport
    import search_provider_runtime as runtime
    transport=CapturedTransport(fail_at=fail_at)
    monkeypatch.setattr(catalog,'prefer_catalogue',lambda *a:True)
    monkeypatch.setattr(runtime,'cooldown_state',lambda *a:None)
    def replay_only(deadline,*,diagnostics):
        diagnostics.extend({'url':r['source_url'],'http_request_sent':True,'http_status':200,'response_complete':True}
            for r in[proof['root'],*[p['receipt']for p in proof['catalogues']]])
        return deepcopy(proof)
    monkeypatch.setattr(catalog,'fetch_catalogue',replay_only)
    monkeypatch.setattr(native,'PublicMopsHttp',lambda:transport)
    return transport


def test_new_route_normal_extraction_keeps_typed_values_and_counts_once(catalogue,monkeypatch):
    from data_fetch import yfinance_extractors as source
    from test_financial_institution_history_projection import NoAnnualSdk
    transport=install_catalogue_route(monkeypatch,catalogue[0])
    monkeypatch.setattr(source,'fetch_financial_institution_histories',lambda *a:pytest.fail('no old XBRL retry'))
    monkeypatch.setattr(source,'fetch_finmind_financial_statement_fallback',lambda *a,**k:pytest.fail('no redundant numeric fallback'))
    value=source.extract_financial_histories(NoAnnualSdk(),'2886.TW',[],industry_context='金融保險')
    assert value['revenue_history']==[None]*5 and len(transport.components)==18
    audit=value['sector_specific_financial_audit']
    assert audit['http_request_count']==25 and len(audit['component_statuses'])==25
    assert audit['record_count']==5 and audit['selection_policy']=='mega-published-holding-catalogue:v1'


def test_new_route_source_refresh_preserves_report_conclusions_and_gates(catalogue,monkeypatch,tmp_path):
    import asyncio
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from test_report_annual_financial_source_refresh import report,init_db,events
    init_db();storage,name,keys,old=report('2886.TW')
    old['data'].update(company_name='兆豐金',sector='Financial Services',industry='Financial Conglomerates')
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    transport=install_catalogue_route(monkeypatch,catalogue[0])
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
        refresh_service=StockDataService(),source='financial_statements',return_refreshed_data=True))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert result['analysis_text_stale']is True and saved['analysis_evidence']==old['analysis_evidence']
    for gate in['report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:
        assert saved[gate]==old[gate]
    assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
    assert len(events())==1 and events()[0]['record_count']==5 and len(transport.components)==18
