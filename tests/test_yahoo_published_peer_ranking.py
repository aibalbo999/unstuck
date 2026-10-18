"""A published industry table supplies candidates, never business comparability."""
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def master(day: date, *, broad: bool = False):
    category = "其他" if broad else "金融保險"
    return [
        {"date": day.isoformat(), "stock_id": "2882", "stock_name": "國泰金",
         "type": "twse", "industry_category": category},
        {"date": day.isoformat(), "stock_id": "2881", "stock_name": "富邦金",
         "type": "twse", "industry_category": category},
        {"date": day.isoformat(), "stock_id": "5314", "stock_name": "世紀民生",
         "type": "tpex", "industry_category": "其他"},
    ]


def page(day: date, *, ticker="2882.TW", company="國泰金", peer="富邦金",
         peer_ticker="2881.TW") -> bytes:
    return f'''<html><head>
      <meta property="og:title" content="{company}({ticker}) 同業比較 - Yahoo股市">
      <meta property="og:url" content="https://tw.stock.yahoo.com/quote/{ticker}/compare">
    </head><body><div id="quote-compare-tables">金融業業各類指標排名
      <span>資料時間：{day:%Y/%m/%d}</span>
      <section id="qsp-compare-rank-symbols">
        <div class="table-row">1 <a href="https://tw.stock.yahoo.com/quote/{peer_ticker}">{peer}</a>
          <span>{peer_ticker}</span> 2.1%</div>
      </section></div></body></html>'''.encode()


def test_published_peer_ranking_requires_current_exact_exchange_identity():
    from data_fetch.market_sources.yahoo_peer_ranking import parse_ranking_page
    today = date(2026, 10, 4)
    result = parse_ranking_page(page(today), "2882.TW", master(today), today=today)
    assert len(result["records"]) == 1
    row = result["records"][0]
    assert row["counterparty"]["ticker"] == "2881.TW"
    assert row["relationship_kind"] == "publisher_ranked_industry_peer"
    assert row["numeric_comparability_verified"] is False
    assert row["business_comparability_verified"] is False
    assert row["observed_at"] == today.isoformat()


@pytest.mark.parametrize("raw,rows,now", [
    (page(date(2026, 10, 4), ticker="2883.TW"), master(date(2026, 10, 4)), date(2026, 10, 4)),
    (page(date(2026, 10, 4), peer="錯誤公司"), master(date(2026, 10, 4)), date(2026, 10, 4)),
    (page(date(2026, 10, 4)), master(date(2026, 10, 4), broad=True), date(2026, 10, 4)),
    (page(date(2026, 9, 20)), master(date(2026, 10, 4)), date(2026, 10, 4)),
])
def test_published_peer_ranking_rejects_wrong_identity_broad_industry_or_stale_page(raw, rows, now):
    from data_fetch.market_sources.yahoo_peer_ranking import parse_ranking_page
    from data_fetch.market_sources.yahoo_peer_ranking import RankingError
    with pytest.raises(RankingError):
        parse_ranking_page(raw, "2882.TW", rows, today=now)


def test_published_peer_record_cannot_be_promoted_to_business_comparison():
    from data_fetch.market_sources.yahoo_peer_ranking import parse_ranking_page, is_published_peer_record
    from peer_relationship_evidence import is_reported_peer_record
    today = date.today()
    row = parse_ranking_page(page(today), "2882.TW", master(today), today=today)["records"][0]
    assert is_published_peer_record(row, "2882.TW", today=today)
    assert not is_reported_peer_record(row, "2882.TW")
    row["numeric_comparability_verified"] = True
    assert not is_published_peer_record(row, "2882.TW", today=today)


