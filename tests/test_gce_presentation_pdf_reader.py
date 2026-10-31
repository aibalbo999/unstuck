"""Exact independent native-page projection; generic reader stays conservative."""
from copy import deepcopy
import io
import json
from pathlib import Path
import pytest
from test_gce_conference import D


def test_exact_original_matches_every_independent_page_and_generic_remains_partial():
    from gce_presentation_pdf_reader import extract_gce_presentation_pages, glyph_evidence
    from source_pdf_reader import extract_pdf_pages
    raw=(D/'gce-20260828-en.body').read_bytes()
    generic=extract_pdf_pages(raw)
    result=extract_gce_presentation_pages(raw)
    assert generic['coverage_status']=='partial' and generic['garbled_pages']==[3]
    assert result['coverage_status']=='complete' and result['page_count']==11
    assert result['pages']==json.loads((D/'gce-glyphs/expected-pages.json').read_text())
    assert result['gce_glyph_evidence']==glyph_evidence()


@pytest.mark.parametrize('mutation',['append','truncate','unknown'])
def test_unknown_original_never_enters_mapping(mutation):
    from gce_presentation_pdf_reader import extract_gce_presentation_pages
    from source_pdf_reader import SourcePdfError
    raw=(D/'gce-20260828-en.body').read_bytes()
    raw=raw+b'\n'if mutation=='append'else raw[:-30]if mutation=='truncate'else b'%PDF-1.7 unknown'
    with pytest.raises(SourcePdfError):extract_gce_presentation_pages(raw)


@pytest.mark.parametrize('part',['program','cmap','cid','fontname','encoding','mixed_fragment','wrong_page'])
def test_only_verified_embedded_standalone_symbols_map(part):
    from pypdf import PdfReader
    from pypdf.generic import NameObject, DecodedStreamObject
    from gce_presentation_pdf_worker import _verified_font, _normalize
    reader=PdfReader(io.BytesIO((D/'gce-20260828-en.body').read_bytes()),strict=True)
    font=reader.get_object(41)
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
        text='\uf0d8 123'if part=='mixed_fragment'else'\uf0d8'
        out,counts=_normalize(text,[(text,font)],3 if part=='mixed_fragment'else 1,{})
        assert out==text and counts=={}
        return
    assert not _verified_font(font)


@pytest.mark.parametrize('field,value',[('raw_bytes_rewritten',0),('font_program_bytes',29328.0),('other_parser_warnings_fatal',False)])
def test_parent_does_not_trust_forged_child_glyph_proof(monkeypatch,field,value):
    import gce_presentation_pdf_reader as reader
    from source_pdf_reader import SourcePdfError
    raw=(D/'gce-20260828-en.body').read_bytes();result=reader.extract_gce_presentation_pages(raw)
    result['gce_glyph_evidence'][field]=value
    monkeypatch.setattr(reader,'_run_worker',lambda *a,**k:json.dumps(result).encode())
    with pytest.raises(SourcePdfError):reader.extract_gce_presentation_pages(raw)
