"""Exact 1623 individual-quarter originals, separate from undated quote inputs."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from html import unescape
import base64
import re
import time
import zlib
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError, cooldown_state, scope_key
from .annual_filing_reference import AnnualReferenceHttp, _NativeHttp, replay_reference as replay_annual
from .mops_public_annual import PROVIDER, _receipt
from .official_annual_cash_flow import index_request
from .official_xbrl_financial import INDEX_URL, IX, XBRLI, NUMBER_RE, FilingError, _context_period, _filing_urls
from .ordinary_individual_annual import FIELDS as ANNUAL_FIELDS, parse_individual_filing

SCHEMA = 'tewc-quarterly-financial-reference:v1'
SOURCE = 'tewc_quarterly_financial_reference'
TICKER = '1623.TW'
ISSUER_NAME = '大東電業廠股份有限公司'
MAX_BYTES = 6_000_000
BASE = 'https://mopsov.twse.com.tw'
CASH_FIELDS = {'CashFlowsFromUsedInOperatingActivities': 'operating_cash_flow',
               'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities': 'ppe_purchase',
               'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities': 'intangible_purchase'}
DEBT_FIELDS = {'ShorttermBorrowings': 'shortterm_borrowings',
               'CurrentPortionOfLongtermBorrowings': 'current_portion_longterm_borrowings',
               'LongtermBorrowings': 'longterm_borrowings',
               'CurrentLeaseLiabilities': 'current_lease_liabilities',
               'NoncurrentLeaseLiabilities': 'noncurrent_lease_liabilities'}
BALANCE_FIELDS = {'Assets': 'assets', 'Liabilities': 'total_liabilities', 'Equity': 'equity', **DEBT_FIELDS}


def _end(year, quarter):
    if type(year) is not int or type(quarter) is not int or not 2013 <= year <= date.today().year or quarter not in (1, 2, 3):
        raise FilingError('quarterly period not admitted')
    end = date(year, quarter * 3 + 1, 1) - timedelta(days=1)
    if end >= date.today():
        raise FilingError('quarterly period is not complete')
    return end


def native_contract(url):
    parsed = urlsplit(url); q = parse_qs(parsed.query, keep_blank_values=True)
    try:
        year = int(q['year'][0]); quarter = int(q['season'][0]); _end(year, quarter)
    except (KeyError, ValueError, TypeError, IndexError):
        raise FilingError('quarterly native period invalid') from None
    if (parsed.scheme != 'https' or parsed.netloc != 'mopsov.twse.com.tw'
            or parsed.path != '/server-java/FileDownLoad' or parsed.fragment
            or q != {'functionName': ['t164sb01'], 'step': ['9'], 'co_id': ['1623'],
                     'year': [str(year)], 'season': [str(quarter)], 'report_id': ['A']}):
        raise FilingError('quarterly native identity or route invalid')
    return MAX_BYTES, {'application/xml', 'text/xml', 'application/xhtml+xml', 'text/html', 'application/octet-stream', ''}


def _quarter_urls(index):
    if not isinstance(index, bytes) or not 0 < len(index) <= 2_500_000:
        raise FilingError('quarterly index body invalid')
    text = index.decode('utf-8', errors='strict'); found = {}; latest = []
    for path in re.findall(r'/server-java/FileDownLoad\?[^\x27\x22<>\s]+', text):
        url = BASE + unescape(path); q = parse_qs(urlsplit(url).query, keep_blank_values=True)
        if q.get('co_id') != ['1623']:
            raise FilingError('quarterly index includes another issuer')
        if q.get('season') == ['4']:
            continue
        try:
            year, quarter = int(q['year'][0]), int(q['season'][0]); _end(year, quarter)
        except (KeyError, TypeError, ValueError, IndexError):
            raise FilingError('quarterly index period invalid') from None
        latest.append((year, quarter))
        if q.get('report_id') != ['A']:
            continue
        native_contract(url)
        if (year, quarter) in found:
            raise FilingError('quarterly index has duplicate period')
        found[year, quarter] = url
    if not latest or max(latest) not in found:
        raise FilingError('latest indexed quarter has no individual original')
    key = max(latest)
    return key, found[key]


def _validate_context_periods(root):
    """Reject ambiguous dates before the shared first-value context parser."""
    for context in root.iter(XBRLI+'context'):
        periods = context.findall(XBRLI+'period')
        if len(periods) != 1 or len(list(context.iter(XBRLI+'period'))) != 1:
            raise FilingError('quarterly reference context period structure invalid')
        period = periods[0]; children = list(period)
        tags = [child.tag for child in children]
        if (tags != [XBRLI+'instant'] and (len(tags) != 2
                or set(tags) != {XBRLI+'startDate', XBRLI+'endDate'})):
            raise FilingError('quarterly reference context dates are ambiguous')
        dates = {}
        for child in children:
            if (list(child) or child.attrib or not isinstance(child.text, str)
                    or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', child.text)
                    or (child.tail or '').strip()):
                raise FilingError('quarterly reference context date structure invalid')
            try:
                dates[child.tag] = date.fromisoformat(child.text)
            except ValueError:
                raise FilingError('quarterly reference context date invalid') from None
        if (period.text or '').strip() or period.attrib:
            raise FilingError('quarterly reference context period content invalid')
        if XBRLI+'startDate' in dates and dates[XBRLI+'startDate'] > dates[XBRLI+'endDate']:
            raise FilingError('quarterly reference context dates reversed')


def parse_quarterly_filing(raw, year, quarter):
    end = _end(year, quarter)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise FilingError('quarterly original body invalid')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FilingError('quarterly original is not complete XML') from exc
    if root.tag != '{http://www.w3.org/1999/xhtml}html' or {n.text for n in root.iter(XBRLI+'identifier')} != {'1623'}:
        raise FilingError('quarterly original identity invalid')
    _validate_context_periods(root)
    contexts = {}; units = {}
    for n in root.iter(XBRLI+'context'):
        key = n.get('id')
        if not key or key in contexts: raise FilingError('duplicate quarterly context')
        contexts[key] = _context_period(n, '1623')
    for n in root.iter(XBRLI+'unit'):
        key = n.get('id')
        if not key or key in units: raise FilingError('duplicate quarterly unit')
        children = list(n)
        units[key] = (children[0].text if len(children) == 1 and children[0].tag == XBRLI+'measure'
                      and not list(children[0]) else None)
    duration = ('duration', f'{year}-01-01', end.isoformat())
    prior_duration = ('duration', f'{year-1}-01-01', end.replace(year=year-1).isoformat())
    metadata = {'CompanyID': '1623', 'CompanyChineseName': ISSUER_NAME, 'Year': str(year), 'Quarter': str(quarter),
                'ReportCategory': 'Individual report', 'ReportType': 'Financial report (general)',
                'IndustrySector': 'Commercial and industrial'}
    for tag, expected in metadata.items():
        nodes = [n for n in root.iter(IX+'nonNumeric') if n.get('name') == 'tifrs-notes:'+tag]
        if len(nodes) != 1 or contexts.get(nodes[0].get('contextRef')) != duration or ''.join(nodes[0].itertext()).strip() != expected:
            raise FilingError('quarterly metadata mismatch: '+tag)
    wanted = {'current_ytd': (duration, CASH_FIELDS), 'prior_ytd': (prior_duration, CASH_FIELDS),
              'balance': (('instant', end.isoformat()), BALANCE_FIELDS),
              'prior_year_end': (('instant', f'{year-1}-12-31'), {'Assets':'assets', 'Equity':'equity'})}
    result = {}
    for label, (period, fields) in wanted.items():
        row = {}
        for n in root.iter(IX+'nonFraction'):
            tag = n.get('name', '').removeprefix('ifrs-full:')
            if n.get('name') != 'ifrs-full:'+tag or tag not in fields or contexts.get(n.get('contextRef')) != period:
                continue
            text = ''.join(n.itertext()).strip(); field = fields[tag]
            if (field in row or units.get(n.get('unitRef')) != 'iso4217:TWD'
                    or n.get('format') != 'ixt:numdotdecimal' or n.get('scale') != '3'
                    or n.get('decimals') not in ('-3', 'INF') or n.get('sign') not in (None, '-')
                    or len(text) > 40 or not NUMBER_RE.fullmatch(text)):
                raise FilingError('quarterly monetary fact invalid: '+tag)
            value = Decimal(text.replace(',', '')) * 1000 * (-1 if n.get('sign') == '-' else 1)
            if value != value.to_integral_value(): raise FilingError('quarterly fractional TWD unsupported')
            row[field] = int(value)
            if tag.startswith('PurchaseOf') and row[field] > 0:
                raise FilingError('quarterly purchase outflow sign invalid')
        if set(row) != set(fields.values()): raise FilingError('quarterly required facts missing: '+label)
        result[label] = row
    balance = result['balance']
    if (balance['equity'] <= 0 or any(v < 0 for v in balance.values())
            or balance['assets'] != balance['total_liabilities'] + balance['equity']
            or sum(balance[field] for field in DEBT_FIELDS.values()) > balance['total_liabilities']):
        raise FilingError('quarterly balance or debt components do not reconcile')
    return result


def replay_reference(value, ticker):
    """Re-read exact originals; no result qualifies an undated provider scalar."""
    result = {'status':'unverified', 'raw_scalar_period_verified':False, 'historical_pit_verified':False,
              'five_year_history_verified':False, 'industrial_dcf_applicable':False}
    try:
        if (ticker != TICKER or not isinstance(value, dict) or value.get('schema') != SCHEMA
                or value.get('ticker') != ticker or value.get('report_scope') != 'individual'):
            raise FilingError('quarterly reference issuer or schema invalid')
        index = _receipt(value['published_index_receipt'], INDEX_URL, 2_500_000)
        (year, quarter), url = _quarter_urls(index); end = _end(year, quarter)
        close = datetime.combine(end + timedelta(days=1), datetime.min.time(), ZoneInfo('Asia/Taipei')).timestamp()
        _receipt(value['published_index_receipt'], INDEX_URL, 2_500_000, not_before=close)
        doc = value['quarterly_document']; annual = value['annual_document']
        if (not isinstance(doc, dict) or type(doc.get('year')) is not int or type(doc.get('quarter')) is not int
                or doc['year'] != year or doc['quarter'] != quarter or doc.get('url') != url):
            raise FilingError('quarterly reference document does not match index')
        raw = _receipt(doc['raw_receipt'], url, MAX_BYTES, not_before=close)
        if sha256(raw).hexdigest() != doc.get('sha256'): raise FilingError('quarterly reference hash mismatch')
        parsed = parse_quarterly_filing(raw, year, quarter)
        annual_url = _filing_urls(index, '1623', report_id='A').get(year-1)
        if (not annual_url or not isinstance(annual, dict) or type(annual.get('year')) is not int
                or annual['year'] != year-1 or type(annual.get('quarter')) is not int
                or annual['quarter'] != 4 or annual.get('url') != annual_url):
            raise FilingError('quarterly prior annual reference mismatch')
        annual_close = datetime(year, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        annual_raw = _receipt(annual['raw_receipt'], annual_url, MAX_BYTES, not_before=annual_close)
        if sha256(annual_raw).hexdigest() != annual.get('sha256'): raise FilingError('quarterly annual hash mismatch')
        # Validate structure before invoking the unchanged annual parser,
        # whose context lookup intentionally returns only the first date.
        if (not 0 < len(annual_raw) <= MAX_BYTES or b'<!DOCTYPE' in annual_raw.upper()
                or b'<!ENTITY' in annual_raw.upper()):
            raise FilingError('quarterly annual original body invalid')
        try:
            annual_root = ET.fromstring(annual_raw)
        except ET.ParseError as exc:
            raise FilingError('quarterly annual original is not complete XML') from exc
        _validate_context_periods(annual_root)
        annual_parsed = parse_individual_filing(annual_raw, '1623', year-1, reference_only=True)
        # Each consumed annual monetary unit must also be simple TWD.
        annual_contexts = {n.get('id'): _context_period(n, '1623') for n in annual_root.iter(XBRLI+'context')}
        annual_periods = {p for y in (year-1, year-2) for p in (
            ('instant', f'{y}-12-31'), ('duration', f'{y}-01-01', f'{y}-12-31'))}
        annual_units = {}
        for unit in annual_root.iter(XBRLI+'unit'):
            children = list(unit)
            annual_units[unit.get('id')] = (children[0].text if len(children) == 1
                and children[0].tag == XBRLI+'measure' and not list(children[0]) else None)
        for fact in annual_root.iter(IX+'nonFraction'):
            if (fact.get('name') in {'ifrs-full:'+tag for tag in ANNUAL_FIELDS}
                    and annual_contexts.get(fact.get('contextRef')) in annual_periods
                    and annual_units.get(fact.get('unitRef')) != 'iso4217:TWD'):
                raise FilingError('quarterly annual monetary unit is not simple TWD')
        annual_facts = annual_parsed[year-1]
        if annual_parsed['inferred_zero_facts']:
            raise FilingError('quarterly reference requires explicitly reported annual purchase components')
        if any(annual_facts[field] != amount for field, amount in parsed['prior_year_end'].items()):
            raise FilingError('quarterly comparative year-end differs from annual original')
        flows = {key: dict(parsed[key]) for key in ('current_ytd', 'prior_ytd')}
        flows['prior_annual'] = {field: annual_facts[field] for field in CASH_FIELDS.values()}
        flows['ttm'] = {field: flows['prior_annual'][field] + flows['current_ytd'][field] - flows['prior_ytd'][field]
                        for field in CASH_FIELDS.values()}
        if any(flows['ttm'][field] > 0 for field in ('ppe_purchase', 'intangible_purchase')):
            raise FilingError('quarterly TTM purchase components conflict with outflow basis')
        for row in flows.values(): row['free_cash_flow'] = sum(row.values())
        balance = dict(parsed['balance']); components = {field: balance.pop(field) for field in DEBT_FIELDS.values()}
        balance.update(as_of=end.isoformat(), interest_bearing_debt_including_leases=sum(components.values()))
        result.update(status='quarterly_originals_verified', ticker=ticker, currency='TWD', report_scope='individual',
                      issuer_name=ISSUER_NAME, source_url=url,
                      acquired_at=datetime.fromtimestamp(doc['raw_receipt']['retrieved_at'], ZoneInfo('Asia/Taipei')).isoformat(),
                      period_start=(end.replace(year=year-1)+timedelta(days=1)).isoformat(), period_end=end.isoformat(),
                      current_ytd_period_start=f'{year}-01-01', prior_ytd_period_start=f'{year-1}-01-01',
                      prior_ytd_period_end=end.replace(year=year-1).isoformat(), prior_annual_year=year-1,
                      cashflows=flows, balance=balance, debt_components=components,
                      ratios={'debt_including_leases_to_equity_pct':sum(components.values())/balance['equity']*100,
                              'total_liabilities_to_equity_pct':balance['total_liabilities']/balance['equity']*100},
                      ratio_definitions={'debt_including_leases_to_equity_pct':'短期借款＋長期借款流動部分＋長期借款＋流動及非流動租賃負債，除以同日權益',
                                         'total_liabilities_to_equity_pct':'總負債除以同日權益'},
                      ttm_formula='prior_annual + current_ytd - prior_ytd',
                      free_cash_flow_definition='營業現金流加明列設備及無形資產現金購置支出；支出為負值',
                      reason='僅為同口徑個別財報補充；不認證原即期純量期間，不替換原資料或分析，也不證明歷史可得性。')
        return result
    except (KeyError, TypeError, ValueError, OSError, EOFError, OverflowError, zlib.error) as exc:
        reason = str(exc)[:240] if isinstance(exc, FilingError) else 'quarterly original validation failed'
        return dict(result, status='unverified', reason=reason)


class _QuarterNativeHttp(_NativeHttp):
    route_contract = staticmethod(native_contract)


class QuarterlyReferenceHttp(AnnualReferenceHttp):
    def __init__(self, **kwargs):
        super().__init__(seconds=kwargs.pop('seconds', 20), **kwargs)

    def request(self, url, *, request=None, json_body=None):
        if url == INDEX_URL:
            return super().request(url, request=request, json_body=json_body)
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        if query.get('co_id') != ['1623']:
            raise FilingError('quarterly transport issuer not admitted')
        if query.get('season') == ['4']:
            return super().request(url, request=request, json_body=json_body)
        native_contract(url)
        if request is not None or json_body is not None: raise FilingError('quarterly original requires GET')
        diag = {'url':url, 'request_method':'GET', 'http_request_sent':False}; self.components.append(diag)
        if cooldown_state(scope_key(PROVIDER, endpoint='mopsov.twse.com.tw')): raise SourceResponseError('cooldown')
        try:
            value = _QuarterNativeHttp(self.deadline)._download(url, diag)
            raw = base64.b64decode(value['body_b64'], validate=True)
            proof = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
            if _receipt(proof, url, MAX_BYTES) != raw: raise FilingError('quarterly archive mismatch')
            diag.update(http_status=200, status='complete', response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw), raw_receipt=proof)
            if not raw.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'<?xml'): raise SourceResponseError('parse_error')
            return raw, proof
        except Exception as exc:
            diag.update(error_kind=getattr(exc, 'error_kind', type(exc).__name__))
            raise


def fetch_reference(ticker, *, transport=None, annual_reference=None):
    """At most index, latest-quarter and prior-annual requests; no core mutation."""
    from source_audit import audited_fetch
    from provider_resilience import _check_provider_state
    from provider_throttle import enforce_provider_throttle
    from .financial_institution_xbrl import PROVIDER as FINANCIAL_PROVIDER
    http = transport or QuarterlyReferenceHttp()
    def acquire():
        if ticker != TICKER: raise FilingError('quarterly reference issuer not admitted')
        _check_provider_state(FINANCIAL_PROVIDER); enforce_provider_throttle(FINANCIAL_PROVIDER)
        with http.batch():
            index, proof = http.request(INDEX_URL, request=index_request('1623'))
            (year, quarter), url = _quarter_urls(index)
            raw, receipt = http.request(url)
            quarterly = {'year':year, 'quarter':quarter, 'url':url, 'sha256':sha256(raw).hexdigest(), 'raw_receipt':receipt}
            annual_url = _filing_urls(index, '1623', report_id='A').get(year-1)
            if not annual_url: raise FilingError('prior individual annual original absent from index')
            if annual_reference is not None:
                if not isinstance(annual_reference, dict):
                    raise FilingError('supplied annual reference invalid')
                verified = replay_annual(annual_reference, ticker)
                candidates = [d for d in annual_reference.get('documents', []) if d.get('year') == year-1 and d.get('url') == annual_url]
                if verified['status'] != 'annual_originals_verified' or len(candidates) != 1:
                    raise FilingError('supplied annual reference cannot be reused')
                annual = {**deepcopy(candidates[0]), 'quarter':4}
            else:
                body, annual_receipt = http.request(annual_url)
                annual = {'year':year-1, 'quarter':4, 'url':annual_url, 'sha256':sha256(body).hexdigest(), 'raw_receipt':annual_receipt}
        value = {'schema':SCHEMA, 'ticker':ticker, 'report_scope':'individual', 'published_index_receipt':proof,
                 'quarterly_document':quarterly, 'annual_document':annual}
        checked = replay_reference(value, ticker)
        if checked['status'] != 'quarterly_originals_verified': raise FilingError(checked['reason'])
        if time.monotonic() >= http.deadline: raise SourceResponseError('timeout')
        return value
    result = audited_fetch(SOURCE, PROVIDER, acquire, record_counter=lambda value: 2,
                           success_message='已核對個別季度及年度補充原件；原即期純量與品質判定保持。')
    components = deepcopy(http.components); count = sum(row.get('http_request_sent') is True for row in components)
    result['audit'].update(http_request_sent=bool(count), http_request_count=count, component_statuses=components,
                           coverage_status='supplementary_originals_only', actual_provider='TWSE MOPS individual quarterly iXBRL originals', admission_provider=PROVIDER)
    return result
