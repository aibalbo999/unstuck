"""One exact KINIK presentation: complete native text, incomplete visual content."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from source_pdf_reader import SourcePdfError, _run_worker, _validate_result

ORIGINAL_SHA256 = '4490a76682ab9655cbe78c30736ede3749c31577c35eaa95ef187f7af8511d4c'
PROGRAM_SHA256 = '948df39aafd11e66ebef0f32d2104e7d118bb1bd2ace797c6bc4ac2bcdde7ef6'
CMAP_SHA256 = '8e195bdc478c3e70a67bdf9a06b43c08fd886b8af3d47066921364da4dfa4600'
INPUT_LIMIT = 8 * 1024 * 1024
MAPPING = {'\uf06c': '●', '\uf075': '◆'}
OCCURRENCES = {'4': {'U+F06C': 5}, '5': {'U+F06C': 3}, '6': {'U+F06C': 4}, '7': {'U+F06C': 1}, '10': {'U+F06C': 2}, '11': {'U+F06C': 3}, '12': {'U+F06C': 3}, '13': {'U+F075': 3}, '15': {'U+F075': 4}, '28': {'U+F06C': 1}, '29': {'U+F06C': 1}, '30': {'U+F06C': 1}, '31': {'U+F06C': 1}}
FRAGMENT_JOIN_SHA256 = {'5': '8e9592f9f1f003f51c0e3acef99b13a0fea56f879f215861c855f8dea5991039', '6': 'fe0ece86b86b5031b45c0f02b8d6fe60db132d0dc1e43a04402ce554807150ea', '7': 'bcb1fed4c6af33e8b683166f6fce2a5def95eccce2f037a05bf0bd8bb9fb1fcd'}
NATIVE_PAGE_TEXT_SHA256 = ('8a5ed090b58533fb0b024bf8a08a949499e0b368fe7a8aad0ea0d9e07ea5c4a3', '52f3ba447e2be16fb7288f755ce314d527c4795c698acec5e62c6854bb3725c5', '1b226d785cc0845303380fc70a437bb516adb314a15a3e6cd68cc8194b9fea57', '73cf40a1eedfe22ac823e9f5bceb55aaacf09d9f83b1da7d2cedae3aa4ac7dc6', '2b6785cec44e492ddf64d411f5fd81c52ab2e735520e15ce4e795bc94e1f82db', 'cfb1d7b36f76f48b93ca6f4bf90634354d34a5f92c1b0d1bc7dd2dbc40238782', '494b8ec1f08f38fd0acac8e86e0caab4d3f8b755913026b981a8cdc7e726b3ca', 'c8db779cfedca7fc593aff0ed99df653ca920112716aee5ec90e36edd3bcf245', '810c3a68f6687478604c7f90cf3d6e7a1a0262098b09b50d880e5b69ab1df4c4', '512c8dd0b87b6db6f145af3ebd7c81637fc136c389246e742c9ff130fd586e3b', 'c296995c64d57160a3c3b32384dc55e7a21ac76a234b899da8f3e21dc9331d13', 'f0a21a96803a207d20e6b7bfde5d0e354e4a1116e47019484cf9b5e273aea9a8', '6483dcda682c7d3b2935b7c6a3069e5c8f0e8a656956323c106b9ba024043854', '518d0fa9c78921f6c4ec3455a9e4d599939ce4f3ae400d62ce3dc5c011cfeaf7', '29e78e11762514a372c60f50e9a6793d3cee5a4f7de93f0dd9b4ecca870cedf0', '54b1189b7eb48ed81a0fb2a301e2a9f6fe2f8ececb5a15d4676e3b8b8e04cdae', 'd58bce656828983ed1a3c77e730551e1cb919b9d88defca705f94bd46a5ab1b9', '7ee29791fc17e986b97128845622b077fb45e349fdb80523fac9dba879b4ad60', '497ef86e768614cac66f9cba35abf1a860398eb67821e96f81c611f53c3cc95d', '544c8b288555f2648924fff364e478de6fc6bbb2b736bec349551e50458b6b63', 'a03378750b30300b35862495d7079c13c467a9d0ed8488aa200d2237c768ee1d', 'fe54fc5f56b58734f09bc54abadf66c36a12a49284a9ee8d62133fb15f14d7b9', '9681d35ebaf123d929c227517addde33527543111c0cda6ceafb4071b537ed9d', '1772fec463dc1b35b8b687afa347cf6e138e0725422c198e3ce796f5a9d16800', 'bbe5c91e73d384f648061c974158b04de67040e1c91179ec496af4367e5364ad', '0cfe7a2b92dcd8b8c1f7c6205d6a6f55283868a806064e6d35067a9061636bc4', 'b56d6d04e965321a5f44051476ce6a0de380c2ead540bf4ae5ddb1b6a98c6d1c', '78b9a5a8ff0c7176783c18978eca4752cb2ef0f5353ce9f2031afaf1531063e0', '873e4cd6ff8cb351d20e4585035345897f12b79e447fc30d41118ac89225556a', '8e638a92fac6cb015e63f4fa105f4b26b749c0b230abc8ab4c1b4b8294162229', '7524d852ef9fee501e22d8db4704fc356b597d715f7301b19f5a29548a6bed7c', 'f26fb9b5e05805f2ed94e31950974a6d427393b0087b8adfedee75f2bbba1a13', '8def9c9088f4f160162125f26e1a98b465032d6e5d2f4afb68ff445154419085', 'c4791c2f421047dc03582349fed2b785b6f75a29af0f96585f0fb4f77d2032f1', '2f0d84799e9de01cd05779f43aa8a259e67cf3f5c548211ef04e51c61a15f29d', '9025117216c655f393bf96866e4f52aaf3aa8a8e1046b44a67370b60017c3076')
PAGE_TEXT_SHA256 = ('8a5ed090b58533fb0b024bf8a08a949499e0b368fe7a8aad0ea0d9e07ea5c4a3', '52f3ba447e2be16fb7288f755ce314d527c4795c698acec5e62c6854bb3725c5', '1b226d785cc0845303380fc70a437bb516adb314a15a3e6cd68cc8194b9fea57', 'cf071a2351e7ad282c02ae982fdf9e58ebff296882a90e8651d3e22b659464e8', '7c22ca62987a44431991ca40833714d91cf753685bc4216be2dcbde30c5c2f26', 'b2eccfc86c63c451dad1aa689bb15e927657e5ff62b665c28db603e67a9a3b02', 'cdf8ecc2e7734586cce5a7120d8a10fdf41f92b7781ab6db78a8b1f3159c308e', 'c8db779cfedca7fc593aff0ed99df653ca920112716aee5ec90e36edd3bcf245', '810c3a68f6687478604c7f90cf3d6e7a1a0262098b09b50d880e5b69ab1df4c4', 'bdee75d4e70d27b4b9be6f818dc8b3b9305e77f24a2ce1e809cb97202a58a262', '96616ad165c313c6e941694dc1dd2e8d938fc7ea42e2c408c0e5678c48edf1b7', '696a7c21273ee071c90c40508b44bc485d249fcf16363b95745bafddf14c0b97', '2833be3b6c142f60e35f93b8ee3711192d9e4586a248de81080f8de27600910e', '518d0fa9c78921f6c4ec3455a9e4d599939ce4f3ae400d62ce3dc5c011cfeaf7', 'ae7f0f7dc3ff778b9e87b76136d3515bf634fea84cd261407f0acf639d557165', '54b1189b7eb48ed81a0fb2a301e2a9f6fe2f8ececb5a15d4676e3b8b8e04cdae', 'd58bce656828983ed1a3c77e730551e1cb919b9d88defca705f94bd46a5ab1b9', '7ee29791fc17e986b97128845622b077fb45e349fdb80523fac9dba879b4ad60', '497ef86e768614cac66f9cba35abf1a860398eb67821e96f81c611f53c3cc95d', '544c8b288555f2648924fff364e478de6fc6bbb2b736bec349551e50458b6b63', 'a03378750b30300b35862495d7079c13c467a9d0ed8488aa200d2237c768ee1d', 'fe54fc5f56b58734f09bc54abadf66c36a12a49284a9ee8d62133fb15f14d7b9', '9681d35ebaf123d929c227517addde33527543111c0cda6ceafb4071b537ed9d', '1772fec463dc1b35b8b687afa347cf6e138e0725422c198e3ce796f5a9d16800', 'bbe5c91e73d384f648061c974158b04de67040e1c91179ec496af4367e5364ad', '0cfe7a2b92dcd8b8c1f7c6205d6a6f55283868a806064e6d35067a9061636bc4', 'b56d6d04e965321a5f44051476ce6a0de380c2ead540bf4ae5ddb1b6a98c6d1c', 'ebe55a12b3b0b6b3307ab581dfd271604ad5e6933a2f71a432c81b606f18f646', 'f2cb187aa853ed421edcee7e4b764f7838e1715957dccc0d25d216a1c254ec1e', '37b2db72b4e1749b14e1c560ea33165bb5d1fcb2bb52f2f49897db4f7adc060e', 'a83665dd446f1940db885557947502296687a87507367fd03b4782d353158fba', 'f26fb9b5e05805f2ed94e31950974a6d427393b0087b8adfedee75f2bbba1a13', '8def9c9088f4f160162125f26e1a98b465032d6e5d2f4afb68ff445154419085', 'c4791c2f421047dc03582349fed2b785b6f75a29af0f96585f0fb4f77d2032f1', '2f0d84799e9de01cd05779f43aa8a259e67cf3f5c548211ef04e51c61a15f29d', '9025117216c655f393bf96866e4f52aaf3aa8a8e1046b44a67370b60017c3076')
_GLYPH_EVIDENCE = {'policy': 'kinik-2026q2-exact-native-symbols.v1', 'complete_original_sha256': '4490a76682ab9655cbe78c30736ede3749c31577c35eaa95ef187f7af8511d4c', 'font_program_sha256': '948df39aafd11e66ebef0f32d2104e7d118bb1bd2ace797c6bc4ac2bcdde7ef6', 'font_program_bytes': 29216, 'font_program_encoded_sha256': 'cea9bb72bfe35dfa57a554af31a18aea7fc3cedc3b4d100dc6a6054a8006e0f2', 'font_program_encoded_bytes': 14066, 'cmap_sha256': '8e195bdc478c3e70a67bdf9a06b43c08fd886b8af3d47066921364da4dfa4600', 'cmap_bytes': 351, 'cmap_encoded_sha256': '0e943d9c208af6b20fefe50c21026b69bca016f6576dd342d21506986471798e', 'cmap_encoded_bytes': 234, 'source_font': 'ABCDEE+Wingdings', 'encoding': 'Identity-H', 'cid_to_gid_map': 'Identity', 'source_cids': {'U+F06C': 122, 'U+F075': 139}, 'mapping': [{'source_character': 'U+F06C', 'replacement_character': 'U+25CF'}, {'source_character': 'U+F075', 'replacement_character': 'U+25C6'}], 'decomposed_outline_sha256': {'U+F06C': 'f2e0c2f4c354ef96ce6662965f1ca3c46103504bafafb94dfd1afdcbb321931b', 'U+F075': 'fc2779b26b1c60315aeacf579bbeac606fc5a8add621c5ec46e88390e2314a88'}, 'occurrences_by_page': {'4': {'U+F06C': 5}, '5': {'U+F06C': 3}, '6': {'U+F06C': 4}, '7': {'U+F06C': 1}, '10': {'U+F06C': 2}, '11': {'U+F06C': 3}, '12': {'U+F06C': 3}, '13': {'U+F075': 3}, '15': {'U+F075': 4}, '28': {'U+F06C': 1}, '29': {'U+F06C': 1}, '30': {'U+F06C': 1}, '31': {'U+F06C': 1}}, 'qualified_fragment_join_sha256': {'5': '8e9592f9f1f003f51c0e3acef99b13a0fea56f879f215861c855f8dea5991039', '6': 'fe0ece86b86b5031b45c0f02b8d6fe60db132d0dc1e43a04402ce554807150ea', '7': 'bcb1fed4c6af33e8b683166f6fce2a5def95eccce2f037a05bf0bd8bb9fb1fcd'}, 'fragment_join_difference_reason': 'On exactly pages 5/6/7 the pinned parser visitor includes repeated table-form text; preserve original extract_text output and replace only independently qualified symbol characters.', 'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True, 'other_parser_warnings_fatal': True, 'visual_semantics_verified': False}

def glyph_evidence():
    """Fresh exact-original contract; returning it does not qualify caller bytes."""
    return copy.deepcopy(_GLYPH_EVIDENCE)


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourcePdfError('timeout')


def extract_kinik_presentation_pages(raw, *, timeout_seconds=10):
    """Keep all 36 native pages, including original ambiguous periods and image-only page 18."""
    if not isinstance(raw, bytes) or not raw or len(raw) > INPUT_LIMIT:
        raise SourcePdfError('invalid_input')
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 10:
        raise SourcePdfError('invalid_timeout')
    deadline = time.monotonic() + float(timeout_seconds)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        _deadline(deadline)
        if digest != ORIGINAL_SHA256:
            raise SourcePdfError('invalid_pdf')
        command = [sys.executable, '-B', str(Path(__file__).with_name('kinik_presentation_pdf_worker.py')), str(deadline)]
        output = _run_worker(raw, deadline, worker_command=command)
        _deadline(deadline)
        value = json.loads(output)
        if isinstance(value, dict) and set(value) == {'error'}:
            _validate_result(value, digest)
        if not isinstance(value, dict):
            raise SourcePdfError('invalid_worker_result')
        proof = value.pop('kinik_glyph_evidence', None)
        expected = glyph_evidence()
        if json.dumps(proof, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise SourcePdfError('invalid_worker_result')
        result = _validate_result(value, digest)
        if (result['page_count'] != 36 or result['coverage_status'] != 'complete'
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages']) != PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['kinik_glyph_evidence'] = expected
        _deadline(deadline)
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
