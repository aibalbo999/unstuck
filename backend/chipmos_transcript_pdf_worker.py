"""Private exact-original cursor adapter; all generic parser guards stay active."""
from __future__ import annotations

import hashlib
import time

import source_pdf_worker as common
from chipmos_transcript_pdf_reader import ORIGINAL_SHA256, _qualify_xref


def _extract(raw, deadline):
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise common._Failure('invalid_pdf')
    try:
        import pypdf
    except ImportError:
        raise common._Failure('parser_unavailable') from None
    base = pypdf.PdfReader
    proof = None

    class QualifiedReader(base):
        def __init__(self, stream, *args, **kwargs):
            nonlocal proof
            if kwargs.get('strict') is not True or stream.getvalue() != raw:
                raise common._Failure('invalid_pdf')
            self._offsets, proof = _qualify_xref(raw, deadline)
            super().__init__(stream, *args, **kwargs)

        def read_object_header(self, stream):
            if time.monotonic() >= deadline:
                raise common._Failure('timeout')
            offset = stream.tell()
            if offset not in self._offsets or stream.read(1) != b'\n':
                raise common._Failure('invalid_pdf')
            # Only a proven single leading LF is consumed. Original parser
            # handles the exact header; its warning handler is not replaced.
            actual = super().read_object_header(stream)
            if actual != self._offsets[offset]:
                raise common._Failure('invalid_pdf')
            return actual

    try:
        pypdf.PdfReader = QualifiedReader
        result = _GENERIC_EXTRACT(raw, deadline)
    finally:
        pypdf.PdfReader = base
    if time.monotonic() >= deadline:
        raise common._Failure('timeout')
    if proof is None or result['page_count'] != 8:
        raise common._Failure('invalid_pdf')
    result['xref_validation_evidence'] = proof
    return result


_GENERIC_EXTRACT = common._extract

if __name__ == '__main__':
    # Same main runs CPU/core/file-size limits before reading input and parsing.
    common._extract = _extract
    common.main()
