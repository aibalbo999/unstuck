"""One USD-base response supplies traceable spot conversions, never bank quotes."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

NOW = datetime(2026, 9, 25, 1, tzinfo=timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def isolated_fx_cache(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    import data_fetch.taiwan_open_data_provider as fx
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(fx, "time", SimpleNamespace(time=lambda: NOW))
    yield
    cache_store.reset_cache_store_for_tests()


def install_responses(monkeypatch, rates=None, **fields):
    import data_fetch.taiwan_open_data_provider as fx
    calls = []
    payload = {"result": "success", "base_code": "USD",
               "time_last_update_utc": "Thu, 24 Sep 2026 00:02:32 +0000",
               "rates": {"USD": 1, "TWD": 31.784395, "EUR": 0.877372, "JPY": 158.127269}}
    if rates is not None:
        payload["rates"] = rates
    payload.update(fields)

    def get(url, **kwargs):
        calls.append(url)
        if url == fx.BOT_EXCHANGE_RATE_URL:
            return SimpleNamespace(content=b"<html>Challenge Validation</html>")
        assert url == fx.ER_API_USD_URL
        return SimpleNamespace(json=lambda: payload)

    monkeypatch.setattr(fx, "sync_get", get)
    return calls


def test_single_er_response_supplies_three_spots_with_original_inputs(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    calls = install_responses(monkeypatch)
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    assert calls == [fx.BOT_EXCHANGE_RATE_URL, fx.ER_API_USD_URL]
    assert result.provider == "open.er-api.com"
    assert result.status == "degraded_enrichment"  # The bank quotes remain unavailable.
    assert result.audit["record_count"] == 3
    assert result.value["coverage"] == dict.fromkeys(("USD", "EUR", "JPY"), "available")
    for currency, denominator in (("USD", 1), ("EUR", .877372), ("JPY", 158.127269)):
        quote = result.value["rates"][currency]
        assert float(quote["spot"]) == pytest.approx(31.784395 / denominator, abs=.00001)
        assert quote["buy"] is quote["sell"] is None
        assert quote["rate_kind"] == "spot"
        assert quote["base_currency"] == currency and quote["quote_currency"] == "TWD"
        assert quote["unit"] == f"TWD per {currency}"
        assert quote["as_of"] == "2026-09-24T00:02:32+00:00"
        assert quote["derived"] is (currency != "USD")
        assert quote["source_rates"]["TWD"] == 31.784395
        if currency != "USD":
            assert quote["source_rates"][currency] == denominator
            assert quote["formula"] == f"rates.TWD / rates.{currency}"


@pytest.mark.parametrize("bad", [None, 0, -1, True, "NaN", "inf", "bad", 1e-320])
def test_invalid_cross_denominator_preserves_other_spots(monkeypatch, bad):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    install_responses(monkeypatch, {"USD": 1, "TWD": 32, "EUR": bad, "JPY": 160})
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    assert result.value["rates"]["EUR"] is None
    assert result.value["coverage"]["EUR"] == "unavailable"
    assert float(result.value["rates"]["JPY"]["spot"]) == pytest.approx(.2)
    assert result.audit["record_count"] == 2


@pytest.mark.parametrize("base", ["EUR", "TWD", "", None])
def test_er_wrong_or_missing_base_cannot_be_used_as_usd(monkeypatch, base):
    import data_fetch.taiwan_open_data_provider as fx
    install_responses(monkeypatch, base_code=base)
    with pytest.raises(ValueError):
        fx._fetch_er_api_usd_twd_rate()


def test_shared_daily_spot_response_is_not_refetched_after_twenty_minutes(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    import shared_provider_cache as shared
    from data_fetch.types import FetchRequest
    now = [NOW]
    monkeypatch.setattr(shared, "time", SimpleNamespace(time=lambda: now[0]))
    monkeypatch.setattr(fx, "time", SimpleNamespace(time=lambda: now[0]))
    calls = install_responses(monkeypatch)
    first = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    now[0] += 20 * 60
    second = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("3702.TW"))
    assert len(calls) == 2
    assert second.audit["cache_hit"] is True
    assert second.value["rates"]["JPY"]["as_of"] == first.value["rates"]["JPY"]["as_of"]
    # Cache is bounded; after an hour the shared source is eligible again.
    now[0] += 41 * 60
    third = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    assert len(calls) == 4 and third.audit["cache_hit"] is False


def test_force_refresh_keeps_explicit_request_semantics(monkeypatch):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    calls = install_responses(monkeypatch)
    fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW", force_refresh=True))
    assert len(calls) == 4


@pytest.mark.parametrize("reported,expected", [("bad", "unknown"),
    ("Tue, 01 Sep 2026 00:00:00 +0000", "stale"),
    ("Sat, 26 Sep 2026 00:00:00 +0000", "future")])
def test_derived_quotes_keep_unknown_old_and_future_dates(monkeypatch, reported, expected):
    import data_fetch.taiwan_open_data_provider as fx
    from data_fetch.types import FetchRequest
    install_responses(monkeypatch, time_last_update_utc=reported)
    result = fx.TaiwanOpenDataProvider().fetch(FetchRequest.from_ticker("2330.TW"))
    for quote in result.value["rates"].values():
        assert quote["stale"] is True and quote["observation_status"] == expected
    assert result.audit["stale"] is True
