"""Dated TWSE monthly tables, anchored to complete issuer and CSV originals.

Only six contiguous monthly amounts are consumed. Other PDF financial/price
tables, presented growth ratios, annual facts, TTM and PIT are not inferred.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import base64
import math
import re
import time

from data_trust import build_source_audit_entry, iso_from_epoch
from official_response_evidence import archive_response, read_response
from provider_correlation import source_operation
from search_provider_runtime import SourceResponseError
from shared_provider_cache import shared_fetch
from source_pdf_reader import extract_pdf_pages
from .issuer_news_transport import IssuerNewsHttp
from .official_company_legal_name import read_cached_listed_roster_bytes, parse_roster
from . import official_monthly_revenue as snapshot_source
from .official_monthly_revenue import (PROVIDER as SNAPSHOT_PROVIDER,
                                     monthly_url, parse_monthly_snapshot, select_monthly_records)

PROVIDER = 'TWSE official monthly revenue history'
POLICY = 'twse-monthly-history-v1'
MAX_BYTES = 8_000_000
TTL = 1800
_TICKER = re.compile(r'[1-9][0-9]{3}\.TW')
_ROW = re.compile(r'(-?(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*)|-)((?:19|20)[0-9]{2})/(0[1-9]|1[0-2])')
_RECEIPT_FIELDS = {'status', 'source_url', 'retrieved_at', 'http_status',
                   'raw_response_sha256', 'raw_response_path', 'raw_response_bytes',
                   'evidence_kind', 'historical_point_in_time_verified', 'finality_guaranteed'}


def _today():
    return snapshot_source._today()


def _receipt_is_fresh(receipt, now=None):
    stamp = receipt.get('retrieved_at') if isinstance(receipt, dict) else None
    return (type(stamp) in (int, float) and math.isfinite(stamp)
            and 0 <= (time.time() if now is None else now) - stamp < TTL)


def _receipt_bytes(receipt, url, limit):
    if (not isinstance(receipt, dict) or set(receipt) != _RECEIPT_FIELDS
            or receipt['status'] != 'archived' or receipt['source_url'] != url
            or type(receipt['http_status']) is not int or receipt['http_status'] != 200
            or receipt['evidence_kind'] != 'raw_http_response_bytes'
            or receipt['historical_point_in_time_verified'] is not False
            or receipt['finality_guaranteed'] is not False
            or not _receipt_is_fresh(receipt)
            or type(receipt['raw_response_bytes']) is not int
            or not 0 < receipt['raw_response_bytes'] <= limit):
        raise ValueError('history_original_receipt_unverified')
    raw = read_response(receipt)
    if len(raw) != receipt['raw_response_bytes'] or sha256(raw).hexdigest() != receipt['raw_response_sha256']:
        raise ValueError('history_original_bytes_unverified')
    if not _receipt_is_fresh(receipt):
        raise ValueError('history_original_receipt_unverified')
    return raw


def _qualified(ticker, snapshot):
    if not _TICKER.fullmatch(str(ticker or '')) or not isinstance(snapshot, dict):
        return None
    master = read_cached_listed_roster_bytes()
    if master is None:
        return None
    raw_master, master_meta = master
    anchor = parse_roster(raw_master, '.TW')['entries'].get(ticker.split('.')[0])
    if anchor is None:
        return None
    audit = snapshot.get('audit') or {}
    if (audit.get('provider') != SNAPSHOT_PROVIDER
            or audit.get('status') not in {'success', 'skipped_fresh_cache'}
            or audit.get('currency') != 'NTD' or audit.get('filed_unit') != 'thousands'):
        return None
    url = monthly_url(ticker)
    raw = _receipt_bytes(audit.get('original_receipt'), url, 2_500_000)
    records, coverage = select_monthly_records(parse_monthly_snapshot(raw, url, _today()), ticker, _today())
    if (not records or records != snapshot.get('value')
            or any(audit.get(k) != coverage[k] for k in ('issuer_code', 'issuer_name', 'covered_months', 'filed_amounts'))
            or coverage['issuer_name'] not in {anchor['short_name'], anchor['legal_name']}):
        raise ValueError('history_snapshot_issuer_or_amount_unverified')
    return anchor, master_meta, coverage


def parse_history(pages, ticker, anchor, coverage, today):
    if pages.get('coverage_status') != 'complete' or pages.get('empty_pages') or pages.get('garbled_pages'):
        raise ValueError('history_native_text_incomplete')
    first = pages['pages'][0]['text']
    codes = re.findall(r'股票代號[:：]\s*([0-9]{4})(?![0-9])', first)
    if (set(codes) != {ticker.split('.')[0]}
            or anchor['legal_name'] not in re.sub(r'\s+', '', first)):
        raise ValueError('history_issuer_unverified')
    dates = re.findall(r'產製日期[:：]\s*([0-9]{4}/[0-9]{2}/[0-9]{2})', first)
    if len(dates) != 1:
        raise ValueError('history_production_date_unverified')
    produced = date.fromisoformat(dates[0].replace('/', '-'))
    if not today - timedelta(days=45) <= produced <= today:
        raise ValueError('history_production_date_future_or_expired')
    tables = [p for p in pages['pages'] if '月營收' in p['text'] and '營收月' in p['text']]
    if len(tables) != 1:
        raise ValueError('history_monthly_table_ambiguous')
    amounts = {}
    # The PDF prints P/E tables before monthly revenue on the same page.
    # Their concatenated decimal/date strings must not become monthly rows.
    monthly_text = tables[0]['text'].rsplit('本益比日期', 1)[-1]
    for line in monthly_text.splitlines():
        match = _ROW.fullmatch(line.strip())
        if not match:
            if re.search(r'[0-9]{4}/[0-9]{2}$', line.strip()):
                raise ValueError('history_monthly_row_unverified')
            continue
        amount, year, month = match.groups()
        period = f'{year}-{month}'
        if period in amounts:
            raise ValueError('history_monthly_period_duplicate')
        value = None if amount == '-' else int(amount.replace(',', ''))
        if value is not None and len(str(abs(value))) > 16:
            raise ValueError('history_monthly_amount_unverified')
        amounts[period] = value
    latest = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    periods = []
    for offset in range(5, -1, -1):
        ordinal = latest.year * 12 + latest.month - 1 - offset
        periods.append(f'{ordinal // 12:04d}-{ordinal % 12 + 1:02d}')
    if (not 6 <= len(amounts) <= 60 or max(amounts) != periods[-1]
            or any(amounts.get(p) is None for p in periods)):
        raise ValueError('history_six_month_window_incomplete')
    for p, amount in zip(coverage['covered_months'], coverage['filed_amounts']):
        if amounts.get(p) != int(Decimal(amount) * 1000):
            raise ValueError('history_snapshot_amount_or_unit_conflict')
    return periods, [amounts[p] for p in periods], produced.isoformat()


def _url_contract(url):
    if not re.fullmatch(r'https://www\.twse\.com\.tw/pdf/ch/[1-9][0-9]{3}_ch\.pdf', url):
        raise SourceResponseError('transport_url_invalid')
    return MAX_BYTES, {'application/pdf'}


class HistoryHttp(IssuerNewsHttp):
    route_contract = staticmethod(_url_contract)

    def __init__(self, deadline, ticker, anchor, coverage):
        super().__init__(deadline)
        self.ticker, self.anchor, self.coverage = ticker, anchor, coverage
        self.cold_pages = None

    def _parse(self, raw):
        remaining = min(10., self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError('timeout')
        pages = extract_pdf_pages(raw, timeout_seconds=remaining)
        parse_history(pages, self.ticker, self.anchor, self.coverage, _today())
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return pages

    def _download(self, url, diagnostic):
        value = super()._download(url, diagnostic)
        diagnostic['http_status'] = 200
        raw = base64.b64decode(value['body_b64'], validate=True)
        if not raw.startswith(b'%PDF-'):
            raise SourceResponseError('unexpected_pdf_body', status_code=200)
        receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
        diagnostic['original_receipt'] = receipt
        try:
            self.cold_pages = (sha256(raw).hexdigest(), self._parse(raw))
        except Exception as exc:
            diagnostic['error_kind'] = getattr(exc, 'error_kind', str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
            raise
        if _receipt_bytes(receipt, url, MAX_BYTES) != raw or time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout', status_code=200)
        return {**value, 'original_receipt': receipt}

    def get(self, url):
        _url_contract(url)
        diagnostic = {'url': url, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        value, meta = shared_fetch('twse-monthly-history-raw:v1:' + url,
                                  lambda: self._download(url, diagnostic),
                                  freshness_seconds=TTL, retention_seconds=TTL,
                                  error_retry_seconds=120,
                                  lock_wait_seconds=min(1., max(0., self.deadline-time.monotonic())))
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')))
        if meta.get('error_kind') or meta.get('stale'):
            raise SourceResponseError(diagnostic.get('error_kind') or meta.get('error_kind') or 'stale_receipt')
        if not isinstance(value, dict) or value.get('url') != url:
            raise SourceResponseError('cache_receipt_invalid')
        encoded = value.get('body_b64')
        if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES+2)//3*4:
            raise SourceResponseError('cache_receipt_invalid')
        raw = base64.b64decode(encoded, validate=True)
        receipt = value['original_receipt']
        stamp = meta.get('fetched_at_epoch')
        if (type(stamp) not in (int, float) or not math.isfinite(stamp)
                or not 0 <= stamp - receipt['retrieved_at'] <= 10
                or not 0 <= time.time() - stamp < TTL
                or sha256(raw).hexdigest() != value.get('sha256')
                or _receipt_bytes(receipt, url, MAX_BYTES) != raw):
            raise SourceResponseError('cache_receipt_invalid')
        pages = self.cold_pages[1] if self.cold_pages and self.cold_pages[0] == sha256(raw).hexdigest() else self._parse(raw)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return raw, receipt, pages


def fetch_official_monthly_history(ticker, snapshot, *, deadline):
    """Return None when not eligible; never replace the usable short snapshot."""
    with source_operation('monthly_revenue', PROVIDER):
        return _fetch(ticker, snapshot, deadline)


def _fetch(ticker, snapshot, deadline):
    started = time.time()
    audit = build_source_audit_entry('monthly_revenue', PROVIDER, 'error', record_count=0,
                                     started_at_epoch=started, finished_at_epoch=started)
    audit.update(event_kind='aggregate', http_request_sent=False, cache_hit=False,
                 stale=False, window_complete=False, parser_version=POLICY)
    http = None
    try:
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            return None
        qualified = _qualified(ticker, snapshot)
        if qualified is None or time.monotonic() >= deadline:
            return None
        anchor, master_meta, coverage = qualified
        http = HistoryHttp(deadline, ticker, anchor, coverage)
        url = 'https://www.twse.com.tw/pdf/ch/' + ticker.split('.')[0] + '_ch.pdf'
        audit['source_url'] = url
        raw, receipt, pages = http.get(url)
        periods, amounts, produced = parse_history(pages, ticker, anchor, coverage, _today())
        # Recheck both constituent originals at handoff; neither epoch is renewed.
        qualified_after = _qualified(ticker, snapshot)
        if qualified_after != qualified or _receipt_bytes(receipt, url, MAX_BYTES) != raw:
            raise ValueError('history_constituent_original_changed')
        records = [f'{p[:4]}年{int(p[5:])}月: NT${Decimal(a)/Decimal(100_000_000):.2f}億'
                   for p, a in zip(periods, amounts)]
        now = time.time()
        if (not all(_receipt_is_fresh(r, now) for r in
                    (receipt, snapshot['audit']['original_receipt']))
                or not 0 <= now - master_meta['fetched_at_epoch'] < 86400):
            raise ValueError('history_constituent_original_expired')
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        stamp = min(receipt['retrieved_at'], snapshot['audit']['original_receipt']['retrieved_at'])
        cached = bool(http.components[0].get('cache_hit'))
        audit.update(status='skipped_fresh_cache' if cached else 'success', record_count=6,
                     currency='NTD', filed_unit='NTD', filed_amounts_NTD=[str(a) for a in amounts],
                     covered_months=periods, observed_month=periods[-1], produced_on=produced,
                     issuer_code=ticker.split('.')[0], issuer_name=anchor['legal_name'],
                     coverage_status='complete_six_contiguous_month_amounts', window_complete=True,
                     historical_point_in_time_verified=False, original_receipt=receipt,
                     snapshot_original_receipt=deepcopy(snapshot['audit']['original_receipt']),
                     issuer_original_metadata=master_meta, cache_hit=cached,
                     fetched_at_epoch=stamp, fetched_at=iso_from_epoch(stamp),
                     event_kind='cache_hit' if cached else 'aggregate',
                     response_sha256=receipt['raw_response_sha256'], response_bytes=len(raw),
                     native_text_page_count=pages['page_count'],
                     message='官方六個月營收金額，與當期CSV兩個月交叉核對；非年度財報、TTM或PIT。')
        return {'value': records, 'audit': audit}
    except Exception as exc:
        audit.update(error_kind=getattr(exc, 'error_kind', str(exc) if isinstance(exc, ValueError) else type(exc).__name__),
                     message='官方月營收歷史未取得完整可核對原件。')
        return {'value': [], 'audit': audit}
    finally:
        if http is not None:
            audit.update(http_request_sent=bool(http.http_request_count),
                         http_request_count=http.http_request_count,
                         transport_components=http.components,
                         cache_hit=bool(http.components and http.components[0].get('cache_hit')))
            if http.components and http.components[0].get('http_status') is not None:
                audit['http_status'] = http.components[0]['http_status']
        audit['duration_ms'] = max(0, round((time.time()-started)*1000))
