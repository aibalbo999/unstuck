"""Qualify only the observed original, preserving strict parser diagnostics."""
from pathlib import Path
from hashlib import sha256
import gzip
import io
import logging
import pytest
from source_pdf_reader import extract_pdf_pages, SourcePdfError

RAW = gzip.decompress((Path(__file__).parent / 'fixtures/source_acquisition/seec1503_pdf_20261016.gz').read_bytes())


def test_exact_seec_original_keeps_native_coverage_limits():
    value = extract_pdf_pages(RAW)
    assert value['page_count'] == 10
    assert value['coverage_status'] == 'partial'
    assert value['empty_pages'] == [10] and value['garbled_pages'] == [2, 3]
    proof = value['object_header_whitespace_evidence']
    assert proof['content_sha256'] == sha256(RAW).hexdigest()
    assert proof['warning_count'] == 99
    assert proof['observations_sha256'] == 'dbc039eea6e8165fd12fa91bc5d18f09d20365d6ba34c9b056c03d586f97d3a2'
    assert proof['raw_bytes_modified'] is False


def test_unknown_revision_still_rejects_warning():
    with pytest.raises(SourcePdfError, match='parser_warning'):
        extract_pdf_pages(RAW + b'\n')


@pytest.mark.parametrize('change', ['missing', 'count', 'observations', 'boolean', 'other_original'])
def test_parent_rejects_forged_recovery(change):
    from source_pdf_reader import _validate_result
    value = extract_pdf_pages(RAW)
    proof = value['object_header_whitespace_evidence']
    if change == 'missing': value.pop('object_header_whitespace_evidence')
    elif change == 'count': proof['warning_count'] -= 1
    elif change == 'observations': proof['observations_sha256'] = '0' * 64
    elif change == 'boolean': proof['raw_bytes_modified'] = 0
    else:
        from source_pdf_header_whitespace import CONTENT_SHA256
        proof['content_sha256'] = CONTENT_SHA256
    with pytest.raises(SourcePdfError, match='invalid_worker_result'):
        _validate_result(value, sha256(RAW).hexdigest())


def test_other_diagnostics_and_unbound_headers_remain_fatal():
    from source_pdf_header_whitespace import HeaderWhitespaceQualification
    q = HeaderWhitespaceQualification(RAW)
    def rec(msg, name='pypdf._reader'):
        return logging.LogRecord(name, 30, '', 0, msg, (), None)
    message = "Superfluous whitespace found in object header b'1' b'0'"
    assert not q.accepts(rec(message))
    stream = io.BytesIO(RAW); stream.seek(1217971)
    with q.header(stream):
        assert not q.accepts(rec('Unknown parser warning'))
        assert not q.accepts(rec(message, 'other.logger'))
        assert q.accepts(rec(message))
        assert not q.accepts(rec(message))
    with pytest.raises(ValueError): q.evidence()
