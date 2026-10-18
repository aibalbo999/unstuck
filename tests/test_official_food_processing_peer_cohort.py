"""Food-segment acquisitions never stand in for whole-company valuation peers."""
from datetime import date
from pathlib import Path

import pytest

TODAY = date(2026, 10, 9)
COHORT = [("1232", "大統益"), ("1225", "福懋油"), ("1216", "統一"), ("1702", "南僑")]
MASTER = [{"stock_id":code,"stock_name":name,"type":"twse","date":"2026-10-09",
           "industry_category":"食品工業"} for code,name in [("1229","聯華"),*COHORT]]


def test_holding_company_can_acquire_segment_metrics_without_valuation_admission(monkeypatch):
    from data_fetch.market_sources import peers
    from stock_snapshot.peers_valuation import _peer_comparison
    from prompt_peer_projection import comparable_peer_rows
    candidates = [{"name":name,"ticker":code+".TW","comparison_status":"official_segment_candidate",
                   "business_comparability_verified_current":False,
                   "comparison_scope":"food_processing_segment"} for code,name in COHORT]
    monkeypatch.setattr(peers,"load_peer_stock_master",lambda:MASTER)
    monkeypatch.setattr(peers,"resolve_legacy_peer_candidates",lambda *a,**k:([],{"selection_status":"broad_industry_only"}))
    monkeypatch.setattr(peers,"documented_peer_candidates",lambda *a,**k:[])
    monkeypatch.setattr(peers,"get_official_food_processing_candidates",lambda *a,**k:{"candidates":candidates,"status":"success"},raising=False)
    class Stock:
        def __init__(self,symbol): self.symbol=symbol
        @property
        def info(self):
            return {"symbol":self.symbol,"quoteType":"EQUITY","industry":"Packaged Foods",
                    "trailingPE":18.,"priceToBook":1.2,"priceToSalesTrailing12Months":1.1,
                    "grossMargins":.15,"operatingMargins":.08,"profitMargins":.07,"returnOnEquity":.12}
    monkeypatch.setattr(peers.yf,"Ticker",Stock)
    monkeypatch.setattr(peers,"_annual_asset_turnover",lambda stock,**k:{"value":.8,"observed_at":"2025-12-31"})
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics("1229.TW","聯華","Industrials","Conglomerates",{})
    assert [r["ticker"] for r in result["peers"]]==[code+".TW" for code,name in COHORT]
    assert result["audit"]["coverage_status"]=="success"
    assert result["audit"]["candidate_attempt_count"]<=10
    assert comparable_peer_rows(result["peers"])==[]
    assert _peer_comparison({"ticker":"1229.TW","dynamic_peer_metrics":result["peers"]})["summary"]["peer_count"]==0


def pages():
    from data_fetch.market_sources import official_food_processing_peer_cohort as source
    base=Path(__file__).parent/"fixtures/source_acquisition"
    return {source.ISSUER_URL:(base/"food_1229_issuer_20261009.html").read_bytes(),
            source.SEGMENT_URL:(base/"food_processing_cohort_20261009.html").read_bytes()}


def acquire(monkeypatch, *, raw=None, master=None, metadata=None):
    from data_fetch.market_sources import official_food_processing_peer_cohort as source
    raw=raw or pages(); calls=[]
    monkeypatch.setattr(source,"_now",lambda:1791513600)
    def download(url, **kwargs):
        import time
        calls.append((url,kwargs["deadline"]-time.monotonic()))
        return raw[url]
    monkeypatch.setattr(source,"download_html",download)
    monkeypatch.setattr(source,"shared_fetch",lambda key,fn,**k:(fn(),metadata or {"stale":False,"fetched_at_epoch":1791513600}))
    result=source.get_official_food_processing_candidates("1229.TW",MASTER if master is None else master,today=TODAY)
    return result,calls


def test_real_two_page_membership_and_current_master_are_both_required(monkeypatch):
    result,calls=acquire(monkeypatch)
    assert [r["ticker"] for r in result["candidates"]]==[code+".TW" for code,name in COHORT]
    assert len(calls)==2 and all(0<seconds<=6 for url,seconds in calls)
    for r in result["candidates"]:
        assert r["business_comparability_verified_current"] is False
        assert r["comparison_scope"]=="food_processing_segment"
        assert "undated_segment_membership" in r["comparison_limitations"]
        assert "whole_company_business_mix_not_verified" in r["comparison_limitations"]
        assert len(r["issuer_response_sha256"])==len(r["segment_response_sha256"])==64


