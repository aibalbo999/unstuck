from pathlib import Path
from copy import deepcopy
import json
import pytest
D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261031/jentech-mops'
@pytest.fixture(scope='module')
def original():
 from source_pdf_reader import extract_pdf_pages
 raw=(D/'research-material.pdf').read_bytes();native=extract_pdf_pages(raw,timeout_seconds=10)
 return raw,native,json.loads((D/'research-material.json').read_text())['selected']

def test_exact_english_original_partial_state_and_whole_pages(original):
 from data_fetch.market_sources.jentech_mops_qualification import qualify_native,qualified_projection,NOTE
 raw,native,selected=original;before=deepcopy(native)
 assert qualify_native(raw,native,selected)=='2025Q3'
 p=qualified_projection(native['pages'])
 assert p['role_page_allowlist']=={str(r):[1,5,6,7,8,11,21]for r in (3,5,12)}
 assert 2 in p['projection_excluded_pages'] and len(p['projection_excluded_pages'])==17
 assert native==before and native['coverage_status']=='partial'
 assert 'Basic EPS' in NOTE and '37,488+' in NOTE and '未驗證商業重用授權' in NOTE

@pytest.mark.parametrize('key,value',[('ticker','3653.TWO'),('symbol','3652'),('company_name','台積電'),('event_date','2026-11-28'),('event_end_date','2025-11-29'),('event_time','15:00'),('material_file_date','2025-11-27'),('filename','365320251128C001.pdf'),('format','pptx'),('language','zh')])
def test_foreign_identity_period_or_other_attachment_fails_closed(original,key,value):
 from data_fetch.market_sources.jentech_mops_qualification import qualify_native
 raw,native,selected=original;selected=deepcopy(selected);selected[key]=value
 with pytest.raises(ValueError):qualify_native(raw,native,selected)

@pytest.mark.parametrize('damage',['raw','page_count','missing_page','nonrole_text','role_text','bool_page','empty_metadata','garbled_metadata','coverage'])
def test_modified_or_incomplete_original_never_enters_role_projection(original,damage):
 from data_fetch.market_sources.jentech_mops_qualification import qualify_native
 raw,native,selected=original;native=deepcopy(native)
 if damage=='raw':raw+=b'junk'
 elif damage=='page_count':native['page_count']=True
 elif damage=='missing_page':native['pages'].pop()
 elif damage=='nonrole_text':native['pages'][1]['text']='audited current financials'
 elif damage=='role_text':native['pages'][20]['text']='EPS in thousands; TTM2026'
 elif damage=='bool_page':native['pages'][0]['page_number']=True
 elif damage=='empty_metadata':native['empty_pages']=None
 elif damage=='garbled_metadata':native['garbled_pages']=[]
 else:native['coverage_status']='complete'
 with pytest.raises(ValueError):qualify_native(raw,native,selected)
