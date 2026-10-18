"""Public boundary checks. Original private-data replay cases remain local."""
import pytest
from test_mops_material_transport import descriptor, PDF
import mops_material_transport as transport
FILENAME = '122920260930E001.pptx'
DISPOSITION = 'attachment; filename="' + FILENAME + '"'

@pytest.mark.parametrize('fmt', ['pdf', 'html'])
def test_blank_mime_exception_is_never_extended_to_pdf_or_index(fmt):
    raw = PDF if fmt == 'pdf' else b'<html><body>Index</body></html>'
    spec = descriptor() if fmt == 'pdf' else transport.index_request('1229.TW', 2026)
    meta = {'http_status': 200, 'effective_url': spec['url'], 'num_redirects': 0, 'size_download': len(raw), 'content_type': '', 'content_length': len(raw), 'method': 'POST', 'proxy_used': 0, 'content_disposition': DISPOSITION}
    assert not transport.validate_response_metadata(meta, raw, spec)
    meta.pop('content_disposition')
    meta['content_type'] = 'application/pdf' if fmt == 'pdf' else 'text/html'
    assert transport.validate_response_metadata(meta, raw, spec)
