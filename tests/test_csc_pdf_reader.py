"""Exact issuer PDF mapping preserves text; generic parser remains conservative."""
from pathlib import Path
from hashlib import sha256
import json
import pytest
from source_pdf_reader import extract_pdf_pages,SourcePdfError
R=Path(__file__).parents[1]
D=R/'docs/evidence/source-acquisition/20261014/free-gap-followup/industrial-research'
RAW=(D/'csc-presentation.body').read_bytes()


def test_csc_reader_decodes_only_the_27_embedded_standalone_symbols():
    from csc_presentation_pdf_reader import extract_csc_presentation_pages,glyph_evidence
    before=sha256(RAW).hexdigest();value=extract_csc_presentation_pages(RAW)
    generic=json.loads((D/'csc-reader-result.json').read_text())['result']
    mapping={'\uf0fc':'\u2713','\uf0a7':'\u25aa','\uf06e':'\u25a0','\uf075':'\u25c6','\uf0d8':'\u27a2'}
    assert value['page_count']==35 and not value['empty_pages'] and not value['garbled_pages']
    assert value['coverage_status']=='complete' and value['csc_glyph_evidence']==glyph_evidence()
    assert value['pages']==[{**p,'text':p['text'].translate(str.maketrans(mapping))}for p in generic['pages']]
    assert sha256(RAW).hexdigest()==before
    assert sum(p['text'].count(ch)for p in generic['pages']for ch in mapping)==27
    assert any('2026.1~7' in p['text'] for p in value['pages'])


def test_generic_reader_does_not_inherit_source_specific_mapping():
    from csc_presentation_pdf_reader import extract_csc_presentation_pages
    extract_csc_presentation_pages(RAW)
    native=extract_pdf_pages(RAW)
    assert native['coverage_status']=='partial' and len(native['garbled_pages'])==10


@pytest.mark.parametrize('raw',[b'garbage',RAW+b'\n',RAW[:-1],b''],ids=['not-pdf','extra-byte','truncated','empty'])
def test_unknown_revision_is_not_qualified(raw):
    from csc_presentation_pdf_reader import extract_csc_presentation_pages
    with pytest.raises(SourcePdfError):extract_csc_presentation_pages(raw)


@pytest.mark.parametrize('timeout',[True,0,11,float('inf'),float('nan'),-1])
def test_invalid_reader_time_cannot_extend_limit(timeout):
    from csc_presentation_pdf_reader import extract_csc_presentation_pages
    with pytest.raises(SourcePdfError)as e:extract_csc_presentation_pages(RAW,timeout_seconds=timeout)
    assert e.value.reason=='invalid_timeout'


def test_worker_cannot_supply_changed_text_or_proof(monkeypatch):
    import csc_presentation_pdf_reader as reader
    native=reader.extract_csc_presentation_pages(RAW)
    native['pages'][0]['text']+=' made-up result'
    monkeypatch.setattr(reader,'_run_worker',lambda *a,**kw:json.dumps(native).encode())
    with pytest.raises(SourcePdfError)as e:reader.extract_csc_presentation_pages(RAW)
    assert e.value.reason=='invalid_worker_result'
