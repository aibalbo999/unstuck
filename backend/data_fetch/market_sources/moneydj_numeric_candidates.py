"""Numeric acquisition leads from a dated publisher list, never valuation peers."""
import time
from .moneydj_peer_cohort import TARGET, URL, _current_identity, acquire_published_cohort, cohort_source_audit


def get_published_food_biotech_candidates(ticker, master_rows, *, today):
    if ticker!=TARGET:
        return {"candidates":[],"status":"not_applicable"}
    if _current_identity("5314",master_rows,today)!=("世紀*","tpex"):
        return {"candidates":[],"status":"current_issuer_identity_unavailable"}
    started=time.time()
    value,meta=acquire_published_cohort(ticker,master_rows,today=today)
    audit=cohort_source_audit(value,meta,started_at_epoch=started)
    if meta.get("error_kind") or meta.get("stale"):
        return {"candidates":[],"status":"published_cohort_unavailable","source_audit":audit}
    candidates=[]
    for row in value.get("records",[]):
        peer=row["counterparty"]
        candidates.append({"name":peer["official_name"],"ticker":peer["ticker"],
            "identity_status":"current_exchange_master_and_dated_publisher_cohort",
            "comparison_status":"published_segment_candidate",
            "comparison_scope":"publisher_food_biotech_candidates",
            "business_comparability_verified_current":False,
            "relationship_basis":"dated_same_publisher_cohort_and_current_stock_master",
            "comparison_limitations":["publisher_classification_only","whole_company_business_mix_not_verified",
                                      "financial_period_comparability_not_verified"],
            "cohort_source_url":URL,"cohort_response_sha256":value["response_sha256"],
            "cohort_observed_at":row["observed_at"],"issuer_cohort_observed_at":row["issuer_observed_at"],
            "cohort_acquired_at_epoch":meta["fetched_at_epoch"],"cohort_cache_hit":bool(meta.get("cache_hit"))})
    return {"candidates":candidates,"status":"success" if candidates else "no_current_verified_candidates",
            "cache_hit":bool(meta.get("cache_hit")),"source_audit":audit}
