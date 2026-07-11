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


def test_ops_dashboard_free_mode_provider_shape_keeps_other_sections(monkeypatch):
    class CostTierWithBrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("free mode cost tier truthiness unavailable")

        def __str__(self):
            return "free"

    class ProvidersWithIteratorFailure:
        def __iter__(self):
            yield {"cost_tier": CostTierWithBrokenTruthiness()}
            raise RuntimeError("free mode provider list unavailable")

    monkeypatch.setattr(
        api_observability_service,
        "build_free_mode_contract",
        lambda: {
            "enabled": True,
            "can_run_without_paid_keys": True,
            "providers": ProvidersWithIteratorFailure(),
            "violations": [],
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["status"] == "ok"
    assert payload["free_mode"] == {
        "enabled": True,
        "can_run_without_paid_keys": True,
        "provider_count": 1,
        "providers_by_cost_tier": {"free": 1},
        "violations": [],
    }
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"


def test_ops_dashboard_free_mode_violation_shape_keeps_other_sections(monkeypatch):
    class ViolationWithBrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("free mode violation truthiness unavailable")

        def __str__(self):
            return "missing free provider"

    monkeypatch.setattr(
        api_observability_service,
        "build_free_mode_contract",
        lambda: {
            "enabled": True,
            "can_run_without_paid_keys": True,
            "providers": [{"cost_tier": "free"}],
            "violations": [ViolationWithBrokenTruthiness(), "", None],
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "build_ops_dashboard_snapshot",
        lambda **_kwargs: {
            "jobs": {"active_count": 0},
            "job_latency": {"p95_seconds": 1.5},
            "stuck_jobs": {"count": 0, "jobs": []},
            "node_telemetry": {"nodes": {}},
            "model_route_budget": {"warnings": []},
        },
    )
    monkeypatch.setattr(
        api_observability_service,
        "snapshot_task_queue",
        lambda _task_queue: {"backend": "rq", "available": True, "queue_name": "stock-analysis", "depth": 0},
    )
    monkeypatch.setattr(
        api_observability_service,
        "get_delivery_audit_summary",
        lambda: {
            "total_count": 1,
            "sent_count": 1,
            "failed_count": 0,
            "pending_count": 0,
            "retry_exhausted_count": 0,
            "channel_counts": {"local": 1},
        },
        raising=False,
    )

    async def fake_provider_payload(*_args, **_kwargs):
        return {"selected_window": "last_24h", "alerts": []}

    async def fake_api_quota_payload(_summary_fetcher):
        return {"services": [{"service": "alpha_vantage"}]}

    monkeypatch.setattr(api_observability_service, "build_provider_sla_payload", fake_provider_payload)
    monkeypatch.setattr(api_observability_service, "build_api_quota_payload", fake_api_quota_payload)

    payload = asyncio.run(
        api_observability_service.build_ops_dashboard_payload(
            lambda _limit: [],
            lambda _limit: [],
            task_queue=object(),
        )
    )

    assert payload["free_mode"]["violations"] == ["missing free provider"]
    assert payload["free_mode"]["provider_count"] == 1
    assert payload["free_mode"]["providers_by_cost_tier"] == {"free": 1}
    assert payload["queue"]["available"] is True
    assert payload["jobs"] == {"active_count": 0}
    assert payload["providers"]["selected_window"] == "last_24h"
    assert payload["api_quotas"] == {"services": [{"service": "alpha_vantage"}]}
    assert payload["notification_delivery"]["health"] == "ok"
