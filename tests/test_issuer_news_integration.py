from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from data_fetch.enrichment_merge import _merge_optional_http_bundle


def test_public_issuer_news_is_planned_only_for_verified_issuer_routes():
    registry = ProviderRegistry()
    name = "Verified issuer news"
    for ticker in ("2206.TW", "3023.TW", "3023"):
        assert name in registry.provider_names(FetchRequest.from_ticker(ticker), "recent_catalysts")
    for ticker in ("3023.TWO", "AAPL", "2330.TW"):
        assert name not in registry.provider_names(FetchRequest.from_ticker(ticker), "recent_catalysts")


def test_issuer_news_bundle_reaches_existing_company_time_selection():
    now = datetime.now(timezone.utc).date().isoformat()
    row = {"title": "三陽工業公開公司訊息", "text": "三陽工業公布一項公司活動。",
           "date": now, "link": "https://www.sanyang.com.tw/busnessnews-page693", "source": "三陽工業官網"}
    data = {"ticker": "2206.TW", "company_name": "三陽工業"}
    actual = _merge_optional_http_bundle(data, {"issuer_news": [row]})
    assert [r["link"] for r in actual["recent_catalysts"]] == [row["link"]]
