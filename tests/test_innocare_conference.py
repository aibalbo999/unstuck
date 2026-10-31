"""Complete official InnoCare originals; only network is replaced in isolation."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64,importlib,time
import pytest
ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261015/next-source-recovery'
MASTER=ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW=1791997000.0
def valid_data():
    return {'ticker':'6861.TW','company_name':'睿生光電 / InnoCare Optoelectronics Corporation',
        'raw_company_name':'InnoCare Optoelectronics Corporation','instrument_type':'EQUITY','quote_type':'EQUITY',
        'company_identity':{'ticker':'6861.TW','stock_id':'6861','official_name':'睿生光電','legal_name':'睿生光電股份有限公司',
        'official_ubn':'69764396','instrument_type':'EQUITY','allowed_aliases':['睿生光電','INCX','6861','6861.TW'],
        'english_names':['InnoCare Optoelectronics Corporation'],'forbidden_aliases':[]}}
@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import innocare_conference_transport as t
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={t.MASTER_URL:MASTER.read_bytes(),t.INDEX_URL:(D/'innocare-index.body').read_bytes(),t.PDF_URL:(D/'innocare-pdf.body').read_bytes()}
    calls=[]
    def download(self,url,diagnostic):
        raw=bodies[url];calls.append(url);self.http_request_count+=1
        meta={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(raw),
            'content_type':'text/csv'if url==t.MASTER_URL else'application/pdf'if url==t.PDF_URL else'text/html',
            'content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'no-cache'}
        if url==t.MASTER_URL:
            from data_fetch.market_sources import official_issuer_master
            meta=official_issuer_master.master_metadata(meta,raw,{})
        else:meta.update(pragma='',expires='',age=None,cf_cache_status='')
        diagnostic.update(http_request_sent=True,http_status=200,response_metadata=meta)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'request_method':'GET','request_body':None,'response_metadata':meta}
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()
def test_official_innocare_missing_body_is_recoverable_with_coverage_limits(request):
    try:s=importlib.import_module('data_fetch.market_sources.innocare_conference')
    except ModuleNotFoundError as e:
        if e.name!='data_fetch.market_sources.innocare_conference':raise
        v={}
    else:
        bodies,calls=request.getfixturevalue('harness');diag={}
        v=s.fetch_innocare_context('6861.TW',diagnostics=diag)
        assert len(calls)==diag['http_request_count']==3
        assert s.validate_context(valid_data(),'6861.TW')
        assert s.verify_context(v,'6861.TW',max_age=1800)
        assert diag['innocare_originals_verified']is True
    assert len(v.get('documents',[]))==1,'6861 official presentation body has no qualified source collector'
    d=v['documents'][0]
    assert d['page_count']==len(d['pages'])==19
    assert d['native_text_coverage']==v['coverage_status']=='partial'
    assert d['missing_text_pages']==[1,19] and d['garbled_pages']==[]
    assert d['full_visual_content_verified']is False and d['financial_statement_complete']is False
    assert d['role_page_allowlist']==[2,3,4,15]
    assert d['event_date']=='2026-09-10' and d['published_at']is None and v['period']==''
    assert not d['q_and_a_transcript_available']

@pytest.mark.parametrize('change',['date','pdf','new_history','duplicate','truncated','trailer','canonical'])
def test_index_drift_does_not_fetch_an_old_or_unqualified_pdf(harness,change):
    from data_fetch.market_sources import innocare_conference as s
    from search_provider_runtime import SourceResponseError
    bodies,calls=harness;r=bodies[s.INDEX_URL]
    if change=='date':r=r.replace(b'2026/9/10',b'2026/11/10')
    elif change=='pdf':r=r.replace(b'20260910142650_0_e8f3ed.pdf',b'new.pdf')
    elif change=='new_history':r=r.replace(b'2025/12/16',b'2026/10/14')
    elif change=='duplicate':r=r.replace(b'data-elementor-id="6463"',b'data-elementor-id="6464"')
    elif change=='truncated':r=r[:r.index(b'</html>')]
    elif change=='trailer':r+=b'<a href="new.pdf">new event</a>'
    else:r=r.replace(b'rel="canonical" href="https://www.innocare-x.com/',b'rel="canonical" href="https://wrong.test/')
    assert r!=bodies[s.INDEX_URL];bodies[s.INDEX_URL]=r
    with pytest.raises(SourceResponseError):s.fetch_innocare_context('6861.TW')
    assert calls==[s.MASTER_URL,s.INDEX_URL]

@pytest.mark.parametrize('change',['epoch','expiry','manifest','page','coverage','financial','boolean','role'])
def test_saved_proof_rejects_retiming_or_content_edits(harness,change):
    from data_fetch.market_sources import innocare_conference as s
    v=s.fetch_innocare_context('6861.TW');r=v['innocare_conference_receipt']['pdf'];d=v['documents'][0]
    if change=='epoch':r['retrieved_at']+=1
    elif change=='expiry':r['fresh_until_epoch']-=1
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='page':d['pages'][14]['text']='工廠已經完成搬遷'
    elif change=='coverage':d['native_text_coverage']='complete'
    elif change=='financial':d['financial_statement_complete']=True
    elif change=='boolean':d['binary_complete']=1
    else:d['role_page_allowlist']=list(range(1,20))
    assert not s.verify_context(v,'6861.TW',max_age=1800)

@pytest.mark.parametrize('change',['name','ubn','alias','forbidden','quote','ticker'])
def test_conflicting_caller_identity_is_rejected(change):
    from data_fetch.market_sources.innocare_conference import validate_context
    d=valid_data()
    if change=='name':d['raw_company_name']='Other company'
    elif change=='ubn':d['company_identity']['official_ubn']='00000000'
    elif change=='alias':d['company_identity']['allowed_aliases'].append('Winbond')
    elif change=='forbidden':d['company_identity']['forbidden_aliases']=['睿生光電']
    elif change=='quote':d['quote_type']='ETF'
    else:d['ticker']='6861.TWO'
    assert not validate_context(d,'6861.TW')

@pytest.mark.parametrize('options',[{}, {'force_refresh':True},{'use_cache':False}])
def test_each_issuer_acquisition_uses_native_originals(harness,options):
    from data_fetch.market_sources import innocare_conference as s
    bodies,calls=harness
    s.fetch_innocare_context('6861.TW')
    s.fetch_innocare_context('6861.TW',**options)
    assert calls.count(s.INDEX_URL)==calls.count(s.PDF_URL)==2

def test_current_real_snapshot_matches_issuer_identity():
    import json
    from data_fetch.market_sources.innocare_conference import validate_context
    p=ROOT/'docs/evidence/source-acquisition/20261015/innocare-integration/current-target.json'
    r=json.loads(p.read_text())
    assert r['body_documents']==0
    assert validate_context(r['identity_input'],'6861.TW')
