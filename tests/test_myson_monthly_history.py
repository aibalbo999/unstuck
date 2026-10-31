from pathlib import Path
from hashlib import sha256
from datetime import date
import base64,gzip,json,time
from copy import deepcopy
from bs4 import BeautifulSoup
import pandas as pd
import pytest
from data_fetch.types import FetchRequest
from data_fetch.taiwan_providers import MonthlyRevenueProvider

FIXTURES=Path(__file__).parent/'fixtures/source_acquisition/myson_monthly_20261013'
CSV='https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv'
MASTER='https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
INDEX='https://www.myson.com.tw/financial'
CURRENT='https://docs.google.com/spreadsheets/d/1YKWYJ7IsMN4FW5gRf-_uPM5cKkpAGLNRZ_CYOkgNbag/edit?gid=0'
PREVIOUS='https://docs.google.com/spreadsheets/d/1TpOCd6i8iFeEGaJLHUKcZs1i4QyuK1eLfxh1N8xwjkU/edit?usp=sharing'
EXPECTED=['2026年4月: NT$4.94億','2026年5月: NT$5.13億','2026年6月: NT$5.79億',
          '2026年7月: NT$5.53億','2026年8月: NT$4.65億','2026年9月: NT$4.73億']

@pytest.fixture
def original_http(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    cache_store.set_cache_backend(InMemoryCache())
    bodies={url:gzip.decompress((FIXTURES/(name+'.gz')).read_bytes()) for url,name in
            [(CSV,'otc.csv'),(MASTER,'otc_roster.json'),(INDEX,'index.html'),(CURRENT,'current.html'),(PREVIOUS,'previous.html')]}
    calls=[]
    def download(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
        raw=bodies[url]
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    class EmptyLoader:
        def taiwan_stock_month_revenue(self,**kwargs):return pd.DataFrame()
    monkeypatch.setattr(IssuerNewsHttp,'_download',download)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader',EmptyLoader)
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue._today',lambda:date(2026,10,13))
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_transport._today',lambda:date(2026,10,13))
    monkeypatch.setenv('PROVIDER_RETRY_BACKOFF_SECONDS','0');monkeypatch.setenv('PROVIDER_RETRY_JITTER_SECONDS','0')
    yield calls,bodies
    cache_store.reset_cache_store_for_tests()

def test_failed_primary_recovers_six_current_months_from_published_sheet(original_http):
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value==EXPECTED
    assert result.audit['filed_amounts_NTD']==['493736000','512687000','578813000','552778000','465313000','472835000']
    assert result.audit['window_complete'] is True
    assert original_http[0]==[CSV,MASTER,INDEX,CURRENT]
    assert result.audit['historical_point_in_time_verified'] is False
    assert result.audit['related_entries'][0]['provider']=='FinMind TaiwanStockMonthRevenue'

def _sheet_edit(bodies, label, month, value, url=CURRENT):
    soup=BeautifulSoup(bodies[url],'html.parser')
    rows=[tr for tr in soup.find_all('tr') if len(tr.find_all(['td','th']))>1
          and tr.find_all(['td','th'])[1].get_text(' ',strip=True)==label]
    assert len(rows)==1
    cell=rows[0].find_all(['td','th'])[month+1];cell.clear();cell.append(value)
    bodies[url]=str(soup).encode()

def _official_csv_change(bodies, **values):
    import csv,io
    reader=csv.DictReader(io.StringIO(bodies[CSV].decode('utf-8-sig')));fields=reader.fieldnames;rows=list(reader)
    next(row for row in rows if row['公司代號']=='5314').update(values)
    stream=io.StringIO();writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows);bodies[CSV]=stream.getvalue().encode()

def test_earlier_month_cannot_conflict_with_official_year_to_date(original_http):
    calls,bodies=original_http
    _sheet_edit(bodies,'本月',4,'593,736')
    for month,total in enumerate([1776730,2289417,2868230,3421008,3886321,4359156],4):
        _sheet_edit(bodies,'本年累計',month,str(total+100000))
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value==EXPECTED[-2:] and not result.audit['window_complete']
    assert result.audit['related_entries'][-1]['error_kind']=='myson_official_year_to_date_conflict'
    assert calls==[CSV,MASTER,INDEX,CURRENT]

@pytest.mark.parametrize('change', ['unit','issuer','scope','period','missing','invalid_number','invalid_grouping',
                                     'future','cumulative','csv_conflict','duplicate_row','duplicate_table'])
def test_unverified_sheet_keeps_official_two_month_partial(original_http,change):
    calls,bodies=original_http
    if change=='unit':bodies[CURRENT]=bodies[CURRENT].replace('單位：新台幣仟元'.encode(),'單位：新台幣百萬元'.encode())
    elif change=='issuer':bodies[CURRENT]=bodies[CURRENT].replace('世紀民生'.encode(),'另一公司'.encode())
    elif change=='scope':bodies[CURRENT]=bodies[CURRENT].replace('配合IFRSs實施，營業收入係以合併營業收入申報'.encode(),'個體報表'.encode())
    elif change=='period':_sheet_edit(bodies,'單位：新台幣仟元',4,'114年04月')
    elif change=='missing':_sheet_edit(bodies,'本月',4,'')
    elif change=='invalid_number':_sheet_edit(bodies,'本月',4,'NaN')
    elif change=='invalid_grouping':_sheet_edit(bodies,'本月',4,'49,3736')
    elif change=='future':_sheet_edit(bodies,'本月',10,'1')
    elif change=='cumulative':_sheet_edit(bodies,'本年累計',4,'1,776,731')
    elif change=='csv_conflict':
        _sheet_edit(bodies,'本月',9,'472,836');_sheet_edit(bodies,'本年累計',9,'4,359,157')
    else:
        soup=BeautifulSoup(bodies[CURRENT],'html.parser')
        row=next(tr for tr in soup.find_all('tr')if len(tr.find_all(['td','th']))>1 and tr.find_all(['td','th'])[1].get_text(strip=True)=='本月')
        target=row if change=='duplicate_row'else row.find_parent('table')
        target.insert_after(deepcopy(target));bodies[CURRENT]=str(soup).encode()
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value==EXPECTED[-2:] and not result.audit['window_complete']
    assert calls==[CSV,MASTER,INDEX,CURRENT]
    failure=result.audit['related_entries'][-1]
    assert failure['status']=='error' and failure['error_kind'].startswith('myson_')
    if change=='csv_conflict':assert failure['error_kind']=='myson_snapshot_amount_or_unit_conflict'

@pytest.mark.parametrize('change',['host','duplicate_year','same_sheet_two_years','section','title'])
def test_only_exact_current_issuer_published_links_are_fetched(original_http,change):
    calls,bodies=original_http;soup=BeautifulSoup(bodies[INDEX],'html.parser')
    a=soup.find('a',href=lambda value:value and CURRENT in value)
    if change=='host':a['href']=a['href'].replace('docs.google.com','docs.google.com.attacker.example')
    elif change=='duplicate_year':a.insert_after(deepcopy(a))
    elif change=='same_sheet_two_years':soup.find('a',href=lambda value:value and PREVIOUS in value)['href']=a['href']
    elif change=='section':
        h=next(h for h in soup.find_all('h3')if h.get_text(strip=True)=='每月營業額報告');h.clear();h.append('其他資料')
    else:soup.title.clear();soup.title.append('另一家公司')
    bodies[INDEX]=str(soup).encode();result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value==EXPECTED[-2:] and calls==[CSV,MASTER,INDEX]

def test_explicit_zero_is_retained_but_blank_is_not_zero(original_http):
    _,bodies=original_http
    _sheet_edit(bodies,'本月',4,'0')
    for month,total in enumerate([1776730,2289417,2868230,3421008,3886321,4359156],4):
        _sheet_edit(bodies,'本年累計',month,str(total-493736))
    _official_csv_change(bodies,**{'累計營業收入-當月累計營收':str(4359156-493736)})
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value==['2026年4月: NT$0.00億',*EXPECTED[1:]]
    assert result.audit['filed_amounts_NTD'][0]=='0'

def test_cross_year_six_months_use_only_two_current_published_sheets(original_http,monkeypatch):
    import csv,io
    calls,bodies=original_http
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue._today',lambda:date(2026,6,13))
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_transport._today',lambda:date(2026,6,13))
    roster=json.loads(bodies[MASTER])
    for row in roster:row['Date']='1150612'
    bodies[MASTER]=json.dumps(roster,ensure_ascii=False).encode()
    reader=csv.DictReader(io.StringIO(bodies[CSV].decode('utf-8-sig')));fields=reader.fieldnames;rows=list(reader)
    for row in rows:
        row.update({'出表日期':'1150613','資料年月':'11505'})
        if row['公司代號']=='5314':row.update({'營業收入-當月營收':'512687','營業收入-上月營收':'493736','累計營業收入-當月累計營收':'2289417'})
    stream=io.StringIO();writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows);bodies[CSV]=stream.getvalue().encode()
    for month in range(6,13):
        _sheet_edit(bodies,'本月',month,'');_sheet_edit(bodies,'本年累計',month,'')
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.audit.get('covered_months')==['2025-12','2026-01','2026-02','2026-03','2026-04','2026-05'],result.audit
    assert result.audit['filed_amounts_NTD']==['422755000','489861000','343315000','449818000','493736000','512687000']
    assert calls==[CSV,MASTER,INDEX,PREVIOUS,CURRENT]
    assert len(result.audit['sheet_original_receipts'])==2


