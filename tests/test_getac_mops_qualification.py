from copy import deepcopy
import pytest
from test_getac_conference import D as LEGACY

@pytest.fixture(scope='module')
def material():
 from data_fetch.market_sources.getac_conference import extract_getac_presentation_pages
 raw=(LEGACY/'getac-pdf.body').read_bytes()
 return raw,extract_getac_presentation_pages(raw,timeout_seconds=10)

def selected():
 return {'ticker':'3005.TW','symbol':'3005','company_name':'神基','event_date':'2026-08-14','event_end_date':'2026-08-14','material_file_date':'2026-08-13','filename':'300520260813E001.pdf','format':'pdf','language':'en'}

def test_new_entry_enabled_and_registered_identity_remains_exact():
 from data_fetch.market_sources import mops_presentation as s
 assert s.supports('3005.TW')
 assert s.validate_context({'ticker':'3005.TW','instrument_type':'EQUITY','company_name':'神基'},'3005.TW')
 assert not s.validate_context({'ticker':'3005.TW','instrument_type':'EQUITY','company_name':'神基','official_ubn':'11111111'},'3005.TW')

def test_original_all_pages_and_role_projection_are_unchanged(material):
 from data_fetch.market_sources.getac_mops_qualification import qualify_native,qualified_projection
 raw,native=material;before=deepcopy(native)
 assert qualify_native(raw,native,selected())=='2026H1'
 assert qualified_projection(native['pages'])['role_page_allowlist']=={'3':[1,2,7,8],'5':[1,2,7,8],'12':[1,2,7,8]}
 assert native==before

@pytest.mark.parametrize('key,value',[('ticker','3004.TW'),('company_name','神達'),('event_date','2026-08-13'),('material_file_date','2026-08-14'),('filename','300520260814E001.pdf'),('language','zh'),('format','pptx')])
def test_changed_identity_date_or_attachment_fails_closed(material,key,value):
 from data_fetch.market_sources.getac_mops_qualification import qualify_native
 raw,native=material;spec=selected();spec[key]=value
 with pytest.raises(ValueError):qualify_native(raw,native,spec)

@pytest.mark.parametrize('damage',['page_text','boolean_page','missing_page','raw','empty','garbled','coverage','missing_empty_metadata','missing_garbled_metadata'])
def test_tampered_or_incomplete_original_is_never_projected(material,damage):
 from data_fetch.market_sources.getac_mops_qualification import qualify_native
 raw,native=material;native=deepcopy(native)
 if damage=='page_text':native['pages'][6]['text']='3004 wholly owned; verified current global market share40%'
 elif damage=='boolean_page':native['pages'][0]['page_number']=True
 elif damage=='missing_page':native['pages'].pop()
 elif damage=='raw':raw+=b'junk'
 elif damage=='empty':native['empty_pages']=[1]
 elif damage=='garbled':native['garbled_pages']=[7]
 elif damage=='missing_empty_metadata':native['empty_pages']=None
 elif damage=='missing_garbled_metadata':native['garbled_pages']=None
 else:native['coverage_status']='partial'
 with pytest.raises(ValueError):qualify_native(raw,native,selected())

@pytest.mark.parametrize('ticker',['3005','3005.TW',' 3005.tw '])
def test_public_route_preserves_supported_ticker_forms(monkeypatch,ticker):
 from data_fetch import earnings_call_fetcher as f
 from data_fetch.market_sources import mops_presentation as m
 calls=[]
 monkeypatch.setattr(m,'fetch_presentation_context',lambda t,**kw:calls.append(t) or {'ok':True})
 assert f.fetch_free_earnings_call_context(ticker)=={'ok':True}
 assert calls==['3005.TW']
