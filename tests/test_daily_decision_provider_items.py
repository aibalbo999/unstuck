from types import MappingProxyType


def test_provider_impact_items_skip_duplicate_reports_and_preserve_identity():
    from daily_decision_provider_items import provider_impact_items

    ledger = MappingProxyType({
        "items": [
            {
                "ticker": "NVDA",
                "report_filename": "nvda_repair.html",
                "pipeline_id": "v2",
                "summary": {
                    "recommended_action": "wait_provider_recovery",
                    "blocks_auto_rerun": True,
                },
                "impacts": [{"message": "covered by report repair"}],
            },
            {
                "ticker": "TSM",
                "filename": "tsm_provider.html",
                "pipeline_id": "v3",
                "summary": MappingProxyType({
                    "recommended_action": "wait_provider_recovery",
                    "blocks_auto_rerun": True,
                }),
                "impacts": [{"message": "market_data/yfinance critical"}],
            },
        ]
    })

    items = provider_impact_items(ledger, skip_keys={"nvda_repair.html"})

    assert items == [{
        "source": "provider_impact",
        "type": "wait_provider_recovery",
        "priority_score": 900,
        "title": "TSM provider 影響需處理",
        "detail": "market_data/yfinance critical",
        "ticker": "TSM",
        "filename": "tsm_provider.html",
        "report_filename": "tsm_provider.html",
        "pipeline_id": "v3",
        "recommended_action": "wait_provider_recovery",
        "blocks_auto_rerun": True,
    }]


def test_provider_impact_items_keep_nonblocking_rows_out_of_action_queue():
    from daily_decision_provider_items import provider_impact_items

    items = provider_impact_items({
        "items": [
            {
                "ticker": "2324.TW",
                "summary": {
                    "recommended_action": "monitor_provider",
                    "blocks_auto_rerun": False,
                },
            }
        ]
    }, skip_keys=set())

    assert items == []


def test_daily_decision_report_key_prefers_artifact_filename_then_ticker_pipeline():
    from daily_decision_report_keys import report_key

    assert report_key({"filename": "nvda.html", "ticker": "ignored", "pipeline_id": "v2"}) == "nvda.html"
    assert report_key({"report_filename": "alias.html"}) == "alias.html"
    assert report_key({"ticker": "TSM", "pipeline_id": "v3"}) == "TSM:v3"
    assert report_key({"ticker": "TSM"}) == "TSM:v1"
    assert report_key({"pipeline_id": "v3"}) == ""
