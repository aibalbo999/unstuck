"""Actual public conference transports, with captured complete master originals."""
from hashlib import sha256
from importlib import import_module
import time
from urllib.parse import urlsplit
import pytest
from test_annual_shared_issuer_master import native_master, RAW, CSV, JSON, NOW
from test_shared_provider_cache import memory_cache

NAMES = ('tewc', 'delta', 'unitech', 'tcfhc')

def transport(name):
    if name == 'tcfhc':
        return import_module('data_fetch.market_sources.tcfhc_qa_transport')
    return import_module('data_fetch.market_sources.' + name + '_conference_transport')

@pytest.mark.parametrize('name', NAMES)
def test_public_csv_timeout_recovers_complete_json_master(native_master, name):
    calls, _ = native_master
    h = transport(name).ConferenceHttp(time.monotonic() + 25)
    raw, receipt = h.get_receipt(CSV)
    assert raw == RAW and receipt['source_url'] == JSON
    assert receipt['raw_response_sha256'] == sha256(RAW).hexdigest()
    assert receipt['evidence_kind'] == 'decoded_http_response_bytes'
    assert [c[0] for c in calls] == [CSV, JSON]
    assert h.http_request_count == 2
    assert h.components[0]['error_kind'] == 'timeout'
    assert transport(name).original_bytes(receipt, JSON, max_age=1800) == RAW
    source = import_module('data_fetch.market_sources.' + name + '_conference')
    assert source.parse_master(raw, receipt['retrieved_at'], receipt['source_url'])['ticker']


def source(name):
    return import_module('data_fetch.market_sources.' + name + '_conference')


def _legacy_key(name, kind):
    t = transport(name)
    return (t.ConferenceHttp._admission_key(CSV) if kind == 'admission' else
            'shared_provider:v1:' + sha256((t.ConferenceHttp.raw_cache_prefix + CSV).encode()).hexdigest())


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('kind,state', [
    ('admission', {}), ('admission', {'retry_at': True}), ('admission', {'retry_at': float('nan')}),
    ('admission', {'retry_at': NOW + 60}), ('raw', {'error_kind':'timeout'}),
    ('raw', {'error_kind':False}), ('raw', {'error_kind':'SourceResponseError', 'retry_after_epoch':NOW + 60}),
    ('raw', {'error_kind':'HTTPStatusError', 'http_status':403, 'retry_after_epoch':NOW + 60}),
])
def test_old_source_namespace_blocks_cold_both_endpoints(native_master, name, kind, state):
    import cache_store
    from search_provider_runtime import SourceResponseError
    calls, _ = native_master
    cache_store.set_cache_json(_legacy_key(name, kind), state, ttl_seconds=1800)
    h = transport(name).ConferenceHttp(time.monotonic()+25)
    with pytest.raises(SourceResponseError): h.get_receipt(CSV)
    assert not calls and h.http_request_count == 0


@pytest.mark.parametrize('name', NAMES)
def test_old_guard_storage_failure_does_not_allow_network(native_master, monkeypatch, name):
    import cache_store
    from search_provider_runtime import SourceResponseError
    old = cache_store.get_cache_json
    def read(key):
        if key == _legacy_key(name, 'raw'): raise OSError('isolated unavailable store')
        return old(key)
    monkeypatch.setattr(cache_store, 'get_cache_json', read)
    h = transport(name).ConferenceHttp(time.monotonic()+25)
    with pytest.raises(SourceResponseError): h.get_receipt(CSV)
    assert not native_master[0] and h.http_request_count == 0


@pytest.mark.parametrize('status', [401,403,429])
@pytest.mark.parametrize('name', NAMES)
def test_denied_csv_never_calls_json(native_master, name, status):
    from search_provider_runtime import SourceResponseError
    calls, control = native_master; control.update(csv_status=status, csv_rc=0)
    h = transport(name).ConferenceHttp(time.monotonic()+25)
    with pytest.raises(SourceResponseError): h.get_receipt(CSV)
    assert [c[0] for c in calls] == [CSV] and h.http_request_count == 1


@pytest.mark.parametrize('name', NAMES)
def test_malformed_successful_csv_does_not_authorize_fallback(native_master, name):
    from search_provider_runtime import SourceResponseError
    calls, control = native_master; control.update(csv_rc=0, csv_body=b'not a complete issuer roster')
    h = transport(name).ConferenceHttp(time.monotonic()+25)
    with pytest.raises((SourceResponseError, ValueError)): h.get_receipt(CSV)
    assert [c[0] for c in calls] == [CSV]


