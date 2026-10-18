"""Full issuer-bound holding statements from MOPS' anonymous public JSON UI.

Only the captured Mega holding layout is admitted. Every consumer reconstructs
the ten explicit facts and revisions from complete bodies and unit templates.
"""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import time
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo
from search_provider_runtime import SourceResponseError

from .mops_public_annual import (
    PublicMopsHttp, STATEMENTS, SOURCE_URL, api_url, template_url, payload,
    MAX_BYTES, _object, _template, _receipt,
)
from .official_xbrl_financial import INDEX_URL, FilingError, _filing_urls
from .official_mopsfin_financial import _amount
from .financial_institution_xbrl import FIELDS, reconcile_comparatives, assemble_histories

PROVIDER = 'TWSE MOPS public financial-holding annual JSON'
SCHEMA = 'financial_holding_public_annual.v1'
LABELS = {
    'BalanceSheet': {
        'ifrs-full:Assets': '資產總計',
        'ifrs-full:EquityAttributableToOwnersOfParent': '歸屬於母公司業主之權益',
    },
    'IncomeStatement': {
        'ifrs-full:RevenueFromInterest': '利息收入',
        'tifrs-bsci-fh:NetInterestIncomeExpense': '利息淨收益',
        'tifrs-bsci-fh:NetServiceFeeChargeAndCommissionsIncomeLoss': '手續費及佣金淨收益',
        'tifrs-bsci-fh:NetIncomeLoss': '淨收益',
        'ifrs-full:ProfitLossAttributableToOwnersOfParent': '母公司業主（淨利∕淨損）',
    },
    'CashflowStatement': {
        'ifrs-full:CashFlowsFromUsedInOperatingActivities': '營業活動之淨現金流入（流出）',
        'ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities': '取得不動產及設備',
        'ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities': '取得無形資產',
    },
}


def supports_public_holding(ticker):
    return ticker == '2886.TW'


def parse_holding_statement(raw, ticker, year, statement, template):
    if (not supports_public_holding(ticker) or statement not in STATEMENTS
            or type(year) is not int or not 2013 <= year < date.today().year
            or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES):
        raise FilingError('public holding statement identity or body invalid')
    _template(template, statement)
    try:
        value = json.loads(raw.decode('utf8', errors='strict'), object_pairs_hook=_object)
        r = value['result']
        if (type(value['code']) is not int or value['code'] != 200 or not isinstance(r, dict)
                or r['reportType'] != '合併' or r['year'] != str(year - 1911) or r['season'] != '4'
                or type(r['fiscalYear']) is not str or r['fiscalYear'].strip()
                or r['companyAbbreviation'] != '兆豐金' or not isinstance(r.get('subsidiary'), list)
                or r.get('subsidiaryCompanyId', '') not in (None, '')
                or any(k in r for k in ('currency', 'unit', 'scale'))):
            raise FilingError('public holding scope, period or unit metadata invalid')
        refs = [v['url'] for v in r['urlList'] if isinstance(v, dict) and v.get('name') == 'XBRL資訊平台']
        if len(refs) != 1:
            raise FilingError('public holding issuer reference ambiguous')
        ref = urlsplit(refs[0])
        if (ref.scheme != 'https' or ref.netloc != 'mopsov.twse.com.tw'
                or ref.path != '/server-java/t164sb01' or ref.fragment
                or parse_qs(ref.query, keep_blank_values=True) != {
                    'step': ['1'], 'CO_ID': ['2886'], 'SYEAR': [str(year)], 'SSEASON': ['4'], 'REPORT_ID': ['C']}):
            raise FilingError('public holding issuer reference mismatch')
        suffix = '年12月31日' if statement == 'BalanceSheet' else '年度'
        sub = [{'main': '金額', 'sub': []}] + ([] if statement == 'CashflowStatement' else [{'main': '%', 'sub': []}])
        expected = [{'main': '會計項目', 'sub': []}, {'main': str(year - 1911) + suffix, 'sub': sub},
                    {'main': str(year - 1912) + suffix, 'sub': sub}]
        # An explicitly dated beginning balance is separate from the closing
        # comparative. Only the first two stated closing periods supply facts.
        third = expected + [{'main': str(year - 1912) + '年01月01日', 'sub': sub}]
        if r['titles'] != expected and not (statement == 'BalanceSheet' and r['titles'] == third):
            raise FilingError('public holding monetary period columns invalid')
        width = 3 if statement == 'CashflowStatement' else 1 + 2 * (len(r['titles']) - 1)
        rows = r['reportList']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 400:
            raise FilingError('public holding statement rows invalid')
        facts = {year: {}, year - 1: {}}
        for tag, label in LABELS[statement].items():
            matches = [v for v in rows if isinstance(v, list) and v and isinstance(v[0], str) and v[0].strip() == label]
            if statement == 'BalanceSheet' and tag == 'ifrs-full:EquityAttributableToOwnersOfParent':
                headings = [v for v in matches if len(v) == width and v[1:] == [''] * (width - 1)]
                if len(headings) > 1:
                    raise FilingError('duplicate public holding equity heading')
                matches = [v for v in matches if v not in headings]
            if len(matches) != 1 or len(matches[0]) != width:
                raise FilingError('missing or duplicate public holding monetary fact: ' + label)
            row = matches[0]
            for period, col in ((year, 1), (year - 1, 2 if statement == 'CashflowStatement' else 3)):
                if type(row[col]) is not str or len(row[col]) > 40:
                    raise FilingError('invalid public holding monetary value: ' + label)
                number = _amount(row[col], label=label)
                if tag.startswith('ifrs-full:PurchaseOf') and number > 0:
                    raise FilingError('public holding cash outflow sign ambiguous')
                facts[period][tag] = number
        return facts
    except (KeyError, TypeError, ValueError, UnicodeError, IndexError) as exc:
        if isinstance(exc, FilingError):
            raise
        raise FilingError('public holding JSON metadata or facts invalid') from exc