def test_warm_read_preserves_original_epoch_and_does_not_count_new_acquisition(original_http):
    from provider_acquisition import observation_kind
    calls, _ = original_http
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    second = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert first.value == second.value == EXPECTED and calls == [CSV, MASTER, INDEX, CURRENT]
    assert second.audit['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert second.audit['http_request_sent'] is False
    assert observation_kind({**second.audit, 'details': second.audit}) == 'fresh_cache_count'


def test_core_merge_keeps_issuer_api_freshness(original_http):
    import asyncio
    from data_fetch.workflow import _run_missing_core_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    data = {'ticker': '5314.TWO', 'recent_monthly_revenue': [], 'source_audit': []}
    result = asyncio.run(_run_missing_core_provider_plan(
        FetchRequest.from_ticker('5314.TWO'), ProviderRegistry([MonthlyRevenueProvider()]), data))
    assert result['recent_monthly_revenue'] == EXPECTED
    assert result['source_freshness']['monthly_revenue']['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert result['source_freshness']['monthly_revenue']['cache_hit'] is True


def test_healthy_primary_does_not_fetch_new_endpoints(original_http, monkeypatch):
    class GoodLoader:
        def taiwan_stock_month_revenue(self, **kwargs):
            return pd.DataFrame([{'revenue_year': 2026, 'revenue_month': 9, 'revenue': 472835000}])
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader', GoodLoader)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.provider == 'FinMind TaiwanStockMonthRevenue' and original_http[0] == []


@pytest.mark.parametrize('data', [{'ticker': '5314.TWO', 'quote_type': 'ETF'}, {'ticker': '2330.TW'}])
def test_conflicting_context_does_not_make_requests(original_http, data):
    saved = deepcopy(data)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'), {'data': data})
    assert result.status == 'not_applicable' and original_http[0] == [] and data == saved


@pytest.mark.parametrize('change,reason', [
    ('name', 'myson_master_identity_unverified'), ('ubn', 'myson_master_identity_unverified'),
    ('domain', 'myson_registered_domain_unverified'), ('partial', 'myson_master_identity_unverified'),
    ('old', 'myson_master_identity_unverified')])
def test_unverified_issuer_master_keeps_two_month_snapshot(original_http, change, reason):
    calls, bodies = original_http
    rows = json.loads(bodies[MASTER]); issuer = next(r for r in rows if r['SecuritiesCompanyCode'] == '5314')
    if change == 'name': issuer['CompanyName'] = '另一家股份有限公司'
    elif change == 'ubn': issuer['UnifiedBusinessNo.'] = '12345678'
    elif change == 'domain': issuer['WebAddress'] = 'https://www.myson.com.tw.attacker.example'
    elif change == 'old': issuer['Date'] = '1151001'
    else: rows = [issuer]
    bodies[MASTER] = json.dumps(rows, ensure_ascii=False).encode()
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value == EXPECTED[-2:] and not result.audit['window_complete']
    assert calls == [CSV, MASTER]
    assert result.audit['related_entries'][-1]['error_kind'] == reason


def test_existing_csv_and_new_history_share_eight_second_budget(original_http, monkeypatch):
    from data_fetch.market_sources import official_monthly_revenue as snapshot
    fetch = snapshot.fetch_official_monthly_revenue; clock = [time.monotonic()]
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    def consume(ticker):
        value = fetch(ticker); clock[0] += 8; return value
    monkeypatch.setattr(snapshot, 'fetch_official_monthly_revenue', consume)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value == EXPECTED[-2:] and original_http[0] == [CSV]


def test_same_fetch_primary_failure_is_not_duplicated(original_http):
    from provider_correlation import correlation_scope
    from source_audit import audited_fetch
    with correlation_scope(replace=True, fetch_id='current', ticker='5314.TWO'):
        first = audited_fetch('monthly_revenue', MonthlyRevenueProvider.name, lambda: [], default=[])
        data = {'ticker': '5314.TWO', 'source_audit': [first['audit']]}; saved = deepcopy(data)
        result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'), {'data': data})
    assert result.value == EXPECTED and data == saved
    assert result.audit['primary_failure_operation_id'] == first['audit']['operation_id']
    assert all(a['provider'] != MonthlyRevenueProvider.name for a in result.audit['related_entries'])


def _seed_isolated_master(bodies, stamp):
    import cache_store
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    raw = bodies[MASTER]
    archive_response(raw, source_url=MASTER, retrieved_at=stamp, http_status=200)
    key = 'shared_provider:v1:' + sha256(b'official-company-roster:v2:.TWO').hexdigest()
    cache_store.set_cache_json(key, {'value': parse_roster(raw, '.TWO'),
                                   'fetched_at_epoch': stamp, 'fresh_until_epoch': stamp + 86400}, 86400)
    return key


def test_existing_full_master_cache_reuses_original_epoch_without_extra_http(original_http):
    calls, bodies = original_http; stamp = time.time() - 100
    _seed_isolated_master(bodies, stamp)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value == EXPECTED and calls == [CSV, INDEX, CURRENT]
    assert result.audit['issuer_original_metadata']['fetched_at_epoch'] == stamp
    assert result.audit['issuer_original_metadata']['http_status_observed'] is False


@pytest.mark.parametrize('change', ['http_bool', 'size', 'future_epoch'])
def test_corrupt_saved_api_receipt_does_not_supply_warm_six_months(original_http, change):
    import cache_store
    calls, _ = original_http
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert first.value == EXPECTED
    key = 'shared_provider:v1:' + sha256(('myson-monthly-raw:v1:' + CURRENT).encode()).hexdigest()
    row = cache_store.get_cache_json(key); receipt = row['value']['original_receipt']
    if change == 'http_bool': receipt['http_status'] = True
    elif change == 'size': receipt['raw_response_bytes'] -= 1
    else: receipt['retrieved_at'] = time.time() + 60
    cache_store.set_cache_json(key, row, 1800)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value == EXPECTED[-2:] and calls == [CSV, MASTER, INDEX, CURRENT]
    assert result.audit['related_entries'][-1]['http_request_sent'] is False


@pytest.mark.parametrize('constituent', ['api', 'csv', 'cached_master'])
def test_expiry_during_final_original_read_prevents_six_month_promotion(original_http, monkeypatch, constituent):
    from data_fetch.market_sources import twse_monthly_history as receipt_helpers
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    calls, bodies = original_http; clock = [time.time()]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    master_stamp = clock[0] - 86394
    if constituent == 'cached_master': _seed_isolated_master(bodies, master_stamp)
    download = IssuerNewsHttp._download
    def spaced(self, url, diagnostic):
        clock[0] += 1
        return download(self, url, diagnostic)
    monkeypatch.setattr(IssuerNewsHttp, '_download', spaced)
    first = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert first.value == EXPECTED
    csv_stamp = first.audit['snapshot_original_receipt']['retrieved_at']
    api_stamp = first.audit['original_receipt']['retrieved_at']
    if constituent != 'cached_master': clock[0] = csv_stamp + 1798
    read = receipt_helpers.read_response; api_reads = []
    def expire(receipt):
        raw = read(receipt)
        if receipt.get('source_url') == CURRENT:
            api_reads.append(1)
            if len(api_reads) == 2:
                clock[0] = (master_stamp + 86400 if constituent == 'cached_master'
                            else api_stamp + 1800 if constituent == 'api' else csv_stamp + 1800) + .01
        return raw
    monkeypatch.setattr(receipt_helpers, 'read_response', expire)
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert len(api_reads) == 2
    assert result.value == EXPECTED[-2:] and not result.audit['window_complete']
    assert calls == ([CSV, INDEX, CURRENT] if constituent == 'cached_master' else [CSV, MASTER, INDEX, CURRENT])
    assert result.audit['related_entries'][-1]['http_request_sent'] is False


def test_csv_name_conflict_stops_issuer_history_before_http(original_http):
    import csv, io
    calls, bodies = original_http
    reader = csv.DictReader(io.StringIO(bodies[CSV].decode('utf-8-sig'), newline=''))
    fields = reader.fieldnames; rows = list(reader)
    next(r for r in rows if r['公司代號'] == '5314')['公司名稱'] = '另一家公司'
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fields)
    writer.writeheader(); writer.writerows(rows); bodies[CSV] = stream.getvalue().encode()
    result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.value == EXPECTED[-2:] and calls == [CSV]
    assert result.audit['related_entries'][-1]['error_kind'] == 'myson_snapshot_issuer_or_amount_unverified'