def test_published_peer_provider_records_only_live_acquisition_as_success(monkeypatch):
    import time
    from data_fetch.enrichment_search_providers import YahooPublishedPeerRankingProvider
    from data_fetch.market_sources import peer_recovery, yahoo_peer_ranking
    from data_fetch.types import FetchRequest
    import shared_provider_cache

    today = yahoo_peer_ranking._today()
    rows = master(today)
    observation = yahoo_peer_ranking.parse_ranking_page(page(today), "2882.TW", rows, today=today)
    monkeypatch.setattr(peer_recovery, "load_peer_stock_master", lambda: rows)
    monkeypatch.setattr(yahoo_peer_ranking, "fetch_published_industry_peers", lambda *args, **kw: observation)
    calls = []

    def shared(_key, callback, **_kwargs):
        if not calls:
            value = callback()
            calls.append(value)
            return value, {"cache_hit": False, "stale": False, "fetched_at_epoch": time.time()}
        return calls[0], {"cache_hit": True, "stale": False, "fetched_at_epoch": time.time()}

    monkeypatch.setattr(shared_provider_cache, "shared_fetch", shared)
    provider = YahooPublishedPeerRankingProvider()
    request = FetchRequest.from_ticker("2882.TW")
    first = provider.fetch(request, {"data": {"ticker": "2882.TW"}})
    second = provider.fetch(request, {"data": {"ticker": "2882.TW"}})
    assert (first.status, first.audit["record_count"], first.audit["http_request_sent"]) == ("success", 1, True)
    assert (second.status, second.audit["record_count"], second.audit["http_request_sent"]) == ("skipped_fresh_cache", 1, False)


def test_taiwan_peer_merge_keeps_published_candidate_separate_from_business_peer():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources.yahoo_peer_ranking import POLICY, parse_ranking_page
    today = date.today()
    published = parse_ranking_page(page(today), "2882.TW", master(today), today=today)["records"][0]
    data = {"ticker": "2882.TW", "source_audit": [{"source": "peer_discovery",
             "provider": "Yahoo Taiwan published industry ranking", "selection_policy": POLICY,
             "status": "success", "record_count": 1}],
            "peer_discovery_results": [{"title": "old raw", "link": "https://example.com/raw"}]}
    result = _merge_optional_http_bundle(
        data, {"search_peer_discovery": [], "publisher_peer_discovery": [published]},
        refreshed_sources=["peer_discovery"],
    )
    assert result["peer_discovery_results"] == [published]
    from prompt_evidence import prompt_evidence_copy
    prompt = prompt_evidence_copy(result)
    assert prompt["peer_discovery_results"][0]["business_comparability_verified"] is False
    assert any(item["reason"] == "legacy_peer_relationship_unverified"
               for item in result["source_record_archive"])
    assert result["source_audit"][-1]["event_kind"] == "aggregate"


def test_peer_aggregate_uses_real_success_when_other_provider_is_locally_blocked():
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.market_sources.yahoo_peer_ranking import POLICY, parse_ranking_page
    today = date.today()
    published = parse_ranking_page(page(today), "2882.TW", master(today), today=today)["records"][0]
    data = {"ticker": "2882.TW", "source_audit": [
        {"source": "peer_discovery", "provider": "Yahoo Taiwan published industry ranking",
         "selection_policy": POLICY, "status": "success", "record_count": 1},
        {"source": "peer_discovery", "provider": "Alternative Search",
         "status": "unavailable", "record_count": 0, "http_request_sent": False},
    ]}
    result = _merge_optional_http_bundle(
        data, {"search_peer_discovery": [], "publisher_peer_discovery": [published]},
        refreshed_sources=["peer_discovery"],
    )
    assert result["peer_discovery_results"] == [published]
    assert result["source_audit"][-1]["status"] == "success"


def test_public_fetch_retains_whole_original_on_provider_cold_and_warm_reads(monkeypatch):
    import httpx
    from hashlib import sha256
    from data_fetch.enrichment_search_providers import YahooPublishedPeerRankingProvider
    from data_fetch.market_sources import peer_recovery, yahoo_peer_ranking
    from data_fetch.types import FetchRequest
    from official_response_evidence import read_response
    today = yahoo_peer_ranking._today()
    raw = page(today) + b'<!-- complete publisher body, not selected fields -->'
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=raw)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    fetch = yahoo_peer_ranking.fetch_published_industry_peers
    monkeypatch.setattr(peer_recovery, 'load_peer_stock_master', lambda: master(today))
    monkeypatch.setattr(yahoo_peer_ranking, 'fetch_published_industry_peers',
                        lambda ticker, **kw: fetch(ticker, client=client, **kw))
    provider = YahooPublishedPeerRankingProvider()
    request = FetchRequest.from_ticker('2882.TW')
    try:
        cold = provider.fetch(request, {'data': {'ticker': '2882.TW'}})
        warm = provider.fetch(request, {'data': {'ticker': '2882.TW'}})
    finally:
        client.close()
    receipt = cold.audit['raw_http_receipt']
    assert read_response(receipt) == raw
    assert receipt['raw_response_sha256'] == cold.audit['response_sha256'] == sha256(raw).hexdigest()
    assert receipt['raw_response_bytes'] == len(raw)
    assert receipt['source_url'] == cold.audit['source_url'] and receipt['http_status'] == 200
    assert receipt['evidence_kind'] == 'decoded_complete_http_response_body'
    assert cold.status == 'success' and warm.status == 'skipped_fresh_cache'
    assert cold.value == warm.value and len(calls) == 1
    assert warm.audit['raw_http_receipt'] == receipt
    assert warm.audit['http_request_sent'] is False
    assert cold.value[0]['business_comparability_verified'] is False
    assert cold.value[0]['numeric_comparability_verified'] is False


