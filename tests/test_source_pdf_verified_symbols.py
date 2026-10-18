"""A real issuer PDF must decode a proven glyph, retaining unknown-text warnings."""
import gzip
import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from source_pdf_reader import extract_pdf_pages


ORIGINAL_SHA = 'bbf5334b5242cb33358bb4b0570a999716cc579adec92fb54e8f0ab4e7a387c2'


def original():
    path = Path(__file__).parent / 'fixtures/source_acquisition/uk1325_presentation_20251219.pdf.gz'
    raw = gzip.decompress(path.read_bytes())
    assert sha256(raw).hexdigest() == ORIGINAL_SHA
    return raw


def test_complete_issuer_presentation_decodes_only_verified_filled_square():
    result = extract_pdf_pages(original())
    assert result['page_count'] == 31
    assert result['coverage_status'] == 'complete'
    assert result['garbled_pages'] == result['empty_pages'] == []
    assert result['content_sha256'] == ORIGINAL_SHA
    assert sum(p['text'].count('\u25a0') for p in result['pages']) == 46
    assert all('\uf0a1' not in p['text'] for p in result['pages'])
    saved = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/uk1325_native_pages_20251219.json').read_text())
    assert saved['raw_sha256'] == ORIGINAL_SHA
    assert result['pages'] == [{'page_number': p['page_number'], 'text': p['text'].replace('\uf0a1', '\u25a0')}
                               for p in saved['pages']]
    proof = result['symbol_mapping_evidence']
    assert sum(p['occurrences'] for p in proof) == 46
    assert {p['page_number'] for p in proof} == {2, 4, 5, 11, 12, 13, 16, 24, 25, 26, 27, 28, 29}


def mutated_font(kind):
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(original()), strict=True))
    font = next(f.get_object() for f in writer.pages[1]['/Resources']['/Font'].values()
                if 'Wingdings2' in str(f.get_object().get('/BaseFont')))
    child = font['/DescendantFonts'][0].get_object()
    if kind == 'font_program':
        descriptor = child['/FontDescriptor'].get_object()
        program = descriptor['/FontFile2'].get_object().get_data()
        stream = DecodedStreamObject()
        stream.set_data(program[:-1] + bytes([program[-1] ^ 1]))
        descriptor[NameObject('/FontFile2')] = writer._add_object(stream)
    elif kind == 'CID_mapping':
        stream = DecodedStreamObject()
        mapping = bytearray(264)
        mapping[262:264] = (132).to_bytes(2, 'big')
        stream.set_data(bytes(mapping))
        child[NameObject('/CIDToGIDMap')] = writer._add_object(stream)
    elif kind == 'font_identity':
        font[NameObject('/BaseFont')] = NameObject('/UnknownSymbols')
    else:
        raise AssertionError(kind)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.parametrize('kind', ['font_program', 'CID_mapping', 'font_identity'])
def test_named_or_changed_font_cannot_turn_unknown_private_text_complete(kind):
    result = extract_pdf_pages(mutated_font(kind))
    assert result['coverage_status'] == 'partial'
    assert result['garbled_pages']
    assert not result.get('symbol_mapping_evidence')
    assert any('\uf0a1' in p['text'] for p in result['pages'])


def test_known_and_unknown_same_private_character_on_one_page_stay_separate():
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(original()), strict=True))
    page = writer.pages[1]
    fonts = page['/Resources']['/Font']
    font = next(f.get_object() for f in fonts.values()
                if 'Wingdings2' in str(f.get_object().get('/BaseFont')))
    unverified = DictionaryObject(dict(font))
    unverified[NameObject('/BaseFont')] = NameObject('/UnverifiedSymbols')
    fonts[NameObject('/UnverifiedSymbol')] = writer._add_object(unverified)
    stream = DecodedStreamObject()
    stream.set_data(page.get_contents().get_data() + b'\nBT /UnverifiedSymbol 20 Tf 50 50 Td <0083> Tj ET\n')
    page[NameObject('/Contents')] = writer._add_object(stream)
    buf = BytesIO()
    writer.write(buf)
    result = extract_pdf_pages(buf.getvalue())
    assert result['coverage_status'] == 'partial'
    assert result['garbled_pages'] == [2]
    assert result['pages'][1]['text'].count('\uf0a1') == 1
    assert sum(p['occurrences'] for p in result['symbol_mapping_evidence']) == 46