def _resolved(primary, comparative):
    rows, revisions = reconcile_comparatives(primary, comparative)
    return assemble_histories(rows, expected_years=sorted(rows)), sorted(revisions, key=lambda v: (v['year'], v['fact']))


def project_public_holding_statement(value, ticker):
    """Rebuild the full statement; saved facts or markers alone never suffice."""
    try:
        if (not isinstance(value, dict) or not supports_public_holding(ticker)
                or value.get('ticker') != ticker or value.get('schema') != SCHEMA
                or value.get('statement_taxonomy') != 'financial_holding' or value.get('currency') != 'TWD'
                or value.get('report_scope') != 'consolidated' or value.get('source_url') != SOURCE_URL):
            return None
        years = value['years']; docs = value['documents']
        if (not isinstance(years, list) or len(years) != 5 or any(type(y) is not str or not y.isdigit() or len(y) != 4 for y in years)
                or years != [str(y) for y in range(int(years[0]), int(years[0]) + 5)]
                or not 2013 <= int(years[0]) <= int(years[-1]) < date.today().year
                or not isinstance(docs, list) or len(docs) != 5):
            return None
        close = datetime(int(years[-1]) + 1, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        index = _receipt(value['published_index_receipt'], INDEX_URL, 2_500_000, not_before=close)
        if sorted(_filing_urls(index, '2886'))[-5:] != [int(y) for y in years]:
            return None
        primary, comparative, templates = {}, {}, {}
        for y, doc in zip(years, docs):
            year = int(y)
            if (not isinstance(doc, dict) or type(doc.get('year')) is not int or doc['year'] != year
                    or doc.get('period_end') != y + '-12-31' or doc.get('report_scope') != 'consolidated'
                    or doc.get('provider') != PROVIDER or doc.get('url') != api_url('BalanceSheet')
                    or not isinstance(doc.get('components'), list) or len(doc['components']) != 3):
                return None
            facts, prior = {}, {}
            for statement, part in zip(STATEMENTS, doc['components']):
                if (not isinstance(part, dict) or part.get('statement') != statement
                        or type(part.get('year')) is not int or part['year'] != year
                        or part.get('period_end') != y + '-12-31' or part.get('provider') != PROVIDER
                        or part.get('url') != api_url(statement) or part.get('request') != payload('2886', year)):
                    return None
                raw = _receipt(part['raw_receipt'], api_url(statement), not_before=datetime(year + 1, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp())
                if sha256(raw).hexdigest() != part.get('sha256'):
                    return None
                unit = part['unit_template_receipt']; key = json.dumps(unit, sort_keys=True)
                if key not in templates:
                    templates[key] = _receipt(unit, template_url(statement), not_before=close)
                parsed = parse_holding_statement(raw, ticker, year, statement, templates[key])
                facts.update(parsed[year]); prior.update(parsed[year - 1])
            if doc.get('sha256') != sha256(';'.join(p['sha256'] for p in doc['components']).encode()).hexdigest():
                return None
            primary[year] = facts
            if year > int(years[0]):
                comparative[year - 1] = prior
        assembled, revisions = _resolved(primary, comparative)
        rows = value['raw_twd_by_year']
        if (not isinstance(rows, dict) or set(rows) != set(years)
                or any(not isinstance(v, dict) or set(v) != set(FIELDS.values()) | {'free_cash_flow'}
                       or any(type(n) is not int for n in v.values()) for v in rows.values())
                or rows != assembled['raw_twd_by_year'] or value.get('comparative_revisions') != revisions):
            return None
        return deepcopy(value)
    except (KeyError, ValueError, TypeError, OverflowError, OSError, EOFError):
        return None


def fetch_public_holding_histories(ticker, *, transport=None):
    if not supports_public_holding(ticker):
        raise FilingError('public holding issuer layout unsupported')
    http = transport or PublicMopsHttp()
    with http.batch():
        index, index_receipt = http.request(INDEX_URL, request={'step': '1', 'firstin': 'ture', 'off': '1', 'queryName': 'co_id', 'inpuType': 'co_id', 'TYPEK': 'all', 'co_id': '2886'})
        years = sorted(_filing_urls(index, '2886'))[-5:]
        if len(years) != 5 or years != list(range(years[0], years[0] + 5)) or years[-1] >= date.today().year:
            raise FilingError('public holding five published annual filings incomplete')
        templates = {s: http.request(template_url(s)) for s in STATEMENTS}
        primary, comparative, docs = {}, {}, []
        for year in years:
            facts, prior, parts = {}, {}, []
            for s in STATEMENTS:
                url = api_url(s); request = payload('2886', year)
                raw, receipt = http.request(url, json_body=request)
                parsed = parse_holding_statement(raw, ticker, year, s, templates[s][0])
                facts.update(parsed[year]); prior.update(parsed[year - 1])
                parts.append({'year': year, 'period_end': f'{year}-12-31', 'statement': s, 'provider': PROVIDER,
                              'url': url, 'request': request, 'sha256': sha256(raw).hexdigest(), 'raw_receipt': receipt,
                              'unit_template_receipt': templates[s][1]})
            primary[year] = facts
            if year > years[0]:
                comparative[year - 1] = prior
            docs.append({'year': year, 'period_end': f'{year}-12-31', 'report_scope': 'consolidated',
                         'provider': PROVIDER, 'url': api_url('BalanceSheet'), 'components': parts,
                         'sha256': sha256(';'.join(p['sha256'] for p in parts).encode()).hexdigest()})
        assembled, revisions = _resolved(primary, comparative)
        value = {**assembled, 'schema': SCHEMA, 'ticker': ticker, 'currency': 'TWD', 'statement_taxonomy': 'financial_holding',
                 'report_scope': 'consolidated', 'source_url': SOURCE_URL, 'published_index_receipt': index_receipt,
                 'documents': docs, 'comparative_revisions': revisions}
        if project_public_holding_statement(value, ticker) is None:
            raise FilingError('public holding complete original projection invalid')
    if time.monotonic() >= http.deadline:
        raise SourceResponseError('timeout')
    return value


def fetch_public_holding_result(ticker, *, transport=None):
    from source_audit import audited_fetch
    http = transport or PublicMopsHttp()
    def acquire():
        try:
            return fetch_public_holding_histories(ticker, transport=http)
        except (FilingError, SourceResponseError):
            raise
        except Exception as exc:
            # Unknown local or cleanup errors cannot restart nineteen requests
            # through the generic provider retry loop or promote a later try.
            raise FilingError('public holding acquisition failed closed: ' + type(exc).__name__) from exc
    result = audited_fetch('financial_statements', PROVIDER, acquire,
                          default=None, record_counter=lambda v: len(v['years']))
    sent = sum(c.get('http_request_sent') is True for c in http.components)
    result['audit'].update(http_request_sent=bool(sent), http_request_count=sent,
        event_kind='aggregate' if sent else 'local_block', component_statuses={str(i): deepcopy(c) for i, c in enumerate(http.components)})
    if http.components:
        result['audit']['http_status'] = http.components[-1].get('http_status')
    return result
