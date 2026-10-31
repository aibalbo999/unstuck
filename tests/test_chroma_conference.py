"""Chroma exact public presentation; live network is replaced in isolation."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64, importlib, json, time
import pytest
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261015/chroma-getac-free-entrances'
MASTER=ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW=1791999300.0

def valid_data():
    return json.loads((ROOT/'docs/evidence/source-acquisition/20261015/chroma-and-conference-retention/current-target.json').read_text())['identity_input']

@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import chroma_conference_transport as t
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={t.MASTER_URL:MASTER.read_bytes(),t.INDEX_URL:(D/'chroma-index.body').read_bytes(),t.PDF_URL:(D/'chroma-pdf.body').read_bytes()};calls=[]
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

def test_chroma_missing_body_recovers_with_event_document_and_financial_scope_distinct(request):
    try:s=importlib.import_module('data_fetch.market_sources.chroma_conference')
    except ModuleNotFoundError as exc:
        if exc.name!='data_fetch.market_sources.chroma_conference':raise
        value={}
    else:
        _,calls=request.getfixturevalue('harness');diagnostic={}
        value=s.fetch_chroma_context('2360.TW',diagnostics=diagnostic)
        assert len(calls)==diagnostic['http_request_count']==3
        assert s.validate_context(valid_data(),'2360.TW')
        assert s.verify_context(value,'2360.TW',max_age=1800)
    assert len(value.get('documents',[]))==1,'The qualified Chroma original has no source collector'
    d=value['documents'][0]
    assert d['page_count']==len(d['pages'])==18 and d['native_text_coverage']=='complete'
    assert d['event_date']=='2026-09-15' and d['material_file_date']=='2026-07-30'
    assert d['content_period']=='2026Q2' and d['published_at']is None
    assert d['coverage_status']=='partial' and d['financial_statement_complete']is False
    assert d['q_and_a_transcript_available']is False and value['transcript_available']is False
    assert d['role_page_allowlist']==[1,5,6,7,10]

@pytest.mark.parametrize('change',['date','pdf','title','new_row','duplicate','truncated','trailer','owner'])
def test_unqualified_index_never_fetches_old_pdf(harness,change):
    from data_fetch.market_sources import chroma_conference as s
    from search_provider_runtime import SourceResponseError
    from bs4 import BeautifulSoup
    bodies,calls=harness;raw=bodies[s.INDEX_URL]
    if change=='date':raw=raw.replace(b'2026.09.15',b'2026.11.15')
    elif change=='pdf':raw=raw.replace(b'20260730_Q2',b'20260731_Q2')
    elif change=='title':raw=raw.replace('第一金證券論壇'.encode(),'另一次活動'.encode())
    elif change in ('new_row','duplicate'):
        soup=BeautifulSoup(raw,'html.parser');node=soup.select('.operation_item')[0];new=deepcopy(node)
        if change=='new_row':new.select('.line-both')[0].string='2026.10.15 新法說'
        node.insert_before(new);raw=str(soup).encode()
    elif change=='truncated':raw=raw[:raw.index(b'</html>')]
    elif change=='trailer':raw+=b'<p>New event</p>'
    else:raw=raw.replace('致茂電子股份有限公司'.encode(),b'Unknown owner')
    assert raw!=bodies[s.INDEX_URL];bodies[s.INDEX_URL]=raw
    with pytest.raises(SourceResponseError):s.fetch_chroma_context('2360.TW')
    assert calls==[s.MASTER_URL,s.INDEX_URL]

@pytest.mark.parametrize('change',['epoch','expiry','manifest','page','coverage','financial','boolean','role','period','document_date'])
def test_saved_original_rejects_retiming_and_scope_edits(harness,change):
    from data_fetch.market_sources import chroma_conference as s
    value=s.fetch_chroma_context('2360.TW');r=value['chroma_conference_receipt']['pdf'];d=value['documents'][0]
    if change=='epoch':r['retrieved_at']+=1
    elif change=='expiry':r['fresh_until_epoch']-=1
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='page':d['pages'][6]['text']='changed free cash flow definition'
    elif change=='coverage':value['coverage_status']='complete'
    elif change=='financial':d['financial_statement_complete']=True
    elif change=='boolean':d['binary_complete']=1
    elif change=='role':d['role_page_allowlist'].append(9)
    elif change=='period':d['content_period']='2026Q3'
    else:d['material_file_date']='2026-09-15'
    assert not s.verify_context(value,'2360.TW',max_age=1800)

@pytest.mark.parametrize('change',['name','ubn','alias','forbidden','quote','ticker'])
def test_conflicting_snapshot_issuer_is_rejected(change):
    from data_fetch.market_sources.chroma_conference import validate_context
    d=valid_data()
    if change=='name':d['raw_company_name']='Other issuer'
    elif change=='ubn':d['company_identity']['official_ubn']='00000000'
    elif change=='alias':d['company_identity']['allowed_aliases'].append('Different company')
    elif change=='forbidden':d['company_identity']['forbidden_aliases']=['致茂']
    elif change=='quote':d['quote_type']='ETF'
    else:d['ticker']='2360.TWO'
    assert not validate_context(d,'2360.TW')

@pytest.mark.parametrize('options',[{}, {'force_refresh':True},{'use_cache':False}])
def test_each_acquisition_reads_native_current_index_and_document(harness,options):
    from data_fetch.market_sources import chroma_conference as s
    bodies,calls=harness;s.fetch_chroma_context('2360.TW');s.fetch_chroma_context('2360.TW',**options)
    assert calls.count(s.INDEX_URL)==calls.count(s.PDF_URL)==2
