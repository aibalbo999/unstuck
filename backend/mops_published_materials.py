"""Pure selection of a MOPS-published attachment, never a guessed filename.

This descriptor proves a request is published in the supplied page. It does not
prove the response, document permissions, financial period or semantic coverage.
``row_sha256`` fingerprints BeautifulSoup's serialized selected ``tr``; the
independent ``index_sha256`` always fingerprints the exact original bytes.
"""
from datetime import date, datetime
from hashlib import sha256
from html.parser import HTMLParser
import math
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

INDEX_PATH = '/mops/web/ajax_t100sb02_1'
DOWNLOAD_PATH = '/server-java/FileDownLoad'
DOWNLOAD_URL = 'https://mopsov.twse.com.tw' + DOWNLOAD_PATH
FILE_PATH = '/home/html/nas/STR/'
MAX_INDEX_BYTES = 2_500_000
_TAIPEI = ZoneInfo('Asia/Taipei')
_HEADERS = ('公司代號', '公司名稱', '召開法人說明會日期', '召開法人說明會時間',
            '召開法人說明會地點', '法人說明會擇要訊息', '法人說明會簡報內容',
            '公司網站是否提供法人說明會相關資訊', '影音連結資訊', '其他應敘明事項', '歷年法人說明會')
_EMPTY = {'', '-', '--', '無', '未輸', '內容檔案於當日會後公告於公開資訊觀測站'}


class _AttributeCheck(HTMLParser):
    """Reject ambiguity or truncation before the forgiving DOM parser runs."""
    structural_tags = {'html', 'head', 'body', 'form', 'table', 'thead', 'tr', 'td', 'th'}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.roots = {'html': 0, 'head': 0, 'body': 0}

    def handle_starttag(self, tag, attrs):
        if tag in self.structural_tags:
            self.stack.append(tag)
        if tag in self.roots:
            self.roots[tag] += 1
        protected = {'form': {'id', 'name', 'action', 'method'},
                     'input': {'id', 'name', 'type', 'value'},
                     'a': {'href', 'onclick'}, 'table': {'id'},
                     'td': {'rowspan', 'colspan'}, 'th': {'rowspan', 'colspan'}}.get(tag, set())
        names = [name for name, _ in attrs if name in protected]
        if len(set(names)) != len(names):
            raise ValueError('MOPS duplicate protected attribute')

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag in self.structural_tags:
            if not self.stack or self.stack.pop() != tag:
                raise ValueError('MOPS structural tags unbalanced')

    def verify_complete(self):
        self.close()
        if self.stack or any(value != 1 for value in self.roots.values()):
            raise ValueError('MOPS original page incomplete')


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _one(items, message):
    if len(items) != 1:
        raise ValueError(message)
    return items[0]


def _day(text):
    match = re.fullmatch(r'([0-9]{3}|[0-9]{4})/([0-9]{1,2})/([0-9]{1,2})', text)
    if match is None:
        raise ValueError('MOPS event date shape invalid')
    year, month, day = map(int, match.groups())
    if len(match[1]) == 3:
        year += 1911
    return date(year, month, day)


def _dates(text):
    parts = text.split(' 至 ')
    if len(parts) not in (1, 2):
        raise ValueError('MOPS event range invalid')
    start, end = _day(parts[0]), _day(parts[-1])
    if end < start:
        raise ValueError('MOPS event range reversed')
    return start, end


def _clock(text):
    if not text:
        return None
    match = re.fullmatch(r'([01][0-9]|2[0-3]):([0-5][0-9])', text)
    if match is None:
        raise ValueError('MOPS event time invalid')
    return tuple(map(int, match.groups()))


def _attachment(cell, symbol, marker):
    anchors = cell.find_all('a')
    if not anchors:
        if _text(cell) not in _EMPTY:
            raise ValueError('MOPS unpublished attachment cell unrecognized')
        return None
    anchor = _one(anchors, 'MOPS attachment ambiguous')
    filename = _text(anchor)
    match = re.fullmatch(re.escape(symbol) + r'([0-9]{8})' + marker + r'[0-9]{3}\.(pdf|pptx)', filename)
    if match is None or _text(cell) != filename or anchor.get('href') != '#':
        raise ValueError('MOPS attachment filename or cell invalid')
    expected = f'document.fm_fileDownload.fileName.value="{filename}";document.fm_fileDownload.submit();'
    if anchor.get('onclick') != expected:
        raise ValueError('MOPS attachment action differs from label')
    digits = match[1]
    file_date = date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    return (filename, match[2], 'en' if marker == 'E' else 'zh-TW', file_date.isoformat())