def test_shared_json_warm_across_issuers_keeps_original_epoch_and_short_expiry(native_master, monkeypatch):
    import cache_store
    calls, control = native_master; control['policy'] = 'max-age=300'
    first = transport('tewc').ConferenceHttp(time.monotonic()+25).get_receipt(CSV)[1]
    assert first['fresh_until_epoch'] == NOW+300
    calls.clear(); monkeypatch.setattr(time,'time',lambda:NOW+30)
    for name in ('delta','unitech','tcfhc'):
        # Warm shared identity is legitimate despite a cold old-namespace lease.
        cache_store.set_cache_json(_legacy_key(name,'admission'),{'retry_at':NOW+90},ttl_seconds=100)
        h = transport(name).ConferenceHttp(time.monotonic()+25,force_refresh=True,use_cache=False)
        raw, receipt = h.get_receipt(CSV)
        assert raw == RAW and receipt['cache_hit'] is True
        assert receipt['retrieved_at'] == first['retrieved_at'] == NOW
        assert receipt['fresh_until_epoch'] == first['fresh_until_epoch']
        assert not calls and h.http_request_count == 0


@pytest.mark.parametrize('name', NAMES)
def test_deadline_and_direct_json_cannot_create_hidden_request(native_master, name):
    from search_provider_runtime import SourceResponseError
    for url, deadline in ((CSV,time.monotonic()-1),(JSON,time.monotonic()+25)):
        h=transport(name).ConferenceHttp(deadline)
        with pytest.raises(SourceResponseError): h.get_receipt(url)
    assert not native_master[0]


