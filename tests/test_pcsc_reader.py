from pathlib import Path
import json
import time
import pytest
from test_pcsc_conference import R


def test_exact_original_keeps_all_pages_pua_and_order():
    from pcsc_presentation_pdf_reader import extract_pcsc_presentation_pages, xref_evidence
    native=extract_pcsc_presentation_pages((R/'pcsc-presentation.body').read_bytes())
    saved=json.loads((R/'research-native-pages.json').read_text())
    assert native['pages']==saved['pages']
    assert native['garbled_pages']==[3,4] and native['coverage_status']=='partial'
    assert native['pages'][2]['text'].count('\uf070')==2
    assert native['xref_validation_evidence']==xref_evidence()
    assert native['xref_validation_evidence']['raw_bytes_rewritten'] is False


@pytest.mark.parametrize('timeout',[True,0,-1,10.1,float('nan'),float('inf')])
def test_public_reader_timeout_is_bounded(timeout):
    from pcsc_presentation_pdf_reader import extract_pcsc_presentation_pages
    from source_pdf_reader import SourcePdfError
    with pytest.raises(SourcePdfError,match='invalid_timeout'):
        extract_pcsc_presentation_pages((R/'pcsc-presentation.body').read_bytes(),timeout_seconds=timeout)


def test_unknown_revision_never_gets_cursor_exception():
    from pcsc_presentation_pdf_reader import extract_pcsc_presentation_pages
    from source_pdf_reader import SourcePdfError
    raw=(R/'pcsc-presentation.body').read_bytes()
    altered=raw.replace(b'%PDF-1.7',b'%PDF-1.6',1)
    assert altered!=raw
    with pytest.raises(SourcePdfError,match='invalid_pdf'):extract_pcsc_presentation_pages(altered)


def test_reader_rejects_worker_page_or_proof_tamper(monkeypatch):
    from pcsc_presentation_pdf_reader import extract_pcsc_presentation_pages
    import source_pdf_reader as common
    from source_pdf_reader import SourcePdfError
    real=common._run_worker
    def changed(*a,**k):
        value=json.loads(real(*a,**k));value['pages'][18]['text']='Safe-looking replacement'
        return json.dumps(value).encode()
    monkeypatch.setattr(common,'_run_worker',changed)
    with pytest.raises(SourcePdfError,match='invalid_worker_result'):
        extract_pcsc_presentation_pages((R/'pcsc-presentation.body').read_bytes())
