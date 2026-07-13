import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from llm_errors import is_requests_per_day_error  # noqa: E402


def test_requests_per_day_error_detects_text_signature():
    error = RuntimeError("429 RESOURCE_EXHAUSTED quotaMetric=GenerateRequestsPerDayPerProject")

    assert is_requests_per_day_error(error) is True


def test_requests_per_day_error_detects_structured_quota_metric():
    error = SimpleNamespace(
        details=[
            {
                "violations": [
                    {
                        "quotaMetric": "generativelanguage.googleapis.com/generate_content_requests_per_day",
                        "quotaDimensions": {"model": "gemini-2.5-flash"},
                    }
                ]
            }
        ]
    )

    assert is_requests_per_day_error(error) is True


def test_requests_per_day_error_rejects_rpm_tpm_and_free_tier():
    assert is_requests_per_day_error(RuntimeError("429 RequestsPerMinute free_tier")) is False
    assert is_requests_per_day_error(RuntimeError("429 TokensPerMinute")) is False
    assert is_requests_per_day_error(RuntimeError("429 RESOURCE_EXHAUSTED free_tier")) is False
