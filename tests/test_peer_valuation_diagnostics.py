"""Peer valuation diagnostics preserve original values without admitting missing PE."""
from datetime import date
import pytest
from data_fetch.market_sources import official_peer_valuation as m
@pytest.mark.parametrize("raw,expected",[("-",None),("",None),("0",None),(True,None),("12.3",12.3)])
def test_diagnostics_do_not_promote_missing_or_invalid_ratio(raw,expected):
 roster={"source_url":m.URLS[".TW"],"response_sha256":"a"*64,"entries":{"6230":{"name":"test","date_roc":"1151030","pe":raw,"pb":"2"}}}
 result=m.select_valuation(roster,"6230.TW",today=date(2026,10,31))
 assert result["metrics"].get("pe_ttm")==expected
 assert result["metrics"]["pb"]==2
 assert result["metric_value_observations"]["pe_ttm"]["raw_value"]==raw
 assert result["status"]=="success" # Existing PB-only source semantics unchanged.
 assert "not_applicable" not in str(result)

@pytest.mark.parametrize("raw",[float("nan"),float("inf"),"x"*65,{},10**100])
def test_diagnostic_raw_value_is_bounded_and_json_safe(raw):
 import json
 roster={"source_url":m.URLS[".TW"],"entries":{"6230":{"name":"test","date_roc":"1151030","pe":raw,"pb":"2"}}}
 result=m.select_valuation(roster,"6230.TW",today=date(2026,10,31))
 assert result["metric_value_observations"]["pe_ttm"]["raw_value"] is None
 json.dumps(result,allow_nan=False)

def test_recovery_retains_diagnostics_in_existing_attempts(monkeypatch):
 import cache_store
 from data_fetch.market_sources import official_peer_valuation,taiwan
 from data_fetch.market_sources import peer_recovery as recovery
 monkeypatch.setattr(cache_store,"get_cache_json",lambda key:None)
 saved=[];monkeypatch.setattr(cache_store,"set_cache_json",lambda *args:saved.append(args))
 monkeypatch.setattr(taiwan,"DataLoader",None)
 monkeypatch.setattr(official_peer_valuation,"fetch_official_peer_valuation",lambda *a,**k:{"metrics":{"pb":2},"status":"success","source":"official","source_url":"https://example.test","response_sha256":"a"*64,"observed_at":"2026-10-30","metric_value_observations":{"pe_ttm":{"raw_value":"-","parse_status":"no_accepted_positive_ratio"}}})
 result=recovery.fetch_peer_valuation_fallback("6230.TW",today=date(2026,10,31))
 assert result["metrics"]=={"pb":2}
 proof=result["attempts"][0]["official_value_diagnostics"]
 assert proof["ticker"]=="6230.TW" and proof["metric_values"]["pe_ttm"]["raw_value"]=="-"
 assert proof["evidence_scope"]=="parsed_fields_only_not_original_http_receipt"
 assert len(saved)==1 and saved[0][2]==1800

@pytest.mark.parametrize("damage",[None,"cookie","auth","cache","redirect","status","unknown"])
def test_original_archive_uses_only_exact_native_public_response(monkeypatch,damage):
 import httpx,official_response_evidence
 calls=[]
 monkeypatch.setattr(official_response_evidence,"archive_response",lambda body,**kw:calls.append((body,kw)) or {"status":"archived"})
 headers={"cookie":"x"} if damage=="cookie" else {"authorization":"x"} if damage=="auth" else {}
 url=m.URLS[".TW"]+("?unexpected=1" if damage=="redirect" else "")
 response=httpx.Response(503 if damage=="status" else 200,content=b"[]",request=httpx.Request("GET",url,headers=headers))
 if damage=="cache":response.extensions["from_cache"]=True
 if damage=="unknown":response=object()
 proof=m._archive_native_roster(response,".TW")
 assert bool(calls)==(damage is None)
 assert (proof is not None)==(damage is None)
 if proof:assert proof["cache_hit"] is False and proof["response_complete"] is True

