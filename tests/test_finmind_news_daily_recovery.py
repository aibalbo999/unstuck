"""A one-day news API must not be mistaken for a thirty-day query."""
from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from data_fetch.types import FetchRequest


ROW = {"date": "2026-10-02 05:36:00", "stock_id": "3023", "title": "信邦(3023)9月營收創新高",
       "link": "https://ww2.money-link.com.tw/realtimenews/NewsContent.aspx?SN=2426815002&PU=1002", "source": "富聯網"}


def observed_forum_row():
    from pathlib import Path
    return json.loads((Path(__file__).parent / "fixtures" / "finmind-forum-only-news-20261012.json").read_bytes())["data"][0]


def test_forum_only_first_sample_continues_to_editorial_news(monkeypatch, isolated):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    from official_response_evidence import read_response

    isolated[0] = datetime(2026, 10, 13, tzinfo=timezone.utc).timestamp()
    forum = observed_forum_row()
    editorial = {**ROW, "stock_id": "6152", "date": "2026-10-11 05:36:00", "title": "百一(6152)9月營收公告"}
    calls = install_http(monkeypatch, {"2026-10-12": [forum], "2026-10-11": [editorial]})

    result = fetch_finmind_news_result(FetchRequest.from_ticker("6152.TW"))

    assert [r["link"] for r in result.value] == [editorial["link"]]
    assert [c["query"]["start_date"][0] for c in calls] == ["2026-10-12", "2026-10-11"]
    assert result.audit["rejected_reason_counts"] == {"forum_post_is_not_news": 1}
    assert result.status == "success"
    assert result.audit["quality_status"] == "partial"
    from provider_acquisition import observation_kind
    assert observation_kind({**result.audit, "details": result.audit}) == "fetched_count"
    assert json.loads(read_response(result.audit["components"][0]["raw_http_receipt"]))["data"] == [forum]


def test_all_forum_samples_are_not_successful_news(monkeypatch, isolated):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    isolated[0] = datetime(2026, 10, 13, tzinfo=timezone.utc).timestamp()
    forum = observed_forum_row()
    by_day = {day: [{**forum, "date": day + " 02:07:04", "social_channel": "cmoney_stock_direct"}]
              for day in ["2026-10-12", "2026-10-11", "2026-10-05"]}
    calls = install_http(monkeypatch, by_day)
    result = fetch_finmind_news_result(FetchRequest.from_ticker("6152.TW"))
    assert result.value == []
    assert result.status != "success"
    assert result.audit["rejected_reason_counts"] == {"forum_post_is_not_news": 3}
    assert len(calls) == result.audit["http_request_count"] == 3


def test_saved_finmind_forum_cannot_count_toward_news_gate():
    from source_content_selection import select_company_records
    forum = observed_forum_row()
    data = {"ticker": "6152.TW", "company_name": "百一"}
    record = {**forum, "source_type": "finmind_news"}
    selected, audit = select_company_records([record], data, cutoff="2026-10-13T00:00:00+00:00")
    assert selected == []
    assert audit["rejected_reason_counts"] == {"forum_post_is_not_news": 1}
    assert audit["source_record_archive"][0]["record"] == record


def test_cmoney_editorial_and_existing_direct_social_role_remain_separate():
    from source_content_selection import select_company_records
    data = {"ticker": "6152.TW", "company_name": "百一"}
    forum = observed_forum_row()
    editorial = {**forum, "title": "百一(6152)法人論壇報導", "link": "https://www.cmoney.tw/notes/note-detail.aspx?nid=12345", "source_type": "finmind_news"}
    social = {**forum, "source_type": "forum_cmoney", "social_channel": "cmoney_stock_direct"}
    selected, audit = select_company_records([editorial, social], data, cutoff="2026-10-13T00:00:00+00:00")
    assert [r["link"] for r in selected] == [editorial["link"], forum["link"]]
    assert audit["rejected_count"] == 0


def editorial_records(count):
    return [{"title": f"百一(6152)營收營運展望新聞 {i}", "date": "2026-10-11T01:00:00+00:00",
             "source": f"publisher{i % 3}", "link": f"https://publisher{i % 3}.example/news/{i}",
             "source_type": "google_news_rss_search"} for i in range(count)]


