"""Large originals require a caller's explicit, bounded archive allowance."""
import gzip
from pathlib import Path

import pytest

PDF_LIMIT = 16 * 1024 * 1024
FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/tewc1623_pdf_20261014.gz'


def test_explicit_allowance_preserves_complete_native_pdf_without_changing_default():
    from official_response_evidence import archive_response, read_response
    raw = gzip.decompress(FIXTURE.read_bytes())
    assert len(raw) == 16_076_336
    assert archive_response(raw, source_url='https://example.test/original.pdf', retrieved_at=1)['status'] == 'unavailable'
    receipt = archive_response(raw, source_url='https://example.test/original.pdf', retrieved_at=1, max_bytes=PDF_LIMIT)
    assert receipt['status'] == 'archived'
    assert receipt['raw_response_sha256'] == '4514db4ca2c720a5113298397baff01075175ff1ac4d16e1b9d23c2732a38c48'
    assert read_response(receipt, max_bytes=PDF_LIMIT) == raw
    with pytest.raises(ValueError): read_response(receipt)


@pytest.mark.parametrize('limit', [True, False, None, '16777216', 16777216., 0, -1, PDF_LIMIT + 1])
def test_archive_limit_is_exact_integer_and_cannot_exceed_hard_ceiling(limit):
    from official_response_evidence import archive_response, read_response
    with pytest.raises(ValueError):
        archive_response(b'original', source_url='https://example.test/source', retrieved_at=1, max_bytes=limit)
    with pytest.raises(ValueError): read_response({}, max_bytes=limit)


def test_explicit_limit_still_rejects_oversized_original():
    from official_response_evidence import archive_response
    assert archive_response(b'x' * (PDF_LIMIT + 1), source_url='https://example.test/source',
                            retrieved_at=1, max_bytes=PDF_LIMIT)['status'] == 'unavailable'
