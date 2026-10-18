"""Replayable issuer presentation; attachment dates and visual gaps stay explicit."""
from copy import deepcopy
from datetime import date, datetime
import math
import re
import time
import zlib
from zoneinfo import ZoneInfo

from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .auras_monthly_history import _json, _master_anchor
from .auras_conference_transport import AurasConferenceHttp, INDEX, MASTER, PROVIDER, original_bytes, pdf_url
from .tcfhc_conference_transport import valid_epoch

TICKER = '3324.TWO'
LEGAL = '雙鴻科技股份有限公司'
POLICY = 'auras-published-presentation-v1'
KNOWN_2Q26_CN_SHA = '3f0919d05136256627516dc80ac65824b39e10995a32bc5f139f2eff505de377'
NOTE = ('雙鴻官網發布的法說簡報，不是逐字稿；末頁Q&A沒有問答正文。'
        '場次日期取自附件標題，未獨立驗證實際舉行；同日場次不推定先後。'
        '封面月份、財季與官網資料列建立日期分開，後者不是首次發布時間。'
        '原生文字可讀不代表全圖表可讀；只引用可見文字，不能補圖中百分比或廠區細節。'
        '公司說法及展望未獨立證實，不覆寫年度經查核財報、合併範圍或TTM；依原簡報提醒核對MOPS修訂。')


def supports_auras(ticker):
    return str(ticker).strip().upper() == TICKER


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def _as_of(epoch, as_of_epoch):
    observed = time.time()
    reference = observed if as_of_epoch is None else as_of_epoch
    try:
        valid = (all(type(v) in (int, float) and math.isfinite(v) for v in (epoch, reference))
                 and 0 < epoch <= reference <= observed)
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise ValueError('invalid original observation date')
    return _today(reference)


def parse_master(raw, epoch, *, as_of_epoch=None):
    today = _as_of(epoch, as_of_epoch)
    anchor = _master_anchor(raw, today=today)
    if date.fromisoformat(anchor['as_of']) > _today(epoch):
        raise ValueError('issuer master not yet dated at original acquisition')
    return anchor


def _row_date(row):
    title = row.get('title')
    match = re.match(r'^(20\d{2})/(\d{2})/(\d{2})_\s*\S', title) if isinstance(title, str) else None
    if not match:
        raise ValueError('current event title has no unambiguous date')
    day = date(*map(int, match.groups()))
    if day.year != row['year']:
        raise ValueError('event year mismatch')
    return day


