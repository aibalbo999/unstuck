"""Discovery originals stay bound to new acquisitions, not invented on replay."""
from copy import deepcopy
from datetime import datetime
import time
import httpx
import pytest
from test_mops_public_annual_financial import fixture_http
from test_public_annual_gap_cache import isolated_cache_and_provider

PROTOCOL='mops-public-consolidated-index-bound.v1'
PREVIOUS='10b71fc346a7584aadba622b1d4ee6458017a8eee51ba6c8aef99bdd8be72750'

def fetch():
    from data_fetch.market_sources import mops_public_annual as m
    def index(request):
        if str(request.url)==m.INDEX_URL:
            links=' '.join('/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3443&year='+str(y)+'&season=4&report_id=C'for y in range(2013,2026))
            return httpx.Response(200,content=('<html><body>'+links+'</body></html>').encode(),headers={'content-type':'text/html'})
    return m.fetch_public_financial_result('3443.TW',transport=m.PublicMopsHttp(client_factory=fixture_http(mutate=index)))

def test_new_acquisition_saves_actual_discovery_original_and_projects_latest_five():
    from data_fetch.market_sources import mops_public_annual as m
    from official_response_evidence import read_response
    out=fetch();assert out['audit']['status']=='success'
    v=out['value'];assert v.get('acquisition_protocol')==PROTOCOL
    assert b'co_id=3443'in read_response(v['published_index_receipt'])
    assert m.project_public_history(v,'3443.TW')is not None

@pytest.mark.parametrize('damage',['missing_receipt','missing_protocol','wrong_protocol','wrong_issuer','latest_year','newer_individual','truncated','before_close','boolean_status'])
def test_new_index_manifest_rejects_lost_wrong_or_stale_discovery(damage):
    from data_fetch.market_sources import mops_public_annual as m
    from official_response_evidence import read_response,archive_response
    v=deepcopy(fetch()['value']);v['acquisition_protocol']=PROTOCOL
    # Baseline deliberately has no top-level index: use a complete test body
    # to exercise admission itself as well as the acquisition assertion above.
    raw=('<html>'+' '.join('/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3443&year='+str(y)+'&season=4&report_id=C'for y in range(2021,2026))+'</html>').encode()
    v['published_index_receipt']=archive_response(raw,source_url=m.INDEX_URL,retrieved_at=time.time())
    if damage=='missing_receipt':v.pop('published_index_receipt')
    elif damage=='missing_protocol':v.pop('acquisition_protocol')
    elif damage=='wrong_protocol':v['acquisition_protocol']='unknown'
    elif damage=='before_close':v['published_index_receipt']['retrieved_at']=1704038400
    elif damage=='boolean_status':v['published_index_receipt']['http_status']=True
    else:
        if damage=='wrong_issuer':raw=raw.replace(b'co_id=3443',b'co_id=2330')
        elif damage=='latest_year':raw=raw.replace(b'year=2025',b'year=2020')
        elif damage=='newer_individual':raw=raw.replace(b'year=2025&season=4&report_id=C',b'year=2025&season=4&report_id=A')
        else:raw=raw.replace(b'</html>',b'')
        v['published_index_receipt']=archive_response(raw,source_url=m.INDEX_URL,retrieved_at=time.time())
    assert m.project_public_history(v,'3443.TW')is None

def test_legacy_five_year_originals_are_preserved_without_inventing_index_provenance():
    from test_mops_public_annual_financial import captured_value
    from data_fetch.market_sources.mops_public_annual import project_public_history
    old=captured_value();assert 'acquisition_protocol'not in old and 'published_index_receipt'not in old
    assert project_public_history(old,'3443.TW')is not None
    assert 'published_index_receipt'not in old

