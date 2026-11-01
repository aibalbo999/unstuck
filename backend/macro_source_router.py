"""Preserve qualified FRED components; fill only gaps from free originals."""
from copy import deepcopy

LABELS = {"us_10y_yield":"美國10年期公債殖利率", "us_cpi_yoy":"CPI年增率", "vix":"VIX"}


def fetch_macro_indicators():
    from macro_fetcher import fetch_key_macro_indicators, _format_macro_summary
    from free_macro_fetcher import fetch_free_macro_component
    primary = fetch_key_macro_indicators(use_cache=True)
    if primary.get("status") == "success":
        return primary
    result = deepcopy(primary)
    indicators = result.setdefault("indicators", {})
    components = result.setdefault("component_statuses", {})
    attempted, acquired, free_transports = [], [], {}
    for name, label in LABELS.items():
        if components.get(name, {}).get("status") == "success" and name in indicators:
            continue
        candidate = fetch_free_macro_component(name)
        free_transports[name] = candidate.get("transport", {})
        if candidate.get("acquisition_attempted"):
            attempted.append(name)
        if candidate.get("new_original_acquired"):
            acquired.append(name)
        observation = candidate.get("observation")
        if candidate.get("status") == "success" and observation:
            meta = candidate["metadata"]
            item = {**observation, **meta, "label":label, "status":"success", "stale":False,
                    "series_id":observation["source_series"], "provider":candidate["provider"], "cache_hit":candidate["cache_hit"]}
            indicators[name] = item
            components[name] = {**meta, "status":"success", "stale":False,
                "provider":candidate["provider"], "series_id":item["series_id"],
                "as_of":observation["date"], "source_url":candidate["source_url"],
                "cache_hit":candidate["cache_hit"], "original_receipt":observation["original_receipt"],
                "http_request_sent":candidate.get("transport", {}).get("http_request_sent", False)}
        else:
            # Keep an existing stale FRED value and its original qualification.
            # A failed replacement is recorded separately, never silently erased.
            components.setdefault(name, {"status":"unavailable", "provider":candidate["provider"]})
            components[name]["free_fallback"] = {
                "provider":candidate["provider"], "status":candidate["status"],
                "metadata":candidate.get("metadata", {}), "transport":candidate.get("transport", {}),
                "qualification_error":candidate.get("qualification_error")}
    fresh = sum(components.get(name, {}).get("status") == "success" for name in LABELS)
    providers = sorted({str(item.get("provider") or "FRED") for item in indicators.values()})
    result.update(status="success" if fresh == 3 else "partial" if fresh else "stale" if indicators else "unavailable",
                  source=" / ".join(providers) or "FRED / free official originals",
                  actual_provider=" / ".join(providers) or "FRED / free official originals",
                  stale=any(item.get("stale") for item in indicators.values()))
    result["source_urls"] = sorted({item["source_url"] for item in indicators.values() if item.get("source_url")}
                                   | ({primary["source_url"]} if "FRED" in providers and primary.get("source_url") else set()))
    if providers != ["FRED"]:
        result.pop("source_url", None)
    result["cache_hit"] = bool(indicators) and all(item.get("cache_hit") for item in indicators.values())
    primary_origin = primary.get("retrieval_origin", {})
    result["retrieval_origin"] = {
        "schema_version":"macro-component-retrieval:v2", "primary":primary_origin,
        "free_attempted_components":attempted, "free_acquired_components":acquired,
        "free_transport":free_transports,
        "new_fetch_attempted":bool(primary_origin.get("new_fetch_attempted") or any(t.get("http_request_sent") for t in free_transports.values()))}
    result["primary_provider_audit"] = {
        "source":"macro_indicators", "provider":"FRED macro indicators",
        "status":"degraded_enrichment" if primary.get("status") in {"partial","stale"} else
                 "not_configured" if primary.get("status")=="not_configured" else "unavailable",
        "record_count":len(primary.get("indicators", {})),
        "cache_hit":primary.get("cache_hit", False), "stale":primary.get("stale", False),
        "component_statuses":deepcopy(primary.get("component_statuses", {})),
        "message":"Primary result retained before free-source fallback; not overwritten by recovery."}
    if not primary_origin.get("new_fetch_attempted"):
        result["primary_provider_audit"].update(event_kind="local_block",http_request_sent=False,http_request_count=0)
    result["summary_text"] = _format_macro_summary(result).replace("FRED 總經：", "總經（"+result["source"]+"）：", 1)
    result["message"] = ("各指標保留自己的供應商、觀測日期及原件；不是歷史首次可得性證明。"
                         if fresh == 3 else "部分總經指標仍不足或過期；保留原失敗與來源缺口。")
    return result
