from copy import deepcopy
from hashlib import sha256
from xml.etree import ElementTree as ET
import time
import pytest

from data_fetch.market_sources.tewc_income_reference import replay_income_reference
from data_fetch.market_sources.official_xbrl_financial import IX, XBRLI
from official_response_evidence import archive_response, read_response
from test_tewc_quarterly_reference import reference


def income_reference():
    ref=reference()
    for kind in ('annual_document','quarterly_document'):
        doc=ref[kind];root=ET.fromstring(read_response(doc['raw_receipt']))
        unit=ET.SubElement(root,XBRLI+'unit',id='EPS')
        div=ET.SubElement(unit,XBRLI+'divide')
        for name,value in [('unitNumerator','iso4217:TWD'),('unitDenominator','xbrli:shares')]:
            child=ET.SubElement(div,XBRLI+name);ET.SubElement(child,XBRLI+'measure').text=value
        def add(tag,ctx,value,unit='TWD',scale='3',decimals='-3'):
            n=ET.SubElement(root,IX+'nonFraction',name='ifrs-full:'+tag,contextRef=ctx,unitRef=unit,
                scale=scale,decimals=decimals,format='ixt:numdotdecimal');n.text=value
        if kind=='annual_document':
            for node in root.iter(IX+'nonFraction'):
                if node.get('name')=='ifrs-full:ProfitLoss':node.text='3000'if node.get('contextRef')=='d2025'else'2000'
            add('BasicEarningsLossPerShare','d2025','13.61','EPS','0','2')
        else:
            for ctx,ni,eps in [('d2026','1000','6.02'),('d2025','800','6.51')]:
                add('ProfitLoss',ctx,ni);add('BasicEarningsLossPerShare',ctx,eps,'EPS','0','2')
            add('IssuedCapital','i2026','660000');add('IssuedCapital','i2025','600000')
        raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))
    return {'schema':'tewc-income-reference:v1','ticker':'1623.TW','financial_reference':ref}


def change_quarterly(value,change):
    doc=value['financial_reference']['quarterly_document'];root=ET.fromstring(read_response(doc['raw_receipt']));change(root)
    raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))


def test_same_scope_net_income_replayed_without_summing_eps_or_upgrading_old_history():
    value=income_reference();before=deepcopy(value)
    got=replay_income_reference(value,'1623.TW')
    assert got['status']=='income_originals_verified',got
    assert got['net_income_ttm_raw']==3200000
    assert got['annual_rows']['2025']['free_cash_flow']==7000000
    assert got['reported_basic_eps']['prior_annual']['value']==13.61
    assert got['reported_basic_eps']['current_ytd']['value']==6.02
    assert got['reported_basic_eps']['prior_ytd']['value']==6.51
    assert got['issued_capital']['2026-06-30']['value']==660000000
    assert got['ttm_eps_verified']is False and got['share_count_bridge_verified']is False
    assert got['historical_pit_verified']is False and got['native_acquisition']is False
    assert got['five_year_history_verified']is False and value==before


@pytest.mark.parametrize('change',[
    lambda r:r.remove(next(n for n in r if n.tag==IX+'nonFraction'and n.get('name')=='ifrs-full:ProfitLoss')),
    lambda r:next(n for n in r.iter(IX+'nonFraction')if n.get('name')=='ifrs-full:ProfitLoss').set('unitRef','EPS'),
    lambda r:next(n for n in r.iter(IX+'nonFraction')if n.get('name')=='ifrs-full:ProfitLoss').set('scale','0'),
    lambda r:next(n for n in r.iter(IX+'nonFraction')if n.get('name')=='ifrs-full:BasicEarningsLossPerShare').set('unitRef','TWD'),
    lambda r:r.append(deepcopy(next(n for n in r if n.tag==IX+'nonFraction'and n.get('name')=='ifrs-full:ProfitLoss'))),
])
def test_income_requires_unique_same_period_and_dimensionally_correct_source(change):
    value=income_reference();change_quarterly(value,change)
    assert replay_income_reference(value,'1623.TW')['status']=='unverified'


def test_new_api_does_not_change_existing_cashflow_v1_return_contract():
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=income_reference();old=replay_reference(value['financial_reference'],'1623.TW')
    assert replay_income_reference(value,'1623.TW')['status']=='income_originals_verified'
    assert replay_reference(value['financial_reference'],'1623.TW')==old
    assert 'net_income_ttm_raw'not in old


@pytest.mark.parametrize('damage',['hash','identity','caller_values','scope'])
def test_bad_receipt_identity_or_caller_facts_never_qualify(damage):
    value=income_reference()
    if damage=='hash':value['financial_reference']['annual_document']['sha256']='0'*64
    elif damage=='identity':value['ticker']='2313.TW'
    elif damage=='caller_values':value['net_income_ttm_raw']=3200000
    else:value['financial_reference']['report_scope']='consolidated'
    assert replay_income_reference(value,'1623.TW')['status']=='unverified'
