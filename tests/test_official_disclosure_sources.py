"""Daily exchange snapshots are evidence, never proof of complete event history."""
from datetime import datetime, timezone
import sys
from types import SimpleNamespace

import httpx
import pytest

NOW = datetime(2026, 9, 25, 1, tzinfo=timezone.utc).timestamp()


def row(**updates):
    return {"出表日期": "1150925", "發言日期": "1150924", "發言時間": "70003",
            "公司代號": "2330", "公司名稱": "台積電", "主旨 ": "公告重要合約",
            "事實發生日": "1150920", "說明": "1.本公司完成合約。\r\n2.金額依公告。", **updates}


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr("time.time", lambda: NOW)
    yield
    cache_store.reset_cache_store_for_tests()


def test_roc_publication_is_separate_from_snapshot_and_fact_date():
    from official_disclosure_sources import parse_disclosure_rows
    documents, rejected = parse_disclosure_rows([row()], "twse", observed_at_epoch=NOW)
    assert rejected == 0
    document = documents[0]
    assert document["ticker"] == "2330.TW"
    assert document["published_at"] == "2026-09-24T07:00:03+08:00"
    assert document["event_date"] == "2026-09-20"
    assert document["retrieved_at_epoch"] == NOW
    assert document["text"] == row()["說明"]
    assert document["source_type"] == "official_disclosure"
    assert document["document_kind"] == "announcement"
    assert document["coverage_status"] == "text_available"
    assert document["title"] == "公告重要合約"


def test_tpex_schema_and_leading_zero_time_are_supported():
    from official_disclosure_sources import parse_disclosure_rows
    payload = {"Date": "1150924", "SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
               "發言日期": "1150923", "發言時間": "4329", "主旨": "增資發行條件",
               "事實發生日": "1150922", "說明": "發行條件。"}
    documents, rejected = parse_disclosure_rows([payload], "tpex", observed_at_epoch=NOW)
    assert rejected == 0
    assert documents[0]["ticker"] == "6488.TWO"
    assert documents[0]["published_at"] == "2026-09-23T00:43:29+08:00"


@pytest.mark.parametrize("update", [
    {"公司代號": "AAPL"}, {"發言日期": ""}, {"發言日期": "1150931"},
    {"發言日期": "1150926"}, {"發言日期": "1150925", "發言時間": "100000"},
    {"發言時間": "250000"}, {"主旨 ": ""},
])
def test_bad_identity_missing_invalid_or_future_publication_is_rejected(update):
    from official_disclosure_sources import parse_disclosure_rows
    documents, rejected = parse_disclosure_rows([row(**update)], "twse", observed_at_epoch=NOW)
    assert documents == []
    assert rejected == 1


def test_same_endpoint_and_day_do_not_collapse_different_events():
    from official_disclosure_sources import parse_disclosure_rows
    docs, _ = parse_disclosure_rows([row(), row(**{"主旨 ": "另一重大事件"})], "twse", observed_at_epoch=NOW)
    repeated, _ = parse_disclosure_rows([row()], "twse", observed_at_epoch=NOW + 100)
    assert docs[0]["url"] == docs[1]["url"]
    assert docs[0]["document_id"] != docs[1]["document_id"]
    assert docs[0]["document_id"] == repeated[0]["document_id"]
    assert docs[0]["content_sha256"] == repeated[0]["content_sha256"]


def test_metadata_without_text_and_explicit_bounded_text_truncation():
    from official_disclosure_sources import parse_disclosure_rows, MAX_TEXT_CHARS
    docs, _ = parse_disclosure_rows([row(**{"說明": ""}), row(**{"主旨 ": "另一重大公告", "說明": "文" * (MAX_TEXT_CHARS + 1)})], "twse", observed_at_epoch=NOW)
    assert docs[0]["coverage_status"] == "metadata_only"
    assert docs[0]["text"] == ""
    assert docs[1]["content_truncated"] is True
    assert len(docs[1]["text"]) == MAX_TEXT_CHARS
    assert docs[1]["original_text_chars"] == MAX_TEXT_CHARS + 1


@pytest.mark.parametrize("payload", [{}, {"error": "denied"}, "<html>denied</html>", ["unknown"]])
def test_unknown_envelopes_are_not_valid_empty(payload):
    from official_disclosure_sources import parse_disclosure_rows
    with pytest.raises(ValueError):
        parse_disclosure_rows(payload, "twse", observed_at_epoch=NOW)


