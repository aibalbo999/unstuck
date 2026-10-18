"""Exact FEIB original and whole-page qualification for the shared MOPS route.

No transport, cache, ledger, clock mutation, OCR or financial-field derivation.
"""
from copy import deepcopy
from hashlib import sha256
import json
import math

CONTENT_SHA256 = '6dc27099b374d06ba9bbf993980f04e2bce05199f54140d159c169c437ba2f8e'
PAGE_TEXT_SHA256 = ('b2ef97ca554be72d5efd3e62a05ea19abc797dd888d049b62c33a092305d3a69', 'b64bc89c5f5e10c156f11c37ce190af6a12952eed64da5e31a52aecad9b3d14d', '9d7a397abd8ff635a24856ed9e73d77444d601b729c9727148e4edf17bda5ade', 'fa681a4959f8047f8d82e9e2e584edf282c829dea4b01c8378cc62eb8c566747', 'ddfc6f27dfe038f36043b64d2a7b18372bd37839cd6b63c79881a4d351262100', 'd5a3496da8a1a6eab556052e738e9acec9a9e28422976efeb468b2b6a000c639', 'c506b0174de78ee22170a7b87ffb8ac5c7ceecee5417a13d462375bda0c75c59', '8d1325c9d8e94945ce311b206c4d4648439d5cb65d330f8cbeaf91eac5931982', '3cbd5282d9d601806a6bebf267ff5bab1427593d9d434446742d987626747fbc', '90c4ac532ee2e4ead632be7fb642232e09d53429fe9e66dcd96bbe299ca5a269', 'dbdc5e47709c7af68244d1ef9e0b9970ed0ad1ded1ca7873b127d14f12e460ed', '8f1c77f128ea0d3f28914f37c57a3d3a7ef4d650a728b1365bdda9aeff4550a2', 'ac9290cdb0672f5528aff12491874895f6e138244e4e1b4b48a6597250584989', '76d079c61e3928090d0b808977aabcdcf09a0bc64f554bf85e6285b3cf88e16b', 'cca1e8761495a2cc0f639828e2838e2c028ea7fcbc60ce4ea378cf4d1fe87d92', '06e83ca2804a1b7b65236276bf9eb7dde5509d4684778593c184c434d884c76b', 'fe7080c24f3c609a1fe4ed1f43028261d1ce0b461e5fb21829a4638cfcfab73d', '728cb342359f887d7ba9f9002e6d98a193bbad5ab2d5eac256efb231ae9d1efb', 'edfeed511d0b65dfcd4b0b5e7c3c40cafad83da8cd699d0c8eaba41552acd5e1', '186bde58a607b1748619f50646da5f949bcde5e9661fcad0dbfd7c4dcc61934b', '5569a6bbc4bf70470d132ad38a20fe5f1164776acba0dee5766c1ab66c9e9680', '425059b5a02fb9053b9da84ae4824ada044aa0a69f9775f0c8ebeb906e4f522c', '3a7137e8912c75a13eaaafbb30f7dfc41136f63d9534d5e1798e0d313b75e858')
SELECTED = {'ticker': '2845.TW', 'symbol': '2845', 'company_name': '遠東銀', 'event_date': '2026-08-20', 'event_end_date': '2026-08-20', 'event_time': '15:00', 'event_location': '線上會議', 'event_summary': '遠銀2026年第二季經營績效及未來營運策略', 'material_file_date': '2026-08-20', 'filename': '284520260820E002.pdf', 'format': 'pdf', 'language': 'en', 'row_sha256': '2b3f21ae3905efa85f524b2809e1bd4e592fae13d5ef0ef0c8cf355a9747a8ad', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'method': 'POST', 'request_body': 'step=9&filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&fileName=284520260820E002.pdf&functionName=t100sb02_1', 'request_sha256': '585355c9a17a8eb97b0a28c3190489c30895c6029289c6ebcafe7cf2cad7f49f'}
METADATA = {'projection_policy': 'feib-presentation-role-v1', 'role_page_allowlist': [1, 4, 16, 18, 23], 'excluded_native_text_pages': [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 19, 20, 21, 22], 'financial_statement_complete': False, 'full_visual_content_verified': False, 'presentation_cover_date': '2026-08-20', 'identity_text_basis': 'MOPS issuer master and exact published row; p23 names Far Eastern International Bank. Cover issuer logo is an image.', 'native_editorial_caution': 'All23 pages preserved without text edits. Role pages1/4/16/18/23 were compared with rendered originals and remain whole, including p23 disclaimer. Native text complete does not mean all images or layout relationships were extracted.', 'subsidiary_scope_caution': 'Page2 describes Far Eastern Group and is excluded from roles; its assets, companies and operations are not bank-level facts.', 'period_scope_caution': 'Cover2Q2026 and August20 date are retained. The presentation mixes June30 balances, year-to-June results, individual quarters and annualized ratios. Page4 IBT growth39.6% is year-to-June, not an isolated second-quarter growth rate. Page19 annualized EPS1.08 differs in basis from p12/21 half-year EPS0.54; neither numeric page is supplied to roles.', 'unit_scope_caution': 'Page4 assets overNT$900Bn/net worth overNT$70Bn are issuer highlights, not audited fact inputs. Bn means billions of NTD; the excluded appendix uses NT$m, percentages and per-share units. Do not infer financial values from chart reading order.', 'financial_scope_caution': 'Prepared bank presentation is not a five-year audited financial statement. Consolidated bank results, unconsolidated regulatory ratios, industry benchmarks and group data have different scopes. No annual/TTM/FCF fields are overwritten.', 'forward_looking_caution': 'Page16 business actions and page18 ESG/awards are issuer statements. Plans, budgets, estimated savings and participation are not independently verified completion or certification. Page18 governance ranking refers to2025; page17 manpower savings are estimates, and p15 values marked2026 Budget are not actuals.', 'visual_semantics_caution': 'All23 rendered pages inspected for qualification. Bank logos, illustrations, chart series/colors, table geometry and full visual semantics remain outside verified text. Page17 has image-only chart labels. Only whole text pages1/4/16/18/23 are supplied to roles.'}


