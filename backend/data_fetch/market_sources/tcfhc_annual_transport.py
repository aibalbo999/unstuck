"""Exact published TCFHC annual originals, with existing native HTTP guards."""
from __future__ import annotations

import base64
import csv
import io
import math
import re
import time
from datetime import date, datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from search_provider_runtime import SourceResponseError
from .annual_issuer_master import request_master, JSON_URL
from .tcfhc_conference_transport import (
    ConferenceHttp, RAW_TTL, RECEIPT_FIELDS, original_bytes as _original_bytes, valid_epoch,
)

PROVIDER = 'TCFHC official audited annual financial statements'
MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
HOST = 'https://www.tcfhc.com.tw'
IR_URL = HOST + '/investors-relations/financial-info/financial-reports?sc_lang=en'
YEARS = (2021, 2022, 2023, 2024, 2025)
PDF_PATH = '/-/media/files/tcfhc/investors-relations/financial-info/financial-reports/'
PDF_LIMIT = 8 * 1024 * 1024
MASTER_FIELDS = (
    '出表日期', '公司代號', '公司名稱', '公司簡稱', '外國企業註冊地國', '產業別', '住址',
    '營利事業統一編號', '董事長', '總經理', '發言人', '發言人職稱', '代理發言人', '總機電話',
    '成立日期', '上市日期', '普通股每股面額', '實收資本額', '私募股數', '特別股', '編制財務報表類型',
    '股票過戶機構', '過戶電話', '過戶地址', '簽證會計師事務所', '簽證會計師1', '簽證會計師2',
    '英文簡稱', '英文通訊地址', '傳真機號碼', '電子郵件信箱', '網址', '已發行普通股數或TDR原股發行股數',
)
_PDF = re.compile(re.escape(HOST + PDF_PATH)
                  + r'(202[1-5])-consolidated-financial-statements\.pdf\?sc_lang=en&hash=[A-F0-9]{32}')


def _bad(message):
    raise ValueError('TCFHC annual ' + message)


def contract(url):
    if url == MASTER_URL:
        return 2_500_000, {'text/csv', 'application/csv', 'application/octet-stream'}
    if url == IR_URL:
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if isinstance(url, str) and _PDF.fullmatch(url):
        return PDF_LIMIT, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def parse_master(raw, today=None, source_url=MASTER_URL):
    """Validate the complete CSV shape and one exact, recently dated issuer."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= contract(MASTER_URL)[0]:
        _bad('master size invalid')
    try:
        if source_url == MASTER_URL:
            rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True))
            if (not rows or tuple(rows[0]) != MASTER_FIELDS or not 500 <= len(rows) - 1 <= 2000
                    or any(len(row) != len(MASTER_FIELDS) for row in rows[1:])):
                _bad('master complete shape invalid')
            records = [dict(zip(MASTER_FIELDS, row)) for row in rows[1:]]
        elif source_url == JSON_URL:
            from .official_issuer_master_json import parse_rows
            if today is not None and type(today) is not date:
                _bad('master replay date invalid')
            stamp = time.time() if today is None else datetime.combine(today, datetime.min.time(), ZoneInfo('Asia/Taipei')).timestamp()
            records = parse_rows(raw, stamp)
        else:
            _bad('master source invalid')
        codes = [r['公司代號'] for r in records]
        stamps = {r['出表日期'] for r in records}
        if (len(codes) != len(set(codes)) or any(not re.fullmatch(r'\d{4,6}', c) for c in codes)
                or len(stamps) != 1):
            _bad('master row identity or date ambiguous')
        stamp = stamps.pop()
        if not re.fullmatch(r'\d{7}', stamp):
            _bad('master date invalid')
        as_of = date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:]))
        today = datetime.fromtimestamp(time.time(), ZoneInfo('Asia/Taipei')).date() if today is None else today
        if type(today) is not date or not 0 <= (today - as_of).days <= 7:
            _bad('master date stale or future')
        selected = [r for r in records if r['公司代號'] == '5880']
        expected = {'公司名稱': '合作金庫金融控股股份有限公司', '公司簡稱': '合庫金',
                    '營利事業統一編號': '53021433', '英文簡稱': 'TCFHC', '網址': 'www.tcfhc.com.tw'}
        if len(selected) != 1 or any(selected[0][k] != v for k, v in expected.items()):
            _bad('master issuer identity mismatch')
        return {'ticker': '5880.TW', 'legal_name': expected['公司名稱'], 'official_name': '合庫金',
                'official_ubn': '53021433', 'english_abbreviation': 'TCFHC',
                'registered_website': expected['網址'], 'master_as_of': as_of.isoformat(),
                'master_response_sha256': sha256(raw).hexdigest()}
    except (csv.Error, UnicodeError, TypeError, IndexError) as exc:
        raise ValueError('TCFHC annual master invalid') from exc


def _text(tag):
    return ' '.join(tag.get_text(' ', strip=True).replace('\u200b', '').split())


def parse_index(raw):
    """Bind each annual book to its published year block and unique original href."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= contract(IR_URL)[0]:
        _bad('index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if (not soup.html or soup.html.get('lang') != 'en-US' or not soup.title
            or _text(soup.title) != 'Financial Statements'
            or 'TCFHC. All Rights Reserved.' not in soup.get_text(' ', strip=True)
            or not raw.rstrip().lower().endswith(b'</html>')):
        _bad('index publisher, language or completeness invalid')
    result = {}
    for year in YEARS:
        blocks = [b for b in soup.select('div.l-textBlock')
                  if any(_text(t) == f'{year} Financial Statements' for t in b.select('div.o-textTitle'))]
        if len(blocks) != 1:
            _bad('annual publication block absent or duplicated')
        title = f'{year} Consolidated Financial Statements'
        rows = [r for r in blocks[0].select('li.c-list__item')
                if any(_text(t) == title for t in r.select('div.c-list__title'))]
        if len(rows) != 1 or len(rows[0].select('div.c-list__title')) != 1:
            _bad('annual consolidated heading absent or duplicated')
        anchors = rows[0].select('a[href]')
        if len(anchors) != 1:
            _bad('annual attachment absent or duplicated')
        href = anchors[0].get('href')
        url = HOST + href if isinstance(href, str) and href.startswith(PDF_PATH) else href
        match = _PDF.fullmatch(url) if isinstance(url, str) else None
        attachment_title = ' '.join(str(anchors[0].get('title') or '').split())
        if (not match or int(match[1]) != year
                or attachment_title not in {f'Pdf {title} file open in a new tab',
                                            f'pdf file {title} open in a new tab.'}
                or len(soup.find_all('a', href=href)) != 1):
            _bad('annual PDF URL or heading mismatch')
        annual_links = []
        for anchor in soup.select('a[href]'):
            candidate = anchor['href']
            candidate = HOST + candidate if candidate.startswith(PDF_PATH) else candidate
            matched = _PDF.fullmatch(candidate)
            if matched and int(matched[1]) == year:
                annual_links.append(candidate)
        if annual_links != [url]:
            _bad('annual PDF publication ambiguous')
        result[year] = url
    return result


