from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pytest

from data_fetch.market_sources.tpex_infohub import (
    PROVIDER,
    fetch_tpex_infohub_earnings_call,
    fetch_tpex_infohub_records,
    infohub_api_url,
    parse_infohub_index,
)
from search_provider_runtime import SourceResponseError


TAIPEI = ZoneInfo("Asia/Taipei")
TICKER = "8299.TWO"
ISSUER = "Phison Electronics Corp."
TITLE = "Announcement: Phison to Attend the 3Q26 Online Earnings Meeting"
NOTICE_URL = (
    "https://emops.twse.com.tw/server-java/t05sr01_1_e?&isNew=Y&seq_no=1"
    "&spoke_time=144450&spoke_date=20261016&co_id=8299"
)


def _payload():
    return {
        "info": {"stkNo": "8299", "shortName": "Phison", "name": ISSUER},
        "news": [{"datetime": "2026/10/16 14:44", "link": NOTICE_URL,
                   "title": TITLE}],
        "financial": [],
        "conferences": [],
    }


def _detail():
    return """<!doctype html><html><head><title>Today's Information</title></head>
    <body><table><tr><td>Provided by: Phison Electronics Corp.</td></tr></table>
    <table><tr><th>SEQ_NO</th><td>1</td></tr>
    <tr><th>Date of announcement</th><td>2026/10/16</td></tr>
    <tr><th>Time of announcement</th><td>14:44:50</td></tr>
    <tr><th>Subject</th><td>Announcement: Phison to Attend the 3Q26 Online Earnings Meeting</td></tr>
    <tr><th>Date of events</th><td>2026/11/06</td></tr>
    <tr><th>Statement</th><td>1. Date of institutional investor conference:2026/11/06\n
    2. Time of institutional investor conference:17:00\n
    3. Location: Online investor conference. The company will present its quarterly results.</td></tr>
    </table></body></html>"""


def test_infohub_url_is_bound_to_a_tpex_company_code():
    assert infohub_api_url(TICKER) == (
        "https://info.tpex.org.tw/api/stkInfo?query=8299&lang=en-us"
    )
    with pytest.raises(ValueError):
        infohub_api_url("8299.TW")


def test_infohub_index_requires_exact_tpex_issuer_and_official_mops_link():
    parsed = parse_infohub_index(
        _payload(), TICKER, now=datetime(2026, 10, 17, 12, tzinfo=TAIPEI)
    )
    assert parsed["issuer_name"] == ISSUER
    assert parsed["candidates"] == [{
        "ticker": TICKER,
        "published_at": "2026-10-16T14:44:00+08:00",
        "title": TITLE,
        "source_url": NOTICE_URL,
    }]

    wrong_issuer = _payload()
    wrong_issuer["info"]["stkNo"] = "8298"
    with pytest.raises(SourceResponseError) as rejected:
        parse_infohub_index(wrong_issuer, TICKER,
                            now=datetime(2026, 10, 17, 12, tzinfo=TAIPEI))
    assert rejected.value.error_kind == "issuer_identity_mismatch"

    unsafe_link = _payload()
    unsafe_link["news"][0]["link"] = NOTICE_URL.replace(
        "https://emops.twse.com.tw", "https://example.com"
    )
    assert parse_infohub_index(
        unsafe_link, TICKER, now=datetime(2026, 10, 17, 12, tzinfo=TAIPEI)
    )["candidates"] == []


def test_infohub_acquires_original_mops_disclosure_and_classifies_conference_notice():
    requested = []

    class Response:
        status_code = 200
        content = b"{}"

        def __init__(self, payload=None, content=None):
            self._payload = payload
            if payload is not None:
                self.content = json.dumps(payload).encode()
            if content is not None:
                self.content = content.encode()

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

        @property
        def text(self):
            return self.content.decode()

    def post(url, **kwargs):
        requested.append(("POST", url))
        return Response(_payload())

    def get(url, **kwargs):
        requested.append(("GET", url))
        return Response(content=_detail())

    records, audit = fetch_tpex_infohub_records(
        TICKER, now=datetime(2026, 10, 17, 12, tzinfo=TAIPEI), post=post, get=get
    )

    assert requested == [("POST", infohub_api_url(TICKER)), ("GET", NOTICE_URL)]
    assert len(records) == 1
    assert records[0]["ticker"] == TICKER
    assert records[0]["source"] == PROVIDER
    assert records[0]["source_type"] == "official_disclosure"
    assert records[0]["is_investor_conference"] is True
    assert records[0]["event_date"] == "2026-11-06"
    assert records[0]["event_time"] == "17:00"
    assert records[0]["transcript_available"] is False
    assert audit["status"] == "success"
    assert audit["coverage_status"] == "latest_10_index"
    assert audit["actual_provider"] == PROVIDER

    context, call_audit = fetch_tpex_infohub_earnings_call(
        TICKER, now=datetime(2026, 10, 17, 12, tzinfo=TAIPEI), post=post, get=get
    )
    assert context["date"] == "2026-11-06"
    assert context["transcript_available"] is False
    assert call_audit["status"] == "success"


def test_infohub_empty_latest_index_does_not_claim_no_recent_catalysts():
    payload = _payload()
    payload["news"] = []

    class Response:
        content = json.dumps(payload).encode()

        def json(self):
            return payload

        def raise_for_status(self):
            return None

    records, audit = fetch_tpex_infohub_records(
        TICKER,
        now=datetime(2026, 10, 17, 12, tzinfo=TAIPEI),
        post=lambda *_args, **_kwargs: Response(),
        get=lambda *_args, **_kwargs: pytest.fail("no detail should be fetched"),
    )
    assert records == []
    assert audit["status"] == "degraded_enrichment"
    assert "does_not_prove_no_recent_disclosures" == audit["error_kind"]


def test_earnings_call_official_index_uses_infohub_when_mops_is_empty(monkeypatch):
    import official_financials
    import official_financials_webpro_conference
    from data_fetch import earnings_call_fetcher
    from data_fetch.market_sources import tpex_infohub

    expected = {"ticker": TICKER, "date": "2026-11-06", "title": TITLE,
                "summary": "Verified official invitation", "transcript_available": False,
                "source": PROVIDER}
    details = {"status": "success", "actual_provider": PROVIDER,
               "record_count": 1, "http_request_sent": True}
    monkeypatch.setattr(official_financials, "fetch_mops_investor_conference_events",
                        lambda *_args, **_kwargs: [])
    monkeypatch.setattr(official_financials_webpro_conference, "taiwan_company_symbol",
                        lambda _ticker: "8299")
    monkeypatch.setattr(tpex_infohub, "fetch_tpex_infohub_earnings_call",
                        lambda _ticker, **_kwargs: (expected, details))

    diagnostics = {}
    result = earnings_call_fetcher._fetch_official_index_context(TICKER, diagnostics=diagnostics)

    assert result == expected
    assert diagnostics["actual_provider"] == PROVIDER
    assert diagnostics["component_statuses"]["TPEx_InfoHub"]["status"] == "success"
