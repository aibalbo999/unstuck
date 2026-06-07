import os
import sys
import asyncio
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch import FetchRequest, StockDataService  # noqa: E402


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.getenv("RUN_LIVE_SMOKE") != "1", reason="set RUN_LIVE_SMOKE=1 to run live provider smoke tests"),
]


def test_live_2449_data_fetch_smoke():
    result = asyncio.run(
        StockDataService().fetch_async(
            FetchRequest.from_ticker("2449", force_refresh=True, skip_optional_http=True)
        )
    )

    assert result.data.get("ticker")
    assert result.data.get("source_audit") is not None
    assert result.data.get("data_trust", {}).get("status") in {"fresh", "partial", "stale", "error", "unknown"}
