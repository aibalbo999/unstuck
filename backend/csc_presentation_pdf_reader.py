"""One qualified CSC original; native text is not visual validation."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time

from source_pdf_reader import SourcePdfError, _run_worker, _validate_result


ORIGINAL_SHA256 = 'e0f2551660c648e950242d8a8de0c40225d43c5c7409149788a721765e98dc05'
CHINESE_ORIGINAL_SHA256 = 'f801da2a4a8fa92512c1d4265c2a6a35c70164bcae909fea45837665a94883e4'
PROGRAM_SHA256 = '829a941f2606d6e47a8439516d61bc0e15a91c8a6c1e59a665a0890c45073da2'
CMAP_SHA256 = '4d23c9a23029456fdb85db42c0c89e688ad1f83196e02c452305783412938d9e'
POLICY = 'csc-20260923-exact-native-symbols.v1'
INPUT_LIMIT = 8 * 1024 * 1024
MAPPING = {'\uf0fc': '✓', '\uf0a7': '▪', '\uf06e': '■', '\uf075': '◆', '\uf0d8': '➢'}
OCCURRENCES = {'6': {'U+F0D8': 3},
 '7': {'U+F0D8': 2},
 '11': {'U+F0FC': 2},
 '12': {'U+F0FC': 2},
 '16': {'U+F0FC': 2},
 '19': {'U+F0D8': 3},
 '22': {'U+F06E': 3},
 '26': {'U+F06E': 2},
 '27': {'U+F075': 3},
 '32': {'U+F0A7': 3, 'U+F0FC': 2}}
PAGE_TEXT_SHA256 = ('7398b453420a572353ab95157a9e6f060724f1585b89420a11c1b076add9f2fe',
 'f2ebb2764d001919b558cd0d4ca4f13f4d0734093d012561ddd745017408e146',
 '85f286a0c3832523c3d325e8b8478a6860a6731540093b08fd7ca5d165e755cb',
 '8ec792a50def74e91626103044d7f72d9f33df93fcf69993467516d528aa5433',
 'fe78b023ccaac812c8a1a1a5b9cef0596d65a249f45abc15aed62a338423d604',
 'c8f72e8aab73b44f26dc84ed14ce28cfdc88cd1a2b518b0a62a48cfeddb71e26',
 '08c9f11f8390dba710b8d4358764de7e9c58e64d114f546f285ef0e795b2582e',
 '5526298fc819bacb23faf962ec1c08e98a99753e294b34cc26f7d4c28765c3ad',
 '15531cae265158fbf4b0267bfea206e048d3d4ce95dde2da1d4bcb84a4941f39',
 '5ccc78ab75971c5752c13131a0b587d7b13d3447d83de004e0bf338428c8b6a2',
 '1c3db8c92790238675d05c2450bf1fb481f83955c8970362148de3a967ceb474',
 '1682744976c86b09896095e9b03765ebb86d704ee57afe8f0bb995826d7fb4a9',
 '5e72a4608041edd869a833b9126e02ec76748af38cfa9ce6164a6d0b8bcc6190',
 '7f9924216accb3dd4abd8b0db7ee3bdee60541b958f750040556aaa9e30353fe',
 '35fb9cc10afb976e18b044f392935c111d24da9e9cc02069b7cd63a5583da3ac',
 '9f18bdc3bc784dcd931ef4d9e19b9df4ea60f9a6aecb3006a7fa4752a5a291ec',
 'a56e6b0e8f02e826a85f1f9fc1013e9dc5c59cd73e484efac293d5c6ed631825',
 'eb6ea643213c983e5273686f5265a136bece3ed0cc3eba6d7af3024f6f822a29',
 '0999d0705526090e840fd2150192db1bd28bf5cc27f57fc2ea14851997a73875',
 'ddd952a136447fde3da599fd0185cb7859958edca2731ee84ff7ee5b63c59aa6',
 '4e63687c348ebc40548208e8d10f87212b5ad8e14c2d6034085d1c55dc12a56b',
 'c582bb707bfff6f10782dc3ba4329a73a6a651bc5606f532022b07588c2eb9ef',
 '4562e84037e3a965d9804509233f3a7d84453a93a9ad0afed809d9f58261d43e',
 'e2c1a01d4a838367a1f8607e3a95c1b7e279dcc8cfd997bfb093b371f08ea380',
 '0845389935009123966833ea64316d4b5ce9a7581be2c5790d285e6c5999f661',
 '811d36e7e6d8718f7eeae65eea76ccb0d31f0ae254e628940a42a55152cae88b',
 '614acdd6b04ffb47efed93eb283fdb535a1a2720e87669ec28407ba436083b61',
 'bc04d891d1ca2a2744bf60252459a2346599ef2e3c069272cc54915e9ca83ec4',
 '1d178b3690b952a9070edebab47e115cc6cadcede15844c95458a2faf33abb7f',
 '4e2d856de294474a152323faf06a51392021ecd4b12e39ad8dd4320c3718754c',
 'e8cc2f7ca60d9a6b76b27703e938db67b00ca93b5e6e2a48da9a79602a7ca21e',
 'c4d0fe6e3eacc48b14b38f91a0a92a1b8ff30175085a1e1672be45f9c47db818',
 'cabdd48dcdee14cc0670d65b0a8a1cdc41ac3459a05a3e6922ce88bb248abaae',
 '4a0dc02bb44ba71701984726b1f98b2bbc70cebb70e31a68f4d9d800b2f2f499',
 'e3ad5679490d618f80a50d6a7bca0f13f9c93e13462c05c8c2d319549b78954e')

CHINESE_OCCURRENCES = {**OCCURRENCES, '26': {'U+F075': 2}}
CHINESE_PAGE_TEXT_SHA256 = (
 'f225622bffb73a96fbf66165cc51fc659df8841aa20b122faa4569c3edda9a49',
 '70c6bfba8b2c7f66ed046924a633ba2dd13712facc05d7493f58005538f24552',
 '16a17c04bc0e8c94e6b0083cce0939188443a965dfd22aafba32c372345c6e17',
 'f8d82d0f247402fde068237032df7f4074791aa13f7bac0837f470172e9af9f9',
 '65aca1d275898802fc6f6a3fb27c85a62943ba7b998c31f04e1368fbac18834a',
 '955ae69f04f1d1efd8dcf127b695cf452293f794cd12054cc173c06396451e53',
 'e40d2fef507c90b5876c73c2dcdb1274678431d30bd7f667667a4b0b7a46e109',
 '762b8ad7cb6ff4ffa65c03556600e55b687e2db54b453d19d069a17ace791903',
 '5c82303ed0099f34c892563993ddb6522e6680433ca90d70006bb0890bfb9746',
 '4031ca00e9a5dea89425e8df24e837b98fadeacc7a92806605ebdcd43b67d5dc',
 'd2043da2effe787f2def630438086c35af4f7fbd06dd072cebea3f25c507757c',
 'a6c0b113053f81fd29975557d1cddf63b8e715de4cf84df46bb480b2a914a8a9',
 'fd4d9b047d77d62c49e51720b9ede00a92fada7c6a3e3b322cfe9a0f00f34a7f',
 '3c66fc206b034dc950bf1fd2aa6e5d44242956927c589a18b504843240919449',
 '9e9a87777f7046f54f2a04ba15d34f688326464a156953fa5a07f32e6b14bba7',
 '1516384f2ed7bc1f5fa6e3ab3fa332ebc1e79b8a8161b4032b5b53373ebdf80b',
 '0fc6782d5a001ccc39d2a1b6813d4ab3c69694599a03c32d54e7a221bbba4cf3',
 '2250bbb53fb3481aaa9ba877a62fa89f8584985a894dc2d01f4f407f918ae4f8',
 '815ab3eea4b8f24363cdc2725f8788670c6b882e0310de7073d0937c890def09',
 'b115fe40afe00b0bb9520151473224722dd5853935ed8202c6e81e1f7ac0c726',
 '1d29759d4ac3c5640a2b61c0a1edd5e4737b044ef398628d31cd53f9cace6a1c',
 'b937ac715286642b53ec94360f7a07488c5f8d0d31f0a212fd4388c06a3b2e1a',
 '2a0f10dff2dcad905b343d3f7b8614ddd0c5e1f777459c6c2dbe23147be1f240',
 'c9e0b0437b5baaf7269fe3f0237403ba3e82908550901b95908b1e8b6187d0ce',
 'db3dd4e40369171c177094df419bb07847f6b689488d20b296ae595f9d94a40c',
 '74af25435d38e59cd7f1f2ce99392db959b2e9bf5eef4d5b7867a1494d7e3dd7',
 '4eb5c504cfed45218a039e2d85d56c65c2099e144bd98a1fdae6a6106276d47a',
 '51aed65359be58dcedf826ed2cda00feca47e7f4e9980df3becb4322a94ba130',
 '7f41df8178d313f2a8661a9cf1129947c168b8747df3e4ef70b98ea5db00ea59',
 '9ceb561df1bd60b7be9bdd3c39cc72edd86f33061e002b1403555e4f8b2c19d5',
 '479b804cc2bd7cfbccd3f0a88a66f2af0eeaf870dae2444b4dcf7513201ab08d',
 '94bbf5beedecacaf81a37c1b65bacdb0fe08df29838927c3bb8ef7dfa8f4359e',
 '3af862a21c3fa36efd600aa001ed13ada78a356673dbd0941635c79cd7808469',
 '1f9baa2e896cecac8f045bb9c2b6dacebe9691f97aa5393f7524474ec0104a65',
 'ac824e7277b75250249f864c4faf7bfad6dcabddcab062f67d5a00711e0e95c4')

PROFILES = {
    ORIGINAL_SHA256: {'occurrences': OCCURRENCES, 'page_text_sha256': PAGE_TEXT_SHA256},
    CHINESE_ORIGINAL_SHA256: {'occurrences': CHINESE_OCCURRENCES, 'page_text_sha256': CHINESE_PAGE_TEXT_SHA256},
}

def glyph_evidence(original_sha256=ORIGINAL_SHA256, occurrences=OCCURRENCES):
    return {
        'policy': POLICY, 'complete_original_sha256': original_sha256,
        'font_program_sha256': PROGRAM_SHA256, 'font_program_bytes': 29636,
        'cmap_sha256': CMAP_SHA256, 'cmap_bytes': 445,
        'source_font': 'Wingdings', 'encoding': 'Identity-H',
        'cid_to_gid_map': 'Identity',
        'mapping': [{'source_character':f'U+{ord(k):04X}', 'replacement_character':f'U+{ord(v):04X}'} for k,v in MAPPING.items()],
        'source_cids': {'U+F0FC':57,'U+F0A7':131,'U+F06E':132,'U+F075':139,'U+F0D8':190},
        'occurrences_by_page': {page:dict(counts) for page,counts in occurrences.items()},
        'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True,
        'other_parser_warnings_fatal': True, 'visual_semantics_verified': False,
    }


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def extract_csc_presentation_pages(raw, *, timeout_seconds=10):
    """Extract an exact qualified 35-page CSC original using guarded private child.

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
        profile = PROFILES.get(digest)
        if profile is None:
            raise SourcePdfError('invalid_pdf')
        command = [sys.executable, '-B', str(Path(__file__).with_name('csc_presentation_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('csc_glyph_evidence', None)
        profile = PROFILES[digest]
        expected = glyph_evidence(digest, profile['occurrences'])
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if (result['page_count'] != 35 or result['coverage_status'] != 'complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages']) != profile['page_text_sha256']):
            raise SourcePdfError('invalid_worker_result')
        result['csc_glyph_evidence'] = expected
        _deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
