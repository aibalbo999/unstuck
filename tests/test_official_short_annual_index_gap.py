"""Real complete public index replay: insufficient history remains a failure."""
from copy import deepcopy
from pathlib import Path
import json,time
import httpx,pytest
from data_fetch.market_sources.official_xbrl_financial import fetch_official_annual_histories
from provider_correlation import correlation_scope

RAW=Path(__file__).parent.joinpath("fixtures/source_acquisition/seetel_short_annual_index_complete_20261010.html").read_bytes()

@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def fetch_loop(raw=RAW):
    calls=[]
    def respond(request):
        calls.append(request)
        assert request.method=="POST"
        assert request.url.path=="/mops/web/ajax_t203sb01"
        return httpx.Response(200,content=raw)
    client=httpx.Client(transport=httpx.MockTransport(respond))
    def fetch(ticker):return fetch_official_annual_histories(ticker,client=client)
    return calls,client,fetch


def test_confirmed_short_index_reuses_one_failure_and_preserves_original_history_gate():
    from data_fetch.official_financial_gap_cache import fetch_official_financial_result
    from provider_observation_details import observation_details
    from provider_acquisition import observation_kind
    calls,client,fetch=fetch_loop()
    try:
        with correlation_scope(replace=True,fetch_id="short-first",ticker="7740.TW"):
            first=fetch_official_financial_result("7740.TW",fetcher=fetch)
        with correlation_scope(replace=True,fetch_id="short-next",ticker="7740.TW"):
            warm=fetch_official_financial_result("7740.TW",fetcher=fetch)
    finally:client.close()
    assert len(calls)==1
    assert first["value"] is warm["value"] is None
    assert first["audit"]["status"]==warm["audit"]["status"]=="error"
    assert first["audit"]["message"]=="fewer than five consolidated annual filings"
    assert first["audit"]["record_count"]==warm["audit"]["record_count"]==0
    assert first["audit"]["available_consolidated_annual_years"]==[2023,2024,2025]
    assert warm["audit"]["fetched_at"]==first["audit"]["fetched_at"]
    assert warm["audit"]["cache_hit"] is True and warm["audit"]["stale"] is False
    assert warm["audit"]["http_request_sent"] is False and warm["audit"]["event_kind"]=="cache_hit"
    assert warm["audit"]["fetch_id"]=="short-next" and warm["audit"]["provider_attempts"]==[]
    for result,kind in ((first,"failed_count"),(warm,"empty_cache_count")):
        a=result["audit"];assert observation_kind({**a,"details":observation_details(a)})==kind


def test_short_index_expiry_does_not_delay_a_real_recheck(monkeypatch):
    import data_fetch.official_financial_gap_cache as source
    calls,client,fetch=fetch_loop()
    try:
        source.fetch_official_financial_result("7740.TW",fetcher=fetch)
        original=source.get_cache_json
        cache_keys=[]
        def expired(key):
            cache_keys.append(key)
            d=deepcopy(original(key))
            if d:d["audit"]["fetched_at_epoch"]=time.time()-301
            return d
        monkeypatch.setattr(source,"get_cache_json",expired)
        source.fetch_official_financial_result("7740.TW",fetcher=fetch)
    finally:client.close()
    assert len(calls)==2


