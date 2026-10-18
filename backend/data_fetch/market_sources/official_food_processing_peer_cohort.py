"""Undated food-processing membership supplies segment leads, not valuation peers.

1229 also has a cloud-system-integration membership. This adapter acquires only
food-segment candidates; it never treats food as the whole holding-company mix.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import math
import re
import time

from bs4 import BeautifulSoup

from shared_provider_cache import shared_fetch
from .construction_cohort_transport import (PROVIDER, FOOD_ISSUER_URL as ISSUER_URL,
                                            FOOD_SEGMENT_URL as SEGMENT_URL, download_html)
from search_provider_runtime import SourceResponseError, cooldown_state, remember_failure, scope_key

IDENTITIES={"1229":("聯華","twse"),"1232":("大統益","twse"),
            "1225":("福懋油","twse"),"1216":("統一","twse"),"1702":("南僑","twse")}
PEER_CODES=("1232","1225","1216","1702")

def _now():
    return time.time()

def _page(raw: bytes):
    if not isinstance(raw,bytes) or not 100<=len(raw)<=250_000:
        raise ValueError("official food_processing page size invalid")
    return BeautifulSoup(raw.decode("utf-8",errors="strict"),"html.parser")

def _compact(value: str):
    return re.sub(r"\s+","",value)

def _issuer_has_segment(raw: bytes):
    page=_page(raw)
    headings=[h for h in page.find_all("h4") if _compact(h.get_text())=="1229聯華所屬產業鏈如下:"]
    if len(headings)!=1:
        return False
    section=headings[0].find_parent("div",class_="content")
    if (section is None or len([h for h in section.find_all("h3") if h.get_text(" ",strip=True)=="個體公司所屬產業鏈"])!=1
            or len([h for h in section.find_all("h4") if re.fullmatch(r"[0-9]{4}.+所屬產業鏈如下:",_compact(h.get_text()))])!=1):
        return False
    for h in section.find_all("h4"):
        if _compact(h.get_text())=="►食品>加工食品":
            links=h.find_all("a",href="introduce.php?ic=M000")
            if len(links)==1 and links[0].get_text(" ",strip=True)=="食品":
                return True
    return False

def _segment_cohort(raw: bytes):
    page=_page(raw)
    groups=page.select('div#companyList_M200[title="加工食品"]')
    if not 1<=len(groups)<=2 or not any(b.get_text(" ",strip=True)=="加工食品" for g in groups for b in g.find_all("b")):
        return []
    panels=[]
    # Desktop/mobile copies must agree for each admitted company. A changed
    # peer must not erase independent receipts for the other valid peers.
    for g in groups:
        found={}
        for a in g.find_all("a",href=True):
            m=re.fullmatch(r"company_basic\.php\?stk_code=([1-9]\d{3})",a["href"])
            if m:
                found.setdefault(m[1],[]).append((a.get_text(" ",strip=True),a.get("title")))
        if found.get("1229")!=[(IDENTITIES["1229"][0],IDENTITIES["1229"][0])]:
            return []
        panels.append(found)
    return [code for code in PEER_CODES
            if all(p.get(code)==[(IDENTITIES[code][0],IDENTITIES[code][0])] for p in panels)]

def _current_master_day(rows,code,*,today):
    dated=[]
    all_days=[]
    for row in rows:
        if not isinstance(row,dict):
            continue
        try:
            observed=date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            continue
        if observed>today:
            continue
        all_days.append(observed)
        if str(row.get("stock_id") or "")==code:
            dated.append((observed,row))
    if not dated or not all_days:
        return None
    latest=max(all_days)
    current=[r for d,r in dated if d==latest]
    name,market=IDENTITIES[code]
    if ((today-latest).days>7 or not current
            or any(r.get("stock_name")!=name or str(r.get("type") or "").lower()!=market for r in current)):
        return None
    return latest

def _fetch_pages():
    deadline=time.monotonic()+12
    raw={}
    guard=scope_key(PROVIDER,endpoint="ic.tpex.org.tw")
    if cooldown_state(guard):
        raise SourceResponseError("cooldown")
    for url in (ISSUER_URL,SEGMENT_URL):
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError("food_processing cohort deadline exceeded")
        try:
            raw[url]=download_html(url,deadline=min(deadline,time.monotonic()+6))
        except SourceResponseError as exc:
            if exc.status_code is not None:
                remember_failure(guard,exc)
            raise
        if time.monotonic()>=deadline:
            raise TimeoutError("food_processing cohort deadline exceeded")
    codes=_segment_cohort(raw[SEGMENT_URL])
    if not _issuer_has_segment(raw[ISSUER_URL]) or not codes:
        raise ValueError("official food_processing membership changed")
    return {"peer_codes":codes,"issuer_response_sha256":sha256(raw[ISSUER_URL]).hexdigest(),
            "segment_response_sha256":sha256(raw[SEGMENT_URL]).hexdigest()}

def get_official_food_processing_candidates(ticker,master_rows,*,today):
    if ticker!="1229.TW":
        return {"candidates":[],"status":"not_applicable"}
    days={code:_current_master_day(master_rows,code,today=today) for code in IDENTITIES}
    if days["1229"] is None:
        return {"candidates":[],"status":"current_master_identity_unverified"}
    try:
        evidence,meta=shared_fetch("official-food-processing-peer-cohort:v1",_fetch_pages,
                                  freshness_seconds=24*60*60,use_cache=True,lock_wait_seconds=12)
    except Exception as exc:
        return {"candidates":[],"status":"official_pages_unavailable",
                "error_kind":getattr(exc,"error_kind",type(exc).__name__)}
    acquired_at=meta.get("fetched_at_epoch") if isinstance(meta,dict) else None
    try:
        time_valid=type(acquired_at) in (int,float) and math.isfinite(acquired_at) and 0<=_now()-acquired_at<=86400
    except OverflowError:
        time_valid=False
    if (not time_valid or not isinstance(meta,dict) or meta.get("stale") or not isinstance(evidence,dict)
            or any(not isinstance(evidence.get(k),str) or not re.fullmatch(r"[0-9a-f]{64}",evidence[k])
                   for k in ("issuer_response_sha256","segment_response_sha256"))
            or not isinstance(evidence.get("peer_codes"),list)
            or not evidence["peer_codes"] or any(code not in PEER_CODES for code in evidence["peer_codes"])
            or len(set(evidence["peer_codes"]))!=len(evidence["peer_codes"])):
        return {"candidates":[],"status":"official_pages_unavailable"}
    candidates=[]
    for code in PEER_CODES:
        if days[code] is None or code not in evidence["peer_codes"]:
            continue
        name,market=IDENTITIES[code]
        candidates.append({"name":name,"ticker":code+(".TW" if market=="twse" else ".TWO"),
            "identity_status":"current_exchange_master_and_official_chain",
            "comparison_status":"official_segment_candidate",
            "comparison_scope":"food_processing_segment",
            "business_comparability_verified_current":False,
            "relationship_basis":"same_undated_tpex_food_processing_segment",
            "comparison_limitations":["undated_segment_membership","whole_company_business_mix_not_verified",
                                      "financial_period_comparability_not_verified"],
            "issuer_master_observed_at":days["1229"].isoformat(),"master_observed_at":days[code].isoformat(),
            "issuer_source_url":ISSUER_URL,"segment_source_url":SEGMENT_URL,**evidence,
            "official_page_acquired_at_epoch":meta.get("fetched_at_epoch")})
    return {"candidates":candidates,"status":"success" if candidates else "no_current_verified_candidates",
            "rejected_candidate_codes":[code for code in PEER_CODES if code not in {c["ticker"].split(".")[0] for c in candidates}],
            "cache_hit":bool(meta.get("cache_hit"))}
