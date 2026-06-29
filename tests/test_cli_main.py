import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_cli_exits_before_fetch_when_api_keys_missing(monkeypatch):
    import main as cli_main

    class FailingStockDataService:
        async def fetch_async(self, _request):
            pytest.fail("CLI should fail fast before fetching data when Gemini API keys are missing")

    monkeypatch.setattr(cli_main, "has_api_keys", lambda: False, raising=False)
    monkeypatch.setattr(cli_main, "API_KEY_SETUP_MESSAGE", "missing keys", raising=False)
    monkeypatch.setattr(cli_main, "API_KEYS", [])
    monkeypatch.setattr(cli_main, "STOCK_DATA_SERVICE", FailingStockDataService())
    monkeypatch.setattr(sys, "argv", ["main.py", "--ticker", "2330.TW", "--no-report"])

    with pytest.raises(cli_main.MissingApiKeyConfiguration):
        asyncio.run(cli_main.main_async())