@pytest.mark.parametrize("mutation",[
    "wrong_year_label","wrong_preview_issuer","wrong_preview_period","wrong_scope_label",
    "security_page","truncated","missing_header","empty_index",
])
def test_unverified_short_index_does_not_hide_a_followup_provider_attempt(mutation):
    from data_fetch.official_financial_gap_cache import fetch_official_financial_result
    text=RAW.decode()
    if mutation=="wrong_year_label":text=text.replace("<td>114Q4</td>","<td>113Q4</td>",1)
    elif mutation=="wrong_preview_issuer":text=text.replace("ci-cr-7740-2025Q4","ci-cr-2330-2025Q4",1)
    elif mutation=="wrong_preview_period":text=text.replace("ci-cr-7740-2025Q4","ci-cr-7740-2025Q3",1)
    elif mutation=="wrong_scope_label":text=text.replace("<td>合併</td>","<td>個體</td>",1)
    elif mutation=="security_page":text="<html><title>Security check</title><body>Verify</body></html>"
    elif mutation=="truncated":text=text[:5000]
    elif mutation=="missing_header":text=text.replace("<th>財報類別</th>","<th>其他</th>")
    elif mutation=="empty_index":text="<html><title>公開資訊觀測站</title><body>無資料</body></html>"
    calls,client,fetch=fetch_loop(text.encode())
    try:
        first=fetch_official_financial_result("7740.TW",fetcher=fetch)
        second=fetch_official_financial_result("7740.TW",fetcher=fetch)
    finally:client.close()
    assert len(calls)==2
    assert first["value"] is second["value"] is None
    assert not second["audit"]["cache_hit"]


@pytest.mark.parametrize("mutation",["audit_years","audit_coverage","proof_hash","proof_issuer","blank_query"])
def test_corrupted_short_index_receipt_never_prevents_a_recheck(monkeypatch,mutation):
    import data_fetch.official_financial_gap_cache as source
    from hashlib import sha256
    calls,client,fetch=fetch_loop()
    try:
        source.fetch_official_financial_result("7740.TW",fetcher=fetch)
        original=source.get_cache_json
        def altered(key):
            d=deepcopy(original(key));assert d is not None
            p=d["validation_gap"]
            if mutation=="audit_years":d["audit"]["available_consolidated_annual_years"]=[2021,2022,2023,2024,2025]
            elif mutation=="audit_coverage":d["audit"]["coverage_status"]="complete"
            elif mutation=="proof_hash":p["index_sha256"]="0"*64
            elif mutation=="proof_issuer":p["issuer"]="2330"
            elif mutation=="blank_query":
                p["index_utf8"]=p["index_utf8"].replace("&report_id=C","&report_id=C&unexpected=",1)
                encoded=p["index_utf8"].encode();p["index_bytes"]=len(encoded);p["index_sha256"]=sha256(encoded).hexdigest()
            return d
        monkeypatch.setattr(source,"get_cache_json",altered)
        result=source.fetch_official_financial_result("7740.TW",fetcher=fetch)
    finally:client.close()
    assert len(calls)==2
    assert result["audit"]["cache_hit"] is False


def test_new_complete_index_after_expiry_can_recover_and_clear_short_gap(monkeypatch):
    import data_fetch.official_financial_gap_cache as source
    from test_official_xbrl_financial import filing
    responses=[];mode=[False]
    index="".join(f'/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=7740&season=4&report_id=C&year={y}" ' for y in range(2021,2026)).encode()
    def respond(request):
        responses.append(request)
        if request.method=="POST":return httpx.Response(200,content=index if mode[0] else RAW)
        return httpx.Response(200,content=filing(int(request.url.params["year"]),issuer="7740"))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetch=lambda ticker:fetch_official_annual_histories(ticker,client=client)
        first=source.fetch_official_financial_result("7740.TW",fetcher=fetch)
        original=source.get_cache_json
        cache_keys=[]
        def expired(key):
            cache_keys.append(key)
            d=deepcopy(original(key))
            if d:d["audit"]["fetched_at_epoch"]=time.time()-301
            return d
        monkeypatch.setattr(source,"get_cache_json",expired);mode[0]=True
        recovered=source.fetch_official_financial_result("7740.TW",fetcher=fetch)
    assert first["value"] is None and first["audit"]["status"]=="error"
    assert recovered["audit"]["status"]=="success"
    assert recovered["value"]["years"]==["2021","2022","2023","2024","2025"]
    assert len(responses)==7
    monkeypatch.setattr(source,"get_cache_json",original)
    assert cache_keys and all(source.get_cache_json(k) is None for k in cache_keys)
