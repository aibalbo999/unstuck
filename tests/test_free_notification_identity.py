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
