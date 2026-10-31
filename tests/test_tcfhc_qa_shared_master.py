"""TCFHC QA must share the verified master fallback, without moving old guards."""
import time
import pytest
from test_annual_shared_issuer_master import native_master, CSV, JSON, RAW, NOW
from test_shared_provider_cache import memory_cache


def test_qa_public_master_timeout_uses_complete_official_json(native_master):
    from data_fetch.market_sources import tcfhc_conference as source
    h = source.ConferenceHttp(time.monotonic() + 20)
    raw, receipt = h.get_receipt(CSV)
    assert raw == RAW and receipt['source_url'] == JSON
    assert [c[0] for c in native_master[0]] == [CSV, JSON]
    assert h.http_request_count == 2
    assert source.parse_master(raw, receipt['retrieved_at'], JSON)['ticker'] == '5880.TW'
    assert source.original_bytes(receipt, JSON, max_age=1800) == raw