def test_published_peer_fetch_does_not_succeed_when_original_archive_fails(monkeypatch):
    import httpx
    from data_fetch.market_sources import yahoo_peer_ranking
    today = yahoo_peer_ranking._today()
    monkeypatch.setattr(yahoo_peer_ranking, 'archive_response',
                        lambda *a, **kw: {'status': 'unavailable'}, raising=False)
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=page(today)))) as client:
        with pytest.raises(yahoo_peer_ranking.RankingError, match='source_archive_unavailable'):
            yahoo_peer_ranking.fetch_published_industry_peers('2882.TW', today=today,
                                                           master_rows=master(today), client=client)


@pytest.mark.parametrize('mode',['archive_removed','receipt_wrong_url','legacy_no_receipt','prompt_no_path'])
def test_public_provider_warm_archive_boundary(monkeypatch,mode):
    import httpx,cache_store
    from data_fetch.enrichment_search_providers import YahooPublishedPeerRankingProvider
    from data_fetch.market_sources import peer_recovery,yahoo_peer_ranking
    from data_fetch.types import FetchRequest
    from prompt_builder import format_data_for_prompt
    today=yahoo_peer_ranking._today();raw=page(today)
    calls=[]
    def respond(req):calls.append(str(req.url));return httpx.Response(200,content=raw)
    client=httpx.Client(transport=httpx.MockTransport(respond))
    fetch=yahoo_peer_ranking.fetch_published_industry_peers
    monkeypatch.setattr(peer_recovery,'load_peer_stock_master',lambda:master(today))
    monkeypatch.setattr(yahoo_peer_ranking,'fetch_published_industry_peers',lambda ticker,**kw:fetch(ticker,client=client,**kw))
    provider=YahooPublishedPeerRankingProvider();request=FetchRequest.from_ticker('2882.TW')
    cold=provider.fetch(request,{'data':{'ticker':'2882.TW'}})
    assert cold.status=='success' and len(cold.value)==1
    if mode=='archive_removed':Path(cold.audit['raw_http_receipt']['raw_response_path']).unlink()
    if mode in {'receipt_wrong_url','legacy_no_receipt'}:
        get=cache_store.get_cache_json
        def changed(key):
            value=get(key)
            if isinstance(value,dict) and isinstance(value.get('value'),dict) and 'raw_http_receipt' in value['value']:
                if mode=='receipt_wrong_url':value['value']['raw_http_receipt']['source_url']='https://evil.test/compare'
                else:value['value'].pop('raw_http_receipt')
            return value
        monkeypatch.setattr(cache_store,'get_cache_json',changed)
    warm=provider.fetch(request,{'data':{'ticker':'2882.TW'}})
    client.close()
    assert len(calls)==1
    if mode in {'archive_removed','receipt_wrong_url'}:
        assert warm.status not in {'success','skipped_fresh_cache'},warm.audit
        assert warm.audit['record_count']==0
    elif mode=='legacy_no_receipt':
        assert warm.status=='skipped_fresh_cache' and warm.value==cold.value
        assert 'raw_http_receipt' not in warm.audit
    else:
        data={'ticker':'2882.TW','company_name':'國泰金','company_identity':{'official_name':'國泰金'},'peer_discovery_results':warm.value,'source_audit':[warm.audit]}
        prompt=format_data_for_prompt(data)
        assert 'raw_response_path' not in prompt and 'raw_http_receipt' not in prompt
        assert warm.audit['raw_http_receipt']==cold.audit['raw_http_receipt']
