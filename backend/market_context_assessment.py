"""Pure final-decision market assessment validation; no source fetching or repair."""

from __future__ import annotations

from market_context_manifest import CONTRACT_VERSION, SOURCE_FIELDS, available_source_count, manifest_matches_input, market_input_fingerprint

_LABELS = {"global_market_context": "全球市場脈絡", "international_news_context": "國際新聞脈絡"}
_REASONS = {"source_unavailable": "此次沒有可用來源，未納入結論評估。",
            "prompt_omitted": "來源存在，但此次提示內容未完整保留來源區塊，未評估。",
            "assessment_missing": "可見來源尚未完成具體評估。",
            "source_reference_invalid": "來源引用無法綁定此次完整可見的輸入，不能視為可信評估。"}


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def _agent_value(values, agent):
    values = _mapping(values)
    return values.get(agent, values.get(str(agent)))


def _reason(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def assess_final_market_context(context: dict) -> dict:
    result = {"status": "not_recorded", "assessment": None, "warnings": [], "critical": [],
              "repair_agent_issues": {}, "coverage_repair_agent_issues": {}, "checks": []}
    pipeline = context.get("pipeline_id", context.get("pipeline", "v1"))
    agent = {"v1": 7, "v2": 16, "v3": 19}.get(pipeline)
    if agent is None:
        result["status"] = "not_applicable"
        return result
    if context.get("market_context_contract_version") != CONTRACT_VERSION:
        return result
    data = _mapping(context.get("data"))
    manifest = _agent_value(context.get("market_context_manifests"), agent)
    output = _agent_value(context.get("structured_outputs"), agent)
    # Current output is authoritative, even when its assessment is absent.
    # A display projection is NEVER raw evidence, even after size governance removes outputs.
    raw = _mapping(output).get("market_context_assessment") if output is not None else context.get("market_context_raw_assessment")
    from market_context_snapshot import snapshot_manifest_matches_input

    original_input = context.get("market_context_original_input_fingerprint")
    input_preserved = original_input is None or original_input == market_input_fingerprint(data)
    trusted_manifest = ((input_preserved and manifest_matches_input(manifest, data, agent))
                        or snapshot_manifest_matches_input(context, manifest, data, raw, agent))
    assessment = _mapping(raw)
    result["assessment"] = {}
    for source, label in _LABELS.items():
        item = _mapping(assessment.get(source))
        impact, reason, refs = item.get("impact"), _reason(item.get("reason")), item.get("source_refs")
        refs_valid_shape = isinstance(refs, list) and all(isinstance(ref, str) for ref in refs)
        info = _mapping(_mapping(manifest).get("sources")).get(source, {}) if trusted_manifest else {}
        visible = info.get("visible_refs", [])
        source_absent = available_source_count(data, source) == 0
        claimed = isinstance(impact, str) and impact in {"affects_conclusion", "no_material_impact"}
        forged = (bool(refs) and (not refs_valid_shape or any(ref not in visible for ref in refs)))
        invalid_claim = forged or (claimed and not trusted_manifest) or (claimed and not visible and bool(reason))
        code = ""
        if invalid_claim:
            code = "source_reference_invalid"
            message = f"Agent {agent} {label}：{_REASONS[code]}"
            result["critical"].append(message)
            result["repair_agent_issues"].setdefault(agent, []).append(message)
        elif source_absent or (trusted_manifest and not visible):
            code = "source_unavailable" if source_absent else "prompt_omitted"
        elif not (claimed and refs_valid_shape and refs and reason and reason not in {*SOURCE_FIELDS, *_LABELS.values(), "N/A", "未評估"}):
            code = "assessment_missing"
            result["coverage_repair_agent_issues"].setdefault(agent, []).append(
                f"{label}：請按完整可見來源提供 impact、具體 reason 與有效 source_refs；不得補造引用。")
        if code:
            if code != "source_reference_invalid":
                result["warnings"].append(f"{label}：{_REASONS[code]}")
            projection = {"impact": "not_assessed", "reason": _REASONS[code], "source_refs": [], "reason_code": code}
        else:
            projection = {"impact": impact, "reason": reason, "source_refs": list(refs)}
        result["assessment"][source] = projection
        result["checks"].append({"source": source, "status": "critical" if invalid_claim else "warning" if code else "passed",
                                 "reason_code": code, "visible_source_count": len(visible)})
    result["status"] = "critical" if result["critical"] else "warning" if result["warnings"] else "passed"
    return result


def market_assessment_text(assessment) -> str:
    """Shared report text for explicit assessments, including legacy absence."""
    if assessment is None:
        return "\n\n### 市場與新聞評估\n- 評估狀態：未記錄。"
    labels = {"affects_conclusion": "影響本次結論", "no_material_impact": "未實質改變結論", "not_assessed": "未評估"}
    lines = ["\n\n### 市場與新聞評估"]
    for source, label in _LABELS.items():
        item = _mapping(_mapping(assessment).get(source))
        raw_impact = item.get("impact")
        impact = labels.get(raw_impact, "未記錄") if isinstance(raw_impact, str) else "未記錄"
        reason = _reason(item.get("reason")).replace("\n", " ") or "未記錄具體理由。"
        lines.append(f"- {label}：{impact}。{reason}")
        refs = item.get("source_refs")
        if isinstance(refs, list) and refs:
            lines.append("  來源項目：" + "、".join(str(ref) for ref in refs))
    return "\n".join(lines)
