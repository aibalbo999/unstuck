"""Dated CAA airline membership supplies search leads, never financial metrics.

The current verified format is the H1 operating table. A new quarter or changed
table is rejected until qualified; no older document is substituted silently.
"""
from __future__ import annotations

import base64
from datetime import date
from hashlib import sha256
import io
import math
import re
import time
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import zipfile

from bs4 import BeautifulSoup

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError
from shared_provider_cache import shared_fetch
from .issuer_news_transport import IssuerNewsHttp

INDEX = 'https://www.caa.gov.tw/Article.aspx?a=518&lang=1'
SCOPE = 'dated_caa_airline_candidates'
RECEIPT_KEY = 'caa_membership_originals'
IDENTITIES = {'2610.TW': ('華航', '中華航空'), '2618.TW': ('長榮航', '長榮航空'),
              '2646.TW': ('星宇航空', '星宇航空'), '6757.TW': ('台灣虎航', '台灣虎航')}
TABLE_NS = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
NATIVE_FIELDS = {'status', 'source_url', 'retrieved_at', 'http_status', 'raw_response_sha256',
                 'raw_response_path', 'raw_response_bytes', 'evidence_kind',
                 'historical_point_in_time_verified', 'finality_guaranteed'}


def related_airline(ticker, peer):
    # China Airlines and Tigerair are a known parent/group pair. Exclude from
    # this independent-peer search, including the broad legacy candidate tail.
    return {ticker, peer} == {'2610.TW', '6757.TW'}


def _contract(url):
    if url == INDEX:
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if re.fullmatch(r'https://www\.caa\.gov\.tw/FileAtt\.ashx\?lang=1&id=[1-9]\d{0,7}', url):
        return 100_000, {'application/octet-stream', 'application/vnd.oasis.opendocument.spreadsheet'}
    raise SourceResponseError('transport_url_invalid')


def _latest(raw, today):
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= _contract(INDEX)[0]:
        raise ValueError('caa_index_size_invalid')
    page = BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')
    periods = []
    for row in page.find_all('tr'):
        first = row.find('td', recursive=False)
        if first is None:
            continue
        labels = set(re.findall(r'(?<!\d)(\d{3})年第([1-4])季', first.get_text()))
        if len(labels) > 1:
            raise ValueError('caa_period_label_ambiguous')
        if labels:
            roc, quarter = next(iter(labels))
            for link in row.select('a[title]'):
                declared = re.match(r'(\d{3})年第([1-4])季', link['title'])
                if declared and (declared[1], declared[2]) != (roc, quarter):
                    raise ValueError('caa_row_attachment_period_mismatch')
            periods.append(((int(roc) + 1911, int(quarter)), row))
    if not periods:
        raise ValueError('caa_index_missing')
    # Determine the newest declared quarter before inspecting its format.
    # A missing/renamed/XLSX-only attachment must never revive an older H1.
    period = max(p for p, _ in periods)
    selected = [link for p, row in periods if p == period
                for link in row.select('a.download-filebase[title][href]')
                if link['title'] == f'{period[0] - 1911}年第{period[1]}季.ods']
    if len(selected) != 1 or period[1] != 2:
        raise ValueError('caa_latest_period_unsupported_or_ambiguous')
    end = date(period[0], 6, 30)
    if not 0 <= (today - end).days <= 180:
        raise ValueError('caa_period_outside_candidate_window')
    link = selected[0]
    row = link.find_parent('tr')
    if row is None or f'{period[0] - 1911}年第2季' not in row.get_text():
        raise ValueError('caa_index_row_unverified')
    url = urljoin(INDEX, link['href'])
    _contract(url)
    if url == INDEX:
        raise ValueError('caa_attachment_invalid')
    return url, end


