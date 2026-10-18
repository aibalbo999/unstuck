"""One qualified English Sigurd original; native text is not visual validation."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time

from source_pdf_reader import SourcePdfError, _run_worker, _validate_result

ORIGINAL_SHA256 = '2e90848f7ad58715bf828870749eed8bf9f14ebcf47a9914e022324f56812aee'
PROGRAM_SHA256 = 'f02eb1e139aff8a12abc432e8063d11b2ee0acb4dd6ee49c4800f40f1148a2d7'
CMAP_SHA256 = 'e03dd673c6523fe47012f09b187e236a7058fe2bad839a018f099c3256e8febc'
POLICY = 'sigurd-20261006-exact-native-diamond.v1'
INPUT_LIMIT = 8 * 1024 * 1024
# Independently captured native pages; only ten standalone U+F075 -> U+25C6.
PAGE_TEXT_SHA256 = (
    'df982367863048d64dc9244e97df985e8bc7918347d471d2f58a69f5aa0d85f4',
    'eba599f3a8b4028958f2f9e0cecfe023d182f1e40fea460e53251411541e6a30',
    '423799a1752bb5b098c42870b2b84d7c2a4ca5ddfb8830bcc3e20578361b4444',
    'aa46fa2a354563db36511ae5706673ee0e882449f628dcde9a80fa344a4f53c7',
    'f505bafd9fb31979cbc901c81c7f7ec6874d10660adad4d7901ea5df6b38ea09',
    '503157c379549b6568d4c6b7ad53397015ec1e61cad22f62ad7fc7374bb7b4cb',
    '9f7b8f571b395ea59b23e935eb9fe5677b7124f6bccd631085b158597c4cf111',
    'af00efbbc874249b0e78dc5eba53a1e5c344f7d848cb6eb777eb611dbd85837b',
    '2633e44a84ee4cc60a7f61e11913e74577d86ce40196c6d3f2467176bb0a4f47',
    'ee6491e46df6b4afcbf2ee1c82e926c2f31c78b29335274cbc766c95c4fcf1fb',
    '629640d1ac960697804c11bd3bf676dbc5712f87021fae3ba45435a3105545ca',
    '78c7a475e6f2acd7353fc6a5d5e59bf5ea664e04b6e1352403ad78c070d9c9e2',
    'f1f170d26b34439cc1c80e78b7b5aafa27ae73d7ac62d760cfd47e9b6070d8a0',
    'ebe1a784b69a64aa12398802bfefc7b84e1047101296cd673a05beb83ce1bbcc',
    '5f75143d89e996db2409039633ea7b349e36c476b47bedc4b26d05399a093a49',
    '36ac3f81db4008df0fc85febb847c1c2dc84edc8c9deb44b980f942a65de4f01',
    'cc0916f87942a9b8fc2765968393ddb7af1d04499c578967547a094f43adf437',
    'ff1a3708a7a37cad24b14d58a6a46eebe21d0009eab6ac832090acb862724370',
    '47249d740f912f9c64c48452f4b6075f454f6c36354d204bffb09a3b2cbe86e5',
    '00d535475461e7500d9be0a115def86f62ceab48bf8224e479b2d8a2e3f21279',
    'f6a006bb8ce3e9086356aeeb53a07a826dca87a6a61dcaeadf227317d4226129',
    '85fe108cd6323cfdf4fcc993fc1aaa253651729b7ea347ce806585967a24d2d9',
    'df89a63d4a7bf63b7b9d01451c1701fc3b17b5eb51f58a0508d0055ebc5f3fcd',
)


def glyph_evidence():
    return {
        'policy': POLICY, 'complete_original_sha256': ORIGINAL_SHA256,
        'font_program_sha256': PROGRAM_SHA256, 'font_program_bytes': 29136,
        'cmap_sha256': CMAP_SHA256, 'cmap_bytes': 337,
        'source_font': 'Wingdings-Regular', 'encoding': 'Identity-H',
        'cid_to_gid_map': 'Identity', 'source_cid': 139, 'glyph_id': 139,
        'source_character': 'U+F075', 'replacement_character': 'U+25C6',
        'qualified_outline': [[173, 740], [1010, 1578], [1848, 740], [1010, -97]],
        'outline_closed': True, 'occurrences_by_page': {'16': 4, '19': 5, '20': 1},
        'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True,
        'other_parser_warnings_fatal': True, 'visual_semantics_verified': False,
    }


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def extract_sigurd_presentation_pages(raw, *, timeout_seconds=10):
    """Extract the exact 23-page English original using guarded private child.

    Completeness concerns native text. Charts, image content, reading order,
    financial claims and future statements retain their original limitations.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > INPUT_LIMIT:
        raise SourcePdfError('invalid_input')
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 10):
        raise SourcePdfError('invalid_timeout')
    deadline = time.monotonic() + float(timeout_seconds)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        _deadline(deadline)
        if digest != ORIGINAL_SHA256:
            raise SourcePdfError('invalid_pdf')
        command = [sys.executable, '-B', str(Path(__file__).with_name('sigurd_presentation_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('sigurd_glyph_evidence', None)
        expected = glyph_evidence()
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if (result['page_count'] != 23 or result['coverage_status'] != 'complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages']) != PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['sigurd_glyph_evidence'] = expected
        _deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
