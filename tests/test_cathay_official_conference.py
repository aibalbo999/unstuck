"""Cathay IR metadata remains distinct from licensed presentation content."""

from datetime import date


def _page():
    return '''<html><title>國泰金融控股 2882</title>
    <div list001item><a href="/holdings/ir/events_and_announcements/events/event_info?EventID=EN2026">
      <div class="d-lg-flex"><div>2026/08/28</div><div>2026年第二季法人說明會(中文)</div></div></a>
      <a id="lnk_FileButtonLink" href="/holdings/-/media/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.pdf?sc_lang=zh-tw">PDF</a>
      <a id="lnk_VideoButtonLink" href="https://www.zucast.com/webcast/SAFEid">Webcast</a>
    </div></html>'''.encode()


def test_cathay_ir_accepts_dated_issuer_event_as_links_only():
    from official_cathay_conference import parse_index

    row = parse_index(_page(), today=date(2026, 10, 4))
    assert row["date"] == "2026-08-28"
    assert row["event_url"].startswith("https://www.cathayholdings.com/")
    assert row["presentation_url"].endswith(".pdf?sc_lang=zh-tw")
    assert row["webcast_url"].startswith("https://www.zucast.com/webcast/")


def test_cathay_ir_rejects_wrong_issuer_and_unsafe_material_link():
    from official_cathay_conference import parse_index

    assert parse_index(_page().replace(b"2882", b"2330"), today=date(2026, 10, 4)) is None
    assert parse_index(_page().replace(b"/holdings/-/media/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.pdf?sc_lang=zh-tw",
                                       b"https://evil.example/file.pdf"), today=date(2026, 10, 4)) is None


def test_cathay_ir_context_does_not_claim_transcript_or_pdf_content(monkeypatch):
    from official_cathay_conference import fetch_cathay_conference_context, INDEX_URL
    import official_cathay_conference as source

    class Response:
        status_code = 200
        content = _page()
        headers = {"content-type": "text/html; charset=utf-8"}

    monkeypatch.delenv("STOCK_AGENT_TEST_NO_NETWORK", raising=False)
    monkeypatch.setattr(source, "sync_get", lambda *a, **k: Response())
    monkeypatch.setattr(source, "record_observation", lambda *a, **k: None)
    monkeypatch.setattr(source, "shared_fetch", lambda _key, fetch, **_k: (fetch(), {"cache_hit": False}))
    details = {}
    context = fetch_cathay_conference_context("2882.TW", diagnostics=details)
    assert context["source_url"] == INDEX_URL
    assert context["summary"] == context["transcript_excerpt"] == ""
    assert context["transcript_available"] is False
    assert context["coverage_status"] == "metadata_only"
    assert all(item["content_retrieved"] is False for item in context["materials"])
    assert details["coverage_status"] == "partial"


def test_earnings_call_uses_cathay_ir_before_mops(monkeypatch):
    import official_cathay_conference as source
    import data_fetch.earnings_call_fetcher as fetcher

    expected = {"ticker": "2882.TW", "source": source.PROVIDER,
                "coverage_status": "metadata_only", "transcript_available": False}
    def official(_ticker, *, diagnostics):
        diagnostics.update(actual_provider=source.PROVIDER, coverage_status="partial")
        return expected
    monkeypatch.setattr(source, "fetch_cathay_conference_context", official)
    monkeypatch.setattr(fetcher, "_fetch_official_index_context",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("unexpected index fallback")))
    details = {}
    assert fetcher.fetch_free_earnings_call_context("2882.TW", diagnostics=details) is expected
    assert details["actual_provider"] == source.PROVIDER
    assert details["coverage_status"] == "partial"


def test_empty_cathay_ir_retains_official_index_fallback(monkeypatch):
    import official_cathay_conference as source
    import data_fetch.earnings_call_fetcher as fetcher

    def official(_ticker, *, diagnostics):
        diagnostics.update(actual_provider=source.PROVIDER, coverage_status="metadata_only")
        return {}
    def index(_ticker, *, diagnostics):
        diagnostics.update(actual_provider="TWSE WebPro conference metadata")
        return {"source": "TWSE WebPro conference metadata", "transcript_available": False}
    monkeypatch.setattr(source, "fetch_cathay_conference_context", official)
    monkeypatch.setattr(fetcher, "_fetch_official_index_context", index)
    details = {}
    assert fetcher.fetch_free_earnings_call_context("2882.TW", diagnostics=details)["source"] == "TWSE WebPro conference metadata"
    assert details["component_statuses"]["cathay_ir"]["actual_provider"] == source.PROVIDER