def test_existing_verified_failure_keeps_original_retry_time_across_manifest_release(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as m
    from test_public_short_annual_index_gap_cache import ShortIndexTransport,run
    monkeypatch.setattr(m,'_fingerprint',lambda:PREVIOUS)
    cold_http=ShortIndexTransport();cold=run(cold_http)
    writes=[];original_set=m.set_cache_json
    monkeypatch.setattr(m,'set_cache_json',lambda *args,**kw:(writes.append((args,kw)),original_set(*args,**kw))[1])
    monkeypatch.setattr(m,'_fingerprint',lambda:'f'*64)
    warm_http=ShortIndexTransport();warm=run(warm_http)
    assert not warm_http.calls and not writes
    assert warm['value']is None and warm['audit']['status']=='error'and warm['audit']['record_count']==0
    assert warm['audit']['http_request_count']==0
    assert warm['audit']['fetched_at']==cold['audit']['fetched_at']
    assert warm['audit']['retry_at']==datetime.fromisoformat(cold['audit']['fetched_at']).timestamp()+86400

@pytest.mark.parametrize('damage',['expired','wrong_receipt'])
def test_previous_fingerprint_does_not_license_stale_or_malformed_failure(monkeypatch,damage):
    from data_fetch.market_sources import mops_public_gap_cache as m
    from test_public_short_annual_index_gap_cache import ShortIndexTransport,run
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(m,'_fingerprint',lambda:PREVIOUS)
    run(ShortIndexTransport())
    key=f'mops-public-annual-validation-gap:{PREVIOUS}:{datetime.now(ZoneInfo("Asia/Taipei")).year}:7740.TW'
    stored=m.get_cache_json(key)
    if damage=='expired':
        stamp=time.time()-86401;stored['audit']['fetched_at_epoch']=stamp
        stored['audit']['fetched_at']=datetime.fromtimestamp(stamp,ZoneInfo('UTC')).isoformat()
    else:stored['originals'][0]['raw_receipt']['source_url']='https://example.invalid/'
    m.set_cache_json(key,stored,86400)
    monkeypatch.setattr(m,'_fingerprint',lambda:'f'*64)
    current=ShortIndexTransport();out=run(current)
    assert len(current.calls)==1 and out['audit']['cache_hit']is False
    assert out['value']is None and out['audit']['status']=='error'

def test_prompt_copy_hides_new_private_index_path_without_mutating_evidence():
    import json
    from prompt_evidence import prompt_evidence_copy
    v=fetch()['value'];before=deepcopy(v);public=prompt_evidence_copy(v)
    assert 'raw_response_path'not in json.dumps(public)
    assert v==before and v['published_index_receipt']['raw_response_path']

def test_actual_taifeng_full_originals_replay_missing_fcf_and_index_binding():
    """Replay the previous live acquisition; 19 mock requests are not HTTP proof."""
    from pathlib import Path
    from data_fetch.market_sources import mops_public_annual as m
    from official_response_evidence import read_response
    import json
    f=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261103/taifeng-full-public-annual'
    calls=[]
    def response(request):
        calls.append(request);url=str(request.url)
        if url==m.INDEX_URL:name='original-index-recovered-by-audit-sha.bin'
        elif url in {m.template_url(s)for s in m.STATEMENTS}:
            s=next(s for s in m.STATEMENTS if m.template_url(s)==url);name='original-'+s+'-template.bin'
        else:
            p=json.loads(request.content);assert p['companyId']=='2102'
            year=int(p['year'])+1911;s=next(s for s in m.STATEMENTS if m.api_url(s)==url)
            name='original-'+str(year)+'-'+s+'.bin'
        ctype='text/html'if url==m.INDEX_URL else'text/javascript'if '/assets/'in url else'application/json'
        return httpx.Response(200,content=(f/name).read_bytes(),headers={'content-type':ctype})
    http=m.PublicMopsHttp(client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(response),**kw))
    result=m.fetch_public_financial_result('2102.TW',transport=http);v=result['value']
    assert result['audit']['status']=='success'and len(calls)==19,result['audit']
    assert v['acquisition_protocol']==PROTOCOL and m.project_public_history(v,'2102.TW')is not None
    assert read_response(v['published_index_receipt'])==(f/'original-index-recovered-by-audit-sha.bin').read_bytes()
    assert v['raw_twd_by_year']['2021']['free_cash_flow']==-761795000-369391000-3895000==-1135081000
    assert v['fcf_history'][0]==-1.135081

def test_four_filing_manifest_with_malformed_first_document_fails_closed():
    from data_fetch.market_sources import mops_public_annual as m
    from official_response_evidence import archive_response
    v=fetch()['value'];v['documents']=[None,*v['documents'][2:]]
    raw=('<html>'+' '.join('/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=3443&year='+str(y)+'&season=4&report_id=C'for y in range(2022,2026))+'</html>').encode()
    v['published_index_receipt']=archive_response(raw,source_url=m.INDEX_URL,retrieved_at=time.time())
    assert m.project_public_history(v,'3443.TW')is None
