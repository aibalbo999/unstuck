"""Synthetic individual-quarter references never qualify undated quote scalars."""
from copy import deepcopy
from hashlib import sha256
from xml.etree import ElementTree as ET
import time

import pytest

from test_ordinary_individual_annual import synthetic_filing
from official_response_evidence import archive_response, read_response
from data_fetch.market_sources.official_xbrl_financial import INDEX_URL, IX, XBRLI

URL = 'https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=1623&year={year}&season={quarter}&report_id=A'
CASH = {'CashFlowsFromUsedInOperatingActivities': (4000, 2000),
        'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities': (-500, -250),
        'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities': (0, -100)}
BALANCE = {'Assets': 10000, 'Liabilities': 4000, 'Equity': 6000,
           'ShorttermBorrowings': 1000, 'CurrentPortionOfLongtermBorrowings': 500,
           'LongtermBorrowings': 1000, 'CurrentLeaseLiabilities': 100,
           'NoncurrentLeaseLiabilities': 200}


def quarterly_raw():
    root = ET.Element('{http://www.w3.org/1999/xhtml}html')
    for cid, year, end in [('d2026', 2026, '06-30'), ('d2025', 2025, '06-30'),
                            ('i2026', 2026, '06-30'), ('i2025', 2025, '12-31')]:
        c = ET.SubElement(root, XBRLI+'context', id=cid)
        entity = ET.SubElement(c, XBRLI+'entity')
        ET.SubElement(entity, XBRLI+'identifier', scheme='http://www.twse.com.tw').text = '1623'
        period = ET.SubElement(c, XBRLI+'period')
        if cid.startswith('i'):
            ET.SubElement(period, XBRLI+'instant').text = f'{year}-{end}'
        else:
            ET.SubElement(period, XBRLI+'startDate').text = f'{year}-01-01'
            ET.SubElement(period, XBRLI+'endDate').text = f'{year}-{end}'
    u = ET.SubElement(root, XBRLI+'unit', id='TWD')
    ET.SubElement(u, XBRLI+'measure').text = 'iso4217:TWD'
    meta = {'CompanyID': '1623', 'CompanyChineseName': '大東電業廠股份有限公司', 'Year': '2026',
            'Quarter': '2', 'ReportCategory': 'Individual report', 'ReportType': 'Financial report (general)',
            'IndustrySector': 'Commercial and industrial'}
    for tag, text in meta.items():
        ET.SubElement(root, IX+'nonNumeric', name='tifrs-notes:'+tag, contextRef='d2026').text = text
    def add(tag, ctx, amount):
        node = ET.SubElement(root, IX+'nonFraction', name='ifrs-full:'+tag, contextRef=ctx,
                             unitRef='TWD', scale='3', decimals='-3', format='ixt:numdotdecimal')
        if amount < 0: node.set('sign', '-')
        node.text = str(abs(amount))
    for tag, values in CASH.items():
        for ctx, amount in zip(('d2026', 'd2025'), values): add(tag, ctx, amount)
    for tag, amount in BALANCE.items(): add(tag, 'i2026', amount)
    for tag, amount in {'Assets':7000, 'Equity':4000}.items(): add(tag, 'i2025', amount)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def annual_raw():
    root = ET.fromstring(synthetic_filing(2025, issuer='1623', company_name='大東電業廠股份有限公司'))
    values = {'Assets':7000, 'Equity':4000, 'CashFlowsFromUsedInOperatingActivities':10000,
              'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities':-2000,
              'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities':-1000}
    for n in root.iter(IX+'nonFraction'):
        tag=n.get('name').split(':')[1]
        if tag in values and n.get('contextRef') in ('d2025','i2025'):
            value=values[tag]; n.text=str(abs(value))
            if value<0: n.set('sign','-')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def reference():
    qurl=URL.format(year=2026,quarter=2); aurl=URL.format(year=2025,quarter=4)
    index=('<html>'+''.join(f'<a href="{url.replace("&","&amp;")}">個別</a>' for url in [qurl,aurl])+'</html>').encode()
    def doc(raw,url,year,quarter):
        return {'year':year,'quarter':quarter,'url':url,'sha256':sha256(raw).hexdigest(),
                'raw_receipt':archive_response(raw,source_url=url,retrieved_at=time.time())}
    return {'schema':'tewc-quarterly-financial-reference:v1','ticker':'1623.TW','report_scope':'individual',
            'published_index_receipt':archive_response(index,source_url=INDEX_URL,retrieved_at=time.time()),
            'quarterly_document':doc(quarterly_raw(),qurl,2026,2),
            'annual_document':doc(annual_raw(),aurl,2025,4)}


