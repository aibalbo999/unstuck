"""Read-only review probes: real saved originals, isolated public refresh seams."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'scripts/project_python.sh').exists())
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'tests')]
HERE = ROOT/'docs/evidence/source-acquisition/20261014/annual-master-and-retention/retention-review'
from data_fetch.annual_financial_source_provider import HISTORY_FIELDS, SCHEMA, project_source_value
from data_fetch.service import StockDataService
from fastapi import HTTPException
from report_refresh_service import refresh_report_data_snapshot
from report_persistence import report_bundle_keys_for_filename
from storage.report_storage import InMemoryStorage
from test_report_refresh_acquisition_audit import init_db, events

OLD = ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/formal-before-data'
FILENAME = '2308_TW_v1_report_20261009_015945.html'

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

@pytest.fixture
def captured(tmp_path):
    """Relocate immutable original copies only into the runner's temporary cache."""
    from runtime_paths import current_runtime_paths
    old = json.loads(OLD.read_bytes())
    current = json.loads((HERE/'current-snapshot.json').read_bytes())
    destination = current_runtime_paths().cache_dir/'official-response-evidence'
    assert destination.resolve() != (ROOT/'backend/cache/official-response-evidence').resolve()
    destination.mkdir(parents=True,exist_ok=True)
    for path in (HERE/'originals').glob('*.gz'):
        shutil.copyfile(path,destination/path.name)
    def relocate(node):
        if isinstance(node,dict):
            if 'raw_response_path' in node:
                node['raw_response_path'] = str(destination/(node['raw_response_sha256']+'.gz'))
            for value in node.values(): relocate(value)
        elif isinstance(node,list):
            for value in node: relocate(value)
    # Only the active source receipts move. The independently hashed original
    # analysis packet is deliberately untouched by fixture setup.
    relocate(old['source_audit'])
    relocate(old['data'].get('source_audit', []))
    audit = next(a for a in old['source_audit'] if a.get('raw_twd_by_year'))
    value = {**{k:deepcopy(old['data'][k]) for k in HISTORY_FIELDS},
             'ticker':'2308.TW','schema':SCHEMA,'report_scope':'consolidated','currency':'TWD',
             **{k:deepcopy(audit[k]) for k in ('source_url','documents','raw_twd_by_year','comparative_revisions','comparative_coverage')}}
    return old,current,value

def saved_bundle(old, filename=FILENAME):
    storage = InMemoryStorage()
    keys = report_bundle_keys_for_filename(filename)
    for key,body,kind in [(keys.html_key,b'original report unchanged','text/html'),
                           (keys.md_key,b'original markdown unchanged','text/markdown'),
                           (keys.data_key,json.dumps(old,ensure_ascii=False).encode(),'application/json')]:
        storage.save_report(key,body,content_type=kind)
    return storage,keys

def test_saved_2308_all_18_originals_replay_without_freshening(captured):
    old,_,value = captured
    before = deepcopy(value)
    projected = project_source_value(value,'2308.TW')
    assert projected is not None
    assert value == before
    assert all(projected[k]==old['data'][k] for k in HISTORY_FIELDS)
    assert min(p['raw_receipt']['retrieved_at'] for d in value['documents'] for p in d['components']) == 1791877998.803464
    assert old['data']['source_freshness']['financial_statements']['fetched_at_epoch'] == 1791878000.442946

@pytest.mark.parametrize('mutation',['wrong_ticker','individual','wrong_currency','changed_fact','missing_original'])
def test_old_proof_is_not_eligible_if_incompatible_or_tampered(captured,mutation):
    _,_,value = captured
    if mutation=='wrong_ticker': value['ticker']='2454.TW'
    elif mutation=='individual': value['report_scope']='individual'
    elif mutation=='wrong_currency': value['currency']='USD'
    elif mutation=='changed_fact': value['raw_twd_by_year']['2021']['revenue_history'] += 1
    elif mutation=='missing_original': Path(value['documents'][0]['components'][0]['raw_receipt']['raw_response_path']).unlink()
    assert project_source_value(value,'2308.TW') is None

