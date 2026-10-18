from __future__ import annotations

from datetime import date, datetime

import httpx
import pytest


INDEX_URL = "https://wwwc.twse.com.tw/rwd/en/IIH/company/events"
NOTICE_URL = (
    "https://emops.twse.com.tw/server-java/t05sr01_1_e?"
    "isNew=Y&seq_no=3&spoke_time=164357&spoke_date=20260805&co_id=2838"
)
MONTH_URL = (
    "https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show"
    "&code=2002&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09"
)


def iih_payload(*, ticker="2838", name="UNION BANK OF TAIWAN", conferences=None):
    return {
        "info": {
            "status": "success",
            "data": {"code": ticker, "name": name, "shortName": "UBOT"},
        },
        "news": [],
        "fina": [],
        "conference": conferences if conferences is not None else [{
            "companyId": "2838",
            "companyName": "UNION BANK OF TAIWAN",
            "subject": "Announcement of Union Bank of Taiwan 2Q26 Institutional Investor Conference",
            "date": "2026/08/05",
            "time": "16:43",
            "link": NOTICE_URL,
        }],
    }


CSC_MONTH_PAYLOAD = iih_payload(
    ticker="2002", name="CHINA STEEL CORPORATION", conferences=[{
        "companyId": "2002", "companyName": "CSC",
        "subject": "2026/09 Investor Conferences", "date": "2026/09/22",
        "time": "13:55", "link": MONTH_URL,
    }],
)

CSC_MONTH_HTML = """<!doctype html><html><body>
<table><tr><th>Market</th><th>Code</th><th>Company Name</th><th colspan="2">Investor Conference</th></tr>
<tr><th>Date</th><th>Time</th></tr>
<tr><td>Listed Company</td><td>2002</td><td>China Steel Corporation</td><td>20260923</td><td>14:00</td></tr>
<tr><td>Investor Conference Information</td><td><a href="/nas/STR/200220260922E001.pdf">200220260922E001.pdf</a></td></tr>
<tr><td>Live Streaming Website</td><td></td></tr>
<tr><td>Video/Audio Replay</td><td>None</td></tr></table></body></html>"""


NOTICE_HTML = """<!doctype html><html><body>
<table><tr><td>Today's Information</td></tr></table>
<table>
 <tr><td>Provided by: UNION BANK OF TAIWAN</td></tr>
 <tr><td>SEQ_NO</td><td>3</td><td>Date of announcement</td><td>2026/08/05</td><td>Time of announcement</td><td>16:43:57</td></tr>
 <tr><td>Subject</td><td>Announcement of Union Bank of Taiwan 2Q26 Institutional Investor Conference</td></tr>
 <tr><td>Date of events</td><td>2026/08/06</td><td>To which item it meets</td><td>paragraph 12</td></tr>
 <tr><td>Statement</td><td>1.Date of institutional investor conference:2026/08/06
 2.Time of institutional investor conference:14:00
 3.Location of institutional investor conference: Internet/webcast
 4.Outline of institutional investor conference: Hold Analysts Meeting announcing 2Q26 operating results in Mandarin.
 5.Any other matters that need to be specified:None</td></tr>
</table></body></html>"""


class FakeResponse:
    def __init__(self, *, payload=None, text="", url="https://example.invalid"):
        self.status_code = 200
        self.content = text.encode("utf-8") if text else b"{}"
        self.text = text
        self.headers = {"content-type": "application/json" if payload is not None else "text/html; charset=utf-8"}
        self._payload = payload
        self.url = url

    def json(self):
        return self._payload


def test_parse_iih_candidates_uses_exact_ticker_and_official_notice_url():
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates

    result = parse_iih_candidates(iih_payload(), "2838.TW", today=date(2026, 10, 17))
    assert result["issuer_name"] == "UNION BANK OF TAIWAN"
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["notice_url"] == NOTICE_URL
    assert result["candidates"][0]["announcement_date"] == "2026-08-05"


