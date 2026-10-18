"""Private exact-original KINIK glyph adapter; generic parser/stream guards stay fatal."""
from __future__ import annotations
import hashlib
import time
import source_pdf_worker as common
from kinik_presentation_pdf_reader import (ORIGINAL_SHA256, PROGRAM_SHA256, CMAP_SHA256,
    MAPPING, OCCURRENCES, FRAGMENT_JOIN_SHA256, NATIVE_PAGE_TEXT_SHA256, glyph_evidence)


def _object(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def _verified_font(font):
    try:
        name = '/ABCDEE+Wingdings'
        if (font.get('/BaseFont') != name or font.get('/Type') != '/Font'
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
        supplement = _object(system.get('/Supplement'))
        if (_object(system.get('/Registry')) != 'Adobe' or _object(system.get('/Ordering')) != 'Identity'
                or not isinstance(supplement, int) or isinstance(supplement, bool) or supplement != 0):
            return False
        descriptor = _object(child.get('/FontDescriptor'))
        if descriptor.get('/FontName') != name:
            return False
        cmap = _object(font.get('/ToUnicode')); program = _object(descriptor.get('/FontFile2'))
        proof = glyph_evidence()
        for stream, prefix, encoded_size in [(cmap, 'cmap', 234), (program, 'font_program', 14066)]:
            if (stream.get('/Filter') != '/FlateDecode' or not isinstance(stream._data, bytes)
                    or len(stream._data) != encoded_size
                    or hashlib.sha256(stream._data).hexdigest() != proof[prefix + '_encoded_sha256']):
                return False
        decoded_cmap = cmap.get_data(); decoded_program = program.get_data()
        return (len(decoded_cmap) == 351 and hashlib.sha256(decoded_cmap).hexdigest() == CMAP_SHA256
                and len(decoded_program) == 29216 and hashlib.sha256(decoded_program).hexdigest() == PROGRAM_SHA256)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def _normalize(text, fragments, page_number, font_cache):
    expected = OCCURRENCES.get(str(page_number))
    if expected is None or fragments is None:
        return text, {}
    if hashlib.sha256(text.encode()).hexdigest() != NATIVE_PAGE_TEXT_SHA256[page_number - 1]:
        return text, {}
    joined = ''.join(fragment for fragment, _ in fragments)
    if joined != text and hashlib.sha256(joined.encode()).hexdigest() != FRAGMENT_JOIN_SHA256.get(str(page_number)):
        return text, {}
    counts = {}
    for fragment, font in fragments:
        source = fragment.strip()
        if font is None or source not in MAPPING:
            if any(c in fragment for c in MAPPING):
                return text, {}
            continue
        key = ('kinik-symbols', id(font))
        if key not in font_cache:
            font_cache[key] = _verified_font(font)
        if not font_cache[key]:
            return text, {}
        label = f'U+{ord(source):04X}'
        counts[label] = counts.get(label, 0) + 1
    if counts != expected or any(text.count(source) != counts.get(f'U+{ord(source):04X}', 0) for source in MAPPING):
        return text, {}
    # Never return the visitor concatenation: it repeats table Form text on
    # three pinned pages. Only replace glyphs within the original native output.
    return text.translate(str.maketrans(MAPPING)), counts


def _extract(raw, deadline):
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise common._Failure('invalid_pdf')
    import source_pdf_symbols
    original = source_pdf_symbols.normalize_verified_symbols
    counts = {}
    def specific(text, fragments, number, font_cache):
        if time.monotonic() >= deadline:
            raise common._Failure('timeout')
        result, count = _normalize(text, fragments, number, font_cache)
        if count:
            counts[str(number)] = count
        if time.monotonic() >= deadline:
            raise common._Failure('timeout')
        return result, []
    try:
        source_pdf_symbols.normalize_verified_symbols = specific
        result = _GENERIC_EXTRACT(raw, deadline)
    finally:
        source_pdf_symbols.normalize_verified_symbols = original
    if time.monotonic() >= deadline:
        raise common._Failure('timeout')
    if result['page_count'] != 36 or result['coverage_status'] != 'complete' or counts != OCCURRENCES:
        raise common._Failure('invalid_pdf')
    result['kinik_glyph_evidence'] = glyph_evidence()
    return result


_GENERIC_EXTRACT = common._extract
if __name__ == '__main__':
    common._extract = _extract
    common.main()
