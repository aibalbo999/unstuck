"""Native PPTX text in one bounded, killable child; never render or run content.

Coverage concerns visible native slide text, not charts/images, reading order,
speaker notes or a transcript. Original slide numbers survive hidden exclusion.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import unicodedata

from source_pdf_reader import SourcePdfError, _run_worker

INPUT_LIMIT = 8 * 1024 * 1024
TIMEOUT_LIMIT = 10
PAGE_LIMIT = 100
CHAR_LIMIT = 200_000
PARSER_VERSION = 'pptx-native-v1'

class SourcePptxError(RuntimeError):
    retryable = False

    def __init__(self, reason, *, content_sha256=None):
        super().__init__(f'PPTX extraction: {reason}')
        self.reason = self.error_kind = reason
        self.content_sha256 = content_sha256


def _worker_command(deadline):
    return [sys.executable, '-B', str(Path(__file__).with_name('source_pptx_worker.py')), str(deadline)]


def _garbled(text):
    return ('\ufffd' in text or bool(re.search(r'\(cid:\d+\)', text)) or
            any(unicodedata.category(c) in {'Co', 'Cs'} or
                unicodedata.category(c) == 'Cc' and c not in '\n\r\t\f' for c in text))


def _validate_result(value, digest):
    if not isinstance(value, dict):
        raise SourcePptxError('invalid_worker_result')
    if set(value) == {'error'}:
        allowed = {'invalid_pptx', 'invalid_input', 'zip_limit', 'unsafe_package',
                   'encrypted_package', 'active_content', 'invalid_xml',
                   'slide_limit', 'character_limit', 'empty_document',
                   'memory_limit', 'resource_limits_unavailable', 'timeout'}
        reason = value['error']
        raise SourcePptxError(reason if isinstance(reason, str) and reason in allowed else 'worker_failed')
    expected = {'pages', 'page_count', 'total_slide_count', 'hidden_pages', 'empty_pages',
                'garbled_pages', 'coverage_status', 'content_sha256', 'parser_version',
                'external_relationship_count', 'embedded_object_count'}
    if (set(value) != expected or value['content_sha256'] != digest or
            value['parser_version'] != PARSER_VERSION):
        raise SourcePptxError('invalid_worker_result')
    total, count, hidden, pages = (value[k] for k in ('total_slide_count', 'page_count', 'hidden_pages', 'pages'))
    if (type(total) is not int or not 1 <= total <= PAGE_LIMIT or type(count) is not int or
            not 1 <= count <= total or not isinstance(hidden, list) or
            any(type(n) is not int or not 1 <= n <= total for n in hidden) or
            hidden != sorted(set(hidden)) or count + len(hidden) != total or
            not isinstance(pages, list) or len(pages) != count):
        raise SourcePptxError('invalid_worker_result')
    numbers = [n for n in range(1, total + 1) if n not in hidden]
    empty, garbled, chars = [], [], 0
    for number, page in zip(numbers, pages):
        if (not isinstance(page, dict) or set(page) != {'page_number', 'text'} or
                type(page['page_number']) is not int or page['page_number'] != number or
                not isinstance(page['text'], str)):
            raise SourcePptxError('invalid_worker_result')
        text = page['text']; chars += len(text)
        if not text.strip(): empty.append(number)
        if _garbled(text): garbled.append(number)
    for name, expected_list in (('empty_pages', empty), ('garbled_pages', garbled)):
        items = value[name]
        if not isinstance(items, list) or any(type(n) is not int for n in items) or items != expected_list:
            raise SourcePptxError('invalid_worker_result')
    if (chars > CHAR_LIMIT or len(empty) == count or
            value['coverage_status'] != ('partial' if empty or garbled else 'complete') or
            any(type(value[k]) is not int or not 0 <= value[k] <= 20_000
                for k in ('external_relationship_count', 'embedded_object_count')) or
            value['embedded_object_count'] > 2000):
        raise SourcePptxError('invalid_worker_result')
    return value


def extract_pptx_pages(raw: bytes, *, timeout_seconds=10) -> dict:
    """Extract visible native text without following links, executing or OCR.

    The deadline includes child startup, input/output and result validation.
    Mandatory kill/reap cleanup can add time after a rejected deadline.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > INPUT_LIMIT:
        raise SourcePptxError('invalid_input')
    digest = hashlib.sha256(raw).hexdigest()
    if (type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= TIMEOUT_LIMIT or
            not math.isfinite(timeout_seconds)):
        raise SourcePptxError('invalid_timeout', content_sha256=digest)
    deadline = time.monotonic() + float(timeout_seconds)
    try:
        output = _run_worker(raw, deadline, worker_command=_worker_command(deadline))
        if time.monotonic() >= deadline:
            raise SourcePptxError('timeout')
        result = _validate_result(json.loads(output), digest)
        if time.monotonic() >= deadline:
            raise SourcePptxError('timeout')
        return result
    except SourcePptxError as exc:
        exc.content_sha256 = digest
        raise
    except SourcePdfError as exc:
        raise SourcePptxError(exc.reason, content_sha256=digest) from None
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise SourcePptxError('invalid_worker_result', content_sha256=digest) from None
