"""CHB official QA originals; replace only HTTP in the isolated harness."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64, importlib, json, time
import pytest
ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261015/chb-wahlee-free-entrances'
MASTER=ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW=1791998500.0

def valid_data():
    return json.loads((ROOT/'docs/evidence/source-acquisition/20261015/chb-qa-integration/current-target.json').read_text())['identity_input']

@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import chb_conference_transport as t
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={t.MASTER_URL:MASTER.read_bytes(),t.INDEX_URL:(D/'chb-index.body').read_bytes(),t.PDF_URL:(D/'chb-qa.body').read_bytes()}
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
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                'request_method':'GET','request_body':None,'response_metadata':meta}
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()

def test_official_chb_qa_gap_recovered_without_claiming_a_transcript(request):
    try:s=importlib.import_module('data_fetch.market_sources.chb_conference')
    except ModuleNotFoundError as e:
        if e.name!='data_fetch.market_sources.chb_conference':raise
        value={}
    else:
        bodies,calls=request.getfixturevalue('harness');diagnostic={}
        value=s.fetch_chb_context('2801.TW',diagnostics=diagnostic)
        assert len(calls)==diagnostic['http_request_count']==3
        assert s.validate_context(valid_data(),'2801.TW')
        assert s.verify_context(value,'2801.TW',max_age=1800)
    assert len(value.get('documents',[]))==1,'CHB official seven-page QA has no qualified source collector'
    doc=value['documents'][0]
    assert doc['document_kind']=='issuer_qa_summary'
    assert doc['page_count']==len(doc['pages'])==7
    assert doc['native_text_coverage']=='complete' and value['coverage_status']=='partial'
    assert doc['missing_text_pages']==doc['garbled_pages']==[]
    assert doc['financial_statement_complete']is False and doc['full_visual_content_verified']is False
    assert doc['event_date']=='2026-08-25' and doc['published_at']is None
    assert doc['content_period']=='2026Q2' and doc['question_count']==12
    assert doc['cross_page_questions']=={'2':[1,2],'4':[2,3],'6':[3,4],'12':[6,7]}
    assert value['transcript_available']is False and doc['q_and_a_transcript_available']is False

@pytest.mark.parametrize('change',['date','pdf','title','new_history','duplicate','truncated','trailer','owner'])
def test_index_drift_never_falls_back_to_an_old_qa(harness,change):
    from data_fetch.market_sources import chb_conference as s
    from search_provider_runtime import SourceResponseError
    bodies,calls=harness;raw=bodies[s.INDEX_URL]
    if change=='date':raw=raw.replace(b'2026/08/25',b'2026/11/25')
    elif change=='pdf':raw=raw.replace(b'1790671904915',b'1790671904916')
    elif change=='title':raw=raw.replace('2026年第2季法人說明會'.encode(),'2026年第3季法人說明會'.encode())
    elif change=='new_history':raw=raw.replace(b'2026/05/26',b'2026/10/14')
    elif change=='duplicate':raw=raw.replace(b'2026/05/26',b'2026/08/25')
    elif change=='truncated':raw=raw[:raw.index(b'</html>')]
    elif change=='trailer':raw+=b'<a href="new.pdf">new event</a>'
    else:raw=raw.replace('© 彰化銀行'.encode(),b'Unknown owner')
    assert raw!=bodies[s.INDEX_URL];bodies[s.INDEX_URL]=raw
    with pytest.raises(SourceResponseError):s.fetch_chb_context('2801.TW')
    assert calls==[s.MASTER_URL,s.INDEX_URL]

@pytest.mark.parametrize('change',['epoch','expiry','manifest','page','coverage','financial','boolean','role','kind','question','period'])
def test_saved_proof_rejects_retiming_missing_answer_or_scope_edit(harness,change):
    from data_fetch.market_sources import chb_conference as s
    value=s.fetch_chb_context('2801.TW');r=value['chb_qa_receipt']['pdf'];d=value['documents'][0]
    if change=='epoch':r['retrieved_at']+=1
    elif change=='expiry':r['fresh_until_epoch']-=1
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='page':d['pages'][1]['text']='新分行全部已開業'
    elif change=='coverage':value['coverage_status']='complete'
    elif change=='financial':d['financial_statement_complete']=True
    elif change=='boolean':d['binary_complete']=1
    elif change=='kind':d['document_kind']='transcript'
    elif change=='question':d['cross_page_questions']={}
    elif change=='period':d['content_period']='2026Q3'
    else:d['role_page_allowlist']=[1,2,3]
    assert not s.verify_context(value,'2801.TW',max_age=1800)

@pytest.mark.parametrize('change',['name','ubn','alias','forbidden','quote','ticker'])
def test_conflicting_current_snapshot_identity_is_rejected(change):
    from data_fetch.market_sources.chb_conference import validate_context
    d=valid_data()
    if change=='name':d['raw_company_name']='Other company'
    elif change=='ubn':d['company_identity']['official_ubn']='00000000'
    elif change=='alias':d['company_identity']['allowed_aliases'].append('First Bank')
    elif change=='forbidden':d['company_identity']['forbidden_aliases']=['彰銀']
    elif change=='quote':d['quote_type']='ETF'
    else:d['ticker']='2801.TWO'
    assert not validate_context(d,'2801.TW')

@pytest.mark.parametrize('options',[{}, {'force_refresh':True},{'use_cache':False}])
def test_each_issuer_acquisition_reads_native_index_and_qa(harness,options):
    from data_fetch.market_sources import chb_conference as s
    bodies,calls=harness;s.fetch_chb_context('2801.TW');s.fetch_chb_context('2801.TW',**options)
    assert calls.count(s.INDEX_URL)==calls.count(s.PDF_URL)==2
