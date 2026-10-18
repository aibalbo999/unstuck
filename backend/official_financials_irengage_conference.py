"""IR Engage conference-list fallback for public MOPS event materials."""
from __future__ import annotations

from datetime import date, datetime
from html import unescape
import re
import time
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from external_http_client import sync_get
from search_provider_runtime import (
    SourceResponseError,
    cooldown_state,
    observe_http_response,
    record_observation,
    remember_failure,
    remember_success,
    scope_key,
)
from shared_provider_cache import shared_fetch


PROVIDER = 'IR Engage conference index'
BASE_URL = 'https://irengage.taiwanindex.com.tw'
LIST_URL = BASE_URL + '/ConferenceList'
PARSER_VERSION = 'irengage-conference-v1'
COVERAGE_NOTE = 'IR Engage 提供公開法說行程、說明及簡報連結；未提供完整逐字稿。'
REQUEST_TIMEOUT = (3, 8)
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
)
HEADERS = {'User-Agent': USER_AGENT}
COOLDOWN_KEY = scope_key(PROVIDER, endpoint='conference_list')
TAIPEI = ZoneInfo('Asia/Taipei')


def fetch_irengage_conference_context(
    ticker: str,
    *,
    year: int | None = None,
    diagnostics: dict | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
    now: datetime | None = None,
) -> dict:
    """Fetch one latest completed event from the public company calendar."""
    from official_financials_webpro_conference import taiwan_company_symbol

    symbol = taiwan_company_symbol(ticker)
    if not symbol:
        return {}
    selected_year = int(year) if year is not None else datetime.now(TAIPEI).year
    if selected_year < 2000 or selected_year > 2100:
        return {}
    captured: dict = {}
    cache_key = f'{PARSER_VERSION}:{symbol}:{selected_year}'

    def fetch():
        started = time.monotonic()
        blocked = cooldown_state(COOLDOWN_KEY)
        if blocked:
            details = {**blocked, 'http_request_sent': False, 'event_kind': 'local_block',
                       'actual_provider': PROVIDER, 'parser_version': PARSER_VERSION}
            captured.update(details, status='error')
            record_observation(PROVIDER, started, outcome='cooldown', source='earnings_call',
                               details=details, sent=False)
            raise SourceResponseError(blocked.get('error_kind', 'cooldown'),
                                      status_code=blocked.get('http_status'),
                                      parser_version=PARSER_VERSION)
        response = None
        request_started_at = time.time()
        try:
            response = sync_get(
                LIST_URL,
                params={'StockCode': symbol, 'Year': str(selected_year)},
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                provider=PROVIDER,
            )
            observe_http_response(response)
            text = str(response.text or '')
            if re.search(r'captcha|access denied|forbidden|驗證碼|安全性考量', text, re.I):
                raise SourceResponseError('access_denied', status_code=response.status_code,
                                          response_text=text, parser_version=PARSER_VERSION)
            events, selection = parse_irengage_conference_page(
                text, symbol, requested_year=selected_year, now=now,
            )
        except Exception as exc:
            details = remember_failure(COOLDOWN_KEY, exc)
            if isinstance(exc, SourceResponseError):
                details.update(exc.diagnostic)
            if response is not None:
                details.setdefault('http_status', getattr(response, 'status_code', None))
            details.update(parser_version=PARSER_VERSION, actual_provider=PROVIDER,
                           http_request_sent=True, event_kind='http_attempt')
            captured.update(details, status='error')
            record_observation(PROVIDER, started, outcome='failure', source='earnings_call',
                               details=details)
            error_kind = details.get('error_kind', 'provider_error')
            raise SourceResponseError(error_kind, status_code=details.get('http_status'),
                                      parser_version=PARSER_VERSION) from exc

        if getattr(response, 'status_code', None) == 200:
            remember_success(COOLDOWN_KEY, request_started_at=request_started_at)
        outcome = 'partial' if selection['rejected_count'] else 'results' if events else 'valid_empty'
        details = {
            **selection,
            'http_status': getattr(response, 'status_code', None),
            'parser_version': PARSER_VERSION,
            'actual_provider': PROVIDER,
            'http_request_sent': True,
            'event_kind': 'http_attempt',
            'outcome': outcome,
        }
        captured.update(details, status='success' if events else 'valid_empty')
        record_observation(PROVIDER, started, outcome=outcome, count=len(events),
                           source='earnings_call', details=details)
        return {'events': events, 'diagnostic': details}

    payload, metadata = shared_fetch(
        cache_key,
        fetch,
        freshness_seconds=86400,
        error_retry_seconds=60,
        use_cache=use_cache,
        force_refresh=force_refresh,
        result_ttl=lambda value: 86400 if value.get('events') else 300,
    )
    if payload is None:
        details = {**metadata, **captured, 'actual_provider': PROVIDER}
        if not captured:
            details.update(cooldown_state(COOLDOWN_KEY), http_request_sent=False,
                           event_kind='local_block')
        if diagnostics is not None:
            diagnostics.update(details)
        raise SourceResponseError(details.get('error_kind') or 'provider_error',
                                  status_code=details.get('http_status'),
                                  parser_version=PARSER_VERSION)

    details = {**payload.get('diagnostic', {}), **metadata, 'actual_provider': PROVIDER}
    if metadata.get('cache_hit'):
        details.update(http_request_sent=False, event_kind='cache_hit')
    if diagnostics is not None:
        diagnostics.update(details)
    events = payload.get('events') or []
    if not events:
        return {}

    event = events[0]
    return {
        'ticker': symbol + ('.TWO' if str(ticker).strip().upper().endswith('.TWO') else '.TW'),
        'date': event['date'],
        'period': event['date'],
        'title': f"{event['company_name'] or symbol} 法人說明會",
        'summary': event['summary'],
        'transcript_excerpt': '',
        'transcript_available': False,
        'materials': list(event['materials']),
        'source': PROVIDER,
        'source_url': event['source_url'],
        'upstream_source': 'MOPS-derived IR Engage public listing',
        'coverage_status': 'materials_available' if event['materials'] else 'metadata_only',
        'coverage_notes': [COVERAGE_NOTE],
        'fetched_at_epoch': details.get('fetched_at_epoch'),
    }


