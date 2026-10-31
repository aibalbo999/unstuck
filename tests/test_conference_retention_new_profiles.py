"""Captured deployed originals through the real general-refresh retention boundary."""
from copy import deepcopy
from pathlib import Path
import importlib, json, shutil, time, os
import pytest
from test_report_conference_retention import refresh
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261015/chroma-and-conference-retention/fixtures'
CASES=[('2801.TW','chb','chb_qa_receipt'),('6861.TW','innocare','innocare_conference_receipt'),('1605.TW','walsin','walsin_conference_receipt')]

@pytest.fixture
def original_capture(monkeypatch):
    from runtime_paths import current_runtime_paths
    import official_response_evidence as evidence
    dest=current_runtime_paths().cache_dir/'official-response-evidence'
    sandbox_cache=Path(os.environ['CACHE_DIR']).resolve()
    assert os.environ.get('STOCK_AGENT_TEST_NO_NETWORK') == '1'
    assert sandbox_cache.parent.name.startswith('prompt-boundary-tests-')
    assert sandbox_cache.parent == Path(os.environ['CACHE_DB_PATH']).resolve().parent
    assert dest.resolve().parent == sandbox_cache
    assert dest.resolve() != (ROOT/'backend/cache/official-response-evidence').resolve()
    dest.mkdir(parents=True,exist_ok=True)
    for p in (D/'originals').glob('*.gz'):shutil.copyfile(p,dest/p.name)
    original=evidence.read_response
    def read_isolated(proof,**kwargs):
        # Change only filesystem resolution. Original manifest bytes and all
        # receipt fields stay untouched and the normal reader still checks SHA.
        v=deepcopy(proof);v['raw_response_path']=str(dest/Path(v['raw_response_path']).name)
        return original(v,**kwargs)
    monkeypatch.setattr(evidence,'read_response',read_isolated)
    for name in ['chb_conference_transport','innocare_conference_transport','walsin_conference_transport','official_issuer_master','official_issuer_master_json']:
        module=importlib.import_module('data_fetch.market_sources.'+name)
        monkeypatch.setattr(module,'read_response',read_isolated)
    def get(ticker):return json.loads((D/f'{ticker}.old.json').read_text())
    return get

def failed_data(old,name,*,now=None):
    module=importlib.import_module('data_fetch.market_sources.'+name+'_conference')
    value=deepcopy(old['data']);value['earnings_call']={}
    value.pop('conference_retention',None)
    value['source_audit']=[a for a in value['source_audit']if a.get('source')!='earnings_call']
    value['source_audit'].append({'source':'earnings_call','provider':module.PROVIDER,'ticker':old['ticker'],
        'status':'error','error_kind':'timeout','record_count':0,'http_request_sent':True,'http_request_count':1,
        'fetched_at_epoch':time.time()if now is None else now,'cache_hit':False,'stale':False,'component_statuses':[]})
    return value

@pytest.mark.parametrize('ticker,name,marker',CASES)
def test_real_acquired_body_survives_transient_refresh_without_new_success(original_capture,tmp_path,ticker,name,marker):
    from provider_acquisition import project_acquisition_events
    old=original_capture(ticker);incoming=failed_data(old,name);before=deepcopy(incoming)
    current,result,keys,storage=refresh(old,incoming,tmp_path)
    assert current['data'].get('earnings_call')==old['data']['earnings_call']
    assert incoming==before and result['refreshed_data']==before
    assert current['data']['conference_retention']['new_acquisition']is False
    assert current['data']['source_freshness']['earnings_call']['stale']is True
    assert current['data']['source_audit'][1:]==incoming['source_audit']
    reused=current['data']['source_audit'][0];now=time.time()
    r=project_acquisition_events([{**reused,'created_at':now,'details_json':json.dumps(reused)}],window='last_24h',now=now)['sources'][0]
    assert r['fetched_count']==r['fetch_attempts']==0 and r['stale_cache_count']==1
    assert storage.get_report(keys.html_key).content==b'original HTML'
    assert storage.get_report(keys.md_key).content==b'original Markdown'
    for k in ('analysis_evidence','report_lint','evidence_exit_gate','content_credibility','report_conformance','final_audit'):assert current.get(k)==old.get(k)

@pytest.mark.parametrize('ticker,name,marker',CASES)
def test_original_time_replay_is_historical_and_does_not_relax_live_ttl(original_capture,monkeypatch,tmp_path,ticker,name,marker):
    module=importlib.import_module('data_fetch.market_sources.'+name+'_conference')
    old=original_capture(ticker);value=old['data']['earnings_call'];future=time.time()+400*86400
    monkeypatch.setattr(time,'time',lambda:future)
    assert not module.verify_context(value,ticker,max_age=1800)
    incoming=failed_data(old,name,now=future)
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call']==value
    assert current['data']['conference_retention']['historical_evidence']['current_acquisition']is False
    again,_,_,_=refresh(current,incoming,tmp_path)
    assert again['data']['conference_retention']==current['data']['conference_retention']

