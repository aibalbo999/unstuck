"""Complete issuer-published holding books, replayed with their original evidence."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import date, datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import math
import time
import zlib
from zoneinfo import ZoneInfo

from .official_xbrl_financial import FilingError
from .financial_institution_xbrl import FIELDS, assemble_histories, reconcile_comparatives
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
from .annual_issuer_master import read_master, current_at, body_audit

TICKER = '5880.TW'
SCHEMA = 'financial_holding_audited_annual.v1'
POLICY = 'tcfhc-five-published-audited-books-positioned.v1'
SOURCE_URL = 'https://www.tcfhc.com.tw/investors-relations/financial-info/financial-reports?sc_lang=en'
PROVIDER = 'TCFHC official audited annual financial statements'
YEARS = (2021, 2022, 2023, 2024, 2025)
NOTE = ('五年年度資料採合庫金控官網發布的英文查核合併財報，逐年核對原始金額與次年比較欄並保留重編依據；'
        '英文與中文有衝突時以中文原件為準，未宣稱為當時首次發布數字。淨收益與一般業營收分開，'
        '自由現金流僅按營業現金流加明列帶符號設備及無形資產支出計算，未證明適用一般業DCF。')


def _bad(reason):
    raise FilingError('TCFHC audited annual ' + reason)


def supports_annual(ticker):
    return ticker == TICKER and date.today().year == 2026


def validate_annual_context(data, ticker):
    if ticker != TICKER:
        return
    identity = data.get('company_identity')
    if identity is None:
        identity = {}
    if not isinstance(identity, dict):
        raise ValueError('tcfhc_annual_identity_invalid')
    expected = {'ticker': TICKER, 'stock_id': '5880', 'official_name': '合庫金',
                'legal_name': '合作金庫金融控股股份有限公司', 'official_ubn': '53021433',
                'instrument_type': 'EQUITY'}
    if any(identity.get(k) not in (None, '', v) for k, v in expected.items()):
        raise ValueError('tcfhc_annual_identity_conflict')
    if any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quote_type', 'quoteType')):
        raise ValueError('tcfhc_annual_instrument_conflict')
    forbidden = identity.get('forbidden_aliases', [])
    if (not isinstance(forbidden, (list, tuple)) or any(not isinstance(v, str) for v in forbidden)
            or {'合庫金', '合作金庫金融控股股份有限公司', 'tcfhc'} & {v.strip().casefold() for v in forbidden}):
        raise ValueError('tcfhc_annual_forbidden_issuer')


def origin_note(value):
    return NOTE if isinstance(value, dict) and value.get('schema') == SCHEMA and value.get('source_basis') == POLICY else None


def _same(left, right):
    return json.dumps(left, ensure_ascii=False, sort_keys=True, separators=(',', ':')) == json.dumps(right, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def _fresh_receipts(receipts):
    completed_at = time.time()
    if not current_at(receipts[0],completed_at):
        _bad('original acquisition TTL expired')
    if any(type(r.get('retrieved_at')) not in (int, float) or not math.isfinite(r['retrieved_at'])
           or not 0 <= completed_at - r['retrieved_at'] < 1800 for r in receipts):
        _bad('original acquisition TTL expired')


def _read(receipt, url):
    from .tcfhc_annual_transport import contract
    from .tcfhc_conference_transport import original_bytes
    # Saved statement verification replays an original, not a current-cache
    # freshness claim. Acquisition separately enforces the original 1800s TTL.
    raw = original_bytes(receipt, url, max_age=100 * 366 * 86400, url_contract=contract)
    return raw


@lru_cache(maxsize=5)
def _parsed_original(raw, year):
    # A bounded pure parse cache is keyed by the entire verified original.
    # It cannot renew a source epoch or bypass archive-byte verification.
    from .tcfhc_audited_financial import parse_book
    return parse_book(raw, year)


def _book(raw, year, deadline=None):
    _deadline(deadline)
    if deadline is not None and deadline - time.monotonic() < 10:
        # No cache miss may outlive the remaining acquisition budget.
        from .tcfhc_audited_financial import parse_book
        parsed = parse_book(raw, year, timeout_seconds=deadline - time.monotonic())
    else:
        parsed = deepcopy(_parsed_original(raw, year))
    _deadline(deadline)
    facts = parsed.get('facts')
    if (not isinstance(facts, dict) or set(facts) != {year, year - 1}
            or any(not isinstance(row, dict) or set(row) != set(FIELDS)
                   or any(type(v) is not int for v in row.values()) for row in facts.values())
            or parsed.get('complete_original_sha256') != sha256(raw).hexdigest()
            or parsed.get('currency') != 'TWD' or parsed.get('report_scope') != 'consolidated'
            or parsed.get('source_unit') != 'TWD_thousand' or parsed.get('source_language') != 'en'
            or parsed.get('Chinese_original_prevails') is not True):
        _bad('complete positioned facts invalid')
    return {**parsed, 'facts': {str(y): row for y, row in facts.items()}}


def _project(original, *, deadline=None, acquiring=False):
    from .tcfhc_annual_transport import MASTER_URL, IR_URL, parse_master, parse_index
    _deadline(deadline)
    if (not isinstance(original, dict) or original.get('ticker') != TICKER
            or original.get('schema') != SCHEMA or original.get('source_url') != SOURCE_URL
            or original.get('source_basis') != POLICY or original.get('currency') != 'TWD'
            or original.get('statement_taxonomy') != 'financial_holding'
            or original.get('report_scope') != 'consolidated'):
        _bad('statement identity invalid')
    mr = original['issuer_master_receipt']; ir = original['issuer_ir_index_receipt']
    master_raw = read_master(mr, _read, max_age=1800 if acquiring else 100*366*86400)
    original_date = datetime.fromtimestamp(mr['retrieved_at'], ZoneInfo('Asia/Taipei')).date()
    identity = parse_master(master_raw, today=date.today() if acquiring else original_date, source_url=mr['source_url'])
    if date.fromisoformat(identity['master_as_of']) > original_date:
        _bad('master future publication')
    links = parse_index(_read(ir, IR_URL))
    docs = original['documents']
    if not isinstance(docs, list) or len(docs) != 5:
        _bad('five originals required')
    primary, comparative, projected_docs = {}, {}, []
    receipts = [mr, ir]
    for year, doc in zip(YEARS, docs):
        _deadline(deadline)
        if (not isinstance(doc, dict) or type(doc.get('year')) is not int or doc['year'] != year
                or doc.get('period_end') != f'{year}-12-31' or doc.get('provider') != PROVIDER
                or doc.get('url') != links[year] or doc.get('report_scope') != 'consolidated'
                or doc.get('format') != 'audited_consolidated_PDF_book'):
            _bad('annual document scope invalid')
        receipt = doc['raw_receipt']; raw = _read(receipt, links[year])
        if doc.get('sha256') != sha256(raw).hexdigest():
            _bad('document digest mismatch')
        if receipt['retrieved_at'] < datetime(year + 1, 1, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp():
            _bad('original retrieval precedes reporting-period close')
        parsed = _book(raw, year, deadline)
        primary[year] = parsed['facts'][str(year)]
        if year > YEARS[0]:
            comparative[year - 1] = parsed['facts'][str(year - 1)]
        projected_docs.append({**{k: deepcopy(doc[k]) for k in ('year', 'period_end', 'provider', 'url', 'report_scope', 'format', 'sha256', 'raw_receipt')},
                               'parsed_book_basis': parsed})
        receipts.append(receipt)
    if acquiring:
        _fresh_receipts(receipts)
    resolved, revisions = reconcile_comparatives(primary, comparative)
    _deadline(deadline)
    return {**assemble_histories(resolved, expected_years=list(YEARS)),
            'schema': SCHEMA, 'ticker': TICKER, 'currency': 'TWD', 'report_scope': 'consolidated',
            'statement_taxonomy': 'financial_holding', 'source_url': SOURCE_URL, 'source_basis': POLICY,
            'source_origin_note': NOTE, 'issuer_anchor': identity, 'issuer_master_receipt': deepcopy(mr),
            'issuer_ir_index_receipt': deepcopy(ir), 'documents': projected_docs,
            'comparative_revisions': sorted(revisions, key=lambda v: (v['year'], v['fact']))}


def project_annual_statement(value, ticker):
    if ticker != TICKER:
        return None
    try:
        rebuilt = _project(value)
        return rebuilt if _same(value, rebuilt) else None
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError, OSError, EOFError, zlib.error, SourcePdfError, SourceResponseError):
        return None


def fetch_annual_histories(ticker, *, transport=None, force_refresh=False):
    from .tcfhc_annual_transport import AnnualHttp, MASTER_URL, IR_URL, parse_master, parse_index
    if not supports_annual(ticker):
        _bad('unsupported issuer or current annual period')
    http = transport or AnnualHttp(force_refresh=force_refresh)
    batch = getattr(http, 'batch', None)
    with batch() if callable(batch) else nullcontext():
        raw, mr = http.request(MASTER_URL); parse_master(raw, source_url=mr['source_url'])
        raw, ir = http.request(IR_URL); links = parse_index(raw)
        docs = []
        for year in YEARS:
            raw, receipt = http.request(links[year])
            docs.append({'year': year, 'period_end': f'{year}-12-31', 'provider': PROVIDER,
                         'url': links[year], 'report_scope': 'consolidated', 'format': 'audited_consolidated_PDF_book',
                         'sha256': sha256(raw).hexdigest(), 'raw_receipt': receipt})
        value = _project({'schema': SCHEMA, 'ticker': TICKER, 'currency': 'TWD', 'report_scope': 'consolidated',
                          'statement_taxonomy': 'financial_holding', 'source_url': SOURCE_URL, 'source_basis': POLICY,
                          'issuer_master_receipt': mr, 'issuer_ir_index_receipt': ir, 'documents': docs},
                         deadline=http.deadline, acquiring=True)
    # Final projection and batch cleanup may outlive a nearly expired original.
    # Check all seven original epochs again at the actual handoff boundary.
    read_master(value['issuer_master_receipt'], _read, max_age=1800)
    _deadline(http.deadline)
    _fresh_receipts([value['issuer_master_receipt'], value['issuer_ir_index_receipt'],
                     *[doc['raw_receipt'] for doc in value['documents']]])
    _deadline(http.deadline)
    return value


def fetch_annual_result(ticker, *, transport=None, force_refresh=False):
    from source_audit import audited_fetch
    from .tcfhc_annual_transport import AnnualHttp
    http = transport or AnnualHttp(force_refresh=force_refresh)
    errors = []
    def acquire():
        try:
            return fetch_annual_histories(ticker, transport=http, force_refresh=force_refresh)
        except (FilingError, SourceResponseError, SourcePdfError) as exc:
            errors.append(exc); raise
        except Exception as exc:
            errors.append(exc)
            # Local failures must not trigger generic repeated downloads.
            raise FilingError('TCFHC acquisition failed closed: ' + type(exc).__name__) from exc
    result = audited_fetch('financial_statements', PROVIDER, acquire, default=None,
                           record_counter=lambda v: len(v['years']), success_message=NOTE)
    audit = result['audit']; components = deepcopy(http.components)
    sent = sum(c.get('http_request_sent') is True for c in components)
    audit.update(http_request_sent=bool(sent), http_request_count=sent,
                 event_kind='aggregate' if sent else 'local_block',
                 component_statuses={str(i): c for i, c in enumerate(components)}, source_mix=POLICY)
    value = result.get('value')
    if isinstance(value, dict):
        audit.update(body_audit([d['raw_receipt'] for d in value['documents']], components),
                     **{k: deepcopy(value[k]) for k in ('source_basis', 'source_origin_note', 'issuer_anchor', 'issuer_master_receipt', 'issuer_ir_index_receipt')})
    if components:
        audit['http_status'] = components[-1].get('http_status')
    if errors:
        audit['error_kind'] = getattr(errors[-1], 'error_kind', type(errors[-1]).__name__)
    return result