def test_source_only_failure_preserves_all_old_snapshot_bytes(captured,tmp_path,monkeypatch):
    old,current,value = captured
    assert project_source_value(value,'2308.TW') is not None
    init_db(); baseline_events = events()
    storage,keys = saved_bundle(old)
    before = storage.get_report(keys.data_key).content
    failure = deepcopy(next(a for a in current['source_audit'] if a.get('provider')=='TWSE MOPS public annual JSON'))
    calls = []
    def attempt(ticker,**kwargs):
        calls.append(ticker)
        return {'value':None,'audit':failure}
    import data_fetch.official_financial_gap_cache as native
    monkeypatch.setattr(native,'fetch_official_financial_result',attempt)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(refresh_report_data_snapshot(FILENAME, output_dir=str(tmp_path), storage=storage,
              refresh_service=StockDataService(),source='financial_statements'))
    assert raised.value.status_code==502
    assert calls==['2308.TW']
    assert storage.get_report(keys.data_key).content==before
    new = events()[len(baseline_events):]
    assert len(new)==1 and new[0]['status']=='error' and new[0]['record_count']==0

@pytest.mark.parametrize('entry',['fetch_async','reused_payload'])
def test_general_refresh_should_retain_verified_annual_slice_after_transient_failure(captured,tmp_path,entry):
    """Expected genuine RED: public refresh currently replaces all annual fields."""
    old,current,value = captured
    assert project_source_value(value,'2308.TW') is not None
    init_db(); before_events=events()
    storage,keys = saved_bundle(old)
    incoming=deepcopy(current['data'])
    incoming_hash=digest(incoming)
    calls=[]
    async def fetch(request):
        calls.append(request)
        return deepcopy(incoming)
    service=StockDataService(fetcher=fetch)
    observed_provider=[]
    original_fetch=service.fetch_async
    async def observe(request):
        result=await original_fetch(request)
        observed_provider.append(deepcopy(result.data))
        return result
    service.fetch_async=observe
    kwargs={'refreshed_data':incoming} if entry=='reused_payload' else {}
    response=asyncio.run(refresh_report_data_snapshot(FILENAME, output_dir=str(tmp_path), storage=storage,
                         refresh_service=service,return_refreshed_data=True,**kwargs))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert digest(incoming)==incoming_hash
    assert len(calls)==(entry=='fetch_async')
    assert storage.get_report(keys.html_key).content==b'original report unchanged'
    assert storage.get_report(keys.md_key).content==b'original markdown unchanged'
    for key in ('analysis_evidence','analysis_completeness','oos_evaluation_inputs','report_lint','evidence_exit_gate','report_conformance','content_credibility','final_audit'):
        if key in old: assert saved[key]==old[key]
    assert saved['data']['current_price']==incoming['current_price']
    failures=[a for a in saved['source_audit'] if a.get('provider')=='TWSE MOPS public annual JSON' and a.get('status')=='error']
    assert len(failures)==1 and failures[0]['error_kind']=='timeout'
    if entry=='reused_payload': assert events()==before_events
    else:
        new_events=events()[len(before_events):]
        assert not any(r['source']=='financial_statements' and r['record_count']==5 for r in new_events)
    # Current code returns ['2022','2023','2024','2025'] here. Do not weaken this.
    assert saved['data']['years']==old['data']['years'], 'complete saved official annual series was replaced by a partial provider fallback'
    for key in HISTORY_FIELDS:
        assert saved['data'][key]==old['data'][key]
    assert response['analysis_text_stale'] is True
    # StockDataService recalculates trust against its isolated observation
    # ledger. Compare the actual returned provider packet, not pre-service input.
    assert response['refreshed_data']==(observed_provider[0] if observed_provider else incoming)
    assert saved['data']['annual_history_retention']['new_acquisition'] is False
    assert saved['source_freshness']['financial_statements']['fetched_at_epoch']==1791878000.442946
    assert saved['source_freshness']['financial_statements']['cache_hit'] is True
    assert saved['source_freshness']['financial_statements']['stale'] is True
    assert all(len(saved['data'][k])==5 for k in ('gross_margin_history','op_margin_history','net_margin_history','roe_history'))
    assert saved['source_freshness']['market_data']==incoming['source_freshness']['market_data']
    assert 'financial_statements' in saved['data_trust']['critical_failures']


