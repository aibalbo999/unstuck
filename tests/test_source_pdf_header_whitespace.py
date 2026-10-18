"""Public boundary checks. Original private-data replay cases remain local."""
import re
import pytest
from source_pdf_reader import extract_pdf_pages, SourcePdfError
from test_source_pdf_reader import make_pdf

def test_other_pdf_with_same_one_byte_xref_error_is_not_silently_repaired():
    raw = make_pdf([b'Original text'])
    raw = re.sub(b'([0-9]{10}) 00000 n ', lambda m: f'{int(m[1]) - 1:010} 00000 n '.encode(), raw)
    with pytest.raises(SourcePdfError):
        extract_pdf_pages(raw)

def test_healthy_original_has_no_recovery_evidence():
    v = extract_pdf_pages(make_pdf([b'Original text']))
    assert v['pages'][0]['text'] == 'Original text' and 'object_header_whitespace_evidence' not in v
