"""Exact-original ChipMOS transcript reader with qualified xref cursor evidence.

No PDF bytes or xref entries are rewritten. This adapter is restricted to the
one published original whose complete classic xref was independently checked.
The common private-child memory, CPU, stream and warning guards remain in use.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

from source_pdf_reader import SourcePdfError, _run_worker, _validate_result

ORIGINAL_SHA256 = '712d554e7f3878cbcb7705bdfc7f9977f410661e176af6288f74fc3e81371d7a'
INPUT_LIMIT = 8 * 1024 * 1024
POLICY = 'chipmos-2026q2-exact-xref-lf.v1'


def _check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def _qualify_xref(raw, deadline):
    """Validate the complete observed structure independently of its digest."""
    _check_deadline(deadline)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= INPUT_LIMIT:
        raise ValueError('input_limit')
    endings = list(re.finditer(rb'(?m)^startxref\n(\d+)\n%%EOF\n', raw))
    if len(endings) != 1 or endings[0].end() != len(raw):
        raise ValueError('trailer_shape')
    start = int(endings[0].group(1))
    prefix = b'xref\n0 69\r\n'
    if raw[start:start + len(prefix)] != prefix:
        raise ValueError('classic_xref_profile')
    block = raw[start + len(prefix):]
    entries = []
    for object_id in range(69):
        _check_deadline(deadline)
        match = re.fullmatch(rb'(\d{10}) (\d{5}) ([fn])\r\n', block[object_id * 20:(object_id + 1) * 20])
        if not match:
            raise ValueError('xref_entry_shape')
        entries.append((int(match[1]), int(match[2]), match[3]))
    trailer = (b'trailer\n<<\n/Info 68 0 R\n/Root 1 0 R\n/Size 69\n>>\nstartxref\n'
               + str(start).encode('ascii') + b'\n%%EOF\n')
    if block[69 * 20:] != trailer or entries[0] != (0, 65535, b'f'):
        raise ValueError('trailer_profile')
    offsets = {}
    for object_id, (offset, generation, kind) in enumerate(entries[1:], 1):
        _check_deadline(deadline)
        if kind != b'n' or generation != 0 or offset in offsets or not 0 < offset < start:
            raise ValueError('object_map')
        header = f'\n{object_id} 0 obj\n'.encode('ascii')
        if raw[offset:offset + len(header)] != header:
            raise ValueError('object_header_offset')
        offsets[offset] = (object_id, generation)
    actual = list(re.finditer(rb'(?m)^(\d+) (\d+) obj\n', raw))
    if (len(actual) != 68 or {(m.start() - 1, int(m[1]), int(m[2])) for m in actual}
            != {(offset, obj, gen) for offset, (obj, gen) in offsets.items()}):
        raise ValueError('unindexed_or_duplicate_header')
    _check_deadline(deadline)
    mapping = [[offset, *offsets[offset]] for offset in sorted(offsets)]
    evidence = {
        'policy': POLICY, 'complete_original_sha256': hashlib.sha256(raw).hexdigest(),
        'classic_xref_offset': start, 'xref_size': 69, 'in_use_objects': 68,
        'verified_offsets_sha256': hashlib.sha256(json.dumps(mapping, separators=(',', ':')).encode()).hexdigest(),
        'cursor_delta_bytes': 1, 'prefix_hex': '0a', 'raw_bytes_rewritten': False,
        'xref_table_rewritten': False, 'other_parser_warnings_fatal': True,
    }
    _check_deadline(deadline)
    return offsets, evidence


def extract_chipmos_transcript_pages(raw, *, timeout_seconds=10):
    """Return all native text pages of the qualified original or fail closed.

    Complete coverage describes native text only; it does not certify images,
    reading order, translation accuracy or the source's conference assertions.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > INPUT_LIMIT:
        raise SourcePdfError('invalid_input')
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 10):
        raise SourcePdfError('invalid_timeout')
    deadline = time.monotonic() + float(timeout_seconds)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        _check_deadline(deadline)
        if digest != ORIGINAL_SHA256:
            raise SourcePdfError('invalid_pdf')
        command = [sys.executable, '-B', str(Path(__file__).with_name('chipmos_transcript_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _check_deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)  # Preserve the common typed failure.
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('xref_validation_evidence', None)
        _, expected = _qualify_xref(raw, deadline)
        # JSON comparison preserves bool/int distinctions in worker evidence.
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if result['page_count'] != 8:
            raise SourcePdfError('invalid_worker_result')
        result['xref_validation_evidence'] = expected
        _check_deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
