"""Supplementary search runs only for a real, current evidence shortage."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from zoneinfo import ZoneInfo

import pytest
from data_fetch.types import FetchRequest, ProviderResult

NOW = datetime.now(timezone.utc)


def feeds(*, count=8):
    local=(NOW-timedelta(hours=1)).astimezone(ZoneInfo("Asia/Taipei"))
    news = [{"date": (NOW-timedelta(hours=2)).isoformat(), "title": f"台積電營運新聞{i}",
             "summary": "台積電公布營运資料", "link": f"https://news{i % 3}.example/article/{i}",
             "source": f"publisher{i % 3}"} for i in range(5)]
    official = [{"date": (NOW-timedelta(hours=1)).isoformat(), "title": f"台積電官方公告{i}",
                 "summary": "台積電公司公告原文",
                 "link": ("https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"
                          f"?COMPANY_ID=2330&SPOKE_DATE={local:%Y%m%d}"
                          f"&SPOKE_TIME={local:%H%M%S}&SEQ_NO={i+1}"),
                 "source": "臺灣證券交易所", "ticker": "2330.TW", "source_type": "official_disclosure",
                 "text": f"台積電（2330） 台積電官方公告{i}\n公開原件的公司說明與發布資訊。", "content_coverage":"text_available", "content_truncated":False}
                for i in range(max(0, count-5))]
    for r in official:
        r["content_sha256"]=hashlib.sha256(r["text"].encode()).hexdigest()
    return [
        ProviderResult("recent_catalysts", "Free news waterfall", "success", value=news,
                       audit={"selection_policy":"company-time-v1", "quality_status":"eligible_evidence", "record_count":len(news)}),
        ProviderResult("recent_catalysts", "TWSE company announcement history", "success", value=official,
                       audit={"coverage_status":"window_complete", "record_count":len(official)}),
    ]


def run_plan(monkeypatch, *, results=None, ticker="2330.TW", elapsed=0, yahoo=False, search=True,notice=False):
    from data_fetch import workflow
    import external_search_providers
    values = results if results is not None else feeds()
    class Provider:
        def __init__(self, name):
            self.name, self.source = name, "recent_catalysts"
    providers = [Provider("Free news waterfall"), Provider("TWSE company announcement history")]
    if search:
        providers.append(Provider("Alternative Search"))
    if yahoo:
        providers.append(Provider("Yahoo Finance"))
    if notice:
        providers.append(Provider("TWSE official trading notices"))
    calls, contexts = [], []
    clock = [0.]
    async def fetch(request, selected, context):
        calls.extend(p.name for p in selected)
        contexts.append(deepcopy(context))
        answer = [deepcopy(r) for r in values if r.provider in {p.name for p in selected}]
        if any(p.name == "Alternative Search" for p in selected):
            answer.append(ProviderResult("recent_catalysts", "Alternative Search", "degraded_enrichment",
                                         value=[], audit={"record_count":0}))
        clock[0] += elapsed
        return answer
    monkeypatch.setattr(workflow, "collect_optional_providers", lambda *a,**k:(providers,{"recent_catalysts":True}))
    monkeypatch.setattr(workflow, "fetch_provider_results", fetch)
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda *a,**k:None)
    monkeypatch.setattr(external_search_providers, "_search_deadline", lambda *a,**k:30.)
    monkeypatch.setattr(workflow, "monotonic", lambda:clock[0], raising=False)
    data={"ticker":ticker,"company_name":"台積電","company_identity":{"allowed_aliases":["台積電"]},
          "source_audit":[],"source_freshness":{}}
    result=asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker(ticker), object(), data))
    return result, calls, contexts


def test_two_current_curated_feeds_satisfying_original_eight_slot_gate_skip_search(monkeypatch):
    data,calls,_=run_plan(monkeypatch)
    assert "Alternative Search" not in calls
    skip=next(r for r in data["source_audit"] if r.get("provider")=="Alternative Search")
    assert skip["event_kind"]=="local_block" and skip["http_request_sent"] is False
    assert skip["record_count"]==0 and skip["reason_code"]=="current_catalyst_evidence_sufficient"


def test_seven_unique_records_still_trigger_supplementary_search(monkeypatch):
    _,calls,contexts=run_plan(monkeypatch,results=feeds(count=7))
    assert calls[-1]=="Alternative Search"
    assert contexts[-1]["catalyst_search_deadline"]==30.


def test_sufficient_original_gate_skips_notice_with_a_local_zero_http_observation(monkeypatch):
    data,calls,_=run_plan(monkeypatch,notice=True)
    assert 'TWSE official trading notices' not in calls
    skip=next(r for r in data['source_audit'] if r.get('provider')=='TWSE official trading notices')
    assert skip['event_kind']=='local_block' and skip['http_request_sent'] is False and skip['record_count']==0


def test_insufficient_original_gate_uses_notice_before_search_without_renewing_budget(monkeypatch):
    _,calls,contexts=run_plan(monkeypatch,results=feeds(count=7),notice=True,elapsed=1)
    assert calls[-2:]==['TWSE official trading notices','Alternative Search']
    assert contexts[-1]['catalyst_search_deadline']==30.


@pytest.mark.parametrize("bad",["future","historical","issuer","duplicate","failed_feed","partial_index",
                              "tampered_text","missing_hash","stale","same_publisher","bad_link","invalid_port",
                              "bad_spoke_time","title_mismatch"])
def test_wrong_or_incomplete_evidence_never_satisfies_eight_slot_gate(monkeypatch,bad):
    results=feeds()
    row=results[1].value[-1]
    if bad=="future":row["date"]=(NOW+timedelta(days=2)).isoformat()
    elif bad=="historical":row["date"]=(NOW-timedelta(days=35)).isoformat()
    elif bad=="issuer":row.update(title="無關公司公告",summary="無關公司原文",ticker="2454.TW")
    elif bad=="duplicate":results[1].value[-1]=deepcopy(results[1].value[0])
    elif bad=="failed_feed":results[1].status="error"
    elif bad=="partial_index":results[1].audit["coverage_status"]="partial"
    elif bad=="tampered_text":row["text"]+="外部修改"
    elif bad=="missing_hash":row.pop("content_sha256")
    elif bad=="stale":results[1].audit["stale"]=True
    elif bad=="bad_link":row["link"]="https://other.invalid/announcement/2330"
    elif bad=="invalid_port":row["link"]="https://mopsov.twse.com.tw:bad/mops/web/ajax_t05sr01_1"
    elif bad=="bad_spoke_time":row["link"]=row["link"].replace("SPOKE_TIME=", "SPOKE_TIME=9")
    elif bad=="title_mismatch":row["title"]="台積電新公告999"
    else:
        for i,r in enumerate(results[0].value):r["link"]=f"https://one.example/{i}"
    _,calls,_=run_plan(monkeypatch,results=results)
    assert "Alternative Search" in calls


def test_current_verified_official_cache_is_existing_evidence_and_not_new_http(monkeypatch):
    results=feeds();results[1].status="skipped_fresh_cache"
    results[1].audit.update(cache_hit=True,fetched_at_epoch=NOW.timestamp())
    data,calls,_=run_plan(monkeypatch,results=results)
    assert "Alternative Search" not in calls
    skip=next(r for r in data["source_audit"] if r.get("provider")=="Alternative Search")
    assert skip["record_count"]==0 and skip["http_request_sent"] is False


@pytest.mark.parametrize("epoch",[10**400, float("nan"), float("inf"), True, -1, NOW.timestamp()+3600,
                                 NOW.timestamp()-1900])
def test_invalid_cache_epoch_cannot_crash_or_satisfy_evidence_gate(monkeypatch,epoch):
    results=feeds();results[1].status="skipped_fresh_cache"
    results[1].audit.update(cache_hit=True,fetched_at_epoch=epoch)
    _,calls,_=run_plan(monkeypatch,results=results)
    assert "Alternative Search" in calls


def test_sequence_leading_zero_aliases_are_one_original_announcement(monkeypatch):
    results=feeds();original=deepcopy(results[1].value[0])
    versions=[]
    for i,seq in enumerate(("1","01","001")):
        row={**deepcopy(original),"link":original["link"].replace("SEQ_NO=1",f"SEQ_NO={seq}"),
             "title":f"台積電同原件更新版{i}", "text":f"台積電（2330） 台積電同原件更新版{i}\n公開說明。"}
        row["content_sha256"]=hashlib.sha256(row["text"].encode()).hexdigest()
        versions.append(row)
    results[1].value=versions
    _,calls,_=run_plan(monkeypatch,results=results)
    assert "Alternative Search" in calls


def test_fallback_does_not_renew_budget_after_primary_wait(monkeypatch):
    data,calls,_=run_plan(monkeypatch,results=feeds(count=7),elapsed=31)
    assert "Alternative Search" not in calls
    skip=next(r for r in data["source_audit"] if r.get("provider")=="Alternative Search")
    assert skip["reason_code"]=="catalyst_search_deadline_exhausted" and skip["http_request_sent"] is False


def test_other_markets_keep_existing_parallel_search_plan(monkeypatch):
    _,calls,contexts=run_plan(monkeypatch,ticker="AAPL")
    assert "Alternative Search" in calls
    assert "catalyst_search_deadline" not in contexts[0]


@pytest.mark.parametrize("search", [True, False])
def test_checked_primary_feeds_do_not_move_redundant_search_to_yahoo(monkeypatch, search):
    data,calls,_=run_plan(monkeypatch,yahoo=True,search=search)
    assert "Yahoo Finance" not in calls
    skip=next(r for r in data["source_audit"] if r.get("provider")=="Yahoo Finance news")
    assert skip["http_request_sent"] is False and skip["record_count"]==0
    assert skip["reason_code"]=="current_catalyst_evidence_sufficient"


def test_genuine_shortage_keeps_yahoo_fallback(monkeypatch):
    _,calls,_=run_plan(monkeypatch,results=feeds(count=7),yahoo=True)
    assert calls[-2:]==["Alternative Search","Yahoo Finance"]


def test_other_markets_keep_yahoo_in_primary_parallel_plan(monkeypatch):
    _,calls,contexts=run_plan(monkeypatch,ticker="AAPL",yahoo=True)
    assert "Yahoo Finance" in calls and "catalyst_search_deadline" not in contexts[0]


def test_provider_expired_parent_budget_is_zero_http_before_admission(monkeypatch):
    import time
    import external_search_providers as search
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from api_usage_recorders import _provider_usage_units
    async def forbidden(*args,**kwargs):
        pytest.fail("expired parent budget must not start search")
    monkeypatch.setattr(search,"fetch_alternative_search_catalysts_async",forbidden)
    result=asyncio.run(AlternativeSearchProvider().fetch_async(
        FetchRequest.from_ticker("2330.TW"),{"data":{"ticker":"2330.TW","company_name":"台積電"},
                                          "catalyst_search_deadline":time.monotonic()-1}))
    assert result.audit["http_request_sent"] is False and result.audit["event_kind"]=="local_block"
    assert result.audit["record_count"]==0 and _provider_usage_units(result.audit,result.status)==0


def test_provider_expiry_during_admission_never_calls_engine(monkeypatch):
    from types import SimpleNamespace
    import time
    import external_search_providers as search
    from data_fetch import enrichment_search_providers as providers
    clock=[0.]
    monkeypatch.setattr(providers,"time",SimpleNamespace(monotonic=lambda:clock[0],time=time.time))
    async def admission(source,name,callback,**kwargs):
        clock[0]=2.
        return {"value":await callback(),"audit":{"source":source,"provider":name,"status":"degraded_enrichment"}}
    async def forbidden(*args,**kwargs):
        pytest.fail("expired admission cannot enter engine")
    monkeypatch.setattr(providers,"audited_fetch_async",admission)
    monkeypatch.setattr(search,"fetch_alternative_search_catalysts_async",forbidden)
    result=asyncio.run(providers.AlternativeSearchProvider().fetch_async(
        FetchRequest.from_ticker("2330.TW"),{"data":{"ticker":"2330.TW","company_name":"台積電"},
                                          "catalyst_search_deadline":1.}))
    assert result.audit["http_request_sent"] is False and result.audit["record_count"]==0


@pytest.mark.parametrize("queries_started,expect_zero",[(0,True),(1,False)])
def test_engine_zero_query_expiry_is_distinct_from_an_attempted_empty_query(monkeypatch,queries_started,expect_zero):
    import time
    import external_search_providers as search
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from api_usage_recorders import _provider_usage_units
    async def engine(*args,diagnostics,**kwargs):
        diagnostics.update(search_budget_exhausted=True,search_queries_started=queries_started)
        return []
    monkeypatch.setattr(search,"fetch_alternative_search_catalysts_async",engine)
    result=asyncio.run(AlternativeSearchProvider().fetch_async(
        FetchRequest.from_ticker("2330.TW"),{"data":{"ticker":"2330.TW","company_name":"台積電"},
                                          "catalyst_search_deadline":time.monotonic()+60}))
    assert (_provider_usage_units(result.audit,result.status)==0) is expect_zero
    assert (result.audit.get("http_request_sent") is False) is expect_zero