def response(payload, status=200, headers=None):
    return httpx.Response(status, json=payload, headers=headers, request=httpx.Request("GET", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"))


def test_whole_market_snapshot_shared_across_tickers_preserves_acquisition(monkeypatch):
    import official_disclosure_sources as module
    calls = []
    monkeypatch.setattr(module, "sync_get", lambda *args, **kwargs: calls.append(args[0]) or response([row(), row(**{"公司代號": "2317"})]))
    first, first_meta = module.fetch_disclosure_snapshot("twse")
    monkeypatch.setattr("time.time", lambda: NOW + 120)
    second, second_meta = module.fetch_disclosure_snapshot("twse")
    assert len(calls) == 1
    assert first["documents"] == second["documents"]
    assert first_meta["fetched_at_epoch"] == second_meta["fetched_at_epoch"] == NOW
    assert second_meta["cache_hit"] is True
    assert second_meta["http_request_sent"] is False


def test_valid_empty_snapshot_does_not_trigger_cooldown(monkeypatch):
    import official_disclosure_sources as module
    monkeypatch.setattr(module, "sync_get", lambda *args, **kwargs: response([]))
    snapshot, meta = module.fetch_disclosure_snapshot("twse")
    assert snapshot["documents"] == []
    assert meta["outcome"] == "valid_empty"
    assert not meta.get("error_kind")


def test_retry_after_blocks_further_http_and_is_not_empty(monkeypatch):
    import official_disclosure_sources as module
    from search_provider_runtime import SourceResponseError
    calls = []
    def limited(*args, **kwargs):
        calls.append(1)
        result = response({}, 429, {"Retry-After": "600"})
        result.raise_for_status()
    monkeypatch.setattr(module, "sync_get", limited)
    with pytest.raises(SourceResponseError) as first:
        module.fetch_disclosure_snapshot("twse")
    monkeypatch.setattr("time.time", lambda: NOW + 61)
    with pytest.raises(SourceResponseError) as second:
        module.fetch_disclosure_snapshot("twse")
    assert len(calls) == 1
    assert first.value.error_kind == "rate_limited"
    assert second.value.diagnostic["http_request_sent"] is False
    assert second.value.diagnostic["retry_at"] == NOW + 600


def test_provider_indexes_all_companies_but_returns_only_matching_recent_ticker(monkeypatch):
    import official_disclosure_sources as module
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    saved, queries = [], []
    def upsert(documents, **kwargs):
        saved.extend(documents)
        return {"accepted": len(documents)}
    def search(ticker, **kwargs):
        queries.append((ticker, kwargs))
        return [item for item in saved if item["ticker"] == ticker]
    monkeypatch.setitem(sys.modules, "source_document_index", SimpleNamespace(upsert_source_documents=upsert, search_source_documents=search))
    monkeypatch.setattr(module, "sync_get", lambda *args, **kwargs: response([row(), row(**{"公司代號": "2317"})]))
    result = OfficialDisclosuresProvider().fetch(FetchRequest("2330.TW"))
    assert {item["ticker"] for item in saved} == {"2330.TW", "2317.TW"}
    assert {item["ticker"] for item in result.value["documents"]} == {"2330.TW"}
    assert queries[0][1]["kinds"] == ("official_disclosure",)
    assert queries[0][1]["since"]
    assert result.status == "degraded_enrichment"
    assert result.value["status"] == "partial"
    assert result.value["coverage_status"] == "partial"
    assert result.audit["coverage_status"] == "partial"
    assert result.audit["event_kind"] == "aggregate"
    assert not result.audit["http_request_sent"]
    assert result.value["fetched_at_epoch"] == NOW
    assert result.audit["fetched_at"] == "2026-09-25T01:00:00+00:00"
    assert result.audit["observed_at"] == "2026-09-24T07:00:03+08:00"


def test_provider_empty_current_company_never_asserts_no_announcements(monkeypatch):
    import official_disclosure_sources as module
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setitem(sys.modules, "source_document_index", SimpleNamespace(upsert_source_documents=lambda *a, **k: {}, search_source_documents=lambda *a, **k: []))
    monkeypatch.setattr(module, "sync_get", lambda *args, **kwargs: response([]))
    result = OfficialDisclosuresProvider().fetch(FetchRequest("2330.TW"))
    assert result.value["documents"] == []
    assert result.value["coverage_status"] == "partial"
    assert result.audit["retrieval_status"] == "valid_empty"
    assert result.status == "degraded_enrichment"


def test_force_refresh_does_not_duplicate_global_acquisition(monkeypatch):
    import official_disclosure_sources as module
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setitem(sys.modules, "source_document_index", SimpleNamespace(upsert_source_documents=lambda *a, **k: {}, search_source_documents=lambda *a, **k: []))
    calls = []
    monkeypatch.setattr(module, "sync_get", lambda *args, **kwargs: calls.append(1) or response([]))
    OfficialDisclosuresProvider().fetch(FetchRequest.from_ticker("2330.TW", force_refresh=True))
    OfficialDisclosuresProvider().fetch(FetchRequest.from_ticker("2317.TW", force_refresh=True))
    assert calls == [1]


def test_skipping_optional_http_reads_index_without_request(monkeypatch):
    import official_disclosure_sources as module
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setitem(sys.modules, "source_document_index", SimpleNamespace(upsert_source_documents=lambda *a, **k: {}, search_source_documents=lambda *a, **k: []))
    def no_http(*args, **kwargs):
        pytest.fail("Optional HTTP must remain disabled")
    monkeypatch.setattr(module, "sync_get", no_http)
    result = OfficialDisclosuresProvider().fetch(FetchRequest.from_ticker("2330.TW", skip_optional_http=True))
    assert result.value["retrieval_status"] == "skipped"
    assert result.audit["fetched_at"] is None


def test_index_failure_fallback_keeps_exact_lookback_and_issuer_boundary(monkeypatch):
    import official_disclosure_sources as module
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    def broken_index(*args, **kwargs):
        raise OSError("Index unavailable")
    monkeypatch.setitem(sys.modules, "source_document_index", SimpleNamespace(upsert_source_documents=broken_index, search_source_documents=broken_index))
    monkeypatch.setattr(module, "sync_get", lambda *a, **k: response([
        row(**{"發言日期": "1150826", "發言時間": "85959"}),
        row(**{"發言日期": "1150826", "發言時間": "90000"}),
        row(**{"公司代號": "2317"}),
    ]))
    result = OfficialDisclosuresProvider().fetch(FetchRequest("2330.TW"))
    assert len(result.value["documents"]) == 1
    assert result.value["documents"][0]["published_at"] == "2026-08-26T09:00:00+08:00"
    assert result.value["index_available"] is False


def test_provider_real_index_retains_dated_evidence_and_marks_failed_refresh_stale(monkeypatch, tmp_path):
    import official_disclosure_sources as module
    import source_document_index as index
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(index, "_database_path", lambda: tmp_path / "operational.sqlite3")
    monkeypatch.setattr(module, "sync_get", lambda *a, **k: response([row(), row(**{"公司代號": "2317"})]))
    provider = OfficialDisclosuresProvider()
    initial = provider.fetch(FetchRequest("2330.TW"))
    assert initial.value["index_available"] is True
    assert len(initial.value["documents"]) == 1
    assert len(index.search_source_documents("2317.TW")) == 1
    assert initial.value["documents"][0]["retrieved_at_epoch"] == NOW
    monkeypatch.setattr("time.time", lambda: NOW + 301)
    def limited(*args, **kwargs):
        response({}, 429, {"Retry-After": "600"}).raise_for_status()
    monkeypatch.setattr(module, "sync_get", limited)
    retained = provider.fetch(FetchRequest("2330.TW"))
    assert len(retained.value["documents"]) == 1
    assert retained.status == "degraded_enrichment"
    assert retained.value["retrieval_status"] == "error"
    assert retained.value["stale"] is True
    assert retained.audit["stale"] is True
    assert retained.audit["error_kind"] == "rate_limited"
    assert retained.audit["fetched_at_epoch"] == NOW
    assert retained.value["fetched_at_epoch"] == NOW
    assert retained.value["documents"][0]["retrieved_at_epoch"] == NOW


@pytest.mark.parametrize("scenario, expected_retrieval", [
    ("no_issuer_match", "success"), ("valid_empty", "valid_empty"), ("skipped", "skipped"),
])
def test_legitimate_no_documents_stays_partial_without_outage_after_real_merge(monkeypatch, tmp_path, scenario, expected_retrieval):
    import official_disclosure_sources as module
    import source_document_index as index
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(index, "_database_path", lambda: tmp_path / "operational.sqlite3")
    payload = [row(**{"公司代號": "2317"})] if scenario == "no_issuer_match" else []
    monkeypatch.setattr(module, "sync_get", lambda *a, **k: response(payload))
    request = FetchRequest.from_ticker("2330.TW", skip_optional_http=scenario == "skipped")
    result = OfficialDisclosuresProvider().fetch(request)
    merged = _merge_optional_http_bundle(
        {"ticker": "2330.TW", "source_audit": [result.audit]},
        {"official_disclosures": result.value}, refreshed_sources=["official_disclosures"],
    )
    audit = [entry for entry in merged["source_audit"] if entry["source"] == "official_disclosures"][-1]
    assert result.status == audit["status"] == "degraded_enrichment"
    assert not audit.get("error_kind")
    assert audit["record_count"] == 0
    assert merged["official_disclosures"]["retrieval_status"] == expected_retrieval
    assert merged["official_disclosures"]["status"] == "partial"


def test_real_provider_error_is_preserved_by_real_merge(monkeypatch, tmp_path):
    import official_disclosure_sources as module
    import source_document_index as index
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(index, "_database_path", lambda: tmp_path / "operational.sqlite3")
    def limited(*args, **kwargs):
        response({}, 429).raise_for_status()
    monkeypatch.setattr(module, "sync_get", limited)
    result = OfficialDisclosuresProvider().fetch(FetchRequest("2330.TW"))
    merged = _merge_optional_http_bundle(
        {"ticker": "2330.TW", "source_audit": [result.audit]},
        {"official_disclosures": result.value}, refreshed_sources=["official_disclosures"],
    )
    audit = [entry for entry in merged["source_audit"] if entry["source"] == "official_disclosures"][-1]
    assert result.status == audit["status"] == "error"
    assert audit["error_kind"] == "rate_limited"


@pytest.mark.parametrize("bare, resolved, expected_market", [("2330", "2330.TW", "twse"), ("6488", "6488.TWO", "tpex")])
def test_bare_ticker_uses_only_matching_context_exchange(monkeypatch, tmp_path, bare, resolved, expected_market):
    import official_disclosure_sources as module
    import source_document_index as index
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(index, "_database_path", lambda: tmp_path / "operational.sqlite3")
    calls = []
    monkeypatch.setattr(module, "sync_get", lambda url, **k: calls.append(url) or response([]))
    provider = OfficialDisclosuresProvider()
    assert provider.supports(FetchRequest(bare))
    result = provider.fetch(FetchRequest(bare), {"data": {"ticker": resolved}})
    assert calls == [module.MARKETS[expected_market]["url"]]
    assert result.value["actual_provider"] == module.MARKETS[expected_market]["provider"]


@pytest.mark.parametrize("context", [{}, {"data": {"ticker": "2317.TW"}}, {"data": {"ticker": "2330"}}, {"data": {"ticker": "AAPL"}}])
def test_bare_ticker_without_same_issuer_qualified_context_never_guesses_or_fetches(monkeypatch, context):
    import official_disclosure_sources as module
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    def no_http(*args, **kwargs):
        pytest.fail("Unresolved issuer must not call an exchange")
    monkeypatch.setattr(module, "sync_get", no_http)
    result = OfficialDisclosuresProvider().fetch(FetchRequest("2330"), context)
    assert result.status == "not_applicable"


def test_qualified_request_conflicting_with_context_issuer_does_not_fetch(monkeypatch, tmp_path):
    import official_disclosure_sources as module
    import source_document_index as index
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(index, "_database_path", lambda: tmp_path / "operational.sqlite3")
    calls = []
    monkeypatch.setattr(module, "sync_get", lambda url, **k: calls.append(url) or response([]))
    result = OfficialDisclosuresProvider().fetch(FetchRequest("6488.TWO"), {"data": {"ticker": "2330.TW"}})
    assert calls == []
    assert result.status == "not_applicable"


def test_context_may_correct_qualified_market_for_same_issuer(monkeypatch, tmp_path):
    import official_disclosure_sources as module
    import source_document_index as index
    from data_fetch.official_disclosures_provider import OfficialDisclosuresProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(index, "_database_path", lambda: tmp_path / "operational.sqlite3")
    calls = []
    monkeypatch.setattr(module, "sync_get", lambda url, **k: calls.append(url) or response([]))
    result = OfficialDisclosuresProvider().fetch(FetchRequest("6488.TW"), {"data": {"ticker": "6488.TWO"}})
    assert calls == [module.MARKETS["tpex"]["url"]]
    assert result.value["actual_provider"] == module.MARKETS["tpex"]["provider"]


def test_corrected_same_announcement_uses_new_revision_not_conflicting_document(monkeypatch, tmp_path):
    import sqlite3
    import official_disclosure_sources as module
    import source_document_index as index
    database = tmp_path / "operational.sqlite3"
    monkeypatch.setattr(index, "_database_path", lambda: database)
    first, _ = module.parse_disclosure_rows([row()], "twse", observed_at_epoch=NOW)
    index.upsert_source_documents(first, observed_at_epoch=NOW)
    monkeypatch.setattr("time.time", lambda: NOW + 301)
    revised, _ = module.parse_disclosure_rows([row(**{"說明": "更正：合約金額依最新公告。", "事實發生日": "1150921"})], "twse", observed_at_epoch=NOW + 301)
    assert first[0]["document_id"] == revised[0]["document_id"]
    assert first[0]["content_sha256"] != revised[0]["content_sha256"]
    index.upsert_source_documents(revised, observed_at_epoch=NOW + 301)
    documents = index.search_source_documents("2330.TW", kinds=("official_disclosure",))
    assert len(documents) == 1
    assert documents[0]["text"] == "更正：合約金額依最新公告。"
    assert documents[0]["event_date"] == "2026-09-21"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 2
