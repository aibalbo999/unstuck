"""Real CAL gzip bytes must traverse the public transport with original receipts."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import gzip,json,time
import pytest

R=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261014/annual-master-and-retention/master-implementation/cal-gzip-research'
WIRE=(R/'response.wire').read_bytes();RAW=(R/'response.decoded.html').read_bytes()
HEADERS=(R/'response.headers').read_bytes();META=(R/'response.metadata').read_bytes()
assert sha256(WIRE).hexdigest()=='e9c91a682e16b385bd6cdaf18774624188df3e04e026482a7aede7cb9c530b62'
assert sha256(RAW).hexdigest()=='9908f12ede501449e12658cae3869cb26285757545efc4487866a23fd034a5ee'

@pytest.fixture
def native(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as native
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    monkeypatch.setattr(native,'cooldown_state',lambda key:None)
    monkeypatch.setattr(native,'remember_failure',lambda *a:None)
    state={'calls':[],'body':WIRE,'headers':HEADERS,'metadata':META,'rc':0,'error':None}
    def run(args,deadline,**kwargs):
        state['calls'].append((args,deadline,kwargs))
        return {k:state[k]for k in ('body','headers','metadata')}|{'process_started':True},state['rc'],state['error']
    monkeypatch.setattr(native,'collect_capped_process',run)
    return state

def test_public_bridge_accepts_complete_real_gzip_and_preserves_typed_wire(native):
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL,parse_index
    from data_fetch.market_sources.cal_annual_bridge import _native
    h=BridgeHttp();body,receipt=h.request(IR_URL)
    assert body==RAW and _native(receipt,IR_URL,1_500_000)==RAW
    assert receipt['raw_response_sha256']==sha256(WIRE).hexdigest()
    assert receipt['decoded_original']['raw_response_sha256']==sha256(RAW).hexdigest()
    assert receipt['cal_ir_metadata']['content_encoding']=='gzip'
    assert parse_index(body)=={str(y):f'https://cms-externalcontent-prod.s3.ap-northeast-1.amazonaws.com/ci/Investor-relations/Consolidated-Financial-Statements/EN/{y}Q4.pdf'for y in (2022,2024,2025)}
    assert len(native['calls'])==1 and h.components[0]['http_request_sent']is True
    assert 'Accept-Encoding: gzip'in native['calls'][0][0]

def response(state,wire,*,encoding='gzip',status=200):
    state['body']=wire
    state['headers']=f'HTTP/2 {status}\r\ncontent-type: text/html; charset=utf-8\r\ncontent-encoding: {encoding}\r\ncontent-length: {len(wire)}\r\n\r\n'.encode()
    meta=json.loads(META);meta.update(http_code=status,size_download=len(wire));state['metadata']=json.dumps(meta).encode()

@pytest.mark.parametrize('kind',['truncated','crc','extra_member','trailing','expanded_limit','wire_limit','empty','unknown_encoding','wrong_issuer','wrong_link','wrong_url','bool_redirect','missing_method','wrong_length','duplicate_encoding','headers_incomplete','native_timeout'])
def test_invalid_transfer_never_returns_usable_original(native,kind):
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    from search_provider_runtime import SourceResponseError
    if kind=='truncated':response(native,WIRE[:-1])
    elif kind=='crc':response(native,WIRE[:-8]+bytes([WIRE[-8]^1])+WIRE[-7:])
    elif kind=='extra_member':response(native,WIRE+gzip.compress(b'extra'))
    elif kind=='trailing':response(native,WIRE+b'extra')
    elif kind=='expanded_limit':response(native,gzip.compress(b'x'*1_500_001))
    elif kind=='wire_limit':response(native,b'x'*1_500_001)
    elif kind=='empty':response(native,b'')
    elif kind=='unknown_encoding':response(native,WIRE,encoding='br')
    elif kind=='wrong_issuer':
        changed=RAW.replace(b'China Airlines',b'Another Airline');assert changed!=RAW;response(native,gzip.compress(changed))
    elif kind=='wrong_link':
        changed=RAW.replace(b'Consolidated-Financial-Statements/EN/2025Q4.pdf',b'Individual-Financial-Statements/EN/2025Q4.pdf');assert changed!=RAW;response(native,gzip.compress(changed))
    elif kind in ('wrong_url','bool_redirect','missing_method'):
        meta=json.loads(META)
        if kind=='wrong_url':meta['url_effective']=IR_URL+'&x=1'
        elif kind=='bool_redirect':meta['num_redirects']=False
        else:meta.pop('method')
        native['metadata']=json.dumps(meta).encode()
    elif kind=='wrong_length':response(native,WIRE);native['headers']=native['headers'].replace(str(len(WIRE)).encode(),b'1')
    elif kind=='duplicate_encoding':response(native,WIRE);native['headers']=native['headers'].replace(b'\r\n\r\n',b'\r\ncontent-encoding: gzip\r\n\r\n')
    elif kind=='headers_incomplete':native['headers']=HEADERS[:-2]
    else:native['rc']=28;native['error']='timeout'
    h=BridgeHttp()
    with pytest.raises((FilingError,SourceResponseError)):h.request(IR_URL)
    assert len(native['calls'])==1 and h.components[0]['http_request_sent']is True
    assert h.components[0].get('status')!='complete'

@pytest.mark.parametrize('kind',['cooldown','guard_storage','whole_deadline','post_read_deadline'])
def test_guard_or_deadline_cannot_be_bypassed(native,monkeypatch,kind):
    from data_fetch.market_sources import issuer_news_transport as transport
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from search_provider_runtime import SourceResponseError
    h=BridgeHttp();clock=[100.];monkeypatch.setattr(transport.time,'monotonic',lambda:clock[0]);h.deadline=h.native.deadline=145.
    if kind=='cooldown':monkeypatch.setattr(transport,'cooldown_state',lambda key:{'retry_at':time.time()+60})
    elif kind=='guard_storage':monkeypatch.setattr(transport,'cooldown_state',lambda key:(_ for _ in ()).throw(OSError('storage')))
    elif kind=='whole_deadline':h.deadline=h.native.deadline=99.
    else:
        run=transport.collect_capped_process
        def late(*a,**kw):
            result=run(*a,**kw);clock[0]=105.01;return result
        monkeypatch.setattr(transport,'collect_capped_process',late)
    with pytest.raises((SourceResponseError,OSError)):h.request(IR_URL)
    assert len(native['calls'])==(1 if kind=='post_read_deadline'else 0)

@pytest.mark.parametrize('status',[401,403,429,503])
def test_refusal_keeps_status_retry_after_and_no_retry(native,monkeypatch,status):
    from data_fetch.market_sources import issuer_news_transport as transport
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from search_provider_runtime import SourceResponseError
    response(native,b'refused',status=status);native['headers']=native['headers'].replace(b'\r\n\r\n',b'\r\nretry-after: 600\r\n\r\n');seen=[]
    monkeypatch.setattr(transport,'remember_failure',lambda key,exc:seen.append((key,exc.response.headers['retry-after'])))
    h=BridgeHttp()
    with pytest.raises(SourceResponseError)as raised:h.request(IR_URL)
    assert raised.value.status_code==status and len(native['calls'])==1
    assert seen==[('provider_endpoint_cooldown:Verified issuer news:www.china-airlines.com:public','600')]

@pytest.fixture
def receipt(native):
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    return BridgeHttp().request(IR_URL)[1]

@pytest.mark.parametrize('kind',['transport_policy','cal_ir_metadata','decoded_original','cal_ir_manifest','wire_hash','decoded_hash','wire_size_bool','http_status_bool','cache','epoch','decoded_epoch','encoding','url','manifest_kind','historical_claim','extra_marker'])
def test_saved_receipt_tamper_fails_closed_after_sanitizer(receipt,kind):
    from data_trust import sanitize_for_snapshot
    from data_fetch.market_sources.cal_annual_bridge import _native
    from data_fetch.market_sources.cal_annual_transport import IR_URL
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    p=deepcopy(receipt)
    if kind in {'transport_policy','cal_ir_metadata','decoded_original','cal_ir_manifest'}:p.pop(kind)
    elif kind=='wire_hash':p['raw_response_sha256']='0'*64
    elif kind=='decoded_hash':p['decoded_original']['raw_response_sha256']='0'*64
    elif kind=='wire_size_bool':p['raw_response_bytes']=True
    elif kind=='http_status_bool':p['http_status_observed']=1
    elif kind=='cache':p['cache_hit']=True
    elif kind=='epoch':p['retrieved_at']+=1
    elif kind=='decoded_epoch':p['decoded_original']['retrieved_at']+=1
    elif kind=='encoding':p['cal_ir_metadata']['content_encoding']='identity'
    elif kind=='url':p['source_url']=IR_URL+'&variant=1'
    elif kind=='manifest_kind':p['cal_ir_manifest']['evidence_kind']='raw_http_response_bytes'
    elif kind=='historical_claim':p['historical_point_in_time_verified']=True
    else:p['http_request_sent']=False
    with pytest.raises(FilingError):_native(sanitize_for_snapshot(p),IR_URL,1_500_000)


def test_snapshot_sanitizer_keeps_original_replay_and_epoch(receipt):
    from data_trust import sanitize_for_snapshot
    from data_fetch.market_sources.cal_annual_bridge import _native
    from data_fetch.market_sources.cal_annual_transport import IR_URL
    cleaned=sanitize_for_snapshot(receipt)
    assert cleaned==receipt and _native(cleaned,IR_URL,1_500_000)==RAW
    assert cleaned['retrieved_at']==receipt['decoded_original']['retrieved_at']==receipt['cal_ir_manifest']['retrieved_at']


def test_identity_response_is_recorded_truthfully_and_old_identity_replays(native):
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from data_fetch.market_sources.cal_annual_bridge import _native
    from official_response_evidence import archive_response
    from test_cal_annual_bridge import raw
    response(native,RAW,encoding='identity')
    b,p=BridgeHttp().request(IR_URL)
    assert b==RAW and p['cal_ir_metadata']['content_encoding']=='identity'and _native(p,IR_URL,1_500_000)==RAW
    old=archive_response(raw('ir-index'),source_url=IR_URL,retrieved_at=time.time(),http_status=200)
    assert _native(old,IR_URL,1_500_000)==raw('ir-index')


def test_full_five_year_public_acquisition_and_saved_packet_replay(native):
    from test_cal_annual_bridge import Http,M
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_result,project_bridge_history
    from data_trust import sanitize_for_snapshot
    class Mixed(Http):
        def request(self,url,**kwargs):
            if url!=IR_URL:return super().request(url,**kwargs)
            real=BridgeHttp();real.deadline=real.native.deadline=self.deadline
            b,p=real.request(url);self.calls.append('ir-index');self.components.extend(real.components);return b,p
    h=Mixed();result=fetch_bridge_result('2610.TW',transport=h)
    assert result['audit']['status']=='success'and result['audit']['record_count']==5, result['audit']
    value=result['value'];saved=sanitize_for_snapshot(value)
    assert saved==value and project_bridge_history(saved,'2610.TW')==saved
    assert result['audit']['http_request_count']==24 and len(h.calls)==24 and len(native['calls'])==1
    assert result['audit']['cache_hit']is False and value['years']==['2021','2022','2023','2024','2025']
    p=deepcopy(saved);receipt=p['issuer_ir_index_receipt']
    for key in ('transport_policy','cal_ir_metadata','decoded_original','cal_ir_manifest','http_status_observed','request_method','response_complete','cache_hit'):receipt.pop(key)
    assert project_bridge_history(p,'2610.TW')is None


def test_new_receipt_archive_damage_and_manifest_mismatch_are_rejected(receipt,tmp_path):
    from data_fetch.market_sources.cal_annual_bridge import _native
    from data_fetch.market_sources.cal_annual_transport import IR_URL
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    from official_response_evidence import archive_response
    p=deepcopy(receipt);original=p['cal_ir_manifest']
    p['cal_ir_manifest']=archive_response(b'{}',source_url=IR_URL,retrieved_at=p['retrieved_at'],evidence_kind='private_acquisition_manifest',http_status=None)
    with pytest.raises(FilingError):_native(p,IR_URL,1_500_000)
    target=Path(receipt['decoded_original']['raw_response_path']);before=target.read_bytes()
    try:
        target.write_bytes(b'corrupt archive')
        with pytest.raises(FilingError):_native(receipt,IR_URL,1_500_000)
    finally:target.write_bytes(before)

def test_archive_readback_time_still_consumes_original_native_deadline(native,monkeypatch):
    from data_fetch.market_sources import cal_ir_gzip as content
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from search_provider_runtime import SourceResponseError
    clock=[100.];monkeypatch.setattr(content.time,'monotonic',lambda:clock[0]);h=BridgeHttp(seconds=45)
    read=content.read_response
    def late(proof,**kwargs):
        value=read(proof,**kwargs)
        if proof['evidence_kind']=='private_acquisition_manifest':clock[0]=105.01
        return value
    monkeypatch.setattr(content,'read_response',late)
    with pytest.raises(SourceResponseError)as exc:h.request(IR_URL)
    assert exc.value.error_kind=='timeout'and len(native['calls'])==1
    assert h.components[0].get('status')!='complete'


def test_no_success_cache_and_only_exact_ir_uses_gzip(native):
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    h=BridgeHttp();a=h.request(IR_URL);b=h.request(IR_URL)
    assert a[0]==b[0]==RAW and len(native['calls'])==2
    assert a[1]['cache_hit']is b[1]['cache_hit']is False
    assert b[1]['retrieved_at']>=a[1]['retrieved_at']
    with pytest.raises(FilingError):h.request(IR_URL+'&another=1')
    assert len(native['calls'])==2

@pytest.mark.parametrize('broken',[False,True])
def test_source_only_gzip_route_preserves_conclusions_and_failure_artifacts(native,monkeypatch,tmp_path,broken):
    import asyncio
    from fastapi import HTTPException
    from test_cal_annual_bridge import Http,DATA
    from test_report_annual_financial_source_refresh import report
    from test_report_refresh_acquisition_audit import init_db
    from report_refresh_service import refresh_report_data_snapshot
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import cal_annual_bridge as bridge
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    init_db()
    class Mixed(Http):
        def request(self,url,**kwargs):
            if url!=IR_URL:return super().request(url,**kwargs)
            real=BridgeHttp();real.deadline=real.native.deadline=self.deadline
            b,p=real.request(url);self.calls.append('ir-index');self.components.extend(real.components);return b,p
    h=Mixed();monkeypatch.setattr(bridge,'BridgeHttp',lambda **kwargs:h)
    storage,name,keys,old=report('2610.TW');old['data'].update(deepcopy(DATA))
    old['analysis_completeness']={'retained':True};old['oos_evaluation_inputs']={'trade_setup':{'original':True}}
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');before=storage.get_report(keys.data_key).content
    if broken:response(native,WIRE[:-1])
    action=refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements')
    if broken:
        with pytest.raises(HTTPException)as error:asyncio.run(action)
        assert error.value.status_code==502 and storage.get_report(keys.data_key).content==before
    else:
        asyncio.run(action);saved=json.loads(storage.get_report(keys.data_key).content)
        for key in ('analysis_evidence','analysis_completeness','oos_evaluation_inputs','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert saved[key]==old[key]
        for key in ('current_price','daily_market_data','recent_catalysts','earnings_call'):assert saved['data'][key]==old['data'][key]
        assert saved['data']['years']==['2021','2022','2023','2024','2025']
        audit=next(a for a in saved['source_audit']if a['source']=='financial_statements')
        assert bridge._native(audit['issuer_ir_index_receipt'],IR_URL,1_500_000)==RAW
    assert storage.get_report(keys.html_key).content==storage.get_report(keys.md_key).content==b'original conclusions'
    assert len(native['calls'])==1


def test_content_rejection_keeps_actual_http200(native):
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp,IR_URL
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    changed=RAW.replace(b'Consolidated-Financial-Statements/EN/2025Q4.pdf',b'Individual-Financial-Statements/EN/2025Q4.pdf')
    assert changed!=RAW;response(native,gzip.compress(changed));h=BridgeHttp()
    with pytest.raises(FilingError):h.request(IR_URL)
    assert h.components[0]['http_status']==200 and h.components[0]['http_request_sent']is True
    assert h.components[0].get('status')!='complete'