def select_presentation(raw, epoch, *, as_of_epoch=None):
    today = _as_of(epoch, as_of_epoch)
    root = _json(raw)
    info = root.get('info') if isinstance(root, dict) else None
    if (not isinstance(info, dict) or root.get('status') is not True
            or type(root.get('totalCount')) is not int or root['totalCount'] != 1
            or root.get('infos') != [info] or root.get('errorMessage') not in ('', None)
            or type(info.get('unitId')) is not int or info['unitId'] != 46
            or type(info.get('unitParentId')) is not int or info['unitParentId'] != 6
            or info.get('tcn', {}).get('unitName') != '法人說明會'
            or info.get('tcn', {}).get('path') != '投資人關係/法人說明會'):
        raise ValueError('published conference unit unverified')
    current = {}
    for language in ('CN', 'ENG'):
        rows = info.get('unitAnnexFileList_' + language)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 300:
            raise ValueError('annex list unverified')
        ids, groups, candidates = set(), set(), []
        for row in rows:
            if (not isinstance(row, dict) or type(row.get('fileId')) is not int or row['fileId'] <= 0
                    or type(row.get('groupNumber')) is not int or row['groupNumber'] <= 0
                    or type(row.get('year')) is not int or not 2000 <= row['year'] <= today.year + 1
                    or row['fileId'] in ids or row['groupNumber'] in groups):
                raise ValueError('annex identity or uniqueness invalid')
            ids.add(row['fileId']); groups.add(row['groupNumber'])
            # Older legacy rows have ROC/undated titles; they cannot compete
            # with current/previous-year explicitly dated events.
            if row['year'] < today.year - 1:
                continue
            day = _row_date(row)
            if day <= _today(epoch) and 0 <= (today - day).days <= 370:
                candidates.append((day, row))
        current[language] = candidates
    if not current['CN']:
        raise ValueError('no dated past current presentation')
    day, chosen = max(current['CN'], key=lambda item: (item[0], item[1]['groupNumber']))
    same_day = [r for d, r in current['CN'] if d == day]
    match = re.fullmatch(r'(20\d{2}) AURAS_([1-4])Q(\d{2}) External_CH\.pdf', chosen.get('fileName', ''))
    if match is None or int(match[1]) != 2000 + int(match[3]) or not pdf_url(chosen.get('filePath')):
        raise ValueError('selected official presentation filename or URL invalid')
    year, quarter = int(match[1]), int(match[2])
    quarter_end = date(year + int(quarter == 4), quarter * 3 % 12 + 1, 1)
    if quarter_end > day or year < day.year - 1:
        raise ValueError('presentation financial period is future or outside current window')
    counterpart = [r for d, r in current['ENG'] if r['groupNumber'] == chosen['groupNumber']]
    if (len(counterpart) != 1 or _row_date(counterpart[0]) != day
            or counterpart[0].get('fileName') != chosen['fileName'].replace('_CH.pdf', '_EN.pdf')):
        raise ValueError('published language pairing conflicts')
    record_created = chosen.get('createDate')
    if (not isinstance(record_created, str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?', record_created)
            or not day <= date.fromisoformat(record_created[:10]) <= _today(epoch)):
        raise ValueError('selected record creation date invalid')
    return {'event_date': day.isoformat(), 'event_title': chosen['title'], 'period': f'{year}Q{quarter}',
            'pdf_url': chosen['filePath'], 'file_id': chosen['fileId'], 'group_number': chosen['groupNumber'],
            'file_name': chosen['fileName'], 'index_record_created_at_unzoned': record_created,
            'same_day_events': [{'group_number': r['groupNumber'], 'title': r['title'], 'url': r['filePath']}
                                for r in sorted(same_day, key=lambda x: x['groupNumber'])],
            'selection_policy': 'latest_past_annex_date_then_highest_group_number_not_time_order'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    try:
        native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline - time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages']; text = '\n'.join(p['text'] for p in pages)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or not 1 <= native['page_count'] <= 50 or '雙鴻科技' not in pages[0]['text']
            or 'Safe Harbor Notice' not in text or 'MOPS' not in text):
        raise ValueError('native issuer presentation incomplete')
    months = 'January February March April May June July August September October November December'.split()
    cover = re.search(r'\b(' + '|'.join(months) + r')\s+(20\d{2})\b', pages[0]['text'])
    if cover is None:
        raise ValueError('presentation cover month missing')
    cover_month = date(int(cover[2]), months.index(cover[1]) + 1, 1)
    year, quarter = selected['period'].split('Q'); q = int(quarter)
    if not date(int(year), q * 3, 1) <= cover_month <= date.fromisoformat(selected['event_date']):
        raise ValueError('cover month conflicts with financial period or event')
    primary_quarters = re.findall(r'季度_簡易損益表\s+NT\$\s*千元\s+([1-4]Q\d{2})(?:\s|$)', text)
    if primary_quarters != [f'{q}Q{year[2:]}']:
        raise ValueError('financial period or unit absent from native text')
    return native, cover_month.strftime('%Y-%m')


def _context(selected, native, cover, proof):
    omissions = ([{'page_number': 8, 'issue': 'product_mix_chart_percentages_missing_from_native_text'}]
                 if native['content_sha256'] == KNOWN_2Q26_CN_SHA else [])
    doc = {'document_id': '3324:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'title': selected['event_title'], 'url': selected['pdf_url'], 'event_date': selected['event_date'],
           'event_date_basis': 'issuer_published_annex_title', 'event_time': None, 'event_timezone': None,
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'content_period': selected['period'], 'presentation_cover_month': cover, 'published_at': None,
           'index_record_created_at_unzoned': selected['index_record_created_at_unzoned'],
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': native['empty_pages'],
           'garbled_pages': native['garbled_pages'], 'known_native_text_omissions': omissions,
           'parser_version': native['parser_version']}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': selected['period'],
            'title': selected['event_title'], 'source': PROVIDER, 'source_url': INDEX,
            'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'zh-TW'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'same_day_events': selected['same_day_events'], 'selection_policy': selected['selection_policy'],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'auras_conference_receipt': proof}


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic() + 10.
    try:
        _check(deadline)
        if not supports_auras(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['auras_conference_receipt']
        if set(proof) != {'policy', 'identity', 'index', 'pdf', 'selected'} or proof['policy'] != POLICY:
            return False
        parse_master(original_bytes(proof['identity'], MASTER, max_age=max_age), proof['identity']['retrieved_at'])
        selected = select_presentation(original_bytes(proof['index'], INDEX, max_age=max_age), proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        native, cover = native_presentation(original_bytes(proof['pdf'], selected['pdf_url'], max_age=max_age), selected, deadline)
        expected = _context(selected, native, cover, proof)
        _check(deadline)
        return (all(valid_epoch(proof[k]['retrieved_at'], max_age) for k in ('identity', 'index', 'pdf'))
                and value == expected)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout':
            raise
        return False
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, OSError, EOFError, zlib.error, SourcePdfError):
        return False


def fetch_auras_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_auras(ticker):
        return {}
    deadline = time.monotonic() + 20.
    http = AurasConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'auras_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER); parse_master(raw, identity['retrieved_at'])
        raw, index = http.get_receipt(INDEX); selected = select_presentation(raw, index['retrieved_at'])
        raw, pdf = http.get_receipt(selected['pdf_url']); native, cover = native_presentation(raw, selected, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'pdf': pdf, 'selected': selected}
        value = _context(selected, native, cover, proof)
        if not verify_context(value, ticker, deadline=deadline, max_age=1800):
            raise SourceResponseError('original_unverified')
        details.update(auras_originals_verified=True, coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'], fetched_at_epoch=pdf['retrieved_at'], message=NOTE)
        _check(deadline)
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        details.update(error_kind=exc.error_kind, status='error', component_statuses=deepcopy(http.components),
                       http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:
            diagnostics.update(details)
        if exc is original:
            raise
        raise exc from original
    details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count),
                   http_request_count=http.http_request_count)
    if diagnostics is not None:
        diagnostics.update(details)
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data, dict) or data.get('ticker') != ticker
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quote_type', 'quoteType'))):
        return False
    identity = data.get('company_identity')
    if identity is None:
        identity = {}
    if not isinstance(identity, dict):
        return False
    for key, expected in [('ticker', TICKER), ('stock_id', '3324'), ('official_name', '雙鴻'),
                          ('legal_name', LEGAL), ('official_ubn', '16619628'), ('instrument_type', 'EQUITY')]:
        if identity.get(key) not in (None, '', expected):
            return False
    for key in ('allowed_aliases', 'english_names', 'forbidden_aliases'):
        rows = identity.get(key, [])
        if not isinstance(rows, (list, tuple)) or any(not isinstance(s, str) for s in rows):
            return False
    name = data.get('company_name')
    if name is not None and (not isinstance(name, str) or not all(v.strip().casefold() in {
            '雙鴻', LEGAL, 'auras technology co., ltd.', 'auras technology co. ltd.'} for v in name.split(' / '))):
        return False
    if {'雙鴻', LEGAL} & {s.strip('* ').strip() for s in identity.get('forbidden_aliases', [])}:
        return False
    return True


def is_marked(value):
    if not isinstance(value, dict):
        return False
    return ('auras_conference_receipt' in value or value.get('source') == PROVIDER or value.get('source_url') == INDEX
            or any(isinstance(d, dict) and (d.get('source') == PROVIDER or pdf_url(d.get('url')))
                   for key in ('documents', 'materials') for d in (value.get(key) if isinstance(value.get(key), list) else [])))