@pytest.mark.parametrize('mutation', ['wrong_currency','wrong_issuer','newer_year','complete_new',
    'official_conflict','explicit_individual','terminal_failure','no_failure','missing_original','modified_history'])
def test_general_refresh_does_not_retain_incompatible_or_superseded_history(captured,tmp_path,mutation):
    old,current,_=captured
    incoming=deepcopy(current['data'])
    failure=next(a for a in incoming['source_audit'] if a.get('provider')=='TWSE MOPS public annual JSON')
    if mutation=='wrong_currency': incoming['financial_currency']='USD'
    elif mutation=='wrong_issuer': old['data']['ticker']='2454.TW'
    elif mutation=='newer_year': incoming['years']=['2023','2024','2025','2026']
    elif mutation=='complete_new': incoming.update({k:deepcopy(old['data'][k]) for k in HISTORY_FIELDS})
    elif mutation=='official_conflict': failure['raw_twd_by_year']={'2025':{'revenue_history':1}}
    elif mutation=='explicit_individual': failure['report_scope']='individual'
    elif mutation=='terminal_failure': failure.update(error_kind='access_denied',http_status=403)
    elif mutation=='no_failure': incoming['source_audit'].remove(failure)
    elif mutation=='modified_history': old['data']['operating_income_history'][-1]+=1
    elif mutation=='missing_original':
        audit=next(a for a in old['source_audit'] if a.get('raw_twd_by_year'))
        Path(audit['documents'][0]['components'][0]['raw_receipt']['raw_response_path']).unlink()
    init_db(); storage,keys=saved_bundle(old)
    asyncio.run(refresh_report_data_snapshot(FILENAME,output_dir=str(tmp_path),storage=storage,
                refresh_service=StockDataService(),refreshed_data=incoming))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert saved['data']['years']==incoming['years']
    assert saved['data'].get('annual_history_retention') is None


def test_repeated_report_local_reuse_preserves_epoch_and_never_leaks_to_second_report(captured,tmp_path):
    old,current,_=captured
    incoming=deepcopy(current['data']);init_db();before=events()
    storage,keys=saved_bundle(old)
    first=asyncio.run(refresh_report_data_snapshot(FILENAME,output_dir=str(tmp_path),storage=storage,
                    refresh_service=StockDataService(),refreshed_data=incoming,return_refreshed_data=True))
    once=json.loads(storage.get_report(keys.data_key).content)
    assert once['data']['years']==old['data']['years']
    asyncio.run(refresh_report_data_snapshot(FILENAME,output_dir=str(tmp_path),storage=storage,
                refresh_service=StockDataService(),refreshed_data=first['refreshed_data']))
    twice=json.loads(storage.get_report(keys.data_key).content)
    assert twice['data']['annual_history_retention']==once['data']['annual_history_retention']
    assert twice['source_freshness']['financial_statements']['fetched_at_epoch']==1791878000.442946
    other,otherkeys=saved_bundle(current)
    asyncio.run(refresh_report_data_snapshot(FILENAME,output_dir=str(tmp_path),storage=other,
                refresh_service=StockDataService(),refreshed_data=first['refreshed_data']))
    second=json.loads(other.get_report(otherkeys.data_key).content)
    assert second['data']['years']==incoming['years']
    assert second['data'].get('annual_history_retention') is None
    assert events()==before


def test_new_complete_source_only_acquisition_retires_saved_retention_origin(tmp_path,monkeypatch):
    from test_report_annual_financial_source_refresh import report,acquire
    init_db();storage,name,keys,old=report();acquire(monkeypatch)
    old['data']['annual_history_retention']={'policy':'report-local-verified-mops-annual-retention.v1','original_audit':{'historical':True}}
    note='年度財報沿用此報告已核對原件：older saved observation'
    old['data']['data_source_notes']=[note]
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
                refresh_service=StockDataService(),source='financial_statements'))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert 'annual_history_retention' not in saved['data']
    assert note not in saved['data']['data_source_notes']
    archived=[r for r in saved['data']['source_record_archive'] if r.get('reason')=='superseded_saved_annual_retention']
    assert archived[0]['retention']==old['data']['annual_history_retention']