def original_bytes(receipt, url, *, max_age=86400):
    """Receipt replay keeps the original epoch; callers choose live/snapshot age."""
    raw = _original_bytes(receipt, url, max_age=max_age, url_contract=contract)
    if not valid_epoch(receipt.get('retrieved_at'), max_age):
        raise ValueError('TCFHC annual original expired during readback')
    return raw


class AnnualHttp(ConferenceHttp):
    # Share existing per-URL TCFHC raw error/admission state, including MASTER.
    # Successful warm bytes preserve their original 1800-second lifetime.
    route_contract = staticmethod(contract)

    def __init__(self, deadline=None, *, force_refresh=False, use_cache=True):
        now = time.monotonic()
        if deadline is None:
            deadline = now + 45.
        try:
            valid = type(deadline) in (int, float) and math.isfinite(deadline)
        except OverflowError:
            valid = False
        if not valid:
            raise SourceResponseError('timeout')
        super().__init__(min(deadline, now + 45.), force_refresh=force_refresh, use_cache=use_cache)
        self._published = {}
        self._index_receipt = None

    def _check(self):
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')

    def _validate_body(self, raw, url):
        if not isinstance(raw, bytes) or not 0 < len(raw) <= contract(url)[0]:
            _bad('original body size invalid')
        if url == MASTER_URL:
            parse_master(raw)
        elif url == IR_URL:
            parse_index(raw)
        elif (not re.match(rb'%PDF-1\.[0-9]', raw)
              or not re.search(rb'startxref\s+[0-9]+\s+%%EOF\s*\Z', raw[-1024:])):
            _bad('PDF body is incomplete or not native PDF')
        self._check()

    def download_original(self, url, diagnostic):
        value = super().download_original(url, diagnostic)
        diagnostic.update(http_status=200, http_status_observed=True, request_method='GET')
        try:
            self._validate_body(base64.b64decode(value['body_b64'], validate=True), url)
        except (ValueError, UnicodeError, KeyError) as exc:
            raise SourceResponseError('response_invalid', status_code=200) from exc
        return value

    def read_original(self, receipt, url, *, max_age):
        return original_bytes(receipt, url, max_age=max_age)

    def request(self, url):
        contract(url)
        self._check()
        if url == MASTER_URL:
            raw, receipt = request_master(self, legacy_holding=True)
            parse_master(raw, source_url=receipt['source_url'])
            self._check()
            return raw, receipt
        if url not in {MASTER_URL, IR_URL} and (
                url not in self._published.values() or self._index_receipt is None
                or not valid_epoch(self._index_receipt.get('retrieved_at'), RAW_TTL)):
            raise SourceResponseError('annual_publication_unverified')
        before = len(self.components)
        try:
            raw, receipt = super().get_receipt(url)
            self._validate_body(raw, url)
            self._check()
            if url == IR_URL:
                self._published = parse_index(raw)
                self._index_receipt = receipt
            self._check()
            if not valid_epoch(receipt.get('retrieved_at'), RAW_TTL):
                raise SourceResponseError('original_expired')
            self.components[-1].update(status='complete', response_complete=True, request_method='GET',
                                        response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw))
            return raw, receipt
        except Exception as exc:
            if len(self.components) > before:
                self.components[-1].update(status='unavailable', response_complete=False, request_method='GET',
                                            error_kind=getattr(exc, 'error_kind', type(exc).__name__))
                if getattr(exc, 'status_code', None) is not None:
                    self.components[-1]['http_status'] = exc.status_code
            raise

    get_receipt = request
