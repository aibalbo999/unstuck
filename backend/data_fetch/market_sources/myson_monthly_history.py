"""Issuer-published public Sheets monthly history, bound to official originals."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlsplit, urldefrag
from bs4 import BeautifulSoup
import re
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

PROVIDER = 'Myson official monthly revenue history'
POLICY = 'myson-monthly-history-v1'
TICKER = '5314.TWO'
MASTER = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
INDEX = 'https://www.myson.com.tw/financial'
TTL = 1800
SHEET_URL = re.compile(r'https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]{20,128}/edit\?(?:gid=0|usp=sharing)')


def _json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('myson_duplicate_json_key')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('myson_nonfinite_json')))


def _master_anchor(raw):
    roster = parse_roster(raw, '.TWO')
    if len(roster['entries']) < 700:
        raise ValueError('myson_master_identity_unverified')
    today = snapshot_source._today()
    anchor = select_legal_name(roster, TICKER, '世紀*', today=today)
    if (not anchor or anchor['legal_name'] != '世紀民生科技股份有限公司'
            or anchor['official_ubn'] != '22099815'
            or not 0 <= (today - date.fromisoformat(anchor['as_of'])).days <= 7):
        raise ValueError('myson_master_identity_unverified')
    rows = [r for r in _json(raw) if r.get('SecuritiesCompanyCode') == '5314']
    if len(rows) != 1:
        raise ValueError('myson_master_identity_unverified')
    registered = rows[0].get('WebAddress', '')
    url = urlsplit('https://' + registered if registered == 'www.myson.com.tw' else registered)
    if (url.scheme not in {'http', 'https'} or url.netloc != 'www.myson.com.tw'
            or url.path not in {'', '/'} or url.query or url.fragment):
        raise ValueError('myson_registered_domain_unverified')
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
        raise ValueError('myson_snapshot_unverified')
    url = snapshot_source.monthly_url(TICKER)
    raw = _receipt_bytes(audit.get('original_receipt'), url, snapshot_source.MAX_BYTES)
    today = snapshot_source._today()
    rows = snapshot_source.parse_monthly_snapshot(raw, url, today)
    records, coverage = snapshot_source.select_monthly_records(rows, TICKER, today)
    if (not records or records != snapshot.get('value')
            or coverage['issuer_name'] not in {'世紀*', '世紀民生科技股份有限公司'}
            or any(audit.get(k) != coverage[k] for k in ('issuer_code', 'issuer_name', 'covered_months', 'filed_amounts'))):
        raise ValueError('myson_snapshot_issuer_or_amount_unverified')
    row = next(row for row in rows if row['公司代號'] == '5314')
    coverage['official_year_to_date_thousands'] = str(
        snapshot_source._amount(row['累計營業收入-當月累計營收']))
    return coverage


def _periods():
    today = snapshot_source._today()
    latest = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    return [f'{ordinal // 12:04d}-{ordinal % 12 + 1:02d}'
            for ordinal in range(latest.year * 12 + latest.month - 6, latest.year * 12 + latest.month)]


def _index_links(raw):
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    if not soup.title or soup.title.get_text(strip=True) != '世紀民生科技股份有限公司':
        raise ValueError('myson_index_issuer_unverified')
    headings = [h for h in soup.find_all('h3') if h.get_text(strip=True) == '每月營業額報告']
    if len(headings) != 1:
        raise ValueError('myson_monthly_section_unverified')
    section = headings[0].parent.parent
    links = {}
    for a in section.find_all('a', href=True):
        match = re.fullmatch(r'(\d{3})年度', a.get_text(strip=True))
        if not match:
            raise ValueError('myson_index_year_unverified')
        year = int(match[1]) + 1911
        url, fragment = urldefrag(a['href'])
        if (not SHEET_URL.fullmatch(url) or fragment not in {'', 'gid=0'}
                or not 2000 <= year <= snapshot_source._today().year or year in links
                or url in links.values()):
            raise ValueError('myson_published_sheet_link_unverified')
        links[year] = url
    if not 1 <= len(links) <= 40:
        raise ValueError('myson_index_year_unverified')
    return links


def _sheet_values(raw, year):
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    tables = [[[c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
               for tr in table.find_all('tr')] for table in soup.find_all('table')]
    tables = [rows for rows in tables if any(len(r) > 1 and r[1] == '單位：新台幣仟元' for r in rows)]
    if len(tables) != 1:
        raise ValueError('myson_sheet_unit_or_table_unverified')
    rows = tables[0]
    if (not any(len(r) > 1 and re.sub(r'\s+', '', r[1]) == '本資料由(上櫃公司)世紀民生公司提供' for r in rows)
            or not any(len(r) > 1 and '配合IFRSs實施，營業收入係以合併營業收入申報' in r[1] for r in rows)):
        raise ValueError('myson_sheet_issuer_or_scope_unverified')
    labels = {'單位：新台幣仟元', '本月', '本年累計', '項目'}
    cells = {}
    for row in rows:
        if len(row) > 1 and row[1] in labels:
            if row[1] in cells or len(row) < 14 or any(row[14:]):
                raise ValueError('myson_sheet_layout_unverified')
            cells[row[1]] = row[2:14]
    if (set(cells) != labels or cells['單位：新台幣仟元'] != [f'{year-1911}年{m:02d}月' for m in range(1, 13)]
            or cells['項目'] != ['營業收入淨額'] * 12):
        raise ValueError('myson_sheet_period_or_metric_unverified')

    def amount(value):
        if value == '':
            return None
        if not re.fullmatch(r'-?(?:\d+|[1-9]\d{0,2}(?:,\d{3})+)', value):
            raise ValueError('myson_month_amount_unverified')
        number = int(value.replace(',', ''))
        if abs(number) >= 10**16:
            raise ValueError('myson_month_amount_unverified')
        return number

    values = [amount(v) for v in cells['本月']]
    cumulative = [amount(v) for v in cells['本年累計']]
    today = snapshot_source._today()
    count = today.month - 1 if year == today.year else 12
    if (year > today.year or any(v is None for v in values[:count])
            or any(v is not None for v in values[count:])
            or any(v is not None for v in cumulative[count:])):
        raise ValueError('myson_month_missing_or_future')
    for month in range(1, count + 1):
        if cumulative[month - 1] != sum(values[:month]):
            raise ValueError('myson_cumulative_conflict')
    return {f'{year:04d}-{month:02d}': value for month, value in enumerate(values[:count], 1)}


def _selected_amounts(values, coverage):
    periods = _periods()
    if any(p not in values for p in periods):
        raise ValueError('myson_six_month_window_incomplete')
    for period, value in zip(coverage['covered_months'], coverage['filed_amounts']):
        if period not in values or Decimal(values[period]) != Decimal(value):
            raise ValueError('myson_snapshot_amount_or_unit_conflict')
    latest = coverage['observed_month']
    ytd = [f'{latest[:4]}-{month:02d}' for month in range(1, int(latest[5:]) + 1)]
    if (any(period not in values for period in ytd)
            or Decimal(sum(values[period] for period in ytd)) != Decimal(coverage['official_year_to_date_thousands'])):
        raise ValueError('myson_official_year_to_date_conflict')
    return periods, [values[p] * 1000 for p in periods]


def _url_contract(url):
    if url == MASTER:
        return 2_500_000, {'application/json', 'text/json'}
    if url == INDEX:
        return 150_000, {'text/html', 'application/xhtml+xml'}
    if SHEET_URL.fullmatch(url):
        return 500_000, {'text/html', 'application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')


class MysonHttp(IssuerNewsHttp):
    route_contract = staticmethod(_url_contract)

    def __init__(self, deadline, coverage):
        super().__init__(deadline)
        self.coverage = coverage
        self.sheet_years = {}

    def _validate(self, raw, url):
        if url == MASTER:
            _master_anchor(raw)
        elif url == INDEX:
            _index_links(raw)
        elif url in self.sheet_years:
            _sheet_values(raw, self.sheet_years[url])
        else:
            raise ValueError('myson_unpublished_sheet_url')

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
            diagnostic['error_kind'] = str(exc) if isinstance(exc, ValueError) and str(exc).startswith('myson_') else type(exc).__name__
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
        value, meta = shared_fetch('myson-monthly-raw:v1:' + url,
                                  lambda: self._download(url, diagnostic),
                                  freshness_seconds=TTL, retention_seconds=TTL, error_retry_seconds=120,
                                  lock_wait_seconds=min(1., max(0., self.deadline - time.monotonic())))
        diagnostic['cache_hit'] = bool(meta.get('cache_hit'))
        if meta.get('error_kind') or meta.get('stale'):
            raise SourceResponseError(diagnostic.get('error_kind') or meta.get('error_kind') or 'stale_receipt')
        if not isinstance(value, dict) or value.get('url') != url:
            raise ValueError('myson_cache_receipt_invalid')
        encoded = value.get('body_b64')
        if not isinstance(encoded, str) or len(encoded) > (limit + 2) // 3 * 4:
            raise ValueError('myson_cache_receipt_invalid')
        raw = base64.b64decode(encoded, validate=True)
        receipt = value['original_receipt']
        stamp = meta.get('fetched_at_epoch')
        if (type(stamp) not in (int, float) or not math.isfinite(stamp)
                or not 0 <= time.time() - stamp < TTL or not 0 <= stamp - receipt['retrieved_at'] <= 10
                or sha256(raw).hexdigest() != value.get('sha256') or _receipt_bytes(receipt, url, limit) != raw):
            raise ValueError('myson_cache_receipt_invalid')
        self._validate(raw, url)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        diagnostic.update(original_receipt=receipt, fetched_at_epoch=receipt['retrieved_at'], http_status=200)
        return raw, receipt


def fetch_myson_monthly_history(ticker, snapshot, *, deadline):
    with source_operation('monthly_revenue', PROVIDER):
        return _fetch(ticker, snapshot, deadline)


def _fetch(ticker, snapshot, deadline):
    if (ticker != TICKER or not isinstance(snapshot, dict) or type(deadline) not in (int, float)
            or not math.isfinite(deadline) or time.monotonic() >= deadline):
        return None
    started = time.time()
    audit = build_source_audit_entry('monthly_revenue', PROVIDER, 'error', record_count=0,
                                     started_at_epoch=started, finished_at_epoch=started)
    audit.update(event_kind='aggregate', source_url=INDEX, http_request_sent=False,
                 cache_hit=False, stale=False, window_complete=False, parser_version=POLICY)
    http = None
    try:
        coverage = _qualified_snapshot(snapshot)
        http = MysonHttp(deadline, coverage)
        cached_master = _cached_master()
        master_receipt = None
        if cached_master:
            master_raw, master_meta = cached_master
        else:
            master_raw, master_receipt = http.get(MASTER)
            master_meta = {'fetched_at_epoch': master_receipt['retrieved_at'],
                           'original_receipt': master_receipt}
        anchor = _master_anchor(master_raw)
        index_raw, index_receipt = http.get(INDEX)
        links = _index_links(index_raw)
        years = sorted({int(p[:4]) for p in _periods()})
        if not all(year in links for year in years):
            raise ValueError('myson_required_year_not_published')
        sheets, values = [], {}
        for year in years:
            url = links[year]
            http.sheet_years[url] = year
            raw, receipt = http.get(url)
            values.update(_sheet_values(raw, year))
            sheets.append((raw, receipt, url))
        periods, amounts = _selected_amounts(values, coverage)
        if _qualified_snapshot(snapshot) != coverage:
            raise ValueError('myson_snapshot_changed')
        if cached_master and _cached_master() != cached_master:
            raise ValueError('myson_master_changed_or_expired')
        for raw, receipt, url in [(index_raw, index_receipt, INDEX), *sheets,
                                  *([(master_raw, master_receipt, MASTER)] if master_receipt else [])]:
            if _receipt_bytes(receipt, url, _url_contract(url)[0]) != raw:
                raise ValueError('myson_original_changed')
        now = time.time()
        originals = [index_receipt, snapshot['audit']['original_receipt'], *[r for _, r, _ in sheets]]
        if (not all(_receipt_is_fresh(r, now) for r in originals)
                or master_receipt and not _receipt_is_fresh(master_receipt, now)
                or cached_master and not (0 <= now - master_meta['fetched_at_epoch'] < 86400
                                          and now < master_meta['fresh_until_epoch'])):
            raise ValueError('myson_constituent_original_expired')
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        stamp = min(r['retrieved_at'] for r in originals)
        cached = all(c.get('cache_hit') is True for c in http.components if c['url'] in http.sheet_years)
        records = [f'{p[:4]}年{int(p[5:])}月: NT${Decimal(a)/Decimal(100_000_000):.2f}億'
                   for p, a in zip(periods, amounts)]
        audit.update(status='skipped_fresh_cache' if cached else 'success', record_count=6,
                     cache_hit=cached, event_kind='cache_hit' if cached else 'aggregate',
                     fetched_at_epoch=stamp, fetched_at=iso_from_epoch(stamp), currency='NTD',
                     filed_unit='thousands', filed_amounts_NTD=[str(a) for a in amounts],
                     official_year_to_date_thousands=coverage['official_year_to_date_thousands'],
                     covered_months=periods, observed_month=periods[-1], issuer_code='5314',
                     issuer_name=anchor['legal_name'], consolidation_scope='consolidated',
                     coverage_status='complete_six_contiguous_month_amounts', window_complete=True,
                     historical_point_in_time_verified=False, original_receipt=sheets[-1][1],
                     sheet_original_receipts=[r for _, r, _ in sheets],
                     published_index_original_receipt=index_receipt,
                     snapshot_original_receipt=deepcopy(snapshot['audit']['original_receipt']),
                     issuer_original_metadata=master_meta, issuer_anchor=anchor,
                     source_urls=[url for _, _, url in sheets],
                     response_sha256=sheets[-1][1]['raw_response_sha256'],
                     response_bytes=sum(len(raw) for raw, _, _ in sheets),
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
