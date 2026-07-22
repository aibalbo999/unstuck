import asyncio
from types import MappingProxyType, SimpleNamespace

from data_fetch import FetchResult


def test_prepare_full_rerun_data_refreshes_mapping_safe_snapshot_payload():
    from report_rerun_data import prepare_full_rerun_data

    refresh_requests = []
    progress_events = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            refresh_requests.append(request)
            return FetchResult(
                request=request,
                data=MappingProxyType(
                    {
                        "ticker": request.ticker,
                        "company_name": "京元電子",
                        "current_price": 333.0,
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "fake",
                                    "status": "success",
                                }
                            ),
                        ),
                        "data_trust": MappingProxyType(
                            {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                        ),
                    }
                ),
            )

    result = asyncio.run(
        prepare_full_rerun_data(
            MappingProxyType(
                {
                    "ticker": "2449",
                    "data": MappingProxyType(
                        {
                            "ticker": "2449",
                            "company_name": "京元電子",
                            "current_price": 309.5,
                        }
                    ),
                }
            ),
            pipeline_id="v2",
            refresh_service=FakeRefreshService(),
            progress_callback=progress_events.append,
        )
    )

    assert [request.options.force_refresh for request in refresh_requests] == [True]
    assert refresh_requests[0].ticker == "2449"
    assert progress_events == [
        {
            "type": "status",
            "phase": "rerun_refresh_data",
            "message": "完整重跑前正在刷新資料快照...",
            "pipeline_id": "v2",
        }
    ]
    assert result["current_price"] == 333.0
    assert result["source_audit"][0]["status"] == "success"
    result["source_audit"].append({"source": "rerun", "provider": "pipeline", "status": "success"})
    assert result["source_audit"][-1]["source"] == "rerun"


def test_prepare_full_rerun_data_keeps_existing_snapshot_when_no_refresh_service():
    from report_rerun_data import prepare_full_rerun_data

    snapshot = MappingProxyType(
        {
            "ticker": "2449",
            "data": MappingProxyType(
                {
                    "ticker": "2449",
                    "company_name": "京元電子",
                    "source_audit": (
                        MappingProxyType(
                            {
                                "source": "market_data",
                                "provider": "snapshot",
                                "status": "success",
                            }
                        ),
                    ),
                }
            ),
        }
    )

    result = asyncio.run(prepare_full_rerun_data(snapshot, pipeline_id="v2"))

    assert result["ticker"] == "2449"
    result["source_audit"].append({"source": "rerun", "provider": "pipeline", "status": "success"})
    assert result["source_audit"][-1]["provider"] == "pipeline"


def test_prepare_full_rerun_data_rejects_missing_refresh_ticker():
    import pytest
    from fastapi import HTTPException

    from report_rerun_data import prepare_full_rerun_data

    class FakeRefreshService:
        async def fetch_async(self, request):
            raise AssertionError("should not refresh without a ticker")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            prepare_full_rerun_data(
                {"data": {"company_name": "No Ticker"}},
                pipeline_id="v2",
                refresh_service=FakeRefreshService(),
            )
        )

    assert exc_info.value.status_code == 400
    assert "缺少 ticker" in str(exc_info.value.detail)
