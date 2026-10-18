"""Exact-issuer public monthly JSON, corroborated by the exchange snapshot.

The published frontend asset pins the documented unit and consolidation scope.
It is a versioned contract reference, not proof of current website navigation or
historical publication time. A changed asset/schema/issuer fails closed.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlsplit
import base64
import json
import math
import time

from cache_store import get_cache_json
from data_trust import build_source_audit_entry, iso_from_epoch
from official_response_evidence import archive_response, read_response
from provider_correlation import source_operation
from runtime_paths import current_runtime_paths
from search_provider_runtime import SourceResponseError
from shared_provider_cache import shared_fetch
from .issuer_news_transport import IssuerNewsHttp
from .official_company_legal_name import parse_roster, select_legal_name
from . import official_monthly_revenue as snapshot_source
from .twse_monthly_history import _receipt_bytes, _receipt_is_fresh

PROVIDER = 'Auras official monthly revenue history'
POLICY = 'auras-monthly-history-v1'
TICKER = '3324.TWO'
MASTER = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
UNIT = 'https://www.auras.com.tw/assets/FinancialInformtion-f05283f2.js'
UNIT_SHA = 'e0f38342343e9cdde25f3f3434e1b912db291f967c30856e4cf18fd9ebb947d9'
API = 'https://www.auras.com.tw/CmsApi/api/FinancialReport/getFinancialReportAsync?Year=&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true'
TTL = 1800
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june',
          'july', 'august', 'september', 'october', 'november', 'december')


def _json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('auras_duplicate_json_key')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('auras_nonfinite_json')))


def _master_anchor(raw, *, today=None):
    roster = parse_roster(raw, '.TWO')
    if len(roster['entries']) < 700:
        raise ValueError('auras_master_identity_unverified')
    today = snapshot_source._today() if today is None else today
    anchor = select_legal_name(roster, TICKER, '雙鴻', today=today)
    if (not anchor or anchor['legal_name'] != '雙鴻科技股份有限公司'
            or anchor['official_ubn'] != '16619628'
            or not 0 <= (today - date.fromisoformat(anchor['as_of'])).days <= 7):
        raise ValueError('auras_master_identity_unverified')
    rows = [r for r in _json(raw) if r.get('SecuritiesCompanyCode') == '3324']
    if len(rows) != 1:
        raise ValueError('auras_master_identity_unverified')
    url = urlsplit(rows[0].get('WebAddress', ''))
    if (url.scheme not in {'http', 'https'} or url.netloc != 'www.auras.com.tw'
            or url.path not in {'', '/'} or url.query or url.fragment):
        raise ValueError('auras_registered_domain_unverified')
    return anchor


def _cached_master():
    key = 'shared_provider:v1:' + sha256(b'official-company-roster:v2:.TWO').hexdigest()
    cached = get_cache_json(key)
    if not isinstance(cached, dict) or cached.get('error_kind'):
        return None
    stamp, until = cached.get('fetched_at_epoch'), cached.get('fresh_until_epoch')
    now = time.time()
    if (type(stamp) not in (int, float) or type(until) not in (int, float)
            or not math.isfinite(stamp) or not math.isfinite(until)
            or not 0 <= now - stamp < 86400 or not now < until or not 0 < until - stamp <= 86401):
        return None
    roster = cached.get('value')
    if not isinstance(roster, dict) or not isinstance(roster.get('entries'), dict) or len(roster['entries']) < 700:
        return None
    digest = roster.get('response_sha256')
    if not isinstance(digest, str):
        return None
    receipt = {'raw_response_sha256': digest, 'raw_response_path': str(
        current_runtime_paths().cache_dir / 'official-response-evidence' / (digest + '.gz'))}
    try:
        raw = read_response(receipt)
        if parse_roster(raw, '.TWO') != roster or not 0 <= time.time() - stamp < 86400 or time.time() >= until:
            return None
        return raw, {'source_url': MASTER, 'source_payload_sha256': digest,
                     'source_payload_bytes': len(raw), 'fetched_at_epoch': stamp,
                     'fresh_until_epoch': until, 'cache_hit': True, 'http_status_observed': False,
                     'evidence_kind': 'cached_complete_source_payload_verified_by_digest'}
    except (ValueError, TypeError, OSError, EOFError):
        return None


def _qualified_snapshot(snapshot):
    audit = snapshot.get('audit') or {}
    if (audit.get('provider') != snapshot_source.PROVIDER
            or audit.get('status') not in {'success', 'skipped_fresh_cache'}
            or audit.get('currency') != 'NTD' or audit.get('filed_unit') != 'thousands'):
        raise ValueError('auras_snapshot_unverified')
    url = snapshot_source.monthly_url(TICKER)
    raw = _receipt_bytes(audit.get('original_receipt'), url, snapshot_source.MAX_BYTES)
    today = snapshot_source._today()
    records, coverage = snapshot_source.select_monthly_records(
        snapshot_source.parse_monthly_snapshot(raw, url, today), TICKER, today)
    if (not records or records != snapshot.get('value')
            or coverage['issuer_name'] not in {'雙鴻', '雙鴻科技股份有限公司'}
            or any(audit.get(k) != coverage[k] for k in ('issuer_code', 'issuer_name', 'covered_months', 'filed_amounts'))):
        raise ValueError('auras_snapshot_issuer_or_amount_unverified')
    return coverage


def _monthly_values(raw, coverage):
    response = _json(raw)
    rows = response.get('infos') if isinstance(response, dict) else None
    if (not isinstance(response, dict) or response.get('status') is not True or not isinstance(rows, list) or not 1 <= len(rows) <= 40
            or type(response.get('totalCount')) is not int or response['totalCount'] != len(rows)):
        raise ValueError('auras_financial_list_incomplete')
    today = snapshot_source._today()
    amounts, years = {}, set()
    for row in rows:
        year = row.get('year') if isinstance(row, dict) else None
        if type(year) is not int or not 2000 <= year <= today.year or year in years:
            raise ValueError('auras_year_unverified')
        years.add(year)
        for month, name in enumerate(MONTHS, 1):
            key = name + 'Revenue'
            if key not in row:
                raise ValueError('auras_month_missing')
            value = row[key]
            if value is not None and (type(value) is not int or abs(value) >= 10**16):
                raise ValueError('auras_month_amount_unverified')
            if value is not None and date(year, month, 1) >= today.replace(day=1):
                raise ValueError('auras_future_month_amount')
            amounts[f'{year:04d}-{month:02d}'] = value
    latest = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    periods = []
    for offset in range(5, -1, -1):
        ordinal = latest.year * 12 + latest.month - 1 - offset
        periods.append(f'{ordinal // 12:04d}-{ordinal % 12 + 1:02d}')
    if any(amounts.get(p) is None for p in periods):
        raise ValueError('auras_six_month_window_incomplete')
    for period, value in zip(coverage['covered_months'], coverage['filed_amounts']):
        if Decimal(amounts[period]) != Decimal(value):
            raise ValueError('auras_snapshot_amount_or_unit_conflict')
    return periods, [amounts[p] * 1000 for p in periods]


def _url_contract(url):
    if url == MASTER:
        return 2_500_000, {'application/json', 'text/json'}
    if url == UNIT:
        return 100_000, {'application/javascript', 'text/javascript'}
    if url == API:
        return 150_000, {'application/json', 'text/json'}
    raise SourceResponseError('transport_url_invalid')


class AurasHttp(IssuerNewsHttp):
    route_contract = staticmethod(_url_contract)

    def __init__(self, deadline, coverage):
        super().__init__(deadline)
        self.coverage = coverage

    def _validate(self, raw, url):
        if url == MASTER:
            _master_anchor(raw)
        elif url == UNIT:
            if sha256(raw).hexdigest() != UNIT_SHA or '合併營收金額 (NT$仟元)' not in raw.decode('utf-8'):
                raise ValueError('auras_published_unit_contract_changed')
        else:
            _monthly_values(raw, self.coverage)

    def _download(self, url, diagnostic):
        try:
            value = super()._download(url, diagnostic)
        except SourceResponseError as exc:
            diagnostic.update(http_status=exc.status_code, error_kind=exc.error_kind)
            raise
        raw = base64.b64decode(value['body_b64'], validate=True)
        receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
        diagnostic.update(http_status=200, original_receipt=receipt)
        try:
            self._validate(raw, url)
        except Exception as exc:
            diagnostic['error_kind'] = str(exc) if isinstance(exc, ValueError) and str(exc).startswith('auras_') else type(exc).__name__
            raise
        if _receipt_bytes(receipt, url, _url_contract(url)[0]) != raw or time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout', status_code=200)
        return {**value, 'original_receipt': receipt}

    def get(self, url):
        limit, _ = _url_contract(url)
        diagnostic = {'url': url, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        value, meta = shared_fetch('auras-monthly-raw:v1:' + url,
                                  lambda: self._download(url, diagnostic),
                                  freshness_seconds=TTL, retention_seconds=TTL, error_retry_seconds=120,
                                  lock_wait_seconds=min(1., max(0., self.deadline - time.monotonic())))
        diagnostic['cache_hit'] = bool(meta.get('cache_hit'))
        if meta.get('error_kind') or meta.get('stale'):
            raise SourceResponseError(diagnostic.get('error_kind') or meta.get('error_kind') or 'stale_receipt')
        if not isinstance(value, dict) or value.get('url') != url:
            raise ValueError('auras_cache_receipt_invalid')
        encoded = value.get('body_b64')
        if not isinstance(encoded, str) or len(encoded) > (limit + 2) // 3 * 4:
            raise ValueError('auras_cache_receipt_invalid')
        raw = base64.b64decode(encoded, validate=True)
        receipt = value['original_receipt']
        stamp = meta.get('fetched_at_epoch')
        if (type(stamp) not in (int, float) or not math.isfinite(stamp)
                or not 0 <= time.time() - stamp < TTL or not 0 <= stamp - receipt['retrieved_at'] <= 10
                or sha256(raw).hexdigest() != value.get('sha256') or _receipt_bytes(receipt, url, limit) != raw):
            raise ValueError('auras_cache_receipt_invalid')
        self._validate(raw, url)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        diagnostic.update(original_receipt=receipt, fetched_at_epoch=receipt['retrieved_at'], http_status=200)
        return raw, receipt


def fetch_auras_monthly_history(ticker, snapshot, *, deadline):
    with source_operation('monthly_revenue', PROVIDER):
        return _fetch(ticker, snapshot, deadline)


def _fetch(ticker, snapshot, deadline):
    if (ticker != TICKER or not isinstance(snapshot, dict) or type(deadline) not in (int, float)
            or not math.isfinite(deadline) or time.monotonic() >= deadline):
        return None
    started = time.time()
    audit = build_source_audit_entry('monthly_revenue', PROVIDER, 'error', record_count=0,
                                     started_at_epoch=started, finished_at_epoch=started)
    audit.update(event_kind='aggregate', source_url=API, http_request_sent=False,
                 cache_hit=False, stale=False, window_complete=False, parser_version=POLICY)
    http = None
    try:
        coverage = _qualified_snapshot(snapshot)
        http = AurasHttp(deadline, coverage)
        cached_master = _cached_master()
        master_receipt = None
        if cached_master:
            master_raw, master_meta = cached_master
        else:
            master_raw, master_receipt = http.get(MASTER)
            master_meta = {'fetched_at_epoch': master_receipt['retrieved_at'],
                           'original_receipt': master_receipt}
        anchor = _master_anchor(master_raw)
        unit_raw, unit_receipt = http.get(UNIT)
        api_raw, api_receipt = http.get(API)
        periods, amounts = _monthly_values(api_raw, coverage)
        if _qualified_snapshot(snapshot) != coverage:
            raise ValueError('auras_snapshot_changed')
        if cached_master and _cached_master() != cached_master:
            raise ValueError('auras_master_changed_or_expired')
        for raw, receipt, url in [(unit_raw, unit_receipt, UNIT), (api_raw, api_receipt, API),
                                  *([(master_raw, master_receipt, MASTER)] if master_receipt else [])]:
            if _receipt_bytes(receipt, url, _url_contract(url)[0]) != raw:
                raise ValueError('auras_original_changed')
        now = time.time()
        originals = [unit_receipt, api_receipt, snapshot['audit']['original_receipt']]
        if (not all(_receipt_is_fresh(r, now) for r in originals)
                or master_receipt and not _receipt_is_fresh(master_receipt, now)
                or cached_master and not (0 <= now - master_meta['fetched_at_epoch'] < 86400
                                          and now < master_meta['fresh_until_epoch'])):
            raise ValueError('auras_constituent_original_expired')
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        stamp = min(r['retrieved_at'] for r in originals)
        cached = http.components[-1].get('cache_hit') is True
        records = [f'{p[:4]}年{int(p[5:])}月: NT${Decimal(a)/Decimal(100_000_000):.2f}億'
                   for p, a in zip(periods, amounts)]
        audit.update(status='skipped_fresh_cache' if cached else 'success', record_count=6,
                     cache_hit=cached, event_kind='cache_hit' if cached else 'aggregate',
                     fetched_at_epoch=stamp, fetched_at=iso_from_epoch(stamp), currency='NTD',
                     filed_unit='thousands', filed_amounts_NTD=[str(a) for a in amounts],
                     covered_months=periods, observed_month=periods[-1], issuer_code='3324',
                     issuer_name=anchor['legal_name'], consolidation_scope='consolidated',
                     coverage_status='complete_six_contiguous_month_amounts', window_complete=True,
                     historical_point_in_time_verified=False, original_receipt=api_receipt,
                     unit_contract_original_receipt=unit_receipt,
                     snapshot_original_receipt=deepcopy(snapshot['audit']['original_receipt']),
                     issuer_original_metadata=master_meta, issuer_anchor=anchor,
                     response_sha256=api_receipt['raw_response_sha256'], response_bytes=len(api_raw),
                     message='公司公開六個月合併營收，官方CSV核對最新兩月；非年度財報、TTM或PIT。')
        return {'value': records, 'audit': audit}
    except Exception as exc:
        audit.update(error_kind=getattr(exc, 'error_kind', str(exc) if isinstance(exc, ValueError) else type(exc).__name__),
                     message='公司營收歷史未取得完整可核對原件。')
        return {'value': [], 'audit': audit}
    finally:
        if http is not None:
            audit.update(http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count,
                         transport_components=http.components)
        audit['duration_ms'] = max(0, round((time.time() - started) * 1000))
