"""Official construction-chain leads preserve the whole-business uncertainty."""
from datetime import date
import pytest

TODAY=date(2026,10,9)
COHORT=[("2535","達欣工"),("2546","根基"),("5515","建國"),("2597","潤弘")]
MASTER=[{"stock_id":code,"stock_name":name,"type":"twse","date":"2026-10-09","industry_category":"建材營造"}
        for code,name in [("9945","潤泰新"),*COHORT]]

def test_broad_exchange_category_can_recover_documented_construction_candidates(monkeypatch):
    from data_fetch.market_sources import peers
    from stock_snapshot.peers_valuation import _peer_comparison
    from prompt_peer_projection import comparable_peer_rows
    candidates=[{"name":name,"ticker":code+".TW","comparison_status":"official_segment_candidate",
                 "business_comparability_verified_current":False,"comparison_scope":"construction_segment"}
                for code,name in COHORT]
    monkeypatch.setattr(peers,"load_peer_stock_master",lambda:MASTER)
    monkeypatch.setattr(peers,"resolve_legacy_peer_candidates",lambda *a,**k:([],{"selection_status":"broad_industry_only"}))
    monkeypatch.setattr(peers,"get_official_construction_candidates",lambda *a,**k:{"candidates":candidates,"status":"success"},raising=False)
    class Stock:
        def __init__(self,symbol):self.symbol=symbol
        @property
        def info(self):
            return {"symbol":self.symbol,"quoteType":"EQUITY","industry":"Engineering & Construction",
                    "trailingPE":18.0,"priceToBook":1.2,"priceToSalesTrailing12Months":1.1,
                    "grossMargins":0.15,"operatingMargins":0.08,"profitMargins":0.07,"returnOnEquity":0.12}
    monkeypatch.setattr(peers.yf,"Ticker",Stock)
    monkeypatch.setattr(peers,"_annual_asset_turnover",lambda stock,**k:{"value":0.8,"observed_at":"2025-12-31"})
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics("9945.TW","潤泰新","Industrials","Engineering & Construction",{})
    assert [row["ticker"] for row in result["peers"]]==[code+".TW" for code,name in COHORT]
    assert result["audit"]["coverage_status"]=="success"
    assert result["audit"]["candidate_attempt_count"]<=10
    assert _peer_comparison({"ticker":"9945.TW","dynamic_peer_metrics":result["peers"]})["summary"]["peer_count"]==0
    assert comparable_peer_rows(result["peers"])==[]

def pages():
    from pathlib import Path
    from data_fetch.market_sources import official_construction_peer_cohort as source
    base=Path(__file__).parent/"fixtures/source_acquisition"
    return {source.ISSUER_URL:(base/"construction_9945_issuer_20261009.html").read_bytes(),
            source.SEGMENT_URL:(base/"construction_cohort_20261009.html").read_bytes()}

def acquire(monkeypatch,*,raw=None,master=None,metadata=None):
    from data_fetch.market_sources import official_construction_peer_cohort as source
    raw=raw or pages()
    monkeypatch.setattr(source,"_now",lambda:1791513600)
    calls=[]
    def get(url,**kwargs):
        import time
        calls.append((url,kwargs["deadline"]-time.monotonic()))
        return raw[url]
    monkeypatch.setattr(source,"download_html",get)
    monkeypatch.setattr(source,"shared_fetch",lambda key,fn,**k:(fn(),metadata or {"stale":False,"fetched_at_epoch":1791513600}))
    result=source.get_official_construction_candidates("9945.TW",MASTER if master is None else master,today=TODAY)
    return result,calls

def test_actual_official_pages_match_current_identities_and_preserve_source_limits(monkeypatch):
    from data_fetch.market_sources import official_construction_peer_cohort as source
    result,calls=acquire(monkeypatch)
    assert result["status"]=="success"
    assert [r["ticker"] for r in result["candidates"]]==[code+".TW" for code,name in COHORT]
    assert len(calls)==2 and all(0<seconds<=6 for url,seconds in calls)
    for row in result["candidates"]:
        assert row["business_comparability_verified_current"] is False
        assert row["issuer_source_url"]==source.ISSUER_URL
        assert row["segment_source_url"]==source.SEGMENT_URL
        assert row["master_observed_at"]=="2026-10-09"
        assert len(row["issuer_response_sha256"])==len(row["segment_response_sha256"])==64
        assert "undated_segment_membership" in row["comparison_limitations"]