def test_saved_projection_cannot_promote_finmind_forum_to_eighth_news():
    from copy import deepcopy
    from news_freshness_policy import apply_news_only_freshness
    forum = {**observed_forum_row(), "source_type": "finmind_news"}
    social = {"original": True}
    data = {"ticker": "6152.TW", "company_name": "百一", "recent_catalysts": editorial_records(7),
            "unverified_catalysts": [forum], "social_sentiment": social}
    cutoff = "2026-10-13T00:00:00+00:00"
    apply_news_only_freshness(data, cutoff=cutoff)
    assert data["news_selection"]["eligible_count"] == 7
    assert data["news_selection"]["source_role_unverified_count"] == 1
    assert all(r["link"] != forum["link"] for r in data["recent_catalysts"])
    archived = data["unverified_catalysts"][0]
    assert archived["link"] == forum["link"] and archived["source_role_status"] == "forum_post_is_not_news"
    assert archived["publication_date_original"]["date"] == forum["date"]
    assert data["social_sentiment"] == social
    once = deepcopy(data)
    apply_news_only_freshness(data, cutoff=cutoff)
    assert data == once


def test_source_only_merge_does_not_restore_old_finmind_forum(monkeypatch):
    from copy import deepcopy
    import recent_catalyst_source_refresh as refresh
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(refresh.time, "time", lambda: now.timestamp())
    forum = {**observed_forum_row(), "source_type": "finmind_news"}
    data = {"ticker": "6152.TW", "company_name": "百一", "quote_type": "EQUITY", "recent_catalysts": [forum],
            "current_price": 1., "revenue_ttm_raw": 2., "social_sentiment": {"original": True}, "source_audit": []}
    before = deepcopy(data)
    records = editorial_records(8)
    audit = {"source": "recent_catalysts", "provider": "Alternative Search", "status": "success",
             "record_count": 8, "quality_status": "sufficient_candidates", "selection_policy": "company-time-v1",
             "fetched_at_epoch": now.timestamp(), "fetched_at": now.isoformat(), "selection_cutoff": now.isoformat(),
             "cache_hit": False, "stale": False, "fetch_id": "finmind-role-regression"}
    assert refresh.valid_recent_receipt(records, audit, data)
    merged = refresh.merge_recent_source(data, [], records, [audit], data["ticker"])
    assert merged["news_selection"]["eligible_count"] == 8
    assert all(r["link"] != forum["link"] for key in ("recent_catalysts", "additional_recent_catalysts")
               for r in merged[key])
    assert any(r["link"] == forum["link"] for r in merged["unverified_catalysts"])
    assert data == before
    assert all(merged[key] == before[key] for key in ("current_price", "revenue_ttm_raw", "social_sentiment"))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    import provider_resilience
    from data_fetch.market_sources import finmind_news as news
    cache_store.set_cache_backend(InMemoryCache())
    now = [datetime(2026, 10, 10, 0, tzinfo=timezone.utc).timestamp()]
    monkeypatch.setattr(news.time, "time", lambda: now[0])
    for name in ("_check_provider_state", "enforce_provider_throttle", "_record_provider_success", "_record_provider_failure"):
        monkeypatch.setattr(provider_resilience, name, lambda *a, **k: None)
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "3")
    yield now
    cache_store.reset_cache_store_for_tests()


def install_http(monkeypatch, rows_by_day=None, *, status=200, api_status=200):
    from data_fetch.market_sources import finmind_news_transport as transport
    calls = []

    def collect(argv, deadline, **kwargs):
        url = argv[-1]
        q = parse_qs(urlsplit(url).query)
        calls.append({"url": url, "query": q, "deadline": deadline, "argv": argv, "limits": kwargs})
        rows = (rows_by_day or {}).get(q["start_date"][0], [])
        body = json.dumps({"status": api_status, "msg": "success", "data": rows}, ensure_ascii=False).encode()
        return {"body": body, "headers": f"HTTP/1.1 {status} OK\r\nContent-Type: application/json\r\n\r\n".encode(),
                "metadata": json.dumps({"http_code": status, "url_effective": url, "num_redirects": 0}).encode(),
                "process_started": True}, 0, None

    monkeypatch.setattr(transport, "collect_capped_process", collect)
    # Only the fully replaced process seam can pass the adapter's network guard;
    # sockets and all other transports retain the runner's isolation.
    monkeypatch.delenv("STOCK_AGENT_TEST_NO_NETWORK", raising=False)
    return calls


def test_legacy_public_news_helper_recovers_a_recent_day(monkeypatch):
    from data_fetch.market_sources import taiwan

    calls = install_http(monkeypatch, {"2026-10-02": [ROW]})
    records = taiwan.fetch_finmind_news_catalysts("3023.TW")

    assert len(records) == 1
    assert records[0]["title"] == ROW["title"]
    assert 1 <= len(calls) <= 3
    assert all("end_date" not in c["query"] for c in calls)
    assert all("2026-09-10" < c["query"]["start_date"][0] <= "2026-10-10" for c in calls)


