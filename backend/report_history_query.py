"""Query filter normalization for report history listings."""

from __future__ import annotations

from recommendation_labels import normalize_recommendation_label


PIPELINE_ALIASES = {
    "mode_a": "v1",
    "a": "v1",
    "academic": "v1",
    "mode_b": "v2",
    "b": "v2",
    "trading": "v2",
    "mode_c": "v3",
    "c": "v3",
    "contrarian": "v3",
    "bubble": "v3",
    "short": "v3",
    "mode_d": "v4",
    "d": "v4",
    "swing": "v4",
    "short_term": "v4",
    "short-term": "v4",
    "momentum": "v4",
}
VALID_PIPELINES = {"all", "v1", "v2", "v3", "v4"}
VALID_RECOMMENDATIONS = {"買入", "持有", "避免", "放空"}
VALID_DATA_TRUST = {"all", "fresh", "partial", "stale", "error", "unknown"}


def normalize_include_versions(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def normalize_report_list_filters(
    *,
    q: str,
    pipeline: str,
    recommendation: str,
    data_trust,
    include_versions,
) -> dict:
    pipeline_filter = PIPELINE_ALIASES.get(pipeline.strip().lower(), pipeline.strip().lower())
    if pipeline_filter not in VALID_PIPELINES:
        pipeline_filter = "all"

    recommendation_filter = normalize_recommendation_label(recommendation)
    if recommendation_filter not in VALID_RECOMMENDATIONS:
        recommendation_filter = "all"

    data_trust_value = data_trust if isinstance(data_trust, str) else "all"
    data_trust_filter = data_trust_value.strip().lower()
    if data_trust_filter not in VALID_DATA_TRUST:
        data_trust_filter = "all"

    return {
        "query": q.strip().lower(),
        "pipeline": pipeline_filter,
        "recommendation": recommendation_filter,
        "data_trust": data_trust_filter,
        "include_versions": normalize_include_versions(include_versions),
    }
