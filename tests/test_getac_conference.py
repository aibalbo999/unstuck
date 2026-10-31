"""Getac exact public presentation; live network is replaced in isolation."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import base64, importlib, json, time
import pytest
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261015/chroma-getac-free-entrances'
MASTER=ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW=1792005000.0

def valid_data():
    return json.loads((ROOT/'docs/evidence/source-acquisition/20261015/getac-conference-integration/current-target.json').read_text())['identity_input']

@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import getac_conference_transport as t
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={t.MASTER_URL:MASTER.read_bytes(),t.ROOT_URL:(ROOT/'docs/evidence/source-acquisition/20261015/getac-host-bridge/registered.body').read_bytes(),t.INDEX_URL:(D/'getac-index.body').read_bytes(),t.PDF_URL:(D/'getac-pdf.body').read_bytes()};calls=[]
    def download(self,url,diagnostic):
        raw=bodies[url];calls.append(url);self.http_request_count+=1
        meta={'http_status':302 if url==t.ROOT_URL else 200,'effective_url':url+'/'if url==t.ROOT_URL else url,'num_redirects':0,'size_download':len(raw),
              'content_type':'text/csv'if url==t.MASTER_URL else'application/pdf'if url==t.PDF_URL else'text/html',
              'content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'no-cache'}
        if url==t.MASTER_URL:
            from data_fetch.market_sources import official_issuer_master
            meta=official_issuer_master.master_metadata(meta,raw,{})
        else:meta.update(pragma='',expires='',age=None,cf_cache_status='',location='https://tw.getacgroup.com/'if url==t.ROOT_URL else '')
        diagnostic.update(http_request_sent=True,http_status=meta['http_status'],response_metadata=meta)
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                'request_method':'GET','request_body':None,'response_metadata':meta}
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()

def test_getac_missing_body_recovers_with_event_document_and_financial_scope_distinct(request):
    try:s=importlib.import_module('data_fetch.market_sources.getac_conference')
    except ModuleNotFoundError as exc:
        if exc.name!='data_fetch.market_sources.getac_conference':raise
        value={}
    else:
        _,calls=request.getfixturevalue('harness');diagnostic={}
        value=s.fetch_getac_context('3005.TW',diagnostics=diagnostic)
        assert len(calls)==diagnostic['http_request_count']==4
        assert s.validate_context(valid_data(),'3005.TW')
        assert s.verify_context(value,'3005.TW',max_age=1800)
    assert len(value.get('documents',[]))==1,'The qualified Getac original has no source collector'
    d=value['documents'][0]
    assert d['page_count']==len(d['pages'])==21 and d['native_text_coverage']=='complete'
    assert d['event_date']=='2026-08-14' and d['material_file_date']=='2026-08-14' and d['presentation_cover_month']=='2026-08'
    assert d['content_period']=='2026H1' and d['published_at']is None
    assert d['coverage_status']=='partial' and d['financial_statement_complete']is False
    assert d['q_and_a_transcript_available']is False and value['transcript_available']is False
    assert d['role_page_allowlist']==[1,2,7,8]

@pytest.mark.parametrize('change',['date','pdf','title','new_row','duplicate','truncated','trailer','owner','bridge'])
def test_unqualified_index_never_fetches_old_pdf(harness,change):
    from data_fetch.market_sources import getac_conference as s
    from search_provider_runtime import SourceResponseError
    from bs4 import BeautifulSoup
    bodies,calls=harness;raw=bodies[s.INDEX_URL]
    if change=='bridge':
        bodies[s.ROOT_URL]=bodies[s.ROOT_URL].replace(b'//en.getacgroup.com/',b'//foreign.example/')
    elif change=='date':raw=raw.replace(b'2026-08-14',b'2026-11-14')
    elif change in ('pdf','title'):
        soup=BeautifulSoup(raw,'html.parser');cells=soup.select('table.calendarTable')[1].select('tbody > tr')[0].select('td')
        if change=='pdf':cells[3].select_one('a')['onclick']="window.open('../upload/unqualified.pdf');"
        else:cells[1].select_one('h3 a').string='Another event'
        raw=str(soup).encode()
    elif change in ('new_row','duplicate'):
        soup=BeautifulSoup(raw,'html.parser');node=soup.select('table.calendarTable')[1].select('tbody > tr')[0];new=deepcopy(node)
        if change=='new_row':new.select('td')[0].string='2026-10-15'
        node.insert_before(new);raw=str(soup).encode()
    elif change=='truncated':raw=raw[:raw.index(b'</html>')]
    elif change=='trailer':raw+=b'<p>New event</p>'
    else:raw=raw.replace(b'Getac Technology Corporation',b'Unknown owner')
    bodies[s.INDEX_URL]=raw
    with pytest.raises(SourceResponseError):s.fetch_getac_context('3005.TW')
    assert calls==[s.MASTER_URL,s.ROOT_URL]+([]if change=='bridge'else[s.INDEX_URL])

@pytest.mark.parametrize('change',['epoch','expiry','manifest','page','coverage','financial','boolean','role','period','document_date'])
def test_saved_original_rejects_retiming_and_scope_edits(harness,change):
    from data_fetch.market_sources import getac_conference as s
    value=s.fetch_getac_context('3005.TW');r=value['getac_conference_receipt']['pdf'];d=value['documents'][0]
    if change=='epoch':r['retrieved_at']+=1
    elif change=='expiry':r['fresh_until_epoch']-=1
    elif change=='manifest':r['acquisition_manifest']['raw_response_sha256']='0'*64
    elif change=='page':d['pages'][6]['text']='changed free cash flow definition'
    elif change=='coverage':value['coverage_status']='complete'
    elif change=='financial':d['financial_statement_complete']=True
    elif change=='boolean':d['binary_complete']=1
    elif change=='role':d['role_page_allowlist'].append(9)
    elif change=='period':d['content_period']='2026Q3'
    else:d['material_file_date']='2026-09-14'
    assert not s.verify_context(value,'3005.TW',max_age=1800)

@pytest.mark.parametrize('change',['name','ubn','alias','forbidden','quote','ticker'])
def test_conflicting_snapshot_issuer_is_rejected(change):
    from data_fetch.market_sources.getac_conference import validate_context
    d=valid_data()
    if change=='name':d['raw_company_name']='Other issuer'
    elif change=='ubn':d['company_identity']['official_ubn']='00000000'
    elif change=='alias':d['company_identity']['allowed_aliases'].append('Different company')
    elif change=='forbidden':d['company_identity']['forbidden_aliases']=['神基']
    elif change=='quote':d['quote_type']='ETF'
    else:d['ticker']='3005.TWO'
    assert not validate_context(d,'3005.TW')

@pytest.mark.parametrize('options',[{}, {'force_refresh':True},{'use_cache':False}])
def test_each_acquisition_reads_native_current_index_and_document(harness,options):
    from data_fetch.market_sources import getac_conference as s
    bodies,calls=harness;s.fetch_getac_context('3005.TW');s.fetch_getac_context('3005.TW',**options)
    assert calls.count(s.INDEX_URL)==calls.count(s.PDF_URL)==2
