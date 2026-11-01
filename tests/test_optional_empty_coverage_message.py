from data_fetch.enrichment_merge import _merge_optional_http_bundle


def test_social_empty_unknown_does_not_become_acceptable_empty_after_merge():
    payload={"status":"empty_unknown","sample_count":0,"sentiment_assessment":"not_assessed",
             "dcard":[],"mobile01":[],"pttweb":[],"ptt_stock_direct":[],"cmoney_stock_direct":[],"yahoo_stock_direct":[]}
    data={"ticker":"3653.TW","company_name":"健策","source_audit":[{
        "source":"social_sentiment","provider":"Social Forum Sentiment","status":"degraded_enrichment",
        "record_count":0,"coverage_status":"empty_unknown","cache_hit":False,"stale":False}]}
    result=_merge_optional_http_bundle(data,{"social_sentiment":payload},refreshed_sources=("social_sentiment",))
    row=next(x for x in reversed(result["source_audit"])if x["source"]=="social_sentiment")
    assert "可接受" not in row["message"]
    assert "不證明" in row["message"]
    assert row["status"]=="degraded_enrichment" and row["record_count"]==0
    assert result["social_sentiment"]["status"]=="empty_unknown"
    assert result["social_sentiment"]["sentiment_assessment"]=="not_assessed"