def test_parse_iih_candidates_accepts_exchange_short_name_when_subject_anchors_issuer():
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates

    payload = iih_payload()
    payload["conference"][0]["companyName"] = "UBOT"
    result = parse_iih_candidates(payload, "2838.TW", today=date(2026, 10, 17))
    assert result["candidates"][0]["subject"].startswith("Announcement of Union Bank of Taiwan")


def test_parse_iih_candidates_accepts_twse_legacy_leading_query_separator():
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates

    payload = iih_payload()
    payload["conference"][0]["link"] = payload["conference"][0]["link"].replace("?isNew", "?&isNew")
    result = parse_iih_candidates(payload, "2838.TW", today=date(2026, 10, 17))
    assert len(result["candidates"]) == 1


@pytest.mark.parametrize("changes", [
    {"companyId": "2839"},
    {"link": "https://attacker.example/server-java/t05sr01_1_e?co_id=2838"},
    {"date": "2026/10/18"},
    {"date": "2026/02/30"},
])
def test_parse_iih_candidates_rejects_wrong_issuer_unsafe_link_and_invalid_dates(changes):
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates

    conference = {**iih_payload()["conference"][0], **changes}
    if changes.get("companyId"):
        payload = iih_payload(conferences=[conference])
    else:
        payload = iih_payload(conferences=[conference])
    result = parse_iih_candidates(payload, "2838.TW", today=date(2026, 10, 17))
    assert result["candidates"] == []


def test_parse_iih_candidates_fails_closed_on_mismatched_issuer_envelope():
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates
    from search_provider_runtime import SourceResponseError

    with pytest.raises(SourceResponseError) as error:
        parse_iih_candidates(iih_payload(ticker="2839"), "2838.TW", today=date(2026, 10, 17))
    assert error.value.error_kind == "issuer_identity_mismatch"


def test_parse_notice_page_preserves_announcement_and_event_dates_separately():
    from data_fetch.market_sources.twse_iih_conference_notice import parse_notice_page
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates

    candidate = parse_iih_candidates(iih_payload(), "2838.TW", today=date(2026, 10, 17))["candidates"][0]
    notice = parse_notice_page(
        NOTICE_HTML,
        ticker="2838.TW",
        issuer_name="UNION BANK OF TAIWAN",
        candidate=candidate,
        now=datetime.fromisoformat("2026-10-17T09:00:00+08:00"),
    )
    assert notice["announcement_date"] == "2026-08-05"
    assert notice["event_date"] == "2026-08-06"
    assert notice["event_time"] == "14:00"
    assert "Hold Analysts Meeting" in notice["statement"]
    assert notice["transcript_available"] is False
    assert notice["coverage_status"] == "official_notice_text_only"


@pytest.mark.parametrize("replacement", [
    ("UNION BANK OF TAIWAN", "UNION BANCORP"),
    ("2Q26 Institutional Investor Conference", "2Q26 Quarterly Results"),
    ("Date of events</td><td>2026/08/06", "Date of events</td><td>2099/08/06"),
])
def test_parse_notice_page_rejects_wrong_issuer_nonconference_and_future_event(replacement):
    from data_fetch.market_sources.twse_iih_conference_notice import parse_notice_page
    from data_fetch.market_sources.twse_iih_conference_notice import parse_iih_candidates
    from search_provider_runtime import SourceResponseError

    old, new = replacement
    html = NOTICE_HTML.replace(old, new)
    candidate = parse_iih_candidates(iih_payload(), "2838.TW", today=date(2026, 10, 17))["candidates"][0]
    with pytest.raises(SourceResponseError):
        parse_notice_page(
            html,
            ticker="2838.TW",
            issuer_name="UNION BANK OF TAIWAN",
            candidate=candidate,
            now=datetime.fromisoformat("2026-10-17T09:00:00+08:00"),
        )