def changed_document(value, change):
    doc=value['quarterly_document'];root=ET.fromstring(read_response(doc['raw_receipt']))
    change(root)
    raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))


def test_complete_reference_replays_exact_period_and_two_distinct_debt_definitions():
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference();before=deepcopy(value);result=replay_reference(value,'1623.TW')
    assert result['status']=='quarterly_originals_verified',result
    assert result['period_start']=='2025-07-01' and result['period_end']=='2026-06-30'
    assert result['cashflows']['ttm']=={'operating_cash_flow':12000000,'ppe_purchase':-2250000,'intangible_purchase':-900000,'free_cash_flow':8850000}
    assert result['balance']['interest_bearing_debt_including_leases']==2800000
    assert result['balance']['total_liabilities']==4000000
    assert result['ratios']['debt_including_leases_to_equity_pct']==pytest.approx(46.6666666667)
    assert result['ratios']['total_liabilities_to_equity_pct']==pytest.approx(66.6666666667)
    assert len(result['debt_components'])==5
    assert result['raw_scalar_period_verified'] is False and result['historical_pit_verified'] is False
    assert result['five_year_history_verified'] is False and result['industrial_dcf_applicable'] is False
    assert value==before


@pytest.mark.parametrize('damage',['ticker','scope','hash','path','url','future_receipt','before_period_receipt','declared_year','index_missing','annual_hash'])
def test_reference_identity_path_hash_and_receipt_timing_fail_closed(damage):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference();doc=value['quarterly_document']
    if damage=='ticker':value['ticker']='2330.TW'
    elif damage=='scope':value['report_scope']='consolidated'
    elif damage=='hash':doc['sha256']='0'*64
    elif damage=='path':doc['raw_receipt']['raw_response_path']='/tmp/untrusted.gz'
    elif damage=='url':doc['url']=doc['url'].replace('report_id=A','report_id=C')
    elif damage=='future_receipt':doc['raw_receipt']['retrieved_at']=time.time()+3600
    elif damage=='before_period_receipt':doc['raw_receipt']['retrieved_at']=1
    elif damage=='declared_year':doc['year']=True
    elif damage=='annual_hash':value['annual_document']['sha256']='0'*64
    else:value['published_index_receipt']=archive_response(b'<html>absent</html>',source_url=INDEX_URL,retrieved_at=time.time())
    assert replay_reference(value,'1623.TW')['status']=='unverified'


@pytest.mark.parametrize('damage',['issuer','category','year','quarter','currency','scale','duplicate','missing_intangible','purchase_sign','segment','year_end_equity','balance_sum','negative_debt','declaration','truncated'])
def test_quarterly_body_scope_and_amounts_cannot_be_inferred_or_relabelled(damage):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference()
    def change(root):
        nodes=list(root.iter(IX+'nonFraction'))
        if damage in ('issuer','category','year','quarter'):
            tag={'issuer':'CompanyID','category':'ReportCategory','year':'Year','quarter':'Quarter'}[damage]
            next(n for n in root.iter(IX+'nonNumeric') if n.get('name')=='tifrs-notes:'+tag).text='invalid'
        elif damage=='currency':next(root.iter(XBRLI+'measure')).text='iso4217:USD'
        elif damage=='scale':nodes[0].set('scale','0')
        elif damage=='duplicate':root.append(deepcopy(nodes[0]))
        elif damage=='missing_intangible':root.remove(next(n for n in nodes if 'Intangible' in n.get('name')))
        elif damage=='purchase_sign':next(n for n in nodes if 'PurchaseOfProperty' in n.get('name')).attrib.pop('sign')
        elif damage=='segment':ET.SubElement(next(root.iter(XBRLI+'entity')),XBRLI+'segment')
        elif damage=='year_end_equity':next(n for n in nodes if n.get('name')=='ifrs-full:Equity' and n.get('contextRef')=='i2025').text='4001'
        elif damage=='balance_sum':next(n for n in nodes if n.get('name')=='ifrs-full:Assets' and n.get('contextRef')=='i2026').text='10001'
        elif damage=='negative_debt':next(n for n in nodes if n.get('name')=='ifrs-full:ShorttermBorrowings').set('sign','-')
    if damage in ('declaration','truncated'):
        raw=read_response(value['quarterly_document']['raw_receipt'])
        raw=b'<!DOCTYPE html>'+raw if damage=='declaration' else raw[:-5]
        doc=value['quarterly_document'];doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))
    else:changed_document(value,change)
    assert replay_reference(value,'1623.TW')['status']=='unverified'