def _page(raw, typek):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_INDEX_BYTES:
        raise ValueError('MOPS original size or type invalid')
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise ValueError('MOPS original encoding invalid') from exc
    if re.search(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|因為安全性考量|驗證碼|captcha|access denied', text, re.I):
        raise ValueError('MOPS access denied page')
    if '<![' in text:
        raise ValueError('MOPS unsupported marked declaration')
    structure = _AttributeCheck()
    try:
        structure.feed(text)
        structure.verify_complete()
    except AssertionError as exc:
        # HTMLParser uses AssertionError for unsupported marked declarations.
        # Untrusted malformed HTML remains the public shape-error contract.
        raise ValueError('MOPS original markup invalid') from exc
    soup = BeautifulSoup(text, 'html.parser')
    form = _one(soup.select('form#fm_fileDownload, form[name="fm_fileDownload"]'), 'MOPS download form not unique')
    if (form.get('id') != 'fm_fileDownload' or form.get('name') != 'fm_fileDownload'
            or form.get('action') != DOWNLOAD_PATH or form.get('method') != 'post'
            or len(soup.find_all(id='fm_fileDownload')) != 1):
        raise ValueError('MOPS download form invalid')
    inputs = form.find_all('input')
    expected = {'step': '9', 'filePath': FILE_PATH, 'fileName': '', 'functionName': 't100sb02_1'}
    if (len(inputs) != 4 or any(i.get('type') != 'hidden' for i in inputs)
            or {i.get('name'): i.get('value') for i in inputs} != expected
            or len({i.get('name') for i in inputs}) != 4
            or form.find(['select', 'textarea', 'button', 'form'])):
        raise ValueError('MOPS download fields invalid')
    query = _one(soup.select('form[name="form_t100sb02_1"]'), 'MOPS query form not unique')
    market = _one(soup.select('input[name="TYPEK"]'), 'MOPS market field not unique')
    if (query.get('action') != INDEX_PATH or query.get('method') != 'post'
            or market.find_parent('form') is not query or market.get('type') != 'hidden'
            or market.get('value') != typek):
        raise ValueError('MOPS market identity differs')
    table = _one(soup.find_all(id='myTable'), 'MOPS table not unique')
    if table.name != 'table' or table.find_parent('form') is not query:
        raise ValueError('MOPS table outside query form')
    head = _one(table.find_all('thead', recursive=False), 'MOPS table header invalid')
    header_rows = head.find_all('tr', recursive=False)
    if len(header_rows) != 2 or len(head.find_all(recursive=False)) != 2:
        raise ValueError('MOPS table header rows invalid')
    columns = header_rows[0].find_all('th', recursive=False)
    second = header_rows[1].find_all('th', recursive=False)
    if (tuple(_text(c) for c in columns) != _HEADERS
            or tuple(_text(c) for c in second) != ('中文檔案', '英文檔案')
            or len(header_rows[0].find_all(recursive=False)) != len(columns)
            or len(header_rows[1].find_all(recursive=False)) != len(second)
            or any(c.get('rowspan') != '2' or c.has_attr('colspan') for i, c in enumerate(columns) if i != 6)
            or columns[6].get('colspan') != '2' or columns[6].has_attr('rowspan')
            or any(c.has_attr('rowspan') or c.has_attr('colspan') for c in second)):
        raise ValueError('MOPS table columns invalid')
    rows = [r for r in table.find_all('tr') if r.find_parent('thead') is None]
    if len(rows) > 1000 or any(r.find_parent('table') is not table for r in rows):
        raise ValueError('MOPS table body shape invalid')
    return rows


def select_published_material(raw: bytes, ticker: str, *, as_of_epoch: float,
                              company_name: str | None = None) -> dict | None:
    """Select the latest past-start event's published English (else Chinese).

    The caller supplies an independently verified official *short* company name.
    No I/O, JavaScript evaluation, archive writes or acquisition observations occur.
    Unknown shape/identity/ambiguity raises ValueError; recognized absence is None.
    A multi-day event is eligible only on a day after its listed final day.
    """
    match = re.fullmatch(r'([0-9]{4,6})\.(TW|TWO)', ticker) if isinstance(ticker, str) else None
    if match is None:
        raise ValueError('MOPS explicit ticker and market required')
    symbol, market = match.groups()
    if company_name is not None and (not isinstance(company_name, str) or not company_name.strip()):
        raise ValueError('MOPS company name invalid')
    try:
        if type(as_of_epoch) not in (int, float) or not math.isfinite(as_of_epoch) or as_of_epoch <= 0:
            raise ValueError('MOPS observation time invalid')
        now = datetime.fromtimestamp(as_of_epoch, _TAIPEI)
    except (ValueError, OverflowError, OSError) as exc:
        raise ValueError('MOPS observation time invalid') from exc
    name = ' '.join(company_name.split()) if company_name is not None else None
    candidates = []
    seen = {}
    for row in _page(raw, 'sii' if market == 'TW' else 'otc'):
        cells = row.find_all('td', recursive=False)
        if (row.get('data-type') != 'body' or len(cells) != 12 or len(row.find_all(recursive=False)) != 12
                or any(c.has_attr('rowspan') or c.has_attr('colspan') for c in cells)
                or row.find(['script', 'iframe', 'object', 'form'])):
            raise ValueError('MOPS event row shape invalid')
        issuer, observed_name = _text(cells[0]), _text(cells[1])
        if issuer != symbol or not observed_name or name is not None and observed_name != name:
            raise ValueError('MOPS event issuer differs')
        name = observed_name
        start, end = _dates(_text(cells[2]))
        event_time = _text(cells[3]); clock = _clock(event_time)
        chinese, english = _attachment(cells[6], symbol, 'M'), _attachment(cells[7], symbol, 'E')
        location, summary = _text(cells[4]), _text(cells[5])
        event_key = (start, end, event_time)
        semantic = (location, summary, chinese, english)
        if event_key in seen:
            if seen[event_key] != semantic:
                raise ValueError('MOPS repeated event conflicting')
            continue
        seen[event_key] = semantic
        if start == end == now.date() and clock is None:
            raise ValueError('MOPS same-day event time unknown')
        eligible = (end < now.date() or start == end == now.date()
                    and clock is not None and clock <= (now.hour, now.minute))
        if not eligible:
            continue
        candidates.append({'start': start, 'end': end, 'clock': clock, 'time': event_time,
                           'location': location, 'summary': summary, 'material': english or chinese,
                           'row_sha256': sha256(str(row).encode('utf-8')).hexdigest()})
    if not candidates:
        return None
    newest = max(c['start'] for c in candidates)
    latest = [c for c in candidates if c['start'] == newest]
    if len(latest) > 1:
        if any(c['clock'] is None for c in latest):
            raise ValueError('MOPS event order ambiguous')
        last_clock = max(c['clock'] for c in latest)
        latest = [c for c in latest if c['clock'] == last_clock]
    selected = _one(latest, 'MOPS latest event conflicting')
    if selected['material'] is None:
        return None
    filename, kind, language, file_date = selected['material']
    if file_date > now.date().isoformat():
        raise ValueError('MOPS material date is after observation')
    body = urlencode([('step', '9'), ('filePath', FILE_PATH), ('fileName', filename), ('functionName', 't100sb02_1')])
    return {'ticker': ticker, 'symbol': symbol, 'company_name': name,
            'event_date': selected['start'].isoformat(), 'event_end_date': selected['end'].isoformat(),
            'event_time': selected['time'], 'event_location': selected['location'], 'event_summary': selected['summary'],
            'material_file_date': file_date, 'filename': filename, 'format': kind, 'language': language,
            'index_sha256': sha256(raw).hexdigest(), 'row_sha256': selected['row_sha256'],
            'url': DOWNLOAD_URL, 'method': 'POST', 'request_body': body,
            'request_sha256': sha256(('POST\n' + DOWNLOAD_URL + '\n' + body).encode('ascii')).hexdigest()}