@pytest.mark.parametrize("change",["wrong_issuer","wrong_segment","wrong_group","missing_target","oversized","non_utf8"])
def test_bad_membership_cannot_supply_food_candidates(monkeypatch,change):
    from data_fetch.market_sources import official_food_processing_peer_cohort as source
    raw=pages()
    if change=="wrong_issuer": raw[source.ISSUER_URL]=raw[source.ISSUER_URL].replace(b"1229",b"1228")
    elif change=="wrong_segment": raw[source.ISSUER_URL]=raw[source.ISSUER_URL].replace("加工食品".encode(),"原物料".encode())
    elif change=="wrong_group": raw[source.SEGMENT_URL]=raw[source.SEGMENT_URL].replace(b"companyList_M200",b"companyList_M100")
    elif change=="missing_target": raw[source.SEGMENT_URL]=raw[source.SEGMENT_URL].replace(b"stk_code=1229",b"stk_code=1228")
    elif change=="oversized": raw[source.SEGMENT_URL]=b"x"*250001
    elif change=="non_utf8": raw[source.ISSUER_URL]=b"\xff"*101
    assert acquire(monkeypatch,raw=raw)[0]["candidates"]==[]


def test_other_issuer_footer_cannot_supply_target_membership(monkeypatch):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources import official_food_processing_peer_cohort as source
    raw=pages(); soup=BeautifulSoup(raw[source.ISSUER_URL],"html.parser")
    content=soup.select_one("div.content")
    for h in content.find_all("h4"):
        if source._compact(h.get_text())=="►食品>加工食品": h.decompose()
    soup.append(BeautifulSoup('<div class="content"><h4>1228其他公司所屬產業鏈如下:</h4><h4>►<a href="introduce.php?ic=M000">食品</a>&gt;加工食品</h4></div>',"html.parser"))
    raw[source.ISSUER_URL]=str(soup).encode()
    assert acquire(monkeypatch,raw=raw)[0]["candidates"]==[]


def test_unverified_peer_does_not_erase_other_receipts(monkeypatch):
    result,_=acquire(monkeypatch,master=[MASTER[0],{**MASTER[1],"stock_name":"其他公司"},*MASTER[2:]])
    assert [r["ticker"] for r in result["candidates"]]==[code+".TW" for code,name in COHORT[1:]]
    assert result["rejected_candidate_codes"]==["1232"]


def test_latest_master_date_is_disclosed_without_redating_on_closed_days(monkeypatch):
    result,_=acquire(monkeypatch,master=[{**r,"date":"2026-10-08"} for r in MASTER])
    assert len(result["candidates"])==4
    assert all(r["master_observed_at"]==r["issuer_master_observed_at"]=="2026-10-08"
               for r in result["candidates"])


@pytest.mark.parametrize("epoch",[None,0,False,float("nan"),float("inf"),1791513601,1791513600-86401])
def test_bad_receipt_time_is_not_current_membership(monkeypatch,epoch):
    assert acquire(monkeypatch,metadata={"stale":False,"fetched_at_epoch":epoch})[0]["candidates"]==[]


@pytest.mark.parametrize("change",["issuer_renamed","stale_master","peer_old","peer_market"])
def test_identity_changes_are_not_silently_accepted(monkeypatch,change):
    master=[dict(r) for r in MASTER]
    if change=="issuer_renamed": master[0]["stock_name"]="其他公司"
    elif change=="stale_master": master=[{**r,"date":"2026-09-01"} for r in master]
    elif change=="peer_old": master[1]["date"]="2026-10-08"
    elif change=="peer_market": master[1]["type"]="tpex"
    result,calls=acquire(monkeypatch,master=master)
    if change in {"issuer_renamed","stale_master"}: assert result["candidates"]==[] and calls==[]
    else: assert len(result["candidates"])==3 and "1232.TW" not in [r["ticker"] for r in result["candidates"]]


def test_missing_or_stale_cache_receipt_cannot_supply_leads(monkeypatch):
    from data_fetch.market_sources import official_food_processing_peer_cohort as source
    for cached,meta in [({"peer_codes":["1232"],"issuer_response_sha256":"a"*64,"segment_response_sha256":"b"*64},{"stale":True}),
                        ({"peer_codes":["9999"],"issuer_response_sha256":"a"*64,"segment_response_sha256":"b"*64},{"stale":False,"fetched_at_epoch":1791513600}),
                        ({"peer_codes":["1232"],"issuer_response_sha256":None,"segment_response_sha256":"b"*64},{"stale":False,"fetched_at_epoch":1791513600})]:
        monkeypatch.setattr(source,"shared_fetch",lambda *a,**k:(cached,meta))
        assert source.get_official_food_processing_candidates("1229.TW",MASTER,today=TODAY)["candidates"]==[]
    assert source.get_official_food_processing_candidates("5314.TWO",MASTER,today=TODAY)["status"]=="not_applicable"
