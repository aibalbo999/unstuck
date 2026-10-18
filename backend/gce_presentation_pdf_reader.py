"""One qualified GCE original; native text is not visual validation."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time

from source_pdf_reader import SourcePdfError, _run_worker, _validate_result


ORIGINAL_SHA256 = '5cf45269fd71405896244573487fff93966ca6b68514d611993bfb7e8cfe315d'
PROGRAM_SHA256 = 'bd542fdbf46b75e69f151bea69fd8d25ecf2aa4e5812ff95c8648febb2c96218'
CMAP_SHA256 = 'd108a68ee070eb22a2ed9b833eca548c508e2e372352e67d780d64659228a2f2'
POLICY = 'gce-20260828-exact-native-symbols.v1'
INPUT_LIMIT = 8 * 1024 * 1024
MAPPING = {'\uf0d8': '➢'}
OCCURRENCES = {'3': {'U+F0D8': 6}}
PAGE_TEXT_SHA256 = ('2e609cb19cab4fc019ea145ddd62ea9f60b541b83c442e227c3fda5d1fdb6af8', 'ef9227ba88981137cd08474a325194e152d48e0ed0b0391756f1d10e97df7c67', '246a6bd12f81e027632675e245f20ef19f5a5a7342d6e37a3bc811a9b8e42ded', '9201a9307d84eaa1c1c12b7dad0d3924e39fc37d02e0e26f868534aaa38eed2b', '86b59d9fa153fb17c4c426c4998d536cbfdf638e2a5f3757ced75ebe0ce5aa3a', 'd4451dd0a7949c3396e34bcc4346e3d4b69c90cb42377c7b881c47bebc5364fe', '49bda339d090800bb8459ce9ef8718638466fd1af208ca380ca36c50d444b585', 'f1ab15ef111f09168dccd30726162af46548d62d259650ef2183cb0366e28876', '465e74e7d0dc44db5c62708a6813854d39a29ce5cda6b0b7ad459df48e9bbd8d', '03024e30187b12834e398f7a969b5bfacf9e065ea0340a3c52903c4ad2af5085', '4ca105270a18a6c2c18cbb7e1253a7c7a0628a444985c4fe8c9ff2074259a7f6')

def glyph_evidence():
    return {
        'policy': POLICY, 'complete_original_sha256': ORIGINAL_SHA256,
        'font_program_sha256': PROGRAM_SHA256, 'font_program_bytes': 29328,
        'cmap_sha256': CMAP_SHA256, 'cmap_bytes': 337,
        'source_font': 'ABCDEE+Wingdings', 'encoding': 'Identity-H',
        'cid_to_gid_map': 'Identity',
        'font_program_encoded_sha256': '01a58698cca67a7bcbf10cb3ca9c1ce54958955d07a987bc97fc838f7cef3330',
        'cmap_encoded_sha256': 'a05a18fc20c7d5cd0343bb66e70413a4892f5fe07b01699b5f453a1ae24057fb',
        'decomposed_outline_sha256': 'a399154201b8d1f5a36833d75df4666f8328bebf0504ac64a8f80d4b5a105be9',
        'mapping': [{'source_character':f'U+{ord(k):04X}', 'replacement_character':f'U+{ord(v):04X}'} for k,v in MAPPING.items()],
        'source_cids': {'U+F0D8':190},
        'occurrences_by_page': {page:dict(counts) for page,counts in OCCURRENCES.items()},
        'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True,
        'other_parser_warnings_fatal': True, 'visual_semantics_verified': False,
    }


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def extract_gce_presentation_pages(raw, *, timeout_seconds=10):
    """Extract the exact 11-page English original using guarded private child.

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
        command = [sys.executable, '-B', str(Path(__file__).with_name('gce_presentation_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('gce_glyph_evidence', None)
        expected = glyph_evidence()
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if (result['page_count'] != 11 or result['coverage_status'] != 'complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages']) != PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['gce_glyph_evidence'] = expected
        _deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
