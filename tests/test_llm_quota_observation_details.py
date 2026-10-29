"""Observation preserves evidence without changing quota admission policy."""
import json
from types import SimpleNamespace

import llm_quota_details


def test_missing_value_preserves_known_kind_without_changing_policy():
    from llm_quota_observation_details import observe_quota_details
    error = SimpleNamespace(details={"violations": [{
        "quotaId": "GenerateRequestsPerMinutePerProjectPerModel",
        "quotaMetric": "generativelanguage.googleapis.com/generate_content_requests",
        "quotaDimensions": {"model": "gemini-fixture", "consumer": "private-project"},
    }]})
    before = llm_quota_details.extract_quota_details(error)
    observation = observe_quota_details(error)
    assert observation["violations"][0]["kind"] == "rpm"
    assert observation["violations"][0]["limit"] is None
    assert observation["detail_status"] == "partial"
    assert "private-project" not in json.dumps(observation)
    assert llm_quota_details.extract_quota_details(error) == before == {"violations": [], "retry_delay_seconds": None}


def test_unknown_metric_is_retained_and_parser_failure_is_distinct():
    from llm_quota_observation_details import observe_quota_details
    error = SimpleNamespace(response_json={"error": {"details": [{"violations": [{
        "quotaMetric": "generativelanguage.googleapis.com/new_metric", "quotaValue": "5",
    }]}]}})
    observed = observe_quota_details(error)
    assert observed["violations"][0]["kind"] == "unknown"
    assert observed["violations"][0]["quota_metric"].endswith("/new_metric")
    assert observed["detail_status"] == "unrecognized"
    assert observe_quota_details(SimpleNamespace(message='429 {broken'))["detail_status"] == "parse_error"
    assert observe_quota_details(SimpleNamespace())["detail_status"] == "sdk_fields_absent"


def test_bounded_allowlist_does_not_echo_keys_headers_or_error_text():
    from llm_quota_observation_details import observe_quota_details
    error = SimpleNamespace(details={"violations": [{
        "quotaId": "GenerateRequestsPerDayPerProject", "quotaValue": "20",
        "quotaDimensions": {"model": "gemma-4-31b-it", "location": "global", "consumer": "private-project"},
        "Authorization": "private-header", "message": "private-prompt",
    }]}, message="key=secret-do-not-print", headers={"Retry-After": "30", "Authorization": "private-header"})
    observation = observe_quota_details(error)
    assert observation["violations"][0]["kind"] == "rpd"
    assert observation["violations"][0]["limit"] == 20
    assert observation["retry_delay_seconds"] == 30
    assert observation["detail_status"] == "parsed"
    for secret in ("private-project", "private-header", "private-prompt", "secret-do-not-print"):
        assert secret not in json.dumps(observation)


def test_sdk_metadata_failure_cannot_replace_provider_failure(monkeypatch):
    import llm_quota_observation_details as obs
    obs.sdk_version.cache_clear()
    monkeypatch.setattr(obs,'version',lambda _:(_ for _ in ()).throw(OSError('private-path')))
    observed=obs.observe_quota_details(SimpleNamespace(details={'violations':[{'quotaId':'GenerateRequestsPerDay','quotaValue':20}]}))
    assert observed['sdk_version'] is None
    assert observed['violations'][0]['kind']=='rpd'
    assert 'private-path' not in json.dumps(observed)
    obs.sdk_version.cache_clear()