def test_live_adapter_records_one_verified_notice_success(monkeypatch):
    import data_fetch.market_sources.twse_iih_conference_notice as provider

    calls = []
    observations = []

    class FakeHttp:
        http_request_count = 0

        def __init__(self, deadline):
            self.deadline = deadline

        def get(self, url, *, params=None, **kwargs):
            calls.append((url, params))
            self.http_request_count += 1
            if url == INDEX_URL:
                return FakeResponse(payload=iih_payload(), url=url)
            assert url == NOTICE_URL
            return FakeResponse(text=NOTICE_HTML, url=url)

    monkeypatch.setattr(provider, "BoundedHistoryHttp", FakeHttp)
    monkeypatch.setattr(provider, "record_observation", lambda *a, **k: observations.append((a, k)))
    diagnostics = {}
    context = provider.fetch_twse_iih_conference_notice(
        "2838.TW",
        diagnostics=diagnostics,
        now=datetime.fromisoformat("2026-10-17T09:00:00+08:00"),
    )

    assert [call[0] for call in calls] == [INDEX_URL, NOTICE_URL]
    assert context["ticker"] == "2838.TW"
    assert context["date"] == "2026-08-06"
    assert context["source"] == provider.PROVIDER
    assert context["transcript_available"] is False
    assert context["summary"] == context["conference_notice"]["statement"]
    assert diagnostics["actual_provider"] == provider.PROVIDER
    assert diagnostics["coverage_status"] == "official_notice_text_only"
    assert len(observations) == 1
    assert observations[0][1]["outcome"] == "results"
    assert observations[0][1]["count"] == 1


def test_bounded_history_transport_accepts_only_exact_mops_notice_route():
    from data_fetch.market_sources.twse_history_transport import _mops_conference_notice_url

    assert _mops_conference_notice_url(NOTICE_URL)
    assert _mops_conference_notice_url(NOTICE_URL.replace("?isNew", "?&isNew"))
    assert not _mops_conference_notice_url(NOTICE_URL.replace("emops.twse.com.tw", "attacker.example"))
    assert not _mops_conference_notice_url(NOTICE_URL + "&redirect=https://attacker.example")
    assert not _mops_conference_notice_url(NOTICE_URL.replace("seq_no=3", "seq_no=../3"))


def test_bounded_history_transport_accepts_only_exact_mops_month_page():
    from data_fetch.market_sources.twse_history_transport import _mops_conference_month_url

    assert _mops_conference_month_url(MONTH_URL)
    assert _mops_conference_month_url(MONTH_URL.replace("code=2002", "code=2003"))
    assert not _mops_conference_month_url(MONTH_URL + "&redirect=https://attacker.example")
    assert not _mops_conference_month_url(MONTH_URL.replace("emops.twse.com.tw", "attacker.example"))
    assert not _mops_conference_month_url(MONTH_URL.replace("MM=09", "MM=13"))
    assert not _mops_conference_month_url(MONTH_URL.replace("emops.twse.com.tw", "emops.twse.com.tw:bad"))


def test_official_index_falls_back_to_iih_notice_after_mops_failure(monkeypatch):
    import official_financials
    from data_fetch import earnings_call_fetcher
    from search_provider_runtime import SourceResponseError

    def mops_failure(*args, **kwargs):
        raise SourceResponseError("timeout")

    expected = {
        "ticker": "2838.TW", "date": "2026-08-06", "title": "Official conference notice",
        "summary": "Public announcement text", "source": "TWSE IIH/MOPS official conference notice",
    }

    def iih_success(ticker, *, diagnostics):
        diagnostics.update(actual_provider=expected["source"], status="success",
                           record_count=1, coverage_status="official_notice_text_only",
                           http_request_sent=True)
        return expected

    monkeypatch.setattr(official_financials, "fetch_mops_investor_conference_events", mops_failure)
    monkeypatch.setattr(
        "data_fetch.market_sources.twse_iih_conference_notice.fetch_twse_iih_conference_notice",
        iih_success,
    )
    diagnostics = {}
    result = earnings_call_fetcher._fetch_official_index_context("2838.TW", diagnostics=diagnostics)

    assert result == expected
    assert diagnostics["actual_provider"] == expected["source"]
    assert diagnostics["coverage_status"] == "official_notice_text_only"
    assert diagnostics["component_statuses"]["MOPS"]["error_kind"] == "timeout"
    assert diagnostics["component_statuses"]["TWSE_IIH_MOPS_notice"]["status"] == "success"


