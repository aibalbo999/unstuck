"""Fixed Syntec audited-book native pages; generic PDF limits stay unchanged."""
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

INPUT_LIMIT = 4_000_000
STREAM_LIMIT = 8 * 1024 * 1024
PAGE_LIMIT = 104
SELECTED = (1,4,6,7,8,9,10,11,62,63)
CHAR_LIMIT = 100_000
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
    from pypdf.generic import ContentStream
    from pypdf._text_extraction._layout_mode._fixed_width_page import recurse_to_target_op, resolve_font
    from pypdf._text_extraction._layout_mode._text_state_manager import TextStateManager
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
            if len(document.pages) != PAGE_LIMIT:
                raise _Failure('page_limit')
            pages, empty, garbled = [], [], []
            chars = 0
            for number in SELECTED:
                page = document.pages[number-1]
                if time.monotonic() >= deadline:
                    raise _Failure('timeout')
                fonts=page._layout_mode_fonts()
                ops=iter(ContentStream(page['/Contents'].get_object(),page.pdf,'bytes').operations)
                manager=TextStateManager();positioned=[]
                for operands, op in ops:
                    if op in (b'BT',b'q'):
                        _,parts=recurse_to_target_op(ops,manager,b'ET'if op==b'BT'else b'Q',fonts,True)
                        positioned.extend(parts)
                    elif op==b'Tf':manager.set_font(resolve_font(fonts,operands[0]),operands[1])
                    elif op==b'cm':manager.add_cm(*operands)
                    else:manager.set_state_param(op,operands)
                    if len(positioned)>10000:raise _Failure('segment_limit')
                    if time.monotonic()>=deadline:raise _Failure('timeout')
                segments=[]
                for part in positioned:
                    if part.rotated or not part.font.interpretable:raise _Failure('unsupported_text_position')
                    if not all(math.isfinite(v) and abs(v)<1000000 for v in (part.tx,part.ty,part.displaced_tx,part.font_height)):raise _Failure('invalid_text_position')
                    if part.text.strip():segments.append({'text':part.text,'x':part.tx,'end_x':part.displaced_tx,'y':part.ty,'font_height':part.font_height})
                text = page.extract_text() or ''
                chars += len(text)
                if chars > CHAR_LIMIT:
                    raise _Failure('character_limit')
                pages.append({'page_number': number, 'text': text, 'segments':segments, 'width':float(page.mediabox.width), 'height':float(page.mediabox.height), 'rotation':page.rotation})
                if not text.strip():
                    empty.append(number)
                if _garbled(text):
                    garbled.append(number)
    except pypdf.errors.LimitReachedError:
        raise _Failure('stream_limit') from None
    if empty or garbled:
        raise _Failure('empty_or_garbled_selected_document')
    return {'page_count': len(document.pages), 'selected_full_physical_pages': list(SELECTED), 'extraction_mode': 'native_show_operation_coordinates', 'pages': pages, 'empty_pages': empty,
            'garbled_pages': garbled, 'coverage_status': 'selected_native_text_complete',
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
