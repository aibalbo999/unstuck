"""One qualified Chinese STI original; native text is not visual validation."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time

from source_pdf_reader import SourcePdfError, _run_worker, _validate_result

ORIGINAL_SHA256 = '61a4dececbdb1a30bb4ea6529de24001b4cdf10a26e8a33a85f4feb4378c6e0b'
PROGRAM_SHA256 = 'd4453ea5b93569672519c451ec6623db68cf4fbe53d282413366f060affdefc0'
CMAP_SHA256 = '7e29b156cedaf49bc5951ea216931bbd1e425540b8d5dc3f996678a8f23dc4b3'
POLICY = 'sti-20260805-exact-native-hollow-square.v1'
INPUT_LIMIT = 8 * 1024 * 1024
# Independently captured native pages; only three standalone U+F070 -> U+25A1.
PAGE_TEXT_SHA256 = (
    'b853e15ad04d8b8d8634d33dea04fce5a798d8f51e15b8599c87518d2d587aed',
    '170f721b81bfd730e32f4a23ccf38c7db163cec168e856738c85de2a2fa9bd1a',
    'bdcfc36089f0850ad00a81db66c9d2a60ca4d5ecb144e8ceadcb651de494adaa',
    'd5e64d1b19435aab3401528d7fa4bdb777ca0e49f340e63d70b124dfb00a9091',
    'e90eb265acc9398d855edf96048bbe2ae2352b1d94d34d9663c73aaac85babdb',
    'bb9f9576c3e3d63457a3bf6f1165965016177b24fe905d47cd79d55bdb1f646d',
    '538f7bd0fcc4ba737e501c5aaa961b24c37295192a58a88561538d6c70aad7c1',
    'c22e310e376c3487ce459fbf8d74b8d6224afa9263990107aebe86c39e0372c6',
    '5169a794067fbc004cbc1bc2a1a41c0576ad263b5b13594d4a8ae24282be7d78',
    'b014b26d4de08440c065cb1afd65ab4d6428f42c688d0e87ba7fd5662c5592f5',
    'a98229eaa5ef7a6b3d00d9e529f6b82bcdab1738ece884d30deea70613f8a3a6',
    '255d618596c30a4951f23e7ba46daed989ac834078d321b2cd94fe1f941f6031',
    '89d6a9337e62782fb8fcf2508e87c3c9e291043c773862ba26e4a88aa43a5b9a',
    '1c89a3311acdaf1990fb8c9e4a99622401c1cfcc4d76ffbb2c2d63e563437ae6',
    '267f49316e542ad36a9e7675373003902449687a1ca4f71fabd0ae47385b00f6',
    '2b08722b6983d109887f522708fb0d968b5d02151595742d125b0567197408ec',
    '75cef5320549b3480281f4a89125a242a0493c611c2a50d39b66082dd4dd2f28',
    '67b7d5cad15e82df30a65623181d6feb676a54be23eca9e0c0489109c7abf7e5',
    '9ef2d07e683dcad1394c2f55c47bc42d28cad0a71bd20fe9cc11009313d57691',
    'a11fbed5f8cd8060ab185ed218c10db5f8978fdba14f178324a5def3351d11d9',
    'b145f98b47d6c377adf6cbaea72bdb0bbee272caec25296d76bb2d8aca81610a',
    '48b49fcb272851b9a31f0ea53753d75f0d743a0ca6ceb88648e6c1ff44241a06',
    'fb44c8d54f41b28a1cf1ac6de97830907e71aae6bef7c8f26bfdfc3af153a1bd',
    '4b9e117cc8566bd210870f4bf46ea0d7ffba4c0af4b5dfb42deedd64bcc1424d',
    '8081ffb837117768621063d440d916e2345c4a1c6fbd2fb70be3032af5055cbc',
    '15d5051777fedcd5c9f8db0bacca7af44d24890e30f4e649edfe5635f6058f84',
    '4c5f7a6a08a459e6b5221c42d4f16f92a20e517ba62528168c9264675f5bc609',
    '6faccd0bf2f982bc5382ce65d2621f35a94316cf05cd1d750393f95d94419892',
    '7dc7ca655d9f7a660a61f3c176fa80a66d965a35d3f18e32082b35240e865d1f',
    '833c4914559c520044a8a041bed6e4c75b3ef7849d8307ef46103c07bdcbd412',
    'a8efa44241a76f71ce1f8db3e5f15fcda8091b6311895a6828e133bbe8d7a88b',
    'f190228f8d37c70c9e7b13fb148bbabbfb8e2778824457b0c1b1e90f53a21c2c',
    'aa737747a1709296c9330b309e5db5c2dceaa23d4b2e2371ba046329cdb9fa99',
    '842bafe5426d99c7dbed3ea77539c5124710184e98cb2ca89cc9a007233c8c9f',
    'b0e3bf7864daaf3ce8e8acf4d536be08d1a2aab01ef6c9678d7f026eab474c85',
    '8e26961997e9caa69bd6576946edc7afbf2986f07d2699474496c853f34acaf5',
    '2ec6eacef244d62256322735b29bca7c4a2caa26780a0fd99ec5b2504142b88a',
    '874294a21b2c3e3f4ec6c2186588583502bb45f4621ee8dda8e6cf497342407a',
    '1aaf00980fc66b015645cc862e131db4a33743e3d570c8dc38448c33bc7cc330',
    'f1df611de956adc00146243903cd89ebf4668edd541004206c639a0028fff72c',
    '474b4aabccc3bc42fa4ab11e0abdb748ae4ea9fd8d72aef0ab233255638611f9',
    'bc7b909510398f8349dcc94c556f77df7343a3fe20923ce4949ac2c34495f41b',
    '3d1f7eb4432070ce77bca86442e11f0462d7ec8060ebed30b9321364743efb6a',
    '140bcae4f6863b657d8d422f6f95dad6e699d23f4d5950d4796aff21ed069d7e',
)


def glyph_evidence():
    return {
        'policy': POLICY, 'complete_original_sha256': ORIGINAL_SHA256,
        'font_program_sha256': PROGRAM_SHA256, 'font_program_bytes': 14348,
        'cmap_sha256': CMAP_SHA256, 'cmap_bytes': 351,
        'source_font': 'Wingdings-Regular', 'encoding': 'Identity-H',
        'cid_to_gid_map': 'Identity', 'source_cid': 135, 'glyph_id': 135,
        'source_character': 'U+F070', 'replacement_character': 'U+25A1',
        'qualified_outline_contours': [
            [[469, 296], [1357, 296], [1357, 1184], [469, 1184]],
            [[173, 0], [173, 1480], [1653, 1480], [1653, 0]],
        ],
        'opposite_contour_winding': True,
        'outline_closed': True, 'occurrences_by_page': {'5': 3},
        'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True,
        'other_parser_warnings_fatal': True, 'visual_semantics_verified': False,
    }


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def extract_sti_presentation_pages(raw, *, timeout_seconds=10):
    """Extract the exact 44-page Chinese original using guarded private child.

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
        command = [sys.executable, '-B', str(Path(__file__).with_name('sti_presentation_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('sti_glyph_evidence', None)
        expected = glyph_evidence()
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if (result['page_count'] != 44 or result['coverage_status'] != 'complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages']) != PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['sti_glyph_evidence'] = expected
        _deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