@pytest.mark.parametrize('name', NAMES)
def test_receipt_legacy_and_shared_dispatch_is_explicit(native_master, name):
    from copy import deepcopy
    from official_response_evidence import archive_response
    from pathlib import Path
    calls, _ = native_master
    h=transport(name).ConferenceHttp(time.monotonic()+25)
    raw,new=h.get_receipt(CSV)
    for key in ('retrieval_policy','acquisition_manifest','wire_original','response_metadata'):
        changed=deepcopy(new);changed.pop(key)
        with pytest.raises(ValueError):transport(name).original_bytes(changed,JSON,max_age=1800)
    with pytest.raises(ValueError):transport(name).original_bytes(new,CSV,max_age=1800)
    oldraw=(Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes()
    old=archive_response(oldraw,source_url=CSV,retrieved_at=NOW)
    old.update(http_status_observed=True,request_method='GET',response_complete=True,cache_hit=False)
    assert transport(name).original_bytes(old,CSV,max_age=1800)==oldraw
    assert source(name).parse_master(oldraw,NOW)['ticker']
    old['retrieval_policy']='damaged-new-receipt'
    with pytest.raises(ValueError):transport(name).original_bytes(old,CSV,max_age=1800)


@pytest.mark.parametrize('name', NAMES)
def test_historical_parser_changes_date_age_only(native_master, monkeypatch, name):
    s=source(name); original=s.parse_master(RAW,NOW,JSON)
    monkeypatch.setattr(time,'time',lambda:NOW+40*86400)
    with pytest.raises(ValueError):s.parse_master(RAW,NOW,JSON)
    assert s.parse_master(RAW,NOW,JSON,as_of_epoch=NOW)==original
    for stamp in (True,float('nan'),float('inf'),NOW-1,NOW+41*86400):
        with pytest.raises(ValueError):s.parse_master(RAW,NOW,JSON,as_of_epoch=stamp)
    # JSON cannot be relabelled as old CSV.
    with pytest.raises(ValueError):s.parse_master(RAW,NOW,CSV,as_of_epoch=NOW)


def packet_transport(name, monkeypatch):
    """Saved issuer body originals; only master native process is simulated above."""
    import base64,gzip
    from pathlib import Path
    root=Path(__file__).parents[1];fixtures=root/'tests/fixtures/source_acquisition'
    t=transport(name)
    if name=='tewc':
        from test_tewc_conference import MASTER,INDEX,VIEWER,REDIRECT,PDF
        bodies={url:gzip.decompress((fixtures/f'tewc1623_{kind}_20261014.gz').read_bytes()) for url,kind in ((INDEX,'index'),(VIEWER,'viewer'),(REDIRECT,'redirect'),(PDF,'pdf'))}
    elif name=='delta':
        from test_delta_conference import INDEX,PDF
        bodies={url:gzip.decompress((fixtures/f'delta2308_{kind}_20261013.gz').read_bytes())for url,kind in ((INDEX,'index'),(PDF,'transcript'))}
    elif name == 'tcfhc':
        from test_tcfhc_conference import INDEX, EVENT, QA
        bodies = {url: gzip.decompress((fixtures / f'tcfhc5880_{kind}_20261013.gz').read_bytes())
                  for url, kind in ((INDEX, 'index'), (EVENT, 'event'), (QA, 'qa'))}
    else:
        INDEX=t.INDEX_URL;PDF=t.PDF_URL;d=root/'docs/evidence/source-acquisition/20261014/remaining-four-next'
        bodies={INDEX:(d/'unitech-conference-index.body').read_bytes(),PDF:(d/'unitech-conference-pdf.body').read_bytes()}
    calls=[]
    def download(self,url,diagnostic):
        assert url in bodies,'no hidden legacy master download'
        calls.append(url);raw=bodies[url];self.http_request_count+=1
        is_redirect=name=='tewc' and url==REDIRECT
        diagnostic.update(http_request_sent=True,http_status=303 if is_redirect else 200)
        value={'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
               'http_status':303 if is_redirect else 200,'response_complete':True,'request_method':'GET',
               'http_status_observed':True,'fetched_at_epoch':time.time()}
        if is_redirect:value.update(response_body_bytes=0,response_body_sha256=sha256(b'').hexdigest(),redirect_location=PDF)
        return value
    monkeypatch.setattr(t.ConferenceHttp,'_download',download)
    return bodies,calls


@pytest.mark.parametrize('name,count,pages', [('tewc',6,48),('delta',4,13),('unitech',4,16),('tcfhc',5,10)])
def test_full_packet_json_master_new_body_and_warm_body_audit(native_master, monkeypatch, name,count,pages):
    from copy import deepcopy
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    bodies,body_calls=packet_transport(name,monkeypatch);s=source(name)
    request=FetchRequest.from_ticker(s.TICKER);p=EarningsCallProvider()
    cold=p.fetch(request)
    assert cold.status=='success',cold.audit
    assert cold.audit['http_request_count']==count and cold.audit['cache_hit'] is False
    doc=cold.value['documents'][0];assert doc['page_count']==pages and doc['coverage_status']=='partial'
    proof=next(v for k,v in cold.value.items()if k.endswith('_receipt'))
    assert proof['identity']['source_url']==JSON and s.verify_context(cold.value,s.TICKER)
    changed=deepcopy(cold.value);next(v for k,v in changed.items()if k.endswith('_receipt'))['identity']['source_url']=CSV
    assert not s.verify_context(changed,s.TICKER)
    native_master[0].clear();body_calls.clear();monkeypatch.setattr(time,'time',lambda:NOW+30)
    warm=p.fetch(request)
    assert warm.status=='skipped_fresh_cache',warm.audit
    assert warm.audit['http_request_count']==0 and warm.value['fetched_at_epoch']==NOW
    assert not body_calls and not native_master[0]


@pytest.mark.parametrize('name', NAMES)
def test_json_source_only_preserves_analysis_other_sources_and_artifacts(native_master, monkeypatch, tmp_path, name):
    import asyncio,json
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db,events
    packet_transport(name,monkeypatch);s=source(name);init_db();storage=InMemoryStorage()
    filename,keys,old=saved_report(storage)
    def replace(v):
        if isinstance(v,str):return v.replace('6214.TW',s.TICKER).replace('精誠',s.LEGAL)
        if isinstance(v,dict):return {k:replace(x)for k,x in v.items()}
        if isinstance(v,list):return [replace(x)for x in v]
        return v
    old=replace(old);old['data']['quote_type']='EQUITY'
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    response=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                        refresh_service=service,source='earnings_call',return_refreshed_data=True))
    new=json.loads(storage.get_report(keys.data_key).content)
    assert new['data']['earnings_call']['documents'][0]['page_count'] in {48,13,16,10}
    for k in ('current_price','revenue_history','years','peer_discovery_results'):assert new['data'][k]==old['data'][k]
    for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert new[k]==old[k]
    assert next(a for a in new['source_audit']if a['source']=='market_data')==old['source_audit'][0]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert response['analysis_text_stale'] is True
    assert len(events())==1 and events()[0]['status']=='success'