def test_original_bytes_dedup_and_cache_keep_observation_epoch(monkeypatch, isolated):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    from official_response_evidence import read_response
    from provider_acquisition import observation_kind
    calls = install_http(monkeypatch, {"2026-10-02": [ROW, {**ROW, "source": "另一來源標籤"}]})
    first = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert first.status == "success" and len(first.value) == 1
    assert first.audit["raw_count"] == 2 and first.audit["duplicate_count"] == 1
    assert first.audit["coverage_status"] == "bounded_daily_samples"
    assert first.audit["http_request_count"] == len(calls) == 3
    receipt = first.value[0]["finmind_news_receipt"]
    assert json.loads(read_response(receipt["raw_http_receipt"]))["data"][receipt["row_index"]] == ROW
    assert first.value[0]["date"] == "2026-10-02"
    assert first.value[0]["publication_date_original"]["timezone"] == "not_reported"
    isolated[0] += 100
    second = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert second.value == first.value and len(calls) == 3
    assert second.audit["fetched_at_epoch"] == first.audit["fetched_at_epoch"]
    assert second.status == "skipped_fresh_cache" and second.audit["http_request_sent"] is False
    assert second.audit["provider_attempts"] == []
    assert observation_kind({**second.audit, "details": second.audit}) == "fresh_cache_count"


@pytest.mark.parametrize("http_status,api_status", [(429, 429), (403, 403), (504, 504), (200, 429)])
def test_failure_stops_other_days_and_is_not_empty_success(monkeypatch, http_status, api_status):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    calls = install_http(monkeypatch, {"2026-10-02": [ROW]}, status=http_status, api_status=api_status)
    first = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert first.status == "error" and first.value == [] and first.audit["error_kind"]
    assert len(calls) == first.audit["http_request_count"] == 1
    second = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert len(calls) == 1 and second.audit["http_request_sent"] is False


@pytest.mark.parametrize("changed", [{"stock_id": "2330"}, {"date": "2099-01-01"}, {"date": "2026-10-01"},
                                     {"date": "bad-date"}, {"title": True}, {"link": "http://127.0.0.1/news"}])
def test_wrong_company_date_or_invalid_fields_are_preserved_as_rejections(monkeypatch, changed):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    calls = install_http(monkeypatch, {"2026-10-02": [{**ROW, **changed}, ROW]})
    result = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert result.status == "degraded_enrichment" and len(result.value) == 1
    assert result.audit["rejected_count"] == 1 and len(calls) == 3


def test_valid_empty_is_not_all_window_absence_and_warm_empty_does_not_fetch(monkeypatch):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    calls = install_http(monkeypatch)
    first = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert first.status == "unavailable" and first.value == [] and not first.audit["error_kind"]
    assert len(calls) == 3 and len(first.audit["sampled_dates"]) == 3
    second = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert second.status == "unavailable" and second.audit["cache_hit"] is True
    assert len(calls) == 3 and second.audit["http_request_sent"] is False


def test_new_empty_samples_cannot_recount_cached_nonempty_news_as_acquisition(monkeypatch, isolated):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    from provider_acquisition import observation_kind
    calls = install_http(monkeypatch, {"2026-10-02": [ROW]})
    first = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    isolated[0] += 400  # Empty-day TTL expires; the positive original is still valid.
    mixed = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert len(calls) == 5 and mixed.value == first.value
    assert mixed.audit["fetched_at_epoch"] == first.audit["fetched_at_epoch"]
    assert mixed.audit["http_request_sent"] is True
    assert observation_kind({**mixed.audit, "details": mixed.audit}) != "fetched_count"


def test_non_taiwan_stock_never_requests_finmind(monkeypatch):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    calls = install_http(monkeypatch)
    result = fetch_finmind_news_result(FetchRequest.from_ticker("AAPL"))
    assert result.value == [] and calls == [] and result.audit["http_request_sent"] is False