def test_official_index_uses_iih_notice_after_valid_empty_mops_history(monkeypatch):
    import official_financials
    from data_fetch import earnings_call_fetcher

    mops_years = []
    expected = {
        "ticker": "2838.TW", "date": "2026-08-06",
        "source": "TWSE IIH/MOPS monthly conference index",
        "materials": [{"label": "英文簡報檔案", "url": "https://emops.twse.com.tw/nas/STR/283820260806E001.pdf"}],
    }

    def mops_empty(_ticker, **kwargs):
        mops_years.append(kwargs.get("year"))
        return []

    def iih_success(_ticker, diagnostics, **kwargs):
        details = {"actual_provider": expected["source"], "status": "success",
                   "record_count": 1, "http_request_sent": True,
                   "coverage_status": "official_monthly_event_metadata_with_material_links"}
        components = dict(kwargs.get("components") or {})
        components["TWSE_IIH_MOPS_notice"] = details
        diagnostics.update(details, component_statuses=components)
        return expected

    monkeypatch.setattr(official_financials, "fetch_mops_investor_conference_events", mops_empty)
    monkeypatch.setattr(earnings_call_fetcher, "_fetch_twse_iih_notice_fallback", iih_success)
    monkeypatch.setattr(earnings_call_fetcher, "_fetch_irengage_fallback",
                        lambda _ticker, context, _diagnostics, **_options: context)

    diagnostics = {}
    result = earnings_call_fetcher._fetch_official_index_context(
        "2838.TW", diagnostics=diagnostics, use_cache=False,
    )

    assert result == expected
    assert len(mops_years) == 2
    assert diagnostics["component_statuses"]["TWSE_IIH_MOPS_notice"]["status"] == "success"


def test_iih_fallback_adds_exact_month_mops_material_links(monkeypatch):
    import official_financials
    from data_fetch import earnings_call_fetcher

    notice_context = {
        "ticker": "2002.TW", "date": "2026-09-23", "title": "CSC investor conference",
        "summary": "Official conference notice text", "materials": [],
        "source": "TWSE IIH/MOPS official conference notice",
        "source_url": "https://emops.twse.com.tw/server-java/t05sr01_1_e?co_id=2002",
        "coverage_status": "official_notice_text_only",
    }
    calls = []

    def notice_fetch(ticker, *, diagnostics):
        diagnostics.update(status="success", record_count=1, http_request_count=2,
                           http_request_sent=True, coverage_status="official_notice_text_only")
        return notice_context.copy()

    def month_fetch(ticker, *, year, month, limit, use_cache, force_refresh, diagnostics):
        calls.append((ticker, year, month, limit, use_cache))
        diagnostics.update(status="success", record_count=1, http_request_count=1,
                           http_request_sent=True)
        return [{
            "ticker": "2002", "date": "2026-09-23", "materials": [
                {"label": "英文簡報檔案", "url": "https://mopsov.twse.com.tw/nas/STR/200220260922E001.pdf"}
            ],
        }]

    monkeypatch.setattr(
        "data_fetch.market_sources.twse_iih_conference_notice.fetch_twse_iih_conference_notice",
        notice_fetch,
    )
    monkeypatch.setattr(official_financials, "fetch_mops_investor_conference_events", month_fetch)

    diagnostics = {}
    result = earnings_call_fetcher._fetch_twse_iih_notice_fallback(
        "2002.TW", diagnostics, use_cache=False,
    )

    assert calls == [("2002.TW", 2026, 9, 3, False)], diagnostics["component_statuses"]["MOPS_event_month"]
    assert result["materials"] == [{
        "label": "英文簡報檔案",
        "url": "https://mopsov.twse.com.tw/nas/STR/200220260922E001.pdf",
    }]
    assert result["coverage_status"] == "official_notice_text_only"
    assert diagnostics["component_statuses"]["MOPS_event_month"]["status"] == "success"


