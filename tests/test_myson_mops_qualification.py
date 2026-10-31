from pathlib import Path
import json
from copy import deepcopy
import pytest
D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261031/myson-mops'
@pytest.fixture(scope='module')
def original():
 from source_pdf_reader import extract_pdf_pages
 raw=(D/'research-material.pdf').read_bytes()
 return raw,extract_pdf_pages(raw,timeout_seconds=10),json.loads((D/'research-material.json').read_text())['selected']

def context():
 return {'ticker':'5314.TWO','quote_type':'EQUITY','company_name':'世紀* / Myson Century, Inc.','raw_company_name':'Myson Century, Inc.','company_identity':{'ticker':'5314.TWO','stock_id':'5314','official_name':'世紀*','legal_name':'世紀民生科技股份有限公司','official_ubn':'22099815','instrument_type':'EQUITY','display_name':'世紀* / Myson Century, Inc.','english_names':['Myson Century, Inc.','MYSON-CENTURY TECHNOLOGY INC'],'allowed_aliases':['世紀*','世紀民生科技股份有限公司','Myson Century, Inc.','5314.TWO','5314','MYSON-CENTURY TECHNOLOGY INC'],'forbidden_aliases':[]}}

def test_source_supports_exact_current_master_and_preserved_quote_labels():
 from data_fetch.market_sources.mops_presentation import supports,validate_context,parse_master
 from data_fetch.market_sources.mops_otc_master import OTC_MASTER
 assert supports('5314.TWO') and validate_context(context(),'5314.TWO')
 master=parse_master((D/'fixture-master.body').read_bytes(),'5314.TWO',1793440583.,OTC_MASTER)
 assert master['official_ubn']=='22099815' and master['short_name']=='世紀*'

def test_original_and_whole_role_projection_keeps_full_document(original):
 from data_fetch.market_sources.myson_mops_qualification import qualify_native,qualified_projection,ROLE_PAGES,NOTE
 raw,native,selected=original;before=deepcopy(native)
 assert qualify_native(raw,native,selected)=='mixed'
 projection=qualified_projection(native['pages'])
 assert projection['role_page_allowlist']=={str(k):list(v) for k,v in ROLE_PAGES.items()}
 assert native==before and len(native['pages'])==93
 assert 78 in projection['projection_excluded_pages'] and 79 in projection['projection_excluded_pages']
 assert all(sum(len(p['text']) for p in native['pages'] if p['page_number'] in ns)<=6000 for ns in ROLE_PAGES.values())
 assert all(t in NOTE for t in ('2026-04-15','2026/01','2025','幣別','單位','臨床','商業重用'))

@pytest.mark.parametrize('key,value',[('ticker','5314.TW'),('company_name','世紀民生'),('event_date','2026-05-08'),('event_time','15:00'),('filename','531420260415C001.pdf'),('language','zh'),('material_file_date','2026-04-16')])
def test_other_market_identity_period_or_file_cannot_pass(original,key,value):
 from data_fetch.market_sources.myson_mops_qualification import qualify_native
 raw,native,selected=original;selected=deepcopy(selected);selected[key]=value
 with pytest.raises(ValueError):qualify_native(raw,native,selected)

@pytest.mark.parametrize('damage',['raw','missing_page','financial_page_text','role_text','bool_page','coverage','empty','garbled'])
def test_full_original_metadata_and_even_excluded_pages_are_immutable(original,damage):
 from data_fetch.market_sources.myson_mops_qualification import qualify_native
 raw,native,selected=original;native=deepcopy(native)
 if damage=='raw':raw+=b'changed'
 elif damage=='missing_page':native['pages'].pop()
 elif damage=='financial_page_text':native['pages'][78]['text']='Audited TWD thousand results'
 elif damage=='role_text':native['pages'][5]['text']='Independently proven clinical efficacy'
 elif damage=='bool_page':native['pages'][0]['page_number']=True
 elif damage=='coverage':native['coverage_status']='partial'
 elif damage=='empty':native['empty_pages']=[1]
 else:native['garbled_pages']=[1]
 with pytest.raises(ValueError):qualify_native(raw,native,selected)

@pytest.mark.parametrize('field,value',[('official_ubn','00000000'),('stock_id','5315'),('legal_name','另一公司股份有限公司'),('official_name','另一公司')])
def test_wrong_primary_identity_fails_even_with_known_quote_alias(field,value):
 from data_fetch.market_sources.mops_presentation import validate_context
 data=context();data['company_identity'][field]=value
 assert not validate_context(data,'5314.TWO')

@pytest.mark.parametrize('alias',['台積電','MYSON TECHNOLOGY INC','Century Semiconductor','MYSON-CENTURY TECHNOLOGY INC EVIL'])
def test_unrelated_or_predecessor_alias_never_establishes_issuer(alias):
 from data_fetch.market_sources.mops_presentation import validate_context
 data=context();data['company_identity']['allowed_aliases'].append(alias)
 assert not validate_context(data,'5314.TWO')