def test_transport_is_anonymous_bounded_and_never_uses_a_range(monkeypatch):
    from data_fetch.market_sources.finmind_news import fetch_finmind_news_result
    calls = install_http(monkeypatch, {"2026-10-02": [ROW]})
    result = fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert result.status == "success"
    for call in calls:
        args = call["argv"]
        assert args[args.index("--retry") + 1] == "0"
        assert float(args[args.index("--max-time") + 1]) <= 3
        assert args[args.index("--max-redirs") + 1] == "0"
        assert "--insecure" not in args and "--header" not in args
        assert set(call["query"]) == {"dataset", "data_id", "start_date"}
        assert call["limits"]["body_limit"] == 700000


def test_parent_deadline_stops_following_day_queries(monkeypatch):
    from data_fetch.market_sources import finmind_news as news, finmind_news_transport as transport
    calls = install_http(monkeypatch, {"2026-10-02": [ROW]})
    collect = transport.collect_capped_process
    mono = [100.]
    monkeypatch.setattr(news.time, "monotonic", lambda: mono[0])

    def overrun(*a, **k):
        result = collect(*a, **k)
        mono[0] += 11
        return result

    monkeypatch.setattr(transport, "collect_capped_process", overrun)
    result = news.fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert result.status == "error" and result.audit["error_kind"] == "timeout"
    assert len(calls) == 1 and result.value == []


def test_missing_original_archive_never_becomes_success(monkeypatch):
    from data_fetch.market_sources import finmind_news as news, finmind_news_transport as transport
    calls = install_http(monkeypatch, {"2026-10-09": [{**ROW, "date": "2026-10-09 05:36:00"}]})
    monkeypatch.setattr(transport, "archive_response", lambda *a, **k: {"status": "unavailable"})
    result = news.fetch_finmind_news_result(FetchRequest.from_ticker("3023.TW"))
    assert result.status == "error" and result.value == []
    assert result.audit["error_kind"] == "raw_archive_failed" and len(calls) == 1


def test_sync_core_keeps_one_canonical_finmind_audit(monkeypatch):
    from data_fetch import yfinance_sync_enrichment as sync
    from data_fetch.market_sources import finmind_news
    from data_fetch.types import ProviderResult
    import source_applicability
    selected = []
    canonical = {"source": "recent_catalysts", "provider": "FinMind news", "status": "skipped_fresh_cache",
                 "cache_hit": True, "http_request_sent": False, "record_count": 1, "fetched_at_epoch": 100}
    monkeypatch.setattr(finmind_news, "fetch_finmind_news_result", lambda request: ProviderResult(
        source="recent_catalysts", provider="FinMind news", status="skipped_fresh_cache", value=[ROW], audit=canonical))
    monkeypatch.setattr(sync, "_run_named_fetches", lambda entries, **k: (
        selected.extend(entries), {"values": {}, "audit": []})[1])
    monkeypatch.setattr(source_applicability, "source_is_applicable", lambda source, data: source == "recent_catalysts")
    bundle = sync.fetch_sync_enrichment_bundle(ticker="3023.TW", stock=object(), company_name="信邦", sector="Technology",
        industry="Electronics", company_identity={}, years=[], net_income_history=[], shares_outstanding=None,
        skip_optional_http=True, defer_taiwan_yahoo_news=True)
    assert "recent_catalysts_finmind" not in selected
    assert bundle["recent_catalysts"] == [ROW] and bundle["audit"] == [canonical]


def test_reject_expiry_during_record_projection(monkeypatch):
    from data_fetch.market_sources import finmind_news as news
    calls = install_http(monkeypatch, {'2026-10-09': [{**ROW, 'date': '2026-10-09 05:36:00'}]})
    mono = [100.]
    monkeypatch.setattr(news.time, 'monotonic', lambda: mono[0])
    original = news._record
    def delayed(*args, **kwargs):
        row = original(*args, **kwargs)
        mono[0] += 11.
        return row
    monkeypatch.setattr(news, '_record', delayed)
    result = news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    assert result.audit['error_kind'] == 'timeout', result.audit
    assert result.status != 'success'


def test_error_cache_keeps_rate_limit_cause(monkeypatch):
    from data_fetch.market_sources import finmind_news as news
    calls = install_http(monkeypatch, status=429, api_status=429)
    first = news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    assert first.audit['error_kind'] == 'rate_limited'
    second = news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    assert len(calls) == 1
    assert second.audit['error_kind'] == 'rate_limited', second.audit
    assert second.audit['components'][0]['http_status'] == 429


