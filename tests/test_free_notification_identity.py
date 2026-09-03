from free_notification_identity import dedupe_context


def test_dedupe_context_uses_report_identity_when_value_truthiness_fails():
    class BrokenTruthFilename:
        def __bool__(self):
            raise RuntimeError("filename truthiness unavailable")

        def __str__(self):
            return "broken_report.html"

    context = dedupe_context(
        {
            "source": "report_repair",
            "type": "manual_review",
            "filename": BrokenTruthFilename(),
        }
    )

    expected = "notification_plan.v1|report_repair|manual_review|ticker|broken_report.html|v1"
    assert context == {"dedupe_key": expected, "message_id": expected}


def test_dedupe_context_canonicalizes_filename_pipeline_for_report_actions():
    filename = "2330_TW_v4_report_20260628_000000.html"
    placeholder = dedupe_context(
        {
            "source": "report_repair",
            "type": "manual_review",
            "ticker": "2330.TW",
            "filename": filename,
            "pipeline_id": "N/A",
        }
    )
    canonical = dedupe_context(
        {
            "source": "report_repair",
            "type": "manual_review",
            "ticker": "2330.TW",
            "filename": filename,
            "pipeline_id": "v4",
        }
    )

    assert placeholder == canonical
    assert placeholder["dedupe_key"].endswith(f"|{filename}|v4")


def test_dedupe_context_canonicalizes_filename_pipeline_for_backtest_actions():
    filename = "2330_TW_v4_report_20260628_000000.html"
    placeholder = dedupe_context(
        {
            "source": "backtest_due",
            "type": "backtest_due",
            "ticker": "2330.TW",
            "filename": filename,
            "horizon_months": 6,
            "pipeline_id": "N/A",
        }
    )
    canonical = dedupe_context(
        {
            "source": "backtest_due",
            "type": "backtest_due",
            "ticker": "2330.TW",
            "filename": filename,
            "horizon_months": 6,
            "pipeline_id": "v4",
        }
    )

    assert placeholder == canonical
    assert placeholder["dedupe_key"].endswith(f"|6|v4")


def test_dedupe_context_keeps_payload_pipeline_without_report_filename():
    context = dedupe_context(
        {
            "source": "report_repair",
            "type": "manual_review",
            "ticker": "2330.TW",
            "pipeline_id": "v4",
        }
    )

    assert context["dedupe_key"].endswith("|report|v4")
