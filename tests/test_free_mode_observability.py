import asyncio

import api_observability_service


def test_ops_dashboard_includes_free_mode_contract(monkeypatch):
    monkeypatch.setenv("FREE_MODE", "true")

    def summary_fetcher(_limit):
        return []

    def alerts_fetcher(_limit):
        return []

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            summary_fetcher,
            alerts_fetcher,
            task_queue=None,
        )
    )

    assert payload["free_mode"]["enabled"] is True
    assert payload["free_mode"]["can_run_without_paid_keys"] is True
    assert payload["free_mode"]["provider_count"] >= 1
    assert payload["free_mode"]["providers_by_cost_tier"]["free"] >= 1
    assert "violations" in payload["free_mode"]