def test_parse_iih_month_candidate_and_mops_event_page_preserve_exact_official_material():
    from data_fetch.market_sources.twse_iih_conference_notice import (
        parse_iih_candidates, parse_month_index_page,
    )

    candidate = parse_iih_candidates(
        CSC_MONTH_PAYLOAD, "2002.TW", today=date(2026, 10, 17),
    )["month_candidates"][0]
    records = parse_month_index_page(
        CSC_MONTH_HTML, ticker="2002.TW", issuer_name="CHINA STEEL CORPORATION",
        candidate=candidate, today=date(2026, 10, 17),
    )

    assert len(records) == 1
    assert records[0]["date"] == "2026-09-23"
    assert records[0]["materials"] == [{
        "label": "英文簡報檔案",
        "url": "https://emops.twse.com.tw/nas/STR/200220260922E001.pdf",
    }]
    assert records[0]["source_url"] == MONTH_URL


def test_parse_iih_month_page_accepts_official_corporation_abbreviation():
    from data_fetch.market_sources.twse_iih_conference_notice import (
        parse_iih_candidates, parse_month_index_page,
    )

    payload = iih_payload(
        ticker="3703", name="CONTINENTAL HOLDINGS CORPORATION", conferences=[{
            "companyId": "3703",
            "companyName": "CONTINENTAL HOLDINGS CORPORATION",
            "subject": "2026/08 Investor Conferences",
            "date": "2026/08/06",
            "time": "15:00",
            "link": "https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=3703&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=08",
        }],
    )
    candidate = parse_iih_candidates(
        payload, "3703.TW", today=date(2026, 10, 17),
    )["month_candidates"][0]
    html = """<!doctype html><html><body><table>
    <tr><th>Market</th><th>Code</th><th>Company Name</th><th colspan="2">Investor Conference</th></tr>
    <tr><th>Date</th><th>Time</th></tr>
    <tr><td>Listed Company</td><td>3703</td><td>CONTINENTAL HOLDINGS CORP.</td><td>20260810</td><td>15:00</td></tr>
    </table></body></html>"""

    records = parse_month_index_page(
        html, ticker="3703.TW", issuer_name="CONTINENTAL HOLDINGS CORPORATION",
        candidate=candidate, today=date(2026, 10, 17),
    )

    assert len(records) == 1
    assert records[0]["ticker"] == "3703.TW"
    assert records[0]["date"] == "2026-08-10"


@pytest.mark.parametrize("html", [
    CSC_MONTH_HTML.replace("China Steel Corporation", "Other Corporation"),
    CSC_MONTH_HTML.replace("20260923", "20261023"),
])
def test_parse_iih_month_page_fails_closed_on_wrong_identity_or_month(html):
    from data_fetch.market_sources.twse_iih_conference_notice import (
        parse_iih_candidates, parse_month_index_page,
    )
    from search_provider_runtime import SourceResponseError

    candidate = parse_iih_candidates(
        CSC_MONTH_PAYLOAD, "2002.TW", today=date(2026, 10, 17),
    )["month_candidates"][0]
    with pytest.raises(SourceResponseError):
        parse_month_index_page(
            html, ticker="2002.TW", issuer_name="CHINA STEEL CORPORATION",
            candidate=candidate, today=date(2026, 10, 17),
        )