@pytest.mark.parametrize("change",["issuer_code","wrong_segment","missing_group","group_title","missing_target","oversized","non_utf8"])
def test_unverified_official_membership_does_not_add_candidates(monkeypatch,change):
    from data_fetch.market_sources import official_construction_peer_cohort as source
    raw=pages()
    if change=="issuer_code":raw[source.ISSUER_URL]=raw[source.ISSUER_URL].replace(b"9945",b"9946")
    elif change=="wrong_segment":raw[source.ISSUER_URL]=raw[source.ISSUER_URL].replace("營造業".encode(),"建設業".encode())
    elif change=="missing_group":raw[source.SEGMENT_URL]=raw[source.SEGMENT_URL].replace(b"companyList_S600",b"companyList_S999")
    elif change=="group_title":
        raw[source.SEGMENT_URL]=raw[source.SEGMENT_URL].replace('title="營造業"'.encode(),'title="建設業"'.encode())
    elif change=="missing_target":raw[source.SEGMENT_URL]=raw[source.SEGMENT_URL].replace(b"stk_code=9945",b"stk_code=9946")
    elif change=="oversized":raw[source.SEGMENT_URL]=b"x"*250001
    elif change=="non_utf8":raw[source.ISSUER_URL]=b"\xff"*101
    result,_=acquire(monkeypatch,raw=raw)
    assert result["candidates"]==[]

def test_one_unverified_peer_does_not_discard_independent_valid_peers(monkeypatch):
    result,_=acquire(monkeypatch,master=[MASTER[0],{**MASTER[1],"stock_name":"別家公司"},*MASTER[2:]])
    assert [r["ticker"] for r in result["candidates"]]==[code+".TW" for code,name in COHORT[1:]]
    assert result["rejected_candidate_codes"]==["2535"]
    raw=pages()
    from data_fetch.market_sources import official_construction_peer_cohort as source
    raw[source.SEGMENT_URL]=raw[source.SEGMENT_URL].replace("達欣工".encode(),"不明公司".encode())
    result,_=acquire(monkeypatch,raw=raw)
    assert [r["ticker"] for r in result["candidates"]]==[code+".TW" for code,name in COHORT[1:]]

@pytest.mark.parametrize("change",["stale","issuer_renamed","historical_peer","wrong_market"])
def test_changed_or_historical_master_identity_is_not_admitted(monkeypatch,change):
    master=[dict(r) for r in MASTER]
    if change=="stale":master=[{**r,"date":"2026-09-01"} for r in master]
    elif change=="issuer_renamed":master[0]["stock_name"]="其他公司"
    elif change=="historical_peer":master[1]["date"]="2026-10-08"
    elif change=="wrong_market":master[1]["type"]="tpex"
    result,calls=acquire(monkeypatch,master=master)
    if change in {"stale","issuer_renamed"}:
        assert result["candidates"]==[] and calls==[]
    else:
        assert "2535.TW" not in [r["ticker"] for r in result["candidates"]]
        assert len(result["candidates"])==3

def test_stale_or_corrupt_shared_receipt_cannot_supply_candidates(monkeypatch):
    from data_fetch.market_sources import official_construction_peer_cohort as source
    for value,meta in [({"peer_codes":["2535"],"issuer_response_sha256":"a"*64,"segment_response_sha256":"b"*64},{"stale":True}),
                       ({"peer_codes":["9999"],"issuer_response_sha256":"a"*64,"segment_response_sha256":"b"*64},{"stale":False}),
                       ({"peer_codes":["2535"],"issuer_response_sha256":None,"segment_response_sha256":"b"*64},{"stale":False})]:
        monkeypatch.setattr(source,"shared_fetch",lambda *a,**k:(value,meta))
        assert source.get_official_construction_candidates("9945.TW",MASTER,today=TODAY)["candidates"]==[]
    assert source.get_official_construction_candidates("5314.TWO",MASTER,today=TODAY)["status"]=="not_applicable"

def test_other_issuer_section_cannot_supply_target_construction_membership(monkeypatch):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import official_construction_peer_cohort as source
    raw=pages();soup=BeautifulSoup(raw[source.ISSUER_URL],"html.parser")
    content=soup.select_one("div.content")
    for h in content.select("h4"):
        if source._compact(h.get_text())=="►建材營造>營造業":h.decompose()
    other=BeautifulSoup('<div class="content"><h4>9946其他公司所屬產業鏈如下:</h4><h4>►<a href="introduce.php?ic=S000">建材營造</a>&gt;營造業</h4></div>',"html.parser")
    soup.append(other)
    raw[source.ISSUER_URL]=str(soup).encode()
    result,_=acquire(monkeypatch,raw=raw)
    assert result["candidates"]==[]

@pytest.mark.parametrize("epoch",[None,0,False,float("nan"),float("inf"),1791513600+1,1791513600-86401])
def test_invalid_page_acquisition_time_cannot_supply_cached_membership(monkeypatch,epoch):
    from data_fetch.market_sources import official_construction_peer_cohort as source
    monkeypatch.setattr(source,"_now",lambda:1791513600,raising=False)
    result,_=acquire(monkeypatch,metadata={"stale":False,"fetched_at_epoch":epoch})
    assert result["candidates"]==[]
