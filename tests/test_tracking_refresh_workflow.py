import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_refresh_ticker_reports_fetches_once_and_reuses_data_for_remaining_reports():
    from tracking_refresh_workflow import refresh_ticker_reports

    calls = []
    refreshed_payload = {"ticker": "2449.TW", "current_price": 132.0}

    async def fake_refresh_report(filename, *, output_dir, refresh_service, refreshed_data=None, return_refreshed_data=False):
        calls.append({
            "filename": filename,
            "output_dir": output_dir,
            "refresh_service": refresh_service,
            "refreshed_data": refreshed_data,
            "return_refreshed_data": return_refreshed_data,
        })
        response = {"success": True, "filename": filename}
        if return_refreshed_data:
            response["refreshed_data"] = refreshed_payload
        return response

    result = asyncio.run(
        refresh_ticker_reports(
            "2449.TW",
            [
                {"filename": "2449_v1_report_20260609_090000.html"},
                {"filename": "2449_v2_report_20260610_090000.html"},
                {"filename": "2449_v3_report_20260611_090000.html"},
            ],
            output_dir="/tmp/reports",
            refresh_service=object(),
            refresh_report=fake_refresh_report,
        )
    )

    assert result.refreshed_reports_count == 3
    assert result.refreshed_data == refreshed_payload
    assert [call["filename"] for call in calls] == [
        "2449_v1_report_20260609_090000.html",
        "2449_v2_report_20260610_090000.html",
        "2449_v3_report_20260611_090000.html",
    ]
    assert [call["return_refreshed_data"] for call in calls] == [True, False, False]
    assert calls[0]["refreshed_data"] is None
    assert calls[1]["refreshed_data"] == refreshed_payload
    assert calls[2]["refreshed_data"] == refreshed_payload


def test_refresh_ticker_reports_rejects_report_without_filename():
    from tracking_refresh_workflow import refresh_ticker_reports

    async def fake_refresh_report(*_args, **_kwargs):
        raise AssertionError("invalid report should fail before refresh call")

    try:
        asyncio.run(
            refresh_ticker_reports(
                "2449.TW",
                [{}],
                output_dir="/tmp/reports",
                refresh_service=object(),
                refresh_report=fake_refresh_report,
            )
        )
    except ValueError as exc:
        assert "filename" in str(exc)
    else:
        raise AssertionError("missing filename should raise ValueError")