def test_native_contract_is_exact_issuer_individual_completed_quarter():
    from data_fetch.market_sources.tewc_quarterly_reference import native_contract
    url=URL.format(year=2026,quarter=2)
    assert native_contract(url)[0]==6000000
    for bad in [url.replace('1623','2330'),url.replace('report_id=A','report_id=C'),url+'&extra=1',url+'#x',url.replace('2026','2099')]:
        with pytest.raises(ValueError):native_contract(bad)


@pytest.mark.parametrize('reuse', [False, True])
def test_fetch_reuses_verified_annual_and_counts_only_actual_requests(monkeypatch, reuse):
    from contextlib import nullcontext
    from data_fetch.market_sources.tewc_quarterly_reference import fetch_reference, replay_reference
    value=reference(); documents=[value['quarterly_document'],value['annual_document']]
    response={INDEX_URL:value['published_index_receipt'],**{d['url']:d['raw_receipt'] for d in documents}}
    class Transport:
        def __init__(self): self.components=[];self.deadline=time.monotonic()+10
        def batch(self): return nullcontext()
        def request(self,url,**kwargs):
            self.components.append({'url':url,'http_request_sent':True})
            return read_response(response[url]),response[url]
    annual={'schema':'official-annual-filing-reference:v1','ticker':'1623.TW','report_scope':'individual',
            'statement_taxonomy':'ordinary_individual','coverage':'latest_annual_only',
            'published_index_receipt':value['published_index_receipt'], 'documents':[value['annual_document']]}
    http=Transport();result=fetch_reference('1623.TW',transport=http,annual_reference=annual if reuse else None)
    assert result['audit']['status']=='success',result
    assert result['audit']['http_request_count']==(2 if reuse else 3)
    assert result['audit']['coverage_status']=='supplementary_originals_only'
    assert replay_reference(result['value'],'1623.TW')['status']=='quarterly_originals_verified'


def test_latest_quarter_and_duplicate_index_do_not_choose_an_older_original():
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    for suffix in [URL.format(year=2026,quarter=3).replace('report_id=A','report_id=C'), URL.format(year=2026,quarter=2)]:
        value=reference();raw=read_response(value['published_index_receipt'])+f'<a href="{suffix.replace("&","&amp;")}">extra</a>'.encode()
        value['published_index_receipt']=archive_response(raw,source_url=INDEX_URL,retrieved_at=time.time())
        assert replay_reference(value,'1623.TW')['status']=='unverified'


def test_quarter_and_annual_receipts_cannot_be_claimed_as_historical_point_in_time():
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference();value['quarterly_document']['raw_receipt']['historical_point_in_time_verified']=True
    assert replay_reference(value,'1623.TW')['historical_pit_verified'] is False


def test_reference_transport_does_not_admit_another_issuer_annual_route(monkeypatch):
    from data_fetch.market_sources.tewc_quarterly_reference import QuarterlyReferenceHttp, AnnualReferenceHttp
    monkeypatch.setattr(AnnualReferenceHttp, 'request', lambda *a, **k: pytest.fail('parent transport reached for another issuer'))
    with pytest.raises(ValueError,match='issuer'):
        QuarterlyReferenceHttp().request(URL.format(year=2025,quarter=4).replace('1623','7799'))


@pytest.mark.parametrize('field',['PropertyPlantAndEquipment','IntangibleAssets'])
def test_inconsistent_ttm_purchase_components_cannot_become_positive(field):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference()
    def change(root):
        node=next(n for n in root.iter(IX+'nonFraction') if field in n.get('name') and n.get('contextRef')=='d2025')
        node.text='99999'
    changed_document(value,change)
    assert replay_reference(value,'1623.TW')['status']=='unverified'


@pytest.mark.parametrize('damage',['duplicate_measure','compound_divide','nested_measure'])
def test_money_unit_must_be_one_simple_twd_measure(damage):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference()
    def change(root):
        unit=next(root.iter(XBRLI+'unit'))
        if damage=='duplicate_measure':ET.SubElement(unit,XBRLI+'measure').text='iso4217:USD'
        elif damage=='compound_divide':ET.SubElement(unit,XBRLI+'divide')
        else:ET.SubElement(next(unit.iter(XBRLI+'measure')),XBRLI+'measure').text='iso4217:USD'
    changed_document(value,change)
    assert replay_reference(value,'1623.TW')['status']=='unverified'