def _members(raw, period_end):
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= 100_000:
        raise ValueError('caa_ods_size_invalid')
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        entries = book.infolist()
        names = [i.filename for i in entries]
        if (len(entries) > 30 or len(names) != len(set(names))
                or sum(i.file_size for i in entries) > 1_000_000
                or any(i.flag_bits & 1 for i in entries)
                or names.count('content.xml') != 1 or names.count('mimetype') != 1
                or book.read('mimetype') != b'application/vnd.oasis.opendocument.spreadsheet'):
            raise ValueError('caa_ods_archive_invalid')
        content = book.read('content.xml')
    if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        raise ValueError('caa_xml_declaration_invalid')
    root = ET.fromstring(content)
    tables = root.findall('.//' + TABLE_NS + 'table')
    if len(tables) != 1:
        raise ValueError('caa_table_ambiguous')
    rows = tables[0].findall(TABLE_NS + 'table-row')
    if not 5 <= len(rows) <= 100:
        raise ValueError('caa_table_shape_invalid')
    strings, members, in_members, finished = [], [], False, False
    for row in rows:
        cells = list(row)
        if not cells:
            continue
        texts = [re.sub(r'\s+', '', ''.join(c.itertext())) for c in cells]
        if not any(texts):  # Large ODS blank repeated tails are never expanded.
            continue
        if row.get(TABLE_NS + 'number-rows-repeated', '1') != '1':
            raise ValueError('caa_repeated_nonempty_row')
        strings.append(texts[0])
        if texts[0] == '航空公司':
            if in_members or finished:
                raise ValueError('caa_header_ambiguous')
            in_members = True
            continue
        if in_members and texts[0].startswith('註1：'):
            in_members, finished = False, True
        if in_members:
            first = cells[0]
            if (first.tag != TABLE_NS + 'table-cell' or not texts[0]
                    or any(first.get(TABLE_NS + name, '1') != '1' for name in (
                        'number-columns-repeated', 'number-columns-spanned', 'number-rows-spanned'))
                    or not re.fullmatch(r'[\u4e00-\u9fff]{2,20}(?:航空|虎航)', texts[0])):
                raise ValueError('caa_operator_identity_invalid')
            members.append(texts[0])
    expected_title = f'國籍民用航空運輸業{period_end.year - 1911}年上半年營運概況'
    if (not strings or strings[0] != expected_title or not finished
            or not any('本表資料來源為各航空公司所提供之個體財務資料。' in s for s in strings)
            or not 1 <= len(members) <= 30 or len(members) != len(set(members))):
        raise ValueError('caa_membership_scope_unverified')
    return members


def _current_original(receipt, url):
    try:
        stamp = receipt['retrieved_at']
        return (set(receipt) == NATIVE_FIELDS and receipt['status'] == 'archived'
                and receipt['source_url'] == url and type(receipt['http_status']) is int
                and receipt['http_status'] == 200 and receipt['evidence_kind'] == 'raw_http_response_bytes'
                and receipt['historical_point_in_time_verified'] is False
                and receipt['finality_guaranteed'] is False
                and type(stamp) in (int, float) and math.isfinite(stamp)
                and 0 <= time.time() - stamp < 1800)
    except (TypeError, KeyError, ValueError, OverflowError):
        return False