def parse_irengage_conference_page(
    html: str,
    symbol: str,
    *,
    requested_year: int,
    now: datetime | None = None,
) -> tuple[list[dict], dict]:
    """Parse only rows bound to the requested stock code and completed dates."""
    symbol = str(symbol or '').strip()
    if not re.fullmatch(r'\d{4,6}', symbol):
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    soup = BeautifulSoup(str(html or ''), 'lxml')
    stock_input = soup.select_one('form#ConferenceForm input[name="StockCode"]')
    if stock_input is None or str(stock_input.get('value') or '').strip() != symbol:
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)

    table = None
    column_indexes = None
    for candidate in soup.find_all('table'):
        header = [cell.get_text(' ', strip=True) for cell in candidate.find_all('th')]
        mapping = _conference_column_indexes(header)
        if mapping is not None:
            table, column_indexes = candidate, mapping
            break
    if table is None or column_indexes is None:
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)

    local_now = now.astimezone(TAIPEI) if now and now.tzinfo else (now.replace(tzinfo=TAIPEI) if now else datetime.now(TAIPEI))
    today = local_now.date()
    records, rejected = [], []
    for row in table.find_all('tr'):
        cells = row.find_all('td', recursive=False)
        if not cells:
            continue
        company_cell = _cell_text(cells, column_indexes['company'])
        if not re.match(r'^' + re.escape(symbol) + r'(?:\s|$)', company_cell):
            continue
        if max(column_indexes.values()) >= len(cells):
            rejected.append('invalid_row_shape')
            continue
        date_text = _cell_text(cells, column_indexes['date'])
        event_date, event_end = _event_date_bounds(date_text, fallback_year=requested_year)
        if event_date is None or event_end is None:
            rejected.append('invalid_event_date')
            continue
        time_text = _cell_text(cells, column_indexes['time'])
        if event_end > today:
            continue
        if event_end == today:
            parsed_time = re.fullmatch(r'([01]\d|2[0-3]):([0-5]\d)', time_text)
            if not parsed_time or tuple(map(int, parsed_time.groups())) > (local_now.hour, local_now.minute):
                continue
        materials = _parse_material_links(cells[column_indexes['download']], symbol)
        name = re.sub(r'^' + re.escape(symbol) + r'\s*', '', company_cell).strip()
        location = _cell_text(cells, column_indexes['location'])
        summary = _cell_text(cells, column_indexes['summary'])
        source_url = f'{LIST_URL}?StockCode={symbol}&Year={int(requested_year)}'
        records.append({
            'ticker': symbol,
            'company_name': name,
            'date': event_date.isoformat(),
            'time': time_text,
            'location': location,
            'summary': summary,
            'materials': materials,
            'source_url': source_url,
        })
    records.sort(key=lambda item: item['date'], reverse=True)
    selection = {
        'raw_count': len(records) + len(rejected),
        'usable_count': len(records),
        'rejected_count': len(rejected),
        'rejected_reason_counts': {reason: rejected.count(reason) for reason in sorted(set(rejected))},
    }
    return records, selection


