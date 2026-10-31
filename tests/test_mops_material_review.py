"""Independent public-boundary probes; all original I/O comes from saved fixtures."""
from contextlib import contextmanager
import time
import pytest
from test_mops_presentation import harness, NOW


@pytest.mark.parametrize('expiry', ['deadline', 'receipt'])
def test_public_handoff_rejects_expiry_during_external_lease_release(harness, monkeypatch, expiry):
    from data_fetch.market_sources import mops_presentation as source
    from search_provider_runtime import SourceResponseError
    original_monotonic = time.monotonic
    elapsed = [0.0]
    wall = [NOW]
    monkeypatch.setattr(time, 'monotonic', lambda: original_monotonic() + elapsed[0])
    monkeypatch.setattr(time, 'time', lambda: wall[0])

    if expiry == 'receipt':
        source.fetch_presentation_context('1229.TW')
        harness[1].clear()
        wall[0] = NOW + 1799.0

    @contextmanager
    def admitted(*args, **kwargs):
        yield lambda: True
        # External lock release can block; this is after the last in-lease
        # check, while the public collector has not returned its result.
        if expiry == 'deadline':
            elapsed[0] = 26.0
        else:
            wall[0] = NOW + 1800.0

    monkeypatch.setattr(source, 'endpoint_admission', admitted)
    diagnostic = {}
    with pytest.raises(SourceResponseError):
        source.fetch_presentation_context('1229.TW', diagnostics=diagnostic)
    assert diagnostic.get('mops_material_originals_verified') is not True
    expected_http = 0 if expiry == 'receipt' else 3
    assert diagnostic['http_request_count'] == expected_http
    assert len(harness[1]) == expected_http


def test_unexpired_public_handoff_positive_control(harness):
    from data_fetch.market_sources import mops_presentation as source
    diagnostic = {}
    value = source.fetch_presentation_context('1229.TW', diagnostics=diagnostic)
    assert source.verify_context(value, '1229.TW')
    assert diagnostic['mops_material_originals_verified'] is True
    assert diagnostic['http_request_count'] == 3
