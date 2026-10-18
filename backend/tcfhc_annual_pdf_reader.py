"""Bounded native coordinates from fixed TCFHC English annual-book profiles."""
from hashlib import sha256
from pathlib import Path
import json
import math
import re
import sys
import time
import unicodedata

from source_pdf_reader import _run_worker, SourcePdfError, PARSER_VERSION, TIMEOUT_LIMIT

PAGE_COUNTS = {2021: 240, 2022: 238, 2023: 242, 2024: 245, 2025: 247}
SELECTED = {y: (1, 3, 7, 8, 9, 10, 11, 12, 14, 15, 16) for y in PAGE_COUNTS}
SELECTED[2024] = (1, 3, 7, 8, 9, 10, 11, 13, 14, 15)
INPUT_LIMIT = 8 * 1024 * 1024
CHAR_LIMIT = 100_000
ERRORS = {
    'invalid_pdf', 'encrypted_pdf', 'page_limit', 'character_limit',
    'empty_or_garbled_selected_document', 'parser_unavailable', 'parser_version_mismatch',
    'parser_warning', 'stream_limit', 'resource_limits_unavailable', 'timeout',
    'invalid_input', 'memory_limit', 'segment_limit', 'unsupported_text_position',
    'invalid_text_position',
}


def _garbled(text):
    return ('\ufffd' in text or bool(re.search(r'\(cid:\d+\)', text)) or
            any(unicodedata.category(c) in {'Co', 'Cs'} or
                unicodedata.category(c) == 'Cc' and c not in '\n\r\t\f' for c in text))


def validate_positioned_book(value, year, digest=None):
    """Validate the external child boundary again for positioned-parser callers."""
    if type(year) is not int or year not in PAGE_COUNTS:
        raise SourcePdfError('unsupported_annual_profile')
    keys = {'page_count', 'selected_full_physical_pages', 'extraction_mode', 'pages',
            'empty_pages', 'garbled_pages', 'coverage_status', 'parser_version', 'content_sha256'}
    if (not isinstance(value, dict) or set(value) != keys
            or type(value['page_count']) is not int or value['page_count'] != PAGE_COUNTS[year]
            or value['selected_full_physical_pages'] != list(SELECTED[year])
            or any(type(n) is not int for n in value['selected_full_physical_pages'])
            or value['extraction_mode'] != 'native_show_operation_coordinates'
            or value['parser_version'] != PARSER_VERSION
            or not isinstance(value['content_sha256'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', value['content_sha256'])
            or digest is not None and value['content_sha256'] != digest
            or value['empty_pages'] != [] or value['garbled_pages'] != []
            or value['coverage_status'] != 'selected_native_text_complete'
            or not isinstance(value['pages'], list) or len(value['pages']) != len(SELECTED[year])):
        raise SourcePdfError('invalid_worker_result')
    chars = 0
    for number, page in zip(SELECTED[year], value['pages']):
        if (not isinstance(page, dict) or set(page) != {'page_number', 'text', 'segments', 'width', 'height', 'rotation'}
                or type(page['page_number']) is not int or page['page_number'] != number
                or not isinstance(page['text'], str) or not page['text'].strip() or _garbled(page['text'])
                or type(page['rotation']) is not int or page['rotation'] != 0
                or not isinstance(page['segments'], list) or not 1 <= len(page['segments']) <= 10000
                or any(type(page[k]) not in (int, float) or not math.isfinite(page[k])
                       for k in ('width', 'height'))
                # All five balance sheets are A3 portrait; other selected
                # pages are A4. Do not extend any shared geometry limit.
                or abs(page['width'] - (842 if number == 8 else 595)) > 1
                or abs(page['height'] - (1191 if number == 8 else 842)) > 1):
            raise SourcePdfError('invalid_worker_result')
        chars += len(page['text'])
        for s in page['segments']:
            if (not isinstance(s, dict) or set(s) != {'text', 'x', 'end_x', 'y', 'font_height'}
                    or not isinstance(s['text'], str) or len(s['text']) > 10000 or _garbled(s['text'])
                    or any(type(s[k]) not in (int, float) or not math.isfinite(s[k])
                           for k in ('x', 'end_x', 'y', 'font_height'))
                    or not -.1 <= s['x'] <= s['end_x'] <= page['width'] + .1
                    or not -.1 <= s['y'] <= page['height'] + .1 or not 0 < s['font_height'] <= 100):
                raise SourcePdfError('invalid_worker_result')
    if chars > CHAR_LIMIT:
        raise SourcePdfError('character_limit')
    return value


def extract_tcfhc_book(raw, year, *, timeout_seconds=10):
    if type(year) is not int or year not in PAGE_COUNTS:
        raise SourcePdfError('unsupported_annual_profile')
    if (not isinstance(raw, bytes) or not raw.startswith(b'%PDF-') or not 0 < len(raw) <= INPUT_LIMIT
            or type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= TIMEOUT_LIMIT):
        raise SourcePdfError('invalid_input')
    digest = sha256(raw).hexdigest()
    deadline = time.monotonic() + timeout_seconds
    command = [sys.executable, '-B', str(Path(__file__).with_name('tcfhc_annual_pdf_worker.py')), str(deadline), str(year)]
    try:
        value = json.loads(_run_worker(raw, deadline, worker_command=command))
        if time.monotonic() >= deadline:
            raise SourcePdfError('timeout')
        if isinstance(value, dict) and set(value) == {'error'}:
            reason = value['error']
            raise SourcePdfError(reason if isinstance(reason, str) and reason in ERRORS else 'worker_failed')
        result = validate_positioned_book(value, year, digest)
        if time.monotonic() >= deadline:
            raise SourcePdfError('timeout')
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