def _conference_column_indexes(headers: list[str]) -> dict[str, int] | None:
    aliases = {
        'date': ('日期', 'date'),
        'time': ('時間', 'time'),
        'company': ('公司', 'company'),
        'location': ('地點', 'location'),
        'summary': ('訊息', '資訊', 'message', 'information'),
        'download': ('下載', 'download'),
    }
    normalized = [re.sub(r'\s+', '', header).casefold() for header in headers]
    indexes = {}
    for key, candidates in aliases.items():
        match = next((index for index, header in enumerate(normalized)
                      if any(candidate.casefold() in header for candidate in candidates)), None)
        if match is None:
            return None
        indexes[key] = match
    return indexes


def _cell_text(cells, index: int) -> str:
    if index >= len(cells):
        return ''
    return re.sub(r'\s+', ' ', cells[index].get_text(' ', strip=True)).strip()


def _event_date_bounds(value: str, *, fallback_year: int) -> tuple[date | None, date | None]:
    matches = list(re.finditer(
        r'(?:(?P<year>\d{2,4})\s*[/.-]\s*)?(?P<month>\d{1,2})\s*[/.-]\s*(?P<day>\d{1,2})',
        str(value or ''),
    ))
    parsed = []
    inherited_year = None
    for match in matches:
        raw_year = match.group('year')
        year = int(raw_year) if raw_year else (inherited_year or int(fallback_year))
        if raw_year:
            if year < 100:
                year += 2000
            elif year < 1911:
                year += 1911
        inherited_year = year
        try:
            parsed.append(date(year, int(match.group('month')), int(match.group('day'))))
        except ValueError:
            return None, None
    if not parsed:
        return None, None
    return parsed[0], parsed[-1]


def _parse_material_links(cell, symbol: str) -> list[dict]:
    output = []
    seen = set()
    for button in cell.select('button[onclick]'):
        onclick = unescape(str(button.get('onclick') or ''))
        match = re.search(r"window\.open\(\s*(['\"])(.*?)\1", onclick, re.I)
        if not match:
            continue
        url = match.group(2).strip()
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != 'mopsov.twse.com.tw' or parsed.path != '/server-java/FileDownLoad':
            continue
        query = parse_qs(parsed.query)
        filename = (query.get('fileName') or [''])[0]
        file_path = (query.get('filePath') or [''])[0]
        valid = re.fullmatch(r'(' + re.escape(symbol) + r')(\d{8})([ME])(\d{3})\.pdf', filename, re.I)
        if not valid or file_path != '/home/html/nas/STR/' or filename in seen:
            continue
        seen.add(filename)
        language = '中文' if valid.group(3).upper() == 'M' else '英文'
        output.append({'label': language + '簡報檔案', 'url': url})
    return output
