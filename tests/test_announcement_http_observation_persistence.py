"""Synthetic audit persistence checks; these are never acquisition evidence."""
import json

import pytest

from provider_sla import record_source_audit_entries
from test_report_refresh_acquisition_audit import events, init_db


def persist(urls):
    init_db()
    observations = [{"url": url, "method": "POST", "status": "success",
                     "http_request_sent": True, "http_request_count": 1,
                     "http_status": 200, "http_status_observed": True,
                     "response_complete": True, "response_bytes": 100,
                     "request_fingerprint": "a"*64, "response_sha256": "b"*64,
                     "headers": {"Cookie": "PRIVATE"}, "request_json": {"secret": "PRIVATE"}}
                    for url in urls]
    record_source_audit_entries([{
        "source": "recent_catalysts", "provider": "TWSE company announcement history",
        "status": "success", "record_count": 1, "event_kind": "aggregate",
        "http_request_sent": True, "http_request_count": len(observations),
        "request_observations": observations,
    }])
    return json.loads(events()[0]["details_json"])


@pytest.mark.parametrize("url", [
    "https://mops.twse.com.tw/mops/api/t05st01_detail",
    "https://mops.twse.com.tw/mops/api/t59sb01_detail",
    "https://mopsov.twse.com.tw/nas/t59/t59sa01/9103_2026100901_FIM.pdf",
    "https://wwwc.twse.com.tw/rwd/en/IIH/company/events",
])
def test_published_json_tdr_and_english_endpoints_survive_sql_with_only_typed_metadata(url):
    details = persist([url+"?private=PRIVATE#fragment"])
    assert details["request_observations"][0]["url"] == url
    assert details["request_observations"][0]["http_status_observed"] is True
    assert details["request_observations"][0]["response_complete"] is True
    assert details["request_observations"][0]["response_bytes"] == 100
    assert "PRIVATE" not in json.dumps(details)


def test_three_month_indices_and_sixty_four_originals_are_not_truncated():
    index = "https://mops.twse.com.tw/mops/api/t05st01"
    body = "https://mops.twse.com.tw/mops/api/t05st01_detail"
    details = persist([index]*3+[body]*64)
    assert len(details["request_observations"]) == 67
    assert [row["url"] for row in details["request_observations"]] == [index]*3+[body]*64


def test_persisted_observations_stay_bounded_without_headers_or_request_payloads():
    details = persist(["https://mops.twse.com.tw/mops/api/t05st01"]*100)
    assert len(details["request_observations"]) == 70
    assert "PRIVATE" not in json.dumps(details)


@pytest.mark.parametrize("url", [
    "https://evil.invalid/mops/api/t05st01_detail",
    "https://PRIVATE@mops.twse.com.tw/mops/api/t05st01_detail",
    "http://mops.twse.com.tw/mops/api/t05st01_detail",
    "https://mopsov.twse.com.tw/nas/t59/t59sa01/9104_2026100901_FIM.pdf",
    "https://mopsov.twse.com.tw/nas/t59/t59sa01/9103_2026100901_FIM.pdf/extra",
])
def test_unknown_or_credentialed_route_is_not_retained(url):
    details = persist([url])
    assert "url" not in details["request_observations"][0]
    assert "PRIVATE" not in json.dumps(details)