def test_required_fact_in_segment_context_is_not_borrowed_from_group():
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference()
    def change(root):
        context=deepcopy(next(root.iter(XBRLI+'context')));context.set('id','segment')
        ET.SubElement(next(context.iter(XBRLI+'entity')),XBRLI+'segment')
        root.append(context);next(root.iter(IX+'nonFraction')).set('contextRef','segment')
    changed_document(value,change)
    result=replay_reference(value,'1623.TW')
    assert result['status']=='unverified' and 'required facts missing' in result['reason']


def test_unexpected_local_reader_error_does_not_expose_private_path(monkeypatch):
    from data_fetch.market_sources import tewc_quarterly_reference as module
    value=reference()
    def private_error(*a,**k):raise OSError('/private/owner/secret/source.gz')
    monkeypatch.setattr(module,'_receipt',private_error)
    result=module.replay_reference(value,'1623.TW')
    assert result['status']=='unverified'
    assert '/private/' not in result['reason'] and 'secret' not in result['reason']


@pytest.mark.parametrize('extra',['measure','divide'])
def test_annual_replay_also_rejects_ambiguous_money_unit_without_changing_annual_parser(extra):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference();doc=value['annual_document'];root=ET.fromstring(read_response(doc['raw_receipt']))
    ET.SubElement(next(root.iter(XBRLI+'unit')),XBRLI+extra).text='iso4217:USD'
    raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))
    assert replay_reference(value,'1623.TW')['status']=='unverified'


@pytest.mark.parametrize('document',['quarterly_document','annual_document'])
@pytest.mark.parametrize('damage',['duplicate_end','duplicate_start','duplicate_instant','mixed',
                                    'nested_date','nested_period','duplicate_period','unused_ambiguous'])
def test_all_context_period_structures_are_unique_flat_and_unambiguous(document,damage):
    from data_fetch.market_sources.tewc_quarterly_reference import replay_reference
    value=reference();doc=value[document];root=ET.fromstring(read_response(doc['raw_receipt']))
    contexts=list(root.iter(XBRLI+'context'))
    context=next(c for c in contexts if c.find(XBRLI+'period').find(XBRLI+('instant' if damage=='duplicate_instant' else 'endDate')) is not None)
    if damage=='unused_ambiguous':
        context=deepcopy(context);context.set('id','unreferenced_ambiguous');root.append(context)
    period=context.find(XBRLI+'period')
    if damage in ('duplicate_end','unused_ambiguous'):
        ET.SubElement(period,XBRLI+'endDate').text='2020-06-30'
    elif damage=='duplicate_start':ET.SubElement(period,XBRLI+'startDate').text='2020-01-01'
    elif damage=='duplicate_instant':ET.SubElement(period,XBRLI+'instant').text='2020-12-31'
    elif damage=='mixed':ET.SubElement(period,XBRLI+'instant').text='2020-12-31'
    elif damage=='nested_date':ET.SubElement(period.find(XBRLI+'endDate'),XBRLI+'endDate').text='2020-06-30'
    elif damage=='nested_period':ET.SubElement(ET.SubElement(period,XBRLI+'period'),XBRLI+'instant').text='2020-12-31'
    elif damage=='duplicate_period':context.append(deepcopy(period))
    raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))
    assert replay_reference(value,'1623.TW')['status']=='unverified'


def test_ambiguous_annual_period_is_rejected_before_legacy_parser(monkeypatch):
    from data_fetch.market_sources import tewc_quarterly_reference as module
    value=reference();doc=value['annual_document'];root=ET.fromstring(read_response(doc['raw_receipt']))
    context=next(c for c in root.iter(XBRLI+'context') if c.find(XBRLI+'period').find(XBRLI+'endDate') is not None)
    ET.SubElement(context.find(XBRLI+'period'),XBRLI+'endDate').text='2020-12-31'
    raw=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    doc.update(sha256=sha256(raw).hexdigest(),raw_receipt=archive_response(raw,source_url=doc['url'],retrieved_at=time.time()))
    monkeypatch.setattr(module,'parse_individual_filing',lambda *a,**k:pytest.fail('ambiguous period reached legacy annual parser'))
    assert module.replay_reference(value,'1623.TW')['status']=='unverified'
