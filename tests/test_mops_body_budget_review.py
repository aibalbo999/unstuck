"""Public boundary checks. Original private-data replay cases remain local."""
import time
import pytest
from test_mops_material_transport import offline, descriptor, wire, PDF
import mops_material_transport as transport
from search_provider_runtime import SourceResponseError

def install_wire(monkeypatch, response, duration):
    clock = [100.0]
    calls = []
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])

    def collect(args, stop, **kwargs):
        calls.append((args, stop, kwargs))
        clock[0] += duration
        return response
    monkeypatch.setattr(transport, 'collect_capped_process', collect)
    return (clock, calls)

def test_six_second_index_remains_rejected_at_original_five_second_bound(offline, monkeypatch):
    raw = b'<html><body>Complete index</body></html>'
    response = wire(raw, ctype='text/html', meta_changes={'url_effective': transport.INDEX_URL})
    _, calls = install_wire(monkeypatch, response, 6.0)
    diagnostic = {}
    with pytest.raises(SourceResponseError) as error:
        transport.download_conference_index('1229.TW', year=2026, deadline=125.0, diagnostics=diagnostic)
    assert error.value.error_kind == 'timeout'
    assert len(calls) == 1 and calls[0][1] == 105.0 and (calls[0][2]['body_limit'] == 1024 * 1024)
    assert diagnostic['response_complete'] is False and diagnostic['http_status'] == 200

def test_complete_public_presentation_above_8mb_fits_the_bounded_pdf_reader_limit(offline, monkeypatch):
    raw = PDF + b'0' * (8 * 1024 * 1024 + 1)
    response = wire(raw)
    _, calls = install_wire(monkeypatch, response, 1.0)
    diagnostic = {}
    accepted = transport.download_published_material(descriptor(), deadline=125.0, diagnostics=diagnostic)
    assert accepted == raw and diagnostic['response_complete'] is True
    assert diagnostic['response_bytes'] == len(raw)
    assert len(calls) == 1 and calls[0][2]['body_limit'] == 16 * 1024 * 1024