def metadata():
    return deepcopy(METADATA)


def _valid_pages(pages):
    return (isinstance(pages, list) and len(pages) == 23
            and all(isinstance(p, dict) and set(p) == {'page_number', 'text'}
                    and type(p['page_number']) is int and p['page_number'] == n
                    and isinstance(p['text'], str)
                    and sha256(p['text'].encode()).hexdigest() == PAGE_TEXT_SHA256[n-1]
                    for n, p in enumerate(pages, 1)))


def validate_native(raw, native, selected):
    if (sha256(raw).hexdigest() != CONTENT_SHA256
            or {k: v for k, v in selected.items() if k != 'index_sha256'} != SELECTED
            or native.get('content_sha256') != CONTENT_SHA256
            or native.get('parser_version') != '6.19.0'
            or type(native.get('page_count')) is not int or native['page_count'] != 23
            or native.get('coverage_status') != 'complete'
            or native.get('empty_pages') != [] or native.get('garbled_pages') != []
            or not _valid_pages(native.get('pages'))):
        raise ValueError('FEIB published original needs qualification')
    return '2026Q2'


def marked(document):
    return (document.get('projection_policy') == METADATA['projection_policy']
            or document.get('content_sha256') == CONTENT_SHA256
            or document.get('source') == 'MOPS published presentation' and document.get('ticker') == '2845.TW')


def role_pages(document):
    if not isinstance(document, dict) or not _valid_pages(document.get('pages')):
        return []
    try:
        stamp = document['retrieved_at_epoch']
        if type(stamp) not in (float, int) or not math.isfinite(stamp) or stamp <= 0:
            return []
        from .mops_presentation import _context
        native = {'content_sha256': CONTENT_SHA256, 'page_count':23,
                  'pages':document['pages'], 'empty_pages':[], 'garbled_pages':[],
                  'coverage_status':'complete', 'parser_version':'6.19.0'}
        proof = {'material':{'retrieved_at':stamp}, 'index':{'source_url':'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1'}}
        expected = _context(SELECTED, native, '2026Q2', proof)['documents'][0]
        if json.dumps(document,sort_keys=True,allow_nan=False) != json.dumps(expected,sort_keys=True,allow_nan=False):
            return []
        return deepcopy([p for p in document['pages'] if p['page_number'] in METADATA['role_page_allowlist']])
    except (KeyError, TypeError, ValueError, OverflowError):
        return []
