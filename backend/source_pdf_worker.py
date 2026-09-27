"""Private offline PDF parser. Launched only by source_pdf_reader."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import logging
import math
import re
import sys
import time
import unicodedata

INPUT_LIMIT = 16 * 1024 * 1024
STREAM_LIMIT = 8 * 1024 * 1024
PAGE_LIMIT = 100
CHAR_LIMIT = 200_000
PARSER_VERSION = '6.19.0'


class _Failure(Exception):
    pass


def _limits(deadline):
    try:
        import resource
        remaining = deadline - time.monotonic()
        if not 0 < remaining <= 10:
            raise _Failure('timeout')
        seconds = max(1, math.ceil(remaining))
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        if sys.platform.startswith('linux'):
            resource.setrlimit(resource.RLIMIT_AS, (640 * 1024 * 1024, 640 * 1024 * 1024))
        elif sys.platform != 'darwin':
            raise _Failure('resource_limits_unavailable')
    except (ImportError, OSError, ValueError):
        raise _Failure('resource_limits_unavailable') from None


class _FailOnWarning(logging.Handler):
    def emit(self, record):
        # pypdf can otherwise swallow form/decompression errors and return a
        # plausible partial page. Do not publish that as complete extraction.
        raise _Failure('parser_warning')


def _garbled(text):
    return ('\ufffd' in text or bool(re.search(r'\(cid:\d+\)', text)) or
            any(unicodedata.category(c) in {'Co', 'Cs'} or
                unicodedata.category(c) == 'Cc' and c not in '\n\r\t\f' for c in text))


def _extract(raw, deadline):
    try:
        import pypdf
    except ImportError:
        raise _Failure('parser_unavailable') from None
    if pypdf.__version__ != PARSER_VERSION:
        raise _Failure('parser_version_mismatch')
    logger = logging.getLogger('pypdf')
    logger.handlers = [_FailOnWarning()]
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    configuration = pypdf.Configuration(
        maximum_declared_stream_length=STREAM_LIMIT,
        array_based_stream_maximum_output_length=STREAM_LIMIT,
        jbig2_maximum_output_length=STREAM_LIMIT, jbig2dec_binary=None,
        lzw_maximum_output_length=STREAM_LIMIT, run_length_maximum_output_length=STREAM_LIMIT,
        zlib_maximum_output_length=STREAM_LIMIT, zlib_maximum_recovery_input_length=1024 * 1024,
        flate_maximum_columns=100_000, flate_maximum_row_length=1024 * 1024,
        image_maximum_buffer_size=STREAM_LIMIT, xmp_maximum_input_length=STREAM_LIMIT,
        xmp_maximum_element_count=10_000, outline_maximum_entries=1000, outline_maximum_depth=32,
        page_tree_maximum_entries=1000, page_tree_maximum_depth=32,
        xform_maximum_invocations_per_extraction=100, disable_legacy_handling=True,
    )
    try:
        with pypdf.apply_configuration(configuration):
            document = pypdf.PdfReader(BytesIO(raw), strict=True)
            if document.is_encrypted:
                raise _Failure('encrypted_pdf')
            if not 1 <= len(document.pages) <= PAGE_LIMIT:
                raise _Failure('page_limit')
            pages, empty, garbled = [], [], []
            chars = 0
            for number, page in enumerate(document.pages, 1):
                if time.monotonic() >= deadline:
                    raise _Failure('timeout')
                text = page.extract_text() or ''
                chars += len(text)
                if chars > CHAR_LIMIT:
                    raise _Failure('character_limit')
                pages.append({'page_number': number, 'text': text})
                if not text.strip():
                    empty.append(number)
                if _garbled(text):
                    garbled.append(number)
    except pypdf.errors.LimitReachedError:
        raise _Failure('stream_limit') from None
    if len(empty) == len(pages):
        raise _Failure('empty_document')
    return {'page_count': len(pages), 'pages': pages, 'empty_pages': empty,
            'garbled_pages': garbled, 'coverage_status': 'partial' if empty or garbled else 'complete',
            'parser_version': pypdf.__version__, 'content_sha256': hashlib.sha256(raw).hexdigest()}


def main():
    try:
        deadline = float(sys.argv[1])
        _limits(deadline)
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if not raw.startswith(b'%PDF-') or len(raw) > INPUT_LIMIT:
            raise _Failure('invalid_input')
        result = _extract(raw, deadline)
    except _Failure as exc:
        result = {'error': str(exc)}
    except MemoryError:
        result = {'error': 'memory_limit'}
    except Exception:
        result = {'error': 'invalid_pdf'}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True, separators=(',', ':')).encode('ascii'))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
