"""Only the reviewed October attachment is admitted; September replay remains."""
from pathlib import Path
import gzip
import pytest
from bs4 import BeautifulSoup
from data_fetch.market_sources import fubon_conference as old
NOW=1793204886.000863

def index():return gzip.decompress((Path(__file__).parent/'fixtures/fubon_october_index.html.gz').read_bytes())

def test_new_official_attachment_is_explicitly_qualified():
 selected=old.select_presentation(index(),NOW,as_of_epoch=NOW)
 assert selected['event_date']=='2026-10-15' and selected['document_date']=='2026-10-14'
 assert selected['filename']=='288120261014E002.pdf' and selected['period_label']=='2026H1'

def test_september_selection_remains_replayable():
 soup=BeautifulSoup(index(),'html.parser')
 for row in soup.select('tr[data-type="body"]'):
  cells=row.find_all('td',recursive=False)
  if len(cells)==12 and '115/10/' in cells[2].get_text():row.decompose()
 assert old.select_presentation(str(soup).encode(),NOW,as_of_epoch=NOW)==old.QUALIFIED_SELECTED

@pytest.mark.parametrize('change',['attachment','issuer','event'])
def test_unknown_revision_and_identity_still_rejected(change):
 raw=index()
 if change=='attachment':raw=raw.replace(b'288120261014E002.pdf',b'288120261014E003.pdf')
 elif change=='issuer':raw=raw.replace('富邦金'.encode(),'國泰金'.encode())
 else:raw=raw.replace(b'115/10/15',b'115/10/16')
 with pytest.raises(ValueError):old.select_presentation(raw,NOW,as_of_epoch=NOW)


def test_role_projection_preserves_disclaimer_and_rejects_any_page_edit(monkeypatch):
 from data_fetch.market_sources import fubon_october_conference as new
 from hashlib import sha256
 from copy import deepcopy
 pages=[{'page_number':i,'text':f'unit-only page {i}'} for i in range(1,62)]
 monkeypatch.setattr(new,'PAGE_TEXT_SHA256',tuple(sha256(p['text'].encode()).hexdigest()for p in pages))
 native={'pages':pages,'parser_version':'unit-only-parser'}
 doc=new._context(new.QUALIFIED_SELECTED,native,{'pdf':{'retrieved_at':NOW}})['documents'][0]
 assert [p['page_number']for p in old.role_pages(doc)]==[1,2,3,25,33,41,44,47]
 assert doc['coverage_status']=='partial' and doc['full_visual_content_verified'] is False
 assert doc['filename']=='288120261014E002.pdf' and doc['event_end_date']=='2026-10-15'
 assert doc['appended_results_cover_date'] is None
 assert '53' in doc['visual_semantics_caution'] and 'page33' in doc['financial_scope_caution']
 assert doc['financial_statement_complete'] is False
 for damage in ('page','allowlist','period','completeness','extra'):
  changed=deepcopy(doc)
  if damage=='page':changed['pages'][50]['text']='edited excluded page'
  elif damage=='allowlist':changed['role_page_allowlist'].append(50)
  elif damage=='period':changed['content_period']='2026Q3'
  elif damage=='completeness':changed['full_visual_content_verified']=True
  else:changed['unqualified_field']='invented'
  assert old.role_pages(changed)==[]


def test_unreviewed_binary_revision_never_reaches_extractor(monkeypatch):
 from data_fetch.market_sources import fubon_october_conference as new
 import time
 calls=[]
 monkeypatch.setattr(new,'extract_fubon_presentation_pages',lambda *a,**k:calls.append(a))
 with pytest.raises(ValueError,match='revision is not qualified'):
  new.native_presentation(b'%PDF-unreviewed',new.QUALIFIED_SELECTED,time.monotonic()+10)
 assert calls==[]


def test_delegated_failure_retains_actual_request_diagnostics(monkeypatch):
 from data_fetch.market_sources import fubon_october_conference as new
 from search_provider_runtime import SourceResponseError
 class Prefix:
  def __init__(self,*a,**k):self.components=[{'prefix':True}];self.http_request_count=2
  def check_index_guard(self):pass
  def get_receipt(self,url,**kwargs):
   if url==old.MASTER_URL:return b'unit-only',{'retrieved_at':NOW,'source_url':url}
   return new.QUALIFIED_SELECTED,{'retrieved_at':NOW,'source_url':url}
 def fail(ticker,**kwargs):
  kwargs['diagnostics'].update(http_request_count=3,component_statuses=[1,2,3],error_kind='timeout')
  raise SourceResponseError('timeout')
 monkeypatch.setattr(old,'ConferenceHttp',Prefix)
 monkeypatch.setattr(old,'parse_master',lambda *a,**k:None)
 monkeypatch.setattr(new,'fetch_fubon_context',fail)
 diagnostics={}
 with pytest.raises(SourceResponseError):old.fetch_fubon_context('2881.TW',diagnostics=diagnostics)
 assert diagnostics['http_request_count']==3 and diagnostics['component_statuses']==[1,2,3]