@pytest.mark.parametrize('ticker,name,marker',CASES)
@pytest.mark.parametrize('tamper',['body','epoch','manifest','kind','http403','http429','parse_error','new_index_without_original','new_material','identity'])
def test_changed_originals_or_nontransient_result_cannot_be_hidden(original_capture,tmp_path,ticker,name,marker,tamper):
    old=original_capture(ticker);incoming=failed_data(old,name);value=old['data']['earnings_call']
    audit=incoming['source_audit'][-1]
    if tamper=='body':value['documents'][0]['pages'][0]['text']='changed claim'
    elif tamper=='epoch':value[marker]['pdf']['retrieved_at']+=1
    elif tamper=='manifest':value[marker]['pdf']['acquisition_manifest']['raw_response_sha256']='0'*64
    elif tamper=='kind':value['documents'][0]['document_kind']='transcript'
    elif tamper.startswith('http'):audit['http_status']=int(tamper[4:])
    elif tamper=='parse_error':audit['error_kind']='parse_error'
    elif tamper=='new_index_without_original':audit['component_statuses']=[{'url':value['source_url'],'http_status':200}]
    elif tamper=='new_material':incoming['earnings_call']={'materials':[{'url':'https://new.example/new.pdf'}]}
    else:incoming['company_name']='Different issuer'
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call']==incoming['earnings_call']
    assert 'conference_retention'not in current['data']

@pytest.mark.parametrize('ticker,name,marker',CASES)
@pytest.mark.parametrize('missing_original',[False,True])
def test_received_current_master_and_index_are_checked_before_retaining_after_pdf_timeout(original_capture,monkeypatch,tmp_path,ticker,name,marker,missing_original):
    old=original_capture(ticker);value=old['data']['earnings_call'];stamp=value['fetched_at_epoch']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    incoming=failed_data(old,name,now=stamp);audit=incoming['source_audit'][-1]
    provider=importlib.import_module('data_fetch.market_sources.'+name+'_conference').PROVIDER
    original=next(a for a in old['source_audit']if a.get('provider')==provider)
    urls={value[marker][k]['source_url']for k in ['identity','index']}
    audit['component_statuses']=deepcopy([c for c in original['component_statuses']if c.get('url')in urls])
    assert len(audit['component_statuses'])==2
    if missing_original:audit['component_statuses'][-1].pop('original_receipt')
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert bool(current['data'].get('conference_retention'))is not missing_original
    assert current['data']['earnings_call']==({}if missing_original else value)

@pytest.mark.parametrize('tamper',['cache_status','cache_sent','original_unobserved','receipt_cache','index_cache','cache_expired'])
def test_warm_master_receipt_cannot_be_relabelled_as_new_http_or_outlive_expiry(original_capture,monkeypatch,tmp_path,tamper):
    old=original_capture('2801.TW');value=old['data']['earnings_call'];stamp=value['fetched_at_epoch']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    incoming=failed_data(old,'chb',now=stamp);audit=incoming['source_audit'][-1]
    original=next(a for a in old['source_audit']if a.get('provider')==value['source'])
    urls={value['chb_qa_receipt'][k]['source_url']for k in ['identity','index']}
    parts=deepcopy([c for c in original['component_statuses']if c.get('url')in urls])
    audit['component_statuses']=parts
    master=next(c for c in parts if c['cache_hit']is True)
    index=next(c for c in parts if c['cache_hit']is False)
    assert master.get('http_status')is None and master['http_request_sent']is False
    if tamper=='cache_status':master['http_status']=200
    elif tamper=='cache_sent':master['http_request_sent']=True
    elif tamper=='original_unobserved':master['original_http_status_observed']=False
    elif tamper=='receipt_cache':master['original_receipt']['cache_hit']=False
    elif tamper=='index_cache':
        index.update(cache_hit=True,http_status=None,http_request_sent=False)
        index['original_receipt']['cache_hit']=True
    else:audit['fetched_at_epoch']=master['original_receipt']['fresh_until_epoch']+1
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call']=={}
    assert 'conference_retention'not in current['data']


def test_original_capture_refuses_canonical_cache_before_copy(monkeypatch):
    from types import SimpleNamespace
    import runtime_paths
    copied=[]
    monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:SimpleNamespace(cache_dir=ROOT/'backend/cache'))
    monkeypatch.setattr(shutil,'copyfile',lambda *args,**kwargs:copied.append(args))
    with pytest.raises(AssertionError):original_capture.__wrapped__(monkeypatch)
    assert copied==[]
