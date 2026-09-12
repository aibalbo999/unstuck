"""Conservative evidence payloads used when financial model output is invalid."""

from __future__ import annotations

from typing import Any


def financial_evidence_fallback(
    agent_num: int,
    data: Any,
    context: dict,
) -> dict[str, Any]:
    labels = {
        2: "財務品質",
        13: "財務排雷",
        18: "法證財務與資金流",
    }
    label = labels[agent_num]
    data_map = data if isinstance(data, dict) else {}
    ticker = data_map.get("ticker", context.get("ticker", "N/A"))
    company = data_map.get("company_name", context.get("company_name", "N/A"))
    trust = data_map.get("data_trust", {})
    trust_status = trust.get("status", "unknown") if isinstance(trust, dict) else "unknown"
    as_of_date = str(
        data_map.get("fetch_date")
        or data_map.get("as_of_date")
        or "資料時點未提供"
    )
    return {
        "as_of_date": as_of_date,
        "confidence": (
            "low" if trust_status in {"fresh", "partial", "stale"} else "unassessed"
        ),
        "evidence_items": [{
            "finding": f"{label}模型輸出不可用，僅能確認目前資料可信度狀態，不能補造財務數字。",
            "source_refs": ["data_trust"],
            "freshness_note": f"data_trust={trust_status}；資料時點 {as_of_date}。",
            "counterevidence": "缺少可解析的模型證據備忘錄，需等待後續完整財務資料重新驗證。",
        }],
        "analysis_markdown": (
            f"## {label}（保守口徑）\n\n"
            f"標的：{ticker} {company}\n\n"
            "本次未取得可解析且可追溯的模型輸出，因此不引用任何未驗證數字，"
            "也不提出估值、目標價或投資建議。"
        ),
    }


__all__ = ["financial_evidence_fallback"]