def test_archive_failure_keeps_parsed_roster(monkeypatch):
 import httpx,official_response_evidence,json
 body=json.dumps([{"Code":"6230","Name":"test","Date":"1151030","PEratio":"-","PBratio":"2"}]).encode()
 monkeypatch.delenv("STOCK_AGENT_TEST_NO_NETWORK")
 monkeypatch.setattr(m,"sync_get",lambda *a,**kw:httpx.Response(200,content=body,request=httpx.Request("GET",m.URLS[".TW"])))
 def broken(*a,**kw):raise OSError("archive unavailable")
 monkeypatch.setattr(official_response_evidence,"archive_response",broken)
 roster=m._fetch_roster(".TW")
 assert roster==m.parse_roster(body,".TW")

def test_saved_original_replays_exact_selected_fields_and_cache_keeps_origin(monkeypatch):
 import httpx,json
 from official_response_evidence import read_response
 body=json.dumps([{"Code":"6230","Name":"test","Date":"1151030","PEratio":"-","PBratio":"2"}]).encode()
 monkeypatch.delenv("STOCK_AGENT_TEST_NO_NETWORK")
 calls=[]
 def send(*a,**kw):
  calls.append(a);return httpx.Response(200,content=body,request=httpx.Request("GET",m.URLS[".TW"]))
 monkeypatch.setattr(m,"sync_get",send)
 roster=m._fetch_roster(".TW");proof=roster["original_receipt"]
 assert read_response(proof,max_bytes=m.MAX_BYTES)==body
 replay=m.parse_roster(read_response(proof,max_bytes=m.MAX_BYTES),".TW")
 assert replay=={k:v for k,v in roster.items() if k!="original_receipt"}
 first=m.select_valuation(roster,"6230.TW",today=date(2026,10,31))
 monkeypatch.setattr(m,"shared_fetch",lambda *a,**kw:(roster,{"cache_hit":True,"stale":False,"fetched_at_epoch":proof["retrieved_at"]}))
 cached=m.fetch_official_peer_valuation("6230.TW",today=date(2026,10,31))
 assert len(calls)==1 and cached["cache_hit"] is True
 assert cached["original_receipt"]==first["original_receipt"]
 assert cached["metric_value_observations"]==first["metric_value_observations"]
 assert cached["metrics"]=={"pb":2}
 assert "http_request_sent" not in cached

def test_dynamic_peer_payload_retains_diagnostic_but_missing_pe_stays_partial(monkeypatch):
 from data_fetch.market_sources import peers
 monkeypatch.setattr(peers,"_today",lambda:date(2026,10,31))
 monkeypatch.setattr(peers,"load_peer_stock_master",lambda:[{"stock_id":code,"stock_name":code,"type":market,"industry_category":"生技醫療業","date":"2026-10-31"}for code,market in (("6861","twse"),("1234","tpex"))])
 monkeypatch.setattr(peers.yf,"Ticker",lambda symbol:type("Quote",(),{"info":{"symbol":symbol,"quoteType":"EQUITY","industry":"Medical Devices","grossMargins":.4,"operatingMargins":.2,"profitMargins":.1,"returnOnEquity":.12,"priceToSalesTrailing12Months":3,"totalRevenue":9e9,"totalAssets":2e9}})())
 diagnostic={"ticker":"1234.TWO","observed_at":"2026-10-30","metric_values":{"pe_ttm":{"raw_value":"-","parse_status":"no_accepted_positive_ratio"}},"evidence_scope":"parsed_fields_only_not_original_http_receipt"}
 monkeypatch.setattr(peers,"fetch_peer_valuation_fallback",lambda *a,**kw:{"status":"success","metrics":{"pb":2},"attempts":[{"provider":m.PROVIDER,"status":"success","official_value_diagnostics":diagnostic}]})
 result=peers.fetch_dynamic_peer_metrics_with_diagnostics("6861.TW","test","Healthcare","Medical Devices",{"same_industry_peers":[{"stock_id":"1234"}]})
 row=result["peers"][0]
 assert row["pe_ttm"] is None and "pe_ttm" in row["missing_metrics"]
 assert row["metrics_status"]=="partial" and result["audit"]["coverage_status"]=="partial"
 assert row["acquisition_attempts"][1]["official_value_diagnostics"]==diagnostic
 assert result["audit"]["candidate_diagnostics"][0]["acquisition_attempts"][1]["official_value_diagnostics"]==diagnostic
