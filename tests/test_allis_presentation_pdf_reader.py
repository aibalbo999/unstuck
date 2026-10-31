"""Exact independent native-page projection; generic reader stays conservative."""
from copy import deepcopy
import io
import json
from pathlib import Path
import pytest
from test_allis_conference import D


def test_exact_original_matches_every_independent_page_and_generic_remains_partial():
    from allis_presentation_pdf_reader import extract_allis_presentation_pages, glyph_evidence
    from source_pdf_reader import extract_pdf_pages
    raw=(D/'native-allis-pdf.body').read_bytes()
    generic=extract_pdf_pages(raw)
    result=extract_allis_presentation_pages(raw)
    assert generic['coverage_status']=='partial' and generic['garbled_pages']==[2,3,6,9,11,17]
    assert result['coverage_status']=='complete' and result['page_count']==29
    assert result['pages']==json.loads((D/'allis-glyphs/expected-pages.json').read_text())
    assert result['allis_glyph_evidence']==glyph_evidence()


@pytest.mark.parametrize('mutation',['append','truncate','unknown'])
def test_unknown_original_never_enters_mapping(mutation):
    from allis_presentation_pdf_reader import extract_allis_presentation_pages
    from source_pdf_reader import SourcePdfError
    raw=(D/'native-allis-pdf.body').read_bytes()
    raw=raw+b'\n'if mutation=='append'else raw[:-30]if mutation=='truncate'else b'%PDF-1.7 unknown'
    with pytest.raises(SourcePdfError):extract_allis_presentation_pages(raw)


@pytest.mark.parametrize('part',['program','cmap','cid','fontname','encoding','mixed_fragment','wrong_page'])
def test_only_verified_embedded_standalone_symbols_map(part):
    from pypdf import PdfReader
    from pypdf.generic import NameObject, DecodedStreamObject
    from allis_presentation_pdf_worker import _verified_font, _normalize
    reader=PdfReader(io.BytesIO((D/'native-allis-pdf.body').read_bytes()),strict=True)
    font=reader.get_object(236)
    assert _verified_font(font)
    child=font['/DescendantFonts'][0].get_object()
    if part in {'program','cmap'}:
        stream=DecodedStreamObject();stream.set_data(b'wrong original stream')
        if part=='program':child['/FontDescriptor'][NameObject('/FontFile2')]=stream
        else:font[NameObject('/ToUnicode')]=stream
    elif part=='cid':child[NameObject('/CIDToGIDMap')]=NameObject('/Unknown')
    elif part=='fontname':font[NameObject('/BaseFont')]=NameObject('/Wingdings-Regular')
    elif part=='encoding':font[NameObject('/Encoding')]=NameObject('/Identity-V')
    else:
        text='\uf06c 123'if part=='mixed_fragment'else'\uf06c'
        out,counts=_normalize(text,[(text,font)],11 if part=='mixed_fragment'else 1,{})
        assert out==text and counts=={}
        return
    assert not _verified_font(font)


@pytest.mark.parametrize('field,value',[('raw_bytes_rewritten',0),('font_program_bytes',6371.0),('other_parser_warnings_fatal',False)])
def test_parent_does_not_trust_forged_child_glyph_proof(monkeypatch,field,value):
    import allis_presentation_pdf_reader as reader
    from source_pdf_reader import SourcePdfError
    raw=(D/'native-allis-pdf.body').read_bytes();result=reader.extract_allis_presentation_pages(raw)
    result['allis_glyph_evidence'][field]=value
    monkeypatch.setattr(reader,'_run_worker',lambda *a,**k:json.dumps(result).encode())
    with pytest.raises(SourcePdfError):reader.extract_allis_presentation_pages(raw)
