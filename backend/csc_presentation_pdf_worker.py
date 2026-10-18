"""Private exact-original glyph adapter; common warning/resource guards retained."""
from __future__ import annotations

import hashlib
import re
import time

import source_pdf_worker as common
from csc_presentation_pdf_reader import CMAP_SHA256, ORIGINAL_SHA256, PROGRAM_SHA256, MAPPING, OCCURRENCES, PROFILES, glyph_evidence

FONT_NAME = re.compile(r'/[A-Z]{6}\+Wingdings')


def _object(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def _verified_font(font):
    """Pinned bytes prove the qualified five glyphs, not its font name alone."""
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
                or not isinstance(system.get('/Supplement'), int)
                or system.get('/Supplement') != 0 or isinstance(system.get('/Supplement'), bool)):
            return False
        descriptor = _object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName') != name:
            return False
        cmap = _object(font.get('/ToUnicode')).get_data()
        if len(cmap) != 445 or hashlib.sha256(cmap).hexdigest() != CMAP_SHA256:
            return False
        program = _object(descriptor.get('/FontFile2')).get_data()
        return len(program) == 29636 and hashlib.sha256(program).hexdigest() == PROGRAM_SHA256
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def _normalize(text, fragments, page_number, font_cache, occurrences=OCCURRENCES):
    if str(page_number) not in occurrences or fragments is None or ''.join(fragment for fragment, _ in fragments) != text:
        return text, {}
    result, counts = [], {}
    for fragment, font in fragments:
        source = fragment.strip()
        if font is not None and source in MAPPING:
            key = ('csc-symbols', id(font))
            if key not in font_cache:
                font_cache[key] = _verified_font(font)
            if font_cache[key]:
                fragment = fragment.replace(source, MAPPING[source])
                label = f'U+{ord(source):04X}'
                counts[label] = counts.get(label, 0) + 1
        result.append(fragment)
    return ''.join(result), counts


def _extract(raw, deadline):
    digest = hashlib.sha256(raw).hexdigest()
    profile = PROFILES.get(digest)
    if profile is None:
        raise common._Failure('invalid_pdf')
    expected_occurrences = profile['occurrences']
    import source_pdf_symbols
    original = source_pdf_symbols.normalize_verified_symbols
    counts = {}

    def specific(text, fragments, number, font_cache):
        if time.monotonic() >= deadline:
            raise common._Failure('timeout')
        # The exact original uses no other verified private glyph profile.
        # Unrecognized/mixed fragments remain unchanged and hence partial.
        text, count = _normalize(text, fragments, number, font_cache, expected_occurrences)
        if count:
            counts[str(number)] = count
        if time.monotonic() >= deadline:
            raise common._Failure('timeout')
        return text, []

    try:
        source_pdf_symbols.normalize_verified_symbols = specific
        result = _GENERIC_EXTRACT(raw, deadline)
    finally:
        source_pdf_symbols.normalize_verified_symbols = original
    if time.monotonic() >= deadline:
        raise common._Failure('timeout')
    proof = glyph_evidence(digest, expected_occurrences)
    if counts != expected_occurrences:
        raise common._Failure('invalid_pdf')
    result['csc_glyph_evidence'] = proof
    return result


_GENERIC_EXTRACT = common._extract

if __name__ == '__main__':
    common._extract = _extract
    common.main()
