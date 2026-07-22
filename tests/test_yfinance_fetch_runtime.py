import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch.yfinance_fetch_runtime import (  # noqa: E402
    build_core_fetch_request,
    read_current_price,
    read_fresh_cache_payload,
    resolve_core_stock,
)


def test_read_fresh_cache_payload_returns_fresh_payload_and_logs_age():
    request = build_core_fetch_request(" aapl ", now_epoch=lambda: 100.0)
    logs = []

    def fake_get_cached(cache_key):
        assert cache_key == "financial_data:AAPL"
        return {"ticker": "AAPL"}

    def fake_cache_gate(original_ticker, cached, **kwargs):
        assert original_ticker == "AAPL"
        assert cached == {"ticker": "AAPL"}
        assert kwargs["now_epoch"] == 200.0
        return ({"ticker": "AAPL", "data_freshness": {"age_seconds": 120}}, [], False)

    payload = read_fresh_cache_payload(
        request,
        force_refresh=False,
        get_cached=fake_get_cached,
        build_fresh_cache_payload=fake_cache_gate,
        assess_cached=lambda *_args, **_kwargs: (True, {}),
        append_cache_audit=lambda *_args, **_kwargs: None,
        now_epoch=lambda: 200.0,
        emit=logs.append,
    )

    assert payload["ticker"] == "AAPL"
    assert logs == ["  ✅ 使用快取的 AAPL 財務數據（市場資料約 2.0 分鐘前更新）"]


def test_read_fresh_cache_payload_skips_cache_gate_when_force_refresh():
    request = build_core_fetch_request("2330.tw", now_epoch=lambda: 100.0)
    logs = []

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("force_refresh should skip cache reads")

    payload = read_fresh_cache_payload(
        request,
        force_refresh=True,
        get_cached=fail_if_called,
        build_fresh_cache_payload=fail_if_called,
        assess_cached=fail_if_called,
        append_cache_audit=fail_if_called,
        now_epoch=fail_if_called,
        emit=logs.append,
    )

    assert payload is None
    assert logs == ["  ♻️  2330.TW 已要求強制刷新，略過既有財務資料快取..."]


def test_resolve_core_stock_logs_failed_attempts_and_uses_resolved_ticker():
    logs = []
    stock = object()

    class Provider:
        name = "fixture"

        def resolve_stock(self, ticker):
            return (
                stock,
                {"longName": "台積電"},
                True,
                "2330.TW",
                [
                    {"ticker": ticker, "valid": False},
                    {"ticker": "2330.TW", "valid": True},
                ],
            )

    resolved = resolve_core_stock(
        "2330",
        market_data_provider=Provider(),
        get_market_data_provider=lambda _ticker: None,
        emit=logs.append,
    )

    assert resolved.provider.name == "fixture"
    assert resolved.stock is stock
    assert resolved.info == {"longName": "台積電"}
    assert resolved.ticker == "2330.TW"
    assert logs == ["    ⚠️ 2330 查無資料，嘗試 2330.TW..."]


def test_read_current_price_uses_recent_history_when_info_is_missing():
    class CloseSeries:
        iloc = [-1, 123.456]

    class HistoryFrame:
        empty = False

        def __getitem__(self, key):
            assert key == "Close"
            return CloseSeries()

    class Stock:
        def history(self, period):
            assert period == "5d"
            return HistoryFrame()

    def fake_safe_get(payload, key, default="N/A"):
        return payload.get(key, default)

    assert read_current_price(Stock(), {}, safe_get=fake_safe_get) == 123.46