class AirlineHttp(IssuerNewsHttp):
    route_contract = staticmethod(_contract)

    def _download(self, url, diagnostic):
        try:
            value = super()._download(url, diagnostic)
        except SourceResponseError as exc:
            diagnostic.update(http_status=exc.status_code, error_kind=exc.error_kind)
            raise
        raw = base64.b64decode(value['body_b64'], validate=True)
        receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
        diagnostic.update(http_status=200, original_receipt=receipt)
        if receipt.get('status') != 'archived' or read_response(receipt) != raw:
            raise SourceResponseError('caa_original_unverified', status_code=200)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout', status_code=200)
        return {**value, 'original_receipt': receipt}

    def get(self, url):
        limit, _ = _contract(url)
        diagnostic = {'url': url, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        value, meta = shared_fetch('caa-airline-raw:v1:' + url, lambda: self._download(url, diagnostic),
                                  freshness_seconds=1800, retention_seconds=1800,
                                  error_retry_seconds=120,
                                  lock_wait_seconds=min(1., max(0., self.deadline - time.monotonic())))
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')), fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind') or meta.get('stale'):
            raise SourceResponseError(diagnostic.get('error_kind') or meta.get('error_kind') or 'stale_receipt')
        try:
            stamp, receipt = meta['fetched_at_epoch'], value['original_receipt']
            encoded = value['body_b64']
            if (type(stamp) not in (int, float) or not math.isfinite(stamp)
                    or not _current_original(receipt, url) or not 0 <= stamp - receipt['retrieved_at'] <= 10
                    or value['url'] != url or not isinstance(encoded, str) or len(encoded) > (limit + 2) // 3 * 4):
                raise ValueError
            raw = base64.b64decode(encoded, validate=True)
            if (not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value['sha256']
                    or type(receipt['raw_response_bytes']) is not int or receipt['raw_response_bytes'] != len(raw)
                    or read_response(receipt) != raw):
                raise ValueError
        except (ValueError, TypeError, KeyError, OSError, EOFError, OverflowError):
            raise SourceResponseError('cache_receipt_invalid') from None
        diagnostic.update(http_status=200, original_receipt=receipt)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return raw, receipt


def _current_master(ticker, rows, today):
    all_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            day = date.fromisoformat(str(row.get('date') or ''))
        except ValueError:
            continue
        if day <= today:
            all_rows.append((day, row))
    latest = max((day for day, _ in all_rows), default=None)
    if latest is None or not 0 <= (today - latest).days <= 7:
        return None
    found = [r for day, r in all_rows if day == latest and str(r.get('stock_id')) == ticker[:4]]
    if not found or any(r.get('stock_name') != IDENTITIES[ticker][0]
                        or str(r.get('type') or '').lower() != 'twse' for r in found):
        return None
    return latest.isoformat()


def verified_airline_candidates(records, ticker, *, today):
    """Re-read full originals after metrics; a nearly expired source stays expired."""
    try:
        if ticker not in IDENTITIES or not records:
            return False
        originals = records[0][RECEIPT_KEY]
        if len(originals) != 2 or INDEX not in originals:
            return False
        for url, receipt in originals.items():
            if not _current_original(receipt, url):
                return False
        index = read_response(originals[INDEX])
        url, end = _latest(index, today)
        names = _members(read_response(originals[url]), end)
        if IDENTITIES[ticker][1] not in names:
            return False
        for record in records:
            peer = record['ticker']
            if (peer not in IDENTITIES or peer == ticker or related_airline(ticker, peer)
                    or IDENTITIES[peer][1] not in names or record[RECEIPT_KEY] != originals
                    or record.get('membership_period_end') != end.isoformat()
                    or record.get('comparison_scope') != SCOPE
                    or record.get('business_comparability_verified_current') is not False
                    or record.get('numeric_comparability_verified') is not False):
                return False
        return all(_current_original(receipt, url) for url, receipt in originals.items())
    except (ValueError, TypeError, KeyError, OSError, EOFError, OverflowError, zipfile.BadZipFile, ET.ParseError):
        return False


def get_official_airline_candidates(ticker, master_rows, *, today):
    if ticker not in IDENTITIES:
        return {'candidates': [], 'status': 'not_applicable'}
    days = {symbol: _current_master(symbol, master_rows, today) for symbol in IDENTITIES}
    if days[ticker] is None:
        return {'candidates': [], 'status': 'current_master_identity_unverified'}
    deadline = time.monotonic() + 12
    http = AirlineHttp(deadline)
    try:
        index, index_receipt = http.get(INDEX)
        url, period_end = _latest(index, today)
        raw, ods_receipt = http.get(url)
        members = _members(raw, period_end)
        if IDENTITIES[ticker][1] not in members:
            raise ValueError('caa_target_membership_unverified')
        originals = {INDEX: index_receipt, url: ods_receipt}
        candidates = []
        for peer, (short, caa_name) in IDENTITIES.items():
            if peer == ticker or related_airline(ticker, peer) or days[peer] is None or caa_name not in members:
                continue
            candidates.append({'ticker': peer, 'name': short, 'identity_status': 'current_master_and_dated_caa_membership',
                'master_observed_at': days[peer], 'issuer_master_observed_at': days[ticker],
                'comparison_status': 'industry_candidate_only', 'comparison_scope': SCOPE,
                'business_comparability_verified_current': False, 'numeric_comparability_verified': False,
                'membership_period_end': period_end.isoformat(), 'membership_current_effective_date_verified': False,
                'membership_source_url': url, 'membership_index_url': INDEX,
                'comparison_limitations': ['dated_operator_membership_only', 'whole_company_business_mix_not_verified',
                                          'financial_period_comparability_not_verified', 'size_comparability_not_verified'],
                RECEIPT_KEY: originals})
        if candidates and not verified_airline_candidates(candidates, ticker, today=today):
            raise ValueError('caa_originals_expired_or_unverified')
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        return {'candidates': candidates, 'status': 'success' if candidates else 'no_verified_members',
                'http_request_count': http.http_request_count, 'components': http.components,
                'cache_hit': all(c.get('cache_hit') is True for c in http.components)}
    except Exception as exc:
        return {'candidates': [], 'status': 'official_airline_originals_unavailable',
                'error_kind': getattr(exc, 'error_kind', type(exc).__name__),
                'http_request_count': http.http_request_count, 'components': http.components}
