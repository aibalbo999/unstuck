import asyncio
from types import SimpleNamespace


def test_daily_market_refresh_respects_shared_snapshot_ttl_and_records_fetch():
    from annual_disclosure_refresh_scheduler import (
        DAILY_REFRESH_SECONDS,
        REFRESH_GRACE_SECONDS,
        MARKET_SNAPSHOT_TICKERS,
        refresh_due_annual_disclosures,
    )

    now = 1_800_000_000.0
    calls = []

    class Service:
        async def fetch_source_async(self, request, source):
            calls.append((request, source))
            at = now - 20
            return SimpleNamespace(source_audit=[
                {"source": "annual_workforce", "status": "success", "record_count": 1,
                 "stale": False, "error_kind": "", "fetched_at_epoch": at,
                 "cache_hit": True, "http_request_sent": False},
                {"source": "esg_occupational_safety", "status": "success", "record_count": 1,
                 "stale": False, "error_kind": "", "fetched_at_epoch": at + 1,
                 "cache_hit": True, "http_request_sent": False},
            ])

    schedule = {}
    asyncio.run(refresh_due_annual_disclosures(
        SimpleNamespace(data_refresh_service=Service()), schedule, now=now, emit=lambda _message: None,
    ))

    assert [request.ticker for request, _source in calls] == list(MARKET_SNAPSHOT_TICKERS)
    assert all(source == "annual_workforce" for _request, source in calls)
    assert all(request.options.record_provider_sla is True for request, _source in calls)
    assert all(request.options.force_refresh is False for request, _source in calls)
    assert all(schedule[ticker] == now - 20 + DAILY_REFRESH_SECONDS + REFRESH_GRACE_SECONDS
               for ticker in MARKET_SNAPSHOT_TICKERS)

    asyncio.run(refresh_due_annual_disclosures(
        SimpleNamespace(data_refresh_service=Service()), schedule, now=now + 3600,
        emit=lambda _message: None,
    ))
    assert len(calls) == len(MARKET_SNAPSHOT_TICKERS)


def test_refresh_failure_uses_bounded_backoff_without_forcing_or_retrying_immediately():
    from annual_disclosure_refresh_scheduler import (
        FAILURE_RETRY_SECONDS,
        MARKET_SNAPSHOT_TICKERS,
        refresh_due_annual_disclosures,
    )

    now = 1_800_000_000.0
    calls = []

    class Service:
        async def fetch_source_async(self, request, source):
            calls.append((request, source))
            return SimpleNamespace(source_audit=[
                {"source": "annual_workforce", "status": "error", "record_count": 0,
                 "stale": True, "error_kind": "ReadError", "fetched_at_epoch": now - 100_000},
            ])

    schedule = {}
    asyncio.run(refresh_due_annual_disclosures(
        SimpleNamespace(data_refresh_service=Service()), schedule, now=now, emit=lambda _message: None,
    ))
    assert len(calls) == len(MARKET_SNAPSHOT_TICKERS)
    assert all(schedule[ticker] == now + FAILURE_RETRY_SECONDS for ticker in MARKET_SNAPSHOT_TICKERS)

    asyncio.run(refresh_due_annual_disclosures(
        SimpleNamespace(data_refresh_service=Service()), schedule, now=now + 60,
        emit=lambda _message: None,
    ))
    assert len(calls) == len(MARKET_SNAPSHOT_TICKERS)
