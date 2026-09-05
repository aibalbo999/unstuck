import json
from types import SimpleNamespace

import llm_errors


def quota_error(*, rpd=False):
    violations = [{"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_input_token_count",
                   "quotaId": "GenerateContentInputTokensPerModelPerMinute-FreeTier", "quotaValue": "16000",
                   "quotaDimensions": {"model": "gemma-4-31b", "location": "global", "consumer": "private-project"}}]
    if rpd:
        violations.append({"quotaId": "GenerateRequestsPerDayPerProject", "quotaValue": "20"})
    payload = {"error": {"message": "key=secret-do-not-print", "details": [
        {"violations": violations}, {"retryDelay": "28s", "consumer": "private-project"}]}}
    return SimpleNamespace(code=429, status="RESOURCE_EXHAUSTED", message=json.dumps(payload), details=None)


def test_nested_json_message_preserves_only_safe_quota_fields():
    assert hasattr(llm_errors, "extract_quota_details")
    details = llm_errors.extract_quota_details(quota_error())
    assert details["violations"][0]["kind"] == "input_tpm"
    assert details["violations"][0]["limit"] == 16000
    assert details["violations"][0]["model"] == "gemma-4-31b"
    assert details["retry_delay_seconds"] == 28
    serialized = json.dumps(details)
    assert "private-project" not in serialized
    assert "secret-do-not-print" not in serialized


def test_quota_description_does_not_echo_provider_message():
    description = llm_errors.describe_quota_or_rate_error(quota_error())
    assert "secret-do-not-print" not in description
    assert "private-project" not in description
    assert "16000" in description


def test_multiple_quota_kinds_preserved_and_explicit_rpd_is_detected():
    assert hasattr(llm_errors, "extract_quota_details")
    details = llm_errors.extract_quota_details(quota_error(rpd=True))
    assert {v["kind"] for v in details["violations"]} == {"input_tpm", "rpd"}
    assert llm_errors.is_requests_per_day_error(quota_error(rpd=True))


def test_malformed_payload_does_not_invent_quota():
    assert hasattr(llm_errors, "extract_quota_details")
    assert llm_errors.extract_quota_details(RuntimeError("429 resource exhausted"))["violations"] == []
    error = SimpleNamespace(details={"violations": [{"quotaId": "TokensPerMinute", "quotaValue": True}]})
    assert llm_errors.extract_quota_details(error)["violations"] == []


def test_error_event_retains_safe_quota_details():
    from agent_runtime.llm_call_events import llm_model_error_fields
    result = llm_model_error_fields({}, 1, "gemma-4-31b-it", "prompt", SimpleNamespace(keys=["key"]), "key",
                                   timeout_seconds=10, error=quota_error())
    assert result["metadata"]["provider_quota"]["violations"][0]["limit"] == 16000