def test_parse_iih_month_page_returns_empty_for_a_different_company_row():
    from data_fetch.market_sources.twse_iih_conference_notice import (
        parse_iih_candidates, parse_month_index_page,
    )

    candidate = parse_iih_candidates(
        CSC_MONTH_PAYLOAD, "2002.TW", today=date(2026, 10, 17),
    )["month_candidates"][0]
    assert parse_month_index_page(
        CSC_MONTH_HTML.replace("2002</td>", "2003</td>"),
        ticker="2002.TW", issuer_name="CHINA STEEL CORPORATION",
        candidate=candidate, today=date(2026, 10, 17),
    ) == []


def test_live_adapter_prefers_iih_published_month_page_with_material_link(monkeypatch):
    import data_fetch.market_sources.twse_iih_conference_notice as provider

    calls = []
    observations = []

    class FakeHttp:
        http_request_count = 0
        request_observations = []

        def __init__(self, deadline):
            self.deadline = deadline

        def get(self, url, *, params=None, **kwargs):
            calls.append((url, params))
            self.http_request_count += 1
            if url == INDEX_URL:
                return FakeResponse(payload=CSC_MONTH_PAYLOAD, url=url)
            assert url == MONTH_URL
            return FakeResponse(text=CSC_MONTH_HTML, url=url)

    monkeypatch.setattr(provider, "BoundedHistoryHttp", FakeHttp)
    monkeypatch.setattr(provider, "record_observation", lambda *a, **k: observations.append((a, k)))
    diagnostics = {}

    context = provider.fetch_twse_iih_conference_notice(
        "2002.TW", diagnostics=diagnostics,
        now=datetime.fromisoformat("2026-10-17T09:00:00+08:00"),
    )

    assert [url for url, _ in calls] == [INDEX_URL, MONTH_URL]
    assert context["date"] == "2026-09-23"
    assert context["transcript_available"] is False
    assert context["coverage_status"] == "official_monthly_event_metadata_with_material_links"
    assert diagnostics["actual_provider"] == provider.MONTH_INDEX_PROVIDER
    assert len(observations) == 1
    assert observations[0][0][0] == provider.MONTH_INDEX_PROVIDER
    assert observations[0][1]["outcome"] == "results"


def test_official_index_recovery_uses_the_iih_published_month_page(monkeypatch):
    import official_financials
    from data_fetch import earnings_call_fetcher
    from search_provider_runtime import SourceResponseError

    def mops_annual_timeout(*args, **kwargs):
        raise SourceResponseError("timeout")

    recovered = {
        "ticker": "2002.TW", "date": "2026-09-23",
        "materials": [{"label": "英文簡報檔案", "url": "https://emops.twse.com.tw/nas/STR/200220260922E001.pdf"}],
        "source": "TWSE IIH/MOPS monthly conference index",
        "coverage_status": "official_monthly_event_metadata_with_material_links",
    }

    def iih_month_page(ticker, *, diagnostics):
        diagnostics.update(actual_provider=recovered["source"], status="success", record_count=1,
                           http_request_sent=True, http_request_count=2,
                           coverage_status=recovered["coverage_status"])
        return recovered

    monkeypatch.setattr(official_financials, "fetch_mops_investor_conference_events", mops_annual_timeout)
    monkeypatch.setattr(
        "data_fetch.market_sources.twse_iih_conference_notice.fetch_twse_iih_conference_notice",
        iih_month_page,
    )
    monkeypatch.setattr(earnings_call_fetcher, "_fetch_irengage_fallback",
                        lambda ticker, context, diagnostics, **options: context)

    diagnostics = {}
    result = earnings_call_fetcher._fetch_official_index_context(
        "2002.TW", diagnostics=diagnostics, use_cache=False,
    )

    assert result == recovered
    assert diagnostics["fallback_reason"] == "timeout"
    assert diagnostics["actual_provider"] == recovered["source"]
    assert diagnostics["component_statuses"]["TWSE_IIH_MOPS_notice"]["status"] == "success"
