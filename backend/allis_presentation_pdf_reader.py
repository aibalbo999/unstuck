"""One qualified Allis original; native text is not visual validation."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time

from source_pdf_reader import SourcePdfError, _run_worker, _validate_result


ORIGINAL_SHA256 = 'ceb64fce96a13c58e113f132ca2bc98d6efa77f5b4c4f2191054bea5fdefd312'
PROGRAM_SHA256 = '99a9454ba34e6b3f2be11305a6f02257b6723b998bc9dd98b678a9d6898172bc'
CMAP_SHA256 = '31553e7a2ab0aedcd557c06d1f6b2cfeb61aad550938dbd93bc716feacc03d16'
POLICY = 'allis-20260827-exact-native-symbols.v1'
INPUT_LIMIT = 8 * 1024 * 1024
MAPPING = {'\uf06c': '●', '\uf06e': '■', '\uf0d8': '➢'}
OCCURRENCES = {'11': {'U+F06C': 2},
 '17': {'U+F06E': 1},
 '2': {'U+F06E': 2},
 '3': {'U+F0D8': 10},
 '6': {'U+F0D8': 9},
 '9': {'U+F06E': 1}}
PAGE_TEXT_SHA256 = ('f923f2486472e6e63bfe765033d0997ae0872574b582c4d87d904536645abdee',
 '44587a68b1cad07e83cb2ac4c452e8564494b0d39be5a51fd44c2004af256d36',
 'a6e4cb03e682b0b93bd7e2522809d30b2ad0407a669755f81e8d6bfb46995aec',
 '925f98c97b6c57f4c19b22eb7e0028eb30599f3a69e515c3df4b489915432d27',
 '2c1d04da313fc4d3d13365c3c5ecd3cfc101cf548fc0818e6e6c075a084bab9f',
 '83b51f37dc66bbfff682a5ee44ff509055ba9aacadf52a5e62519aa359c840d5',
 'd3ddd61acce645c191a2afd3bcf4d2cc8d66fc26c5c5cb1eecccd25a93190159',
 'd10c676214c9aec56aab548c185ff9d7db8eb4177b9682eeccb28e7dd76baf82',
 '6c0e39afd2f4f06320b134ab3693cf2cddbd5ede2f56c72ceffd83ded547fd26',
 '86520ec045508dfc3f48a5f7e1d65be7a42f4f33b16569747d8a76cce721d58e',
 '8f1bbc772ee9f3ac03e148aa28d1bdac0f982e2842439c0a3733623cb48e1a98',
 '076e371e84aac7f3e6720e2b04c6c74067607eed811e9df379ba06b1217a85bc',
 '234aac7c6cd43592474210634b605cd9890793a5cdd302c9b6508cfe157b9f06',
 'c9224631d843d7c0ac243379be93705c5bd3f3ba625c8f56e91f6bd8a77641f2',
 '24a35e22f72adaf14e31b48415fb1df8f0d67f6204f6309bee983d603c2862b2',
 'a77dff37161947190bfcbbec5e41c404f5723e8cc13bf15bcd6e7203cfddd800',
 'a7beed833584a7c71cb9f800620f6bdc2457c5f0914ce53b255da86293778adc',
 '8d1b947accfa5bddd9598f8688db11a94e78cedacfda65b84b6d7518beeed786',
 'fa3f8d6e8ea789dd25e461da72d0c914fea74345282ce52a0c7f18095cd8a690',
 '42fa26a63406a4020c051087be8ac28ada7bbb0a2005271c684adb55c59f706d',
 '21af1f54f5b74ca606c7fa4f26739cb36dca9d7644cb91fdb80c23ae63b0b7c7',
 '5cbd51862be787c3855c6d8b973ccea893e01382da863100cb37d508e336c114',
 'c198592a40ec2109ebab17ed90a40089482b377e9cb7b10b3d3c8f1b9d307cb4',
 'c4608984347872ba8c7c770664ed015e44c7192cb40133fa8e92542e26512f79',
 'c245a369e4b455b3b2ea674779549ca9399392fbbbeeb8931d4713a871fc6f15',
 'b2d8d4149af8b2049d41eef28f5feff4b953d518ab48c750eda26fc557a36587',
 'c3fedb71f7c62a7ec91a6fcf89127ee59fcc1a002f76bb8f55aa400d16727d65',
 'cc07332851f07fad8d4f26b32a213dbc5258622529a832968691c60de69c0863',
 '3f745d30e7b45fea5d247ea10c9edcdfedce4919aa549fd6e2b34d6520514c09')

def glyph_evidence():
    return {
        'policy': POLICY, 'complete_original_sha256': ORIGINAL_SHA256,
        'font_program_sha256': PROGRAM_SHA256, 'font_program_bytes': 6371,
        'cmap_sha256': CMAP_SHA256, 'cmap_bytes': 366,
        'source_font': 'GEJVSC+Wingdings-Regular', 'encoding': 'Identity-H',
        'cid_to_gid_map': 'Identity',
        'mapping': [{'source_character':f'U+{ord(k):04X}', 'replacement_character':f'U+{ord(v):04X}'} for k,v in MAPPING.items()],
        'source_cids': {'U+F06C':122,'U+F06E':132,'U+F0D8':190},
        'occurrences_by_page': {page:dict(counts) for page,counts in OCCURRENCES.items()},
        'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True,
        'other_parser_warnings_fatal': True, 'visual_semantics_verified': False,
    }


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def extract_allis_presentation_pages(raw, *, timeout_seconds=10):
    """Extract the exact 29-page Chinese original using guarded private child.

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
        command = [sys.executable, '-B', str(Path(__file__).with_name('allis_presentation_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('allis_glyph_evidence', None)
        expected = glyph_evidence()
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if (result['page_count'] != 29 or result['coverage_status'] != 'complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages']) != PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['allis_glyph_evidence'] = expected
        _deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