@pytest.mark.parametrize('name', ('tewc', 'delta', 'unitech'))
def test_index_historical_date_selection_does_not_relax_live_default(native_master,monkeypatch,name):
    bodies,_=packet_transport(name,monkeypatch);s=source(name);raw=bodies[s.INDEX_URL]
    def select(**kwargs):
        return s.select_transcript(raw,**kwargs) if name=='delta' else s.select_presentation(raw,NOW,**kwargs)
    old=select();monkeypatch.setattr(time,'time',lambda:NOW+800*86400)
    with pytest.raises(ValueError):select()
    assert select(as_of_epoch=NOW)==old
    bad=(True,float('nan'),float('inf'),NOW+801*86400) if name=='delta' else (True,float('nan'),float('inf'),NOW-1,NOW+801*86400)
    for epoch in bad:
        with pytest.raises(ValueError):select(as_of_epoch=epoch)


@pytest.mark.parametrize('name', NAMES)
def test_legacy_csv_identity_still_replays_full_saved_packet(native_master,monkeypatch,name):
    from official_response_evidence import archive_response
    from pathlib import Path
    packet_transport(name,monkeypatch);s=source(name)
    value=getattr(s,'fetch_'+name+'_context')(s.TICKER)
    proof=next(v for k,v in value.items()if k.endswith('_receipt'))
    raw=(Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes()
    receipt=archive_response(raw,source_url=CSV,retrieved_at=NOW)
    receipt.update(http_status_observed=True,request_method='GET',response_complete=True,cache_hit=False)
    proof['identity']=receipt
    proof['policy']=s.LEGACY_POLICY
    assert s.verify_context(value,s.TICKER,max_age=1800)


@pytest.mark.parametrize('name', NAMES)
def test_force_refresh_reuses_identity_but_reacquires_body(native_master,monkeypatch,name):
    bodies,calls=packet_transport(name,monkeypatch);s=source(name);fetch=getattr(s,'fetch_'+name+'_context')
    first=fetch(s.TICKER);calls.clear();native_master[0].clear();monkeypatch.setattr(time,'time',lambda:NOW+30)
    d={};again=fetch(s.TICKER,force_refresh=True,diagnostics=d)
    assert len(calls)==len(bodies) and not native_master[0]
    assert d['http_request_count']==len(bodies) and d['cache_hit'] is False
    assert first['fetched_at_epoch']==NOW and again['fetched_at_epoch']==NOW+30
    proof=next(v for k,v in again.items()if k.endswith('_receipt'))
    assert proof['identity']['cache_hit'] is True and proof['identity']['retrieved_at']==NOW


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('mode',['fetch','verify'])
def test_short_master_expiry_rechecked_after_last_body_read(native_master,monkeypatch,name,mode):
    from search_provider_runtime import SourceResponseError
    native_master[1]['policy']='max-age=5';packet_transport(name,monkeypatch);s=source(name)
    fetch=getattr(s,'fetch_'+name+'_context')
    value=fetch(s.TICKER) if mode=='verify' else None
    original=s.original_bytes;reads=0
    def delayed(receipt,url,**kwargs):
        nonlocal reads
        raw=original(receipt,url,**kwargs)
        if urlsplit(url).path.endswith('.pdf') or '/download?' in url:
            reads+=1
            if reads==2:monkeypatch.setattr(time,'time',lambda:NOW+5.1)
        return raw
    monkeypatch.setattr(s,'original_bytes',delayed)
    if mode=='verify':assert not s.verify_context(value,s.TICKER,max_age=1800)
    else:
        d={}
        with pytest.raises(SourceResponseError):fetch(s.TICKER,diagnostics=d)
        assert d.get(name+'_originals_verified') is False and d['http_request_count']=={'tewc':6,'delta':4,'unitech':4,'tcfhc':5}[name]
    assert reads==2


@pytest.mark.parametrize('name',NAMES)
def test_wrong_json_issuer_does_not_get_bodies_or_try_another_master(native_master,monkeypatch,name):
    import json,gzip
    from search_provider_runtime import SourceResponseError
    _,calls=packet_transport(name,monkeypatch);s=source(name)
    rows=json.loads(RAW);row=next(r for r in rows if r['公司代號']==s.TICKER[:4]);row['公司名稱']='不同公司股份有限公司'
    native_master[1]['wire']=gzip.compress(json.dumps(rows,ensure_ascii=False).encode())
    with pytest.raises(SourceResponseError):getattr(s,'fetch_'+name+'_context')(s.TICKER)
    assert not calls and [c[0]for c in native_master[0]]==[CSV,JSON]


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('bad',[None,True,float('nan'),float('inf'),0,NOW+1])
def test_required_receipt_epoch_is_finite_and_not_future(native_master,name,bad):
    with pytest.raises(ValueError):source(name).parse_master(RAW,bad,JSON,as_of_epoch=NOW)


@pytest.mark.parametrize('name',NAMES)
def test_historical_shared_read_is_archive_only_without_renewing_epoch(native_master,monkeypatch,name):
    from data_fetch.market_sources import official_issuer_master as shared
    h=transport(name).ConferenceHttp(time.monotonic()+25);raw,receipt=h.get_receipt(CSV)
    stamp=receipt['retrieved_at'];expiry=receipt['fresh_until_epoch']
    monkeypatch.setattr(time,'time',lambda:NOW+40*86400)
    def forbidden(*args,**kwargs):raise AssertionError('historical original read must not access shared cache')
    monkeypatch.setattr(shared,'get_cache_json',forbidden);monkeypatch.setattr(shared,'set_cache_json',forbidden)
    assert transport(name).original_bytes(receipt,JSON,max_age=100*366*86400)==raw
    assert receipt['retrieved_at']==stamp and receipt['fresh_until_epoch']==expiry
    with pytest.raises(ValueError):transport(name).original_bytes(receipt,JSON,max_age=1800)


@pytest.mark.parametrize('name',NAMES)
def test_component_handoff_must_not_outlive_short_master(native_master,monkeypatch,name):
    from search_provider_runtime import SourceResponseError
    native_master[1]['policy']='max-age=5';packet_transport(name,monkeypatch);s=source(name);old=s.deepcopy
    def copy(value):
        result=old(value)
        if isinstance(value,list) and any(isinstance(x,dict)and 'http_request_sent'in x for x in value):
            monkeypatch.setattr(time,'time',lambda:NOW+5.1)
        return result
    monkeypatch.setattr(s,'deepcopy',copy)
    d={}
    with pytest.raises(SourceResponseError):getattr(s,'fetch_'+name+'_context')(s.TICKER,diagnostics=d)
    assert d[name+'_originals_verified'] is False


@pytest.mark.parametrize('name',NAMES)
def test_new_shared_csv_proof_cannot_drop_all_master_metadata(native_master,monkeypatch,name):
    from pathlib import Path
    from data_fetch.market_sources.tcfhc_conference_transport import RECEIPT_FIELDS
    native_master[1].update(csv_rc=0,csv_body=(Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes())
    packet_transport(name,monkeypatch);s=source(name);value=getattr(s,'fetch_'+name+'_context')(s.TICKER)
    proof=next(v for k,v in value.items()if k.endswith('_receipt'))
    assert 'retrieval_policy' in proof['identity']
    proof['identity']={k:v for k,v in proof['identity'].items()if k in RECEIPT_FIELDS}
    assert not s.verify_context(value,s.TICKER,max_age=1800)


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('variant',['json','csv'])
def test_old_policy_cannot_claim_new_shared_master(native_master,monkeypatch,name,variant):
    from pathlib import Path
    if variant=='csv':native_master[1].update(csv_rc=0,csv_body=(Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes())
    packet_transport(name,monkeypatch);s=source(name);value=getattr(s,'fetch_'+name+'_context')(s.TICKER)
    proof=next(v for k,v in value.items()if k.endswith('_receipt'));proof['policy']=s.LEGACY_POLICY
    assert not s.verify_context(value,s.TICKER,max_age=1800)


@pytest.mark.parametrize('name',NAMES)
def test_old_policy_json_is_never_legacy_even_with_all_markers_removed(native_master,monkeypatch,name):
    from data_fetch.market_sources.tcfhc_conference_transport import RECEIPT_FIELDS
    packet_transport(name,monkeypatch);s=source(name);value=getattr(s,'fetch_'+name+'_context')(s.TICKER)
    proof=next(v for k,v in value.items()if k.endswith('_receipt'));proof['policy']=s.LEGACY_POLICY
    proof['identity']={k:v for k,v in proof['identity'].items()if k in RECEIPT_FIELDS}
    assert not s.verify_context(value,s.TICKER,max_age=1800)
