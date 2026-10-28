"""Native report wrappers must bind to issuer names replayed from both originals."""
from hashlib import sha256
from xml.etree import ElementTree as ET
from copy import deepcopy
import pytest
from official_response_evidence import archive_response,read_response
from data_fetch.market_sources.official_xbrl_financial import IX
from official_financial_projection import project_official_financials
from test_tewc_income_reference import income_reference
from test_official_income_claims import TEXT,income_claims


def data_with_english(*, quarterly_name='TA TUN ELECTRIC WIRE ＆ CABLE CO., LTD.', duplicate=False):
    ref=income_reference()['financial_reference']
    for key in ('annual_document','quarterly_document'):
        doc=ref[key];root=ET.fromstring(read_response(doc['raw_receipt']))
        ctx=next(n.get('contextRef') for n in root.iter(IX+'nonNumeric') if n.get('name')=='tifrs-notes:CompanyChineseName')
        name='TA TUN ELECTRIC WIRE ＆ CABLE CO., LTD.' if key=='annual_document' else quarterly_name
        for _ in range(2 if duplicate and key=='quarterly_document' else 1):
            ET.SubElement(root,IX+'nonNumeric',name='tifrs-notes:CompanyEnglishName',contextRef=ctx).text=name
        raw=ET.tostring(root,encoding='utf-8',xml_declaration=True);doc['sha256']=sha256(raw).hexdigest();doc['raw_receipt']=archive_response(raw,source_url=doc['url'],retrieved_at=__import__('time').time())
    return project_official_financials({'ticker':'1623.TW','company_name':'大東電','financial_currency':'TWD','net_income_ttm_raw':860640000},ref)

TITLE='# 1623.TW 大東電 / Ta Tun Electric Wire & Cable Co., Ltd. - 華爾街深度研究報告'


def test_native_summary_heading_uses_both_official_english_names_not_caller_aliases():
    data=data_with_english();before=deepcopy(data)
    rows=income_claims(TITLE+'\n\n## 一頁式摘要\n'+TEXT,data)
    assert len(rows)==1 and rows[0]['status']=='verified',rows
    assert data==before and data['net_income_ttm_raw']==860640000


@pytest.mark.parametrize('prefix',[
    TITLE.replace('1623.TW','2330.TW'),
    TITLE.replace('Ta Tun Electric Wire & Cable Co., Ltd.','Taiwan Semiconductor Manufacturing Co., Ltd.'),
    TITLE.replace('大東電 /','台積電 /'),
    '# 台積電',
    '# 2024年度財務分析',
    TITLE+'\n# 合併財報',
])
def test_conflicting_ancestor_or_issuer_cannot_hide_under_native_summary(prefix):
    rows=income_claims(prefix+'\n\n## 一頁式摘要\n'+TEXT,data_with_english())
    assert rows and all(r['status']=='unverifiable' for r in rows),rows


@pytest.mark.parametrize('damage',['different','duplicate','caller'])
def test_unqualified_english_names_do_not_bind_the_header(damage):
    data=data_with_english(quarterly_name='OTHER COMPANY' if damage=='different' else 'TA TUN ELECTRIC WIRE ＆ CABLE CO., LTD.',duplicate=damage=='duplicate')
    if damage=='caller':
        data=project_official_financials({'ticker':'1623.TW','company_name':'大東電','financial_currency':'TWD'},income_reference()['financial_reference'])
        data['company_identity']={'allowed_aliases':['Ta Tun Electric Wire & Cable Co., Ltd.']}
    rows=income_claims(TITLE+'\n\n## 一頁式摘要\n'+TEXT,data)
    assert rows and all(r['status']=='unverifiable' for r in rows),rows
