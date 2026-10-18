"""Decode one native symbol with its exact embedded glyph and CMap evidence.

The qualified font's identity CID 131 is a single closed four-corner filled
square. Its program, CMap, and standalone text fragments were read from the
complete issuer original; unknown fonts and private characters stay unknown.
"""
from hashlib import sha256
import re

POLICY = 'native-embedded-filled-square-v1'
PROGRAM_SHA256 = 'a40a43264ab7ae486f65584049edb847bc980bdf54a242e871eb39349b401db3'
CMAP_SHA256 = '15fe21b4a24525625c0cc85fecb5197fd27f0975399583b83ddc537bac29cc3c'
SOURCE = '\uf0a1'
TARGET = '\u25a0'
FONT_NAME = re.compile(r'/[A-Z]{6}\+Wingdings2')
EVIDENCE_FIELDS = {'policy', 'page_number', 'font_program_sha256', 'cmap_sha256',
                   'source_font', 'source_character', 'replacement_character', 'occurrences'}


def _object(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def _verified_font(font):
    try:
        name = str(font.get('/BaseFont'))
        if (not FONT_NAME.fullmatch(name) or font.get('/Type') != '/Font'
                or font.get('/Subtype') != '/Type0' or font.get('/Encoding') != '/Identity-H'):
            return False
        children = _object(font.get('/DescendantFonts'))
        if not isinstance(children, list) or len(children) != 1:
            return False
        child = _object(children[0])
        if (child.get('/Type') != '/Font' or child.get('/Subtype') != '/CIDFontType2'
                or child.get('/BaseFont') != name or child.get('/CIDToGIDMap') != '/Identity'):
            return False
        system = _object(child.get('/CIDSystemInfo'))
        if (system.get('/Registry') != 'Adobe' or system.get('/Ordering') != 'Identity'
                or system.get('/Supplement') != 0):
            return False
        descriptor = _object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName') != name:
            return False
        cmap = _object(font.get('/ToUnicode')).get_data()
        if len(cmap) != 337 or sha256(cmap).hexdigest() != CMAP_SHA256:
            return False
        program = _object(descriptor.get('/FontFile2')).get_data()
        return len(program) == 14660 and sha256(program).hexdigest() == PROGRAM_SHA256
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def _normalize_verified_square(text, fragments, page_number, font_cache):
    """Preserve native ordering and whitespace; decode only qualified markers."""
    if SOURCE not in text or fragments is None:
        return text, []
    if ''.join(fragment for fragment, _ in fragments) != text:
        return text, []
    normalized, occurrences = [], 0
    for fragment, font in fragments:
        if font is not None and fragment.strip() == SOURCE:
            key = id(font)
            if key not in font_cache:
                font_cache[key] = _verified_font(font)
            if font_cache[key]:
                fragment = fragment.replace(SOURCE, TARGET)
                occurrences += 1
        normalized.append(fragment)
    if not occurrences:
        return text, []
    evidence = {'policy': POLICY, 'page_number': page_number,
                'font_program_sha256': PROGRAM_SHA256, 'cmap_sha256': CMAP_SHA256,
                'source_font': 'Wingdings2', 'source_character': 'U+F0A1',
                'replacement_character': 'U+25A0', 'occurrences': occurrences}
    return ''.join(normalized), [evidence]


def _valid_square_evidence(evidence, pages):
    if not isinstance(evidence, list) or not evidence or len(evidence) > len(pages):
        return False
    seen = []
    for row in evidence:
        if not isinstance(row, dict) or set(row) != EVIDENCE_FIELDS:
            return False
        page, count = row['page_number'], row['occurrences']
        if (type(page) is not int or not 1 <= page <= len(pages)
                or type(count) is not int or not 0 < count <= pages[page-1]['text'].count(TARGET)
                or row['policy'] != POLICY or row['font_program_sha256'] != PROGRAM_SHA256
                or row['cmap_sha256'] != CMAP_SHA256 or row['source_font'] != 'Wingdings2'
                or row['source_character'] != 'U+F0A1' or row['replacement_character'] != 'U+25A0'):
            return False
        seen.append(page)
    return seen == sorted(set(seen))


def normalize_verified_symbols(text, fragments, page_number, font_cache):
    from source_pdf_txc_symbols import MAPPING, normalize_fragment
    from source_pdf_npc_symbols import normalize_fragment as normalize_npc_fragment
    if not any(source in text for source in MAPPING):
        return _normalize_verified_square(text, fragments, page_number, font_cache)
    if fragments is None or ''.join(fragment for fragment, _ in fragments) != text:
        return text, []
    result, evidence = [], {}
    for fragment, font in fragments:
        changed, mapped = _normalize_verified_square(fragment, [(fragment, font)], page_number, font_cache)
        if not mapped:
            changed, mapped = normalize_fragment(fragment, font, page_number, font_cache)
        if not mapped:
            changed, mapped = normalize_npc_fragment(fragment, font, page_number, font_cache)
        result.append(changed)
        for row in mapped:
            key = (row['policy'], row['source_character'])
            if key in evidence:
                evidence[key]['occurrences'] += row['occurrences']
            else:
                evidence[key] = dict(row)
    return ''.join(result), [evidence[key] for key in sorted(evidence)]


def _valid_legacy_evidence(evidence, pages):
    from source_pdf_txc_symbols import POLICY as TXC_POLICY, valid_evidence
    if not isinstance(evidence, list) or not any(isinstance(r, dict) and r.get('policy') == TXC_POLICY for r in evidence):
        return _valid_square_evidence(evidence, pages)
    if any(not isinstance(r, dict) or r.get('policy') not in {POLICY, TXC_POLICY} for r in evidence):
        return False
    old = [r for r in evidence if r['policy'] == POLICY]
    new = [r for r in evidence if r['policy'] == TXC_POLICY]
    if old and not _valid_square_evidence(old, pages) or not valid_evidence(new, pages):
        return False
    keys = [(r['page_number'], r['policy'], r['source_character']) for r in evidence]
    return keys == sorted(set(keys))


def valid_symbol_evidence(evidence, pages):
    from source_pdf_npc_symbols import POLICIES, valid_evidence
    if not isinstance(evidence,list) or any(not isinstance(r,dict)or not isinstance(r.get('policy'),str)for r in evidence):
        return False
    new=[r for r in evidence if r['policy']in POLICIES]
    if not new:return _valid_legacy_evidence(evidence,pages)
    old=[r for r in evidence if r['policy']not in POLICIES]
    if not valid_evidence(new,pages)or old and not _valid_legacy_evidence(old,pages):return False
    # Mixed old/new policies share the same visible symbols, so each subgroup
    # cannot independently claim all occurrences on a page.
    totals={}
    for row in evidence:
        key=(row['page_number'],row['replacement_character'])
        totals[key]=totals.get(key,0)+row['occurrences']
        if totals[key]>pages[key[0]-1]['text'].count(chr(int(key[1][2:],16))):return False
    keys=[(r['page_number'],r['policy'],r['source_character'])for r in evidence]
    return keys==sorted(set(keys))
