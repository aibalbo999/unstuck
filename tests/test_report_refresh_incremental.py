import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from data_trust import data_snapshot_filename_for_report  # noqa: E402
from report_persistence import report_bundle_keys_for_filename  # noqa: E402
from storage.report_storage import InMemoryStorage  # noqa: E402


def test_report_refresh_forces_quote_refresh_when_financial_statements_are_fresh(tmp_path):
    import report_refresh_service

    filename = "2308_TW_v2_report_20260626_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage = InMemoryStorage()
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    fresh_time = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    previous_snapshot = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline": "v2",
        "data": {"current_price": 100},
        "source_audit": [
            {"source": "financial_statements", "provider": "FinMind", "status": "success", "record_count": 1, "fetched_at": fresh_time},
            {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1, "fetched_at": fresh_time},
        ],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
    }
    storage.save_report(
        keys.data_key,
        json.dumps(previous_snapshot, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )

    seen_requests = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            seen_requests.append(request)
            return SimpleNamespace(
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "台達電",
                    "current_price": 101,
                    "source_audit": [],
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
                }
            )

    asyncio.run(
        report_refresh_service.refresh_report_data_snapshot(
            filename,
            output_dir=str(tmp_path),
            refresh_service=FakeRefreshService(),
            storage=storage,
        )
    )

    assert seen_requests
    assert seen_requests[0].ticker == "2308.TW"
    assert seen_requests[0].options.force_refresh is True
    assert "financial_statements" not in report_refresh_service._stale_sources(previous_snapshot)
    assert data_snapshot_filename_for_report(filename)
