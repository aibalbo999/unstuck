"""Offline acquisition cadence must never renew an institutional observation."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from data_fetch.taiwan_providers import InstitutionalTradingProvider
from data_fetch.types import FetchRequest


@pytest.fixture(autouse=True)
def isolated_source(monkeypatch):
    import cache_store
    import provider_resilience
    import shared_provider_cache
    from cache_backends import InMemoryCache

    cache_store.set_cache_backend(InMemoryCache())
    now = [datetime(2026, 9, 23, 12, tzinfo=timezone.utc).timestamp()]
    monkeypatch.setattr(shared_provider_cache.time, "time", lambda: now[0])
    monkeypatch.setattr(provider_resilience, "_check_provider_state", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "enforce_provider_throttle", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "_record_provider_success", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "_record_provider_failure", lambda *a, **kw: None)
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "1")
    yield now
    cache_store.reset_cache_store_for_tests()


def install_rows(monkeypatch, rows):
    from data_fetch.market_sources import taiwan
    calls = []

    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            calls.append(kwargs)
            if isinstance(rows, Exception):
                raise rows
            return pd.DataFrame(rows)

    monkeypatch.setattr(taiwan, "DataLoader", Loader)
    return calls


def observation(day="2026-09-08", stock_id="2321"):
    return [dict(date=day, stock_id=stock_id, name=name, buy=0, sell=89 if name == "Dealer_self" else 0)
            for name in ("Foreign_Investor", "Investment_Trust", "Dealer_self", "Dealer_Hedging")]


def test_repeated_acquisition_keeps_old_observation_and_uses_source_cache(monkeypatch, isolated_source):
    calls = install_rows(monkeypatch, observation())
    request = FetchRequest.from_ticker("2321.TW")
    first = InstitutionalTradingProvider().fetch(request)
    isolated_source[0] += 100
    second = InstitutionalTradingProvider().fetch(request)

    assert len(calls) == 1
    assert first.value["latest_date"] == second.value["latest_date"] == "2026-09-08"
    assert second.value["total_net_buy_shares"] == -89
    assert first.audit["stale"] is second.audit["stale"] is True
    assert first.audit["observation_status"] == second.audit["observation_status"] == "stale"
    assert second.audit["cache_hit"] is True
    assert first.audit["fetched_at_epoch"] == second.audit["fetched_at_epoch"]
    assert second.audit["provider_attempts"] == []
    assert second.audit["event_kind"] == "aggregate"
    assert second.audit.get("http_request_sent") is not True


def test_provider_error_is_not_empty_and_cooldown_does_not_repeat_callback(monkeypatch, isolated_source):
    calls = install_rows(monkeypatch, TimeoutError("sensitive upstream detail must not be persisted"))
    request = FetchRequest.from_ticker("2321.TW")
    first = InstitutionalTradingProvider().fetch(request)
    isolated_source[0] += 10
    second = InstitutionalTradingProvider().fetch(request)
    assert first.status == second.status == "error"
    assert first.audit["error_kind"] == second.audit["error_kind"] == "TimeoutError"
    assert len(calls) == 1
    assert second.audit["cooldown"] is True
    assert second.audit["http_request_sent"] is False
    assert first.audit["fetched_at"] is second.audit["fetched_at"] is None
    assert "sensitive" not in str(first.audit)
    assert first.audit["component_statuses"]["institutional_observations"]["reason_code"] == "acquisition_failed"


def test_exact_stock_and_observation_dates_are_screened_without_filling_gaps(monkeypatch):
    rows = observation() + observation("2026-09-23", "2330") + observation("2099-09-23") + observation("bad-date")
    install_rows(monkeypatch, rows)
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert result.value["latest_date"] == "2026-09-08"
    assert result.value["total_net_buy_shares"] == -89
    assert result.value["lookback_trading_days"] == 1
    assert result.value["last_5_trading_days_net_buy_thousand_shares"] is None
    assert result.value["observed_date_count"] == 1
    assert result.audit["coverage_status"] == "partial"
    assert result.audit["stale"] is True


@pytest.mark.parametrize("day", ["bad-date", "2099-09-23"])
def test_only_invalid_or_future_dates_cannot_be_current(monkeypatch, day):
    install_rows(monkeypatch, observation(day))
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert not result.value
    assert result.status != "success"
    assert result.audit["observation_status"] != "recent"


def legacy_bundle(monkeypatch):
    import data_fetch.yfinance_sync_enrichment as legacy
    for name in ("fetch_finmind_news_catalysts", "fetch_yfinance_news_catalysts",
                 "fetch_dynamic_peer_metrics", "build_pe_river_chart_data"):
        monkeypatch.setattr(legacy, name, lambda *a, **kw: [])
    return legacy.fetch_sync_enrichment_bundle(
        ticker="2321.TW", stock=None, company_name="東訊", sector="Technology", industry="Communication",
        company_identity={"instrument_type": "EQUITY"}, years=[], net_income_history=[],
        shares_outstanding=None, skip_optional_http=True,
    )


def test_legacy_and_registry_share_cache_and_typed_audit(monkeypatch, isolated_source):
    calls = install_rows(monkeypatch, observation())
    typed = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    isolated_source[0] += 100
    bundle = legacy_bundle(monkeypatch)
    assert len(calls) == 1
    audits = [row for row in bundle["audit"] if row["source"] == "institutional_trading"]
    assert len(audits) == 1
    assert audits[0]["cache_hit"] is True and audits[0]["stale"] is True
    assert audits[0]["fetched_at_epoch"] == typed.audit["fetched_at_epoch"]
    assert audits[0]["provider_attempts"] == []
    assert bundle["institutional_trading"]["latest_date"] == "2026-09-08"


def test_legacy_finalization_keeps_institutional_acquisition_age(monkeypatch, isolated_source):
    from types import SimpleNamespace
    from data_fetch.yfinance_payload import finalize_and_cache_legacy_payload
    install_rows(monkeypatch, observation())
    typed = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    acquired = typed.audit["fetched_at_epoch"]
    isolated_source[0] += 100
    typed = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    data = {"ticker": "2321.TW", "institutional_trading": typed.value}
    result = finalize_and_cache_legacy_payload(
        data=data, ticker="2321.TW", original_cache_key="test-only:legacy", provider=SimpleNamespace(name="fixture"),
        fetch_started_epoch=isolated_source[0], skip_optional_http=True, enrichment_audit=[typed.audit],
        fmp_quote_audit=None, monthly_revenue_audit=None, finmind_financial_fallback_audit=None,
    )
    freshness = result["source_freshness"]["institutional_trading"]
    assert freshness["fetched_at_epoch"] == acquired
    assert freshness["cache_hit"] is True and freshness["age_seconds"] == 100
    assert freshness["stale"] is True and freshness["observed_at"] == "2026-09-08"
    audits = [row for row in result["source_audit"] if row["source"] == "institutional_trading"]
    assert all(row["cache_hit"] is True for row in audits)
    assert all(row["fetched_at"] == typed.audit["fetched_at"] for row in audits)


def test_registry_merge_keeps_cached_acquisition_time(monkeypatch, isolated_source):
    import asyncio
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.workflow import _run_missing_core_provider_plan
    install_rows(monkeypatch, observation("2026-09-22"))
    request = FetchRequest.from_ticker("2321.TW")
    typed = InstitutionalTradingProvider().fetch(request)
    acquired = typed.audit["fetched_at_epoch"]
    isolated_source[0] += 100
    result = asyncio.run(_run_missing_core_provider_plan(request, ProviderRegistry([InstitutionalTradingProvider()]),
                                                         {"ticker": "2321.TW", "institutional_trading": {}}))
    freshness = result["source_freshness"]["institutional_trading"]
    assert freshness["fetched_at_epoch"] == acquired
    assert freshness["cache_hit"] is True and freshness["age_seconds"] == 100
    assert freshness["stale"] is False and freshness["observed_at"] == "2026-09-22"


def test_fresh_single_observation_has_partial_window_and_persistable_date_details(monkeypatch):
    from provider_observation_details import observation_details
    install_rows(monkeypatch, observation("2026-09-22"))
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert result.audit["stale"] is False
    assert result.audit["coverage_status"] == "partial"
    assert result.value["observed_date_count"] == 1
    assert result.value["last_5_trading_days_net_buy_thousand_shares"] is None
    details = observation_details(result.audit)
    component = details["component_statuses"]["institutional_observations"]
    assert component["as_of"] == "2026-09-22"
    assert component["observation_status"] == "recent"
    assert component["retrieval_status"] == "success"


def test_stale_ttl_expires_then_new_observation_gets_existing_fresh_ttl(monkeypatch, isolated_source):
    from data_freshness import source_max_age_seconds
    rows = observation()
    calls = install_rows(monkeypatch, rows)
    request = FetchRequest.from_ticker("2321.TW")
    InstitutionalTradingProvider().fetch(request)
    isolated_source[0] += 899
    cached = InstitutionalTradingProvider().fetch(request)
    assert len(calls) == 1 and cached.audit["stale"] is True
    rows[:] = observation("2026-09-23")
    isolated_source[0] += 2
    fresh = InstitutionalTradingProvider().fetch(request)
    assert len(calls) == 2 and fresh.audit["stale"] is False
    assert fresh.value["latest_date"] == "2026-09-23"
    isolated_source[0] += source_max_age_seconds("institutional_trading", "2321.TW") - 1
    assert InstitutionalTradingProvider().fetch(request).audit["cache_hit"] is True
    assert len(calls) == 2
    isolated_source[0] += 2
    assert InstitutionalTradingProvider().fetch(request).audit["cache_hit"] is False
    assert len(calls) == 3


def test_empty_short_cache_is_distinct_from_error_and_rechecks(monkeypatch, isolated_source):
    calls = install_rows(monkeypatch, [])
    request = FetchRequest.from_ticker("2321.TW")
    first = InstitutionalTradingProvider().fetch(request)
    isolated_source[0] += 59
    second = InstitutionalTradingProvider().fetch(request)
    assert first.status == second.status == "unavailable"
    assert first.audit["retrieval_status"] == second.audit["retrieval_status"] == "empty"
    assert not first.audit["error_kind"] and not second.audit.get("cooldown")
    assert len(calls) == 1 and second.audit["cache_hit"] is True
    assert second.audit["component_statuses"]["institutional_observations"]["reason_code"] == "no_observations"
    isolated_source[0] += 2
    InstitutionalTradingProvider().fetch(request)
    assert len(calls) == 2


def test_raised_error_retains_value_without_renewing_acquisition(monkeypatch, isolated_source):
    install_rows(monkeypatch, observation())
    request = FetchRequest.from_ticker("2321.TW")
    first = InstitutionalTradingProvider().fetch(request)
    isolated_source[0] += 901
    install_rows(monkeypatch, TimeoutError("unavailable"))
    result = InstitutionalTradingProvider().fetch(request)
    assert result.value["latest_date"] == "2026-09-08"
    assert result.audit["fetched_at_epoch"] == first.audit["fetched_at_epoch"]
    assert result.audit["cache_hit"] is True and result.audit["stale"] is True
    assert result.audit["error_kind"] == "TimeoutError"
    assert result.status == "degraded_enrichment"
    assert result.audit["provider_attempts"]
    assert "http_request_sent" not in result.audit  # SDK callback may have attempted transport.


def test_circuit_local_block_does_not_invoke_loader(monkeypatch):
    import provider_resilience
    calls = install_rows(monkeypatch, observation())
    def blocked(*args):
        raise provider_resilience.ProviderCircuitOpenError("still protected")
    monkeypatch.setattr(provider_resilience, "_check_provider_state", blocked)
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert not calls
    assert result.status == "unavailable"
    assert result.audit["error_kind"] == "ProviderCircuitOpenError"
    assert result.audit["provider_attempts"] == []
    assert result.audit["http_request_sent"] is False


def test_cached_value_does_not_reset_or_bypass_circuit_for_new_acquisition(monkeypatch, isolated_source):
    import provider_resilience
    calls = install_rows(monkeypatch, observation())
    request = FetchRequest.from_ticker("2321.TW")
    InstitutionalTradingProvider().fetch(request)
    checks = []
    def blocked(*args):
        checks.append(1)
        raise provider_resilience.ProviderCircuitOpenError("still protected")
    monkeypatch.setattr(provider_resilience, "_check_provider_state", blocked)
    assert InstitutionalTradingProvider().fetch(request).audit["cache_hit"] is True
    assert not checks
    isolated_source[0] += 901
    blocked_result = InstitutionalTradingProvider().fetch(request)
    assert len(checks) == 1 and len(calls) == 1
    assert blocked_result.audit["error_kind"] == "ProviderCircuitOpenError"
    assert blocked_result.audit["stale"] is True


def test_forced_registry_acquisition_does_not_use_source_cache(monkeypatch):
    calls = install_rows(monkeypatch, observation())
    InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW", force_refresh=True))
    assert len(calls) == 2 and result.audit["cache_hit"] is False


def test_legacy_core_force_refresh_reaches_institutional_acquisition(monkeypatch, isolated_source):
    from test_data_fetch_fixtures import _patch_common_fetch_dependencies, EmptyMonthlyRevenueLoader
    import data_fetch.yfinance_core_fetch as core
    import data_fetch.yfinance_sync_enrichment as legacy
    from data_fetch.market_sources import taiwan
    _patch_common_fetch_dependencies(monkeypatch, resolved_ticker="2321.TW")
    monkeypatch.setattr(core.time_module, "time", lambda: isolated_source[0])
    monkeypatch.setattr(core, "DataLoader", EmptyMonthlyRevenueLoader)
    monkeypatch.setattr(legacy, "fetch_institutional_trading_trend", taiwan.fetch_institutional_trading_trend)
    calls = install_rows(monkeypatch, observation())
    InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    result = core.fetch_stock_data("2321.TW", skip_optional_http=True, force_refresh=True)
    assert "error" not in result
    assert len(calls) == 2
    assert result["institutional_trading"]["cache_hit"] is False


def test_last_five_observations_with_session_holes_are_not_a_five_session_window(monkeypatch):
    dates = ("2026-09-08", "2026-09-10", "2026-09-14", "2026-09-18", "2026-09-23")
    install_rows(monkeypatch, [row for day in dates for row in observation(day)])
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert result.value["observed_date_count"] == 5
    assert result.value["last_5_trading_days_net_buy_thousand_shares"] is None
    assert result.value["last_5_window_status"] == "missing_sessions"


def test_complete_five_session_observations_have_a_verified_five_day_sum(monkeypatch):
    dates = ("2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23")
    install_rows(monkeypatch, [row for day in dates for row in observation(day)])
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert result.value["last_5_trading_days_net_buy_thousand_shares"] == pytest.approx(-445 / 1000, abs=0.0051)
    assert result.value["last_5_window_status"] == "complete"


def test_unknown_calendar_cannot_certify_five_session_window(monkeypatch):
    import data_freshness_market
    monkeypatch.setattr(data_freshness_market, "market_calendar", lambda *a, **kw: {"coverage_status": "unknown"})
    dates = ("2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23")
    install_rows(monkeypatch, [row for day in dates for row in observation(day)])
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert result.value["last_5_trading_days_net_buy_thousand_shares"] is None
    assert result.value["last_5_window_status"] == "calendar_unknown"


def test_extra_weekend_observation_does_not_displace_a_real_five_session_member(monkeypatch):
    dates = ("2026-09-17", "2026-09-18", "2026-09-19", "2026-09-21", "2026-09-22", "2026-09-23")
    install_rows(monkeypatch, [row for day in dates for row in observation(day)])
    result = InstitutionalTradingProvider().fetch(FetchRequest.from_ticker("2321.TW"))
    assert result.value["last_5_trading_days_net_buy_thousand_shares"] is None
    assert result.value["last_5_window_status"] == "missing_sessions"


@pytest.mark.parametrize("rows", [[], TimeoutError("upstream failed")])
def test_forced_legacy_then_missing_core_plan_does_not_repeat_same_fetch(monkeypatch, isolated_source, rows):
    import asyncio
    from test_data_fetch_fixtures import _patch_common_fetch_dependencies, EmptyMonthlyRevenueLoader
    import data_fetch.yfinance_core_fetch as core
    import data_fetch.yfinance_sync_enrichment as legacy
    from data_fetch.market_sources import taiwan
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.workflow import _run_missing_core_provider_plan
    from provider_correlation import correlation_scope
    _patch_common_fetch_dependencies(monkeypatch, resolved_ticker="2321.TW")
    monkeypatch.setattr(core.time_module, "time", lambda: isolated_source[0])
    monkeypatch.setattr(core, "DataLoader", EmptyMonthlyRevenueLoader)
    monkeypatch.setattr(legacy, "fetch_institutional_trading_trend", taiwan.fetch_institutional_trading_trend)
    calls = install_rows(monkeypatch, rows)
    request = FetchRequest.from_ticker("2321.TW", force_refresh=True)
    with correlation_scope(fetch_id="current-fetch", ticker=request.ticker):
        data = core.fetch_stock_data(request.ticker, skip_optional_http=True, force_refresh=True)
        assert "error" not in data
        asyncio.run(_run_missing_core_provider_plan(request, ProviderRegistry([InstitutionalTradingProvider()]), data))
    assert len(calls) == 1
    audits = [entry for entry in data["source_audit"] if entry["source"] == "institutional_trading"]
    assert len(audits) == 1 and audits[0]["fetch_id"] == "current-fetch"


@pytest.mark.parametrize("missing_field", [None, "fetch_id", "operation_id", "actual_provider", "retrieval_status"])
def test_unproven_or_historical_audit_never_suppresses_forced_acquisition(monkeypatch, missing_field):
    import asyncio
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.workflow import _run_missing_core_provider_plan
    from provider_correlation import correlation_scope
    calls = install_rows(monkeypatch, [])
    request = FetchRequest.from_ticker("2321.TW", force_refresh=True)
    with correlation_scope(fetch_id="historical-fetch" if missing_field is None else "current-fetch", ticker=request.ticker):
        old = InstitutionalTradingProvider().fetch(request)
    if missing_field:
        old.audit.pop(missing_field)
    with correlation_scope(fetch_id="current-fetch", ticker=request.ticker):
        asyncio.run(_run_missing_core_provider_plan(request, ProviderRegistry([InstitutionalTradingProvider()]),
                                                     {"ticker": request.ticker, "source_audit": [old.audit]}))
    assert len(calls) == 2
