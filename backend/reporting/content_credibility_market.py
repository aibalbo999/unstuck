"""Read-only market-source credibility uses the same current validator as report text."""

from market_context_assessment import assess_final_market_context


def evaluate_market_context_credibility(context: dict, snapshot: dict, data: dict, pipeline: str) -> dict:
    current = assess_final_market_context({**snapshot, **context, "data": data, "pipeline_id": pipeline})
    result = {"blocking_issues": [], "warnings": [], "checks": []}
    if current["status"] in {"not_recorded", "not_applicable"}:
        return result
    status = "blocked" if current["critical"] else current["status"]
    for field, messages in (("blocking_issues", current["critical"]), ("warnings", current["warnings"])):
        result[field] = [{"id": "market_context_assessment", "message": message, "details": current}
                         for message in messages]
    result["checks"] = [{"id": "market_context_assessment", "status": status,
                         "message": "市場與新聞來源採目前保存資料重新驗證。", "details": current}]
    return result