def test_public_prompt_hides_new_raw_receipt_path(monkeypatch):
    from data_fetch.market_sources import finmind_news as news
    from news_freshness_policy import apply_news_freshness
    from prompt_builder import format_data_for_prompt
    install_http(monkeypatch, {'2026-10-02': [ROW]})
    result = news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    data = {'ticker': '3023.TW', 'company_name':'信邦', 'company_identity':{'official_name':'信邦'},
            'recent_catalysts': result.value}
    apply_news_freshness(data, cutoff=datetime(2026,10,10,tzinfo=timezone.utc))
    assert len(data['recent_catalysts']) == 1
    prompt = format_data_for_prompt(data)
    assert 'raw_response_path' not in prompt, prompt[prompt.index('finmind_news_receipt'):prompt.index('finmind_news_receipt')+1100]


@pytest.mark.parametrize('change', [{'status':'unavailable'}, {'evidence_kind':'selected_fields_only'}, {'raw_response_bytes':1}])
def test_original_receipt_shape_is_required_on_warm_read(monkeypatch, change):
    from data_fetch.market_sources import finmind_news as news, finmind_news_transport as transport
    import cache_store
    install_http(monkeypatch, {'2026-10-09': [{**ROW,'date':'2026-10-09 05:36:00'}]})
    first = news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    assert first.status == 'success'
    get = cache_store.get_cache_json
    def changed(key):
        v = get(key)
        if isinstance(v,dict) and isinstance(v.get('value'),dict) and 'raw_http_receipt' in v['value']:
            v['value']['raw_http_receipt'].update(change)
        return v
    monkeypatch.setattr(cache_store,'get_cache_json',changed)
    result=news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    assert result.status != 'skipped_fresh_cache', result.audit
    assert result.audit['error_kind']=='cache_receipt_invalid'


def test_observed_refusal_is_not_replaced_by_deadline(monkeypatch):
    from data_fetch.market_sources import finmind_news as news, finmind_news_transport as transport
    calls = install_http(monkeypatch, status=429, api_status=429)
    original = transport.collect_capped_process
    mono = [100.]
    monkeypatch.setattr(news.time, 'monotonic', lambda: mono[0])
    def late_refusal(*a, **k):
        response = original(*a, **k)
        mono[0] += 11.
        return response
    monkeypatch.setattr(transport, 'collect_capped_process', late_refusal)
    result = news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    assert len(calls) == 1
    assert result.audit['components'][0]['http_status'] == 429
    assert result.audit['components'][0]['error_kind'] == 'rate_limited'
    assert result.audit['error_kind'] == 'rate_limited', result.audit


@pytest.mark.parametrize('second_mode',['cached_only','fresh_eligible','fresh_rejected','http_refusal'])
def test_mixed_acquisition_classification_and_counts(monkeypatch,isolated,second_mode):
    from data_fetch.market_sources import finmind_news as news,finmind_news_transport as transport
    from provider_acquisition import observation_kind
    rows={'2026-10-02':[ROW]}
    calls=install_http(monkeypatch,rows)
    first=news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    isolated[0]+=400
    if second_mode=='fresh_eligible': rows['2026-10-09']=[{**ROW,'date':'2026-10-09 05:36:00','link':'https://example.com/fresh'}]
    if second_mode=='fresh_rejected': rows['2026-10-09']=[{**ROW,'date':'2026-10-09 05:36:00','stock_id':'2330'}]
    if second_mode=='http_refusal':
        collect=transport.collect_capped_process
        def refused(*a,**k):
            p,rc,e=collect(*a,**k);p['headers']=p['headers'].replace(b'200 OK',b'429 Too Many Requests');return p,rc,e
        monkeypatch.setattr(transport,'collect_capped_process',refused)
    result=news.fetch_finmind_news_result(FetchRequest.from_ticker('3023.TW'))
    kind=observation_kind({**result.audit,'details':result.audit})
    if second_mode=='fresh_eligible':
        assert kind=='fetched_count' and result.status=='success'
        assert result.audit['new_record_count']==len(result.value)==1
        assert result.audit['cached_record_count']==0
    elif second_mode=='http_refusal':
        assert result.audit['error_kind']=='rate_limited', result.audit
        assert kind=='failed_count', result.audit
        assert result.value==[] and result.audit['new_record_count']==0
        assert len(calls)==4
    else:
        assert kind=='degraded_count' and result.status=='degraded_enrichment'
        assert result.value==first.value and result.audit['fetched_at_epoch']==first.audit['fetched_at_epoch']
        assert result.audit['new_record_count']==0 and result.audit['cached_record_count']==len(result.value)==1
        assert len(calls)==5 and result.audit['http_request_count']==2
        if second_mode=='fresh_rejected':assert result.audit['rejected_count']==1
