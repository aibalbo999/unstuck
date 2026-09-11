"""Compare explicit DCF claims with the same method, unit and scenario."""

from __future__ import annotations

import re

from quant_input_contract import finite_number
from quant_metric_contract import CONTRACT_VERSION, DCF_METHOD, trusted_dcf_scenarios
from validators import strip_generated_audit_sections

SCENARIO_LABELS = {"bear": "熊市情境", "base": "基本情境", "bull": "牛市情境"}


def dcf_conflict_warnings(analyses, data, structured_outputs=None):
    """Compatibility facade; publication callers use findings for severity routing."""
    return [finding["message"] for finding in dcf_audit_findings(analyses, data, structured_outputs)]


def dcf_audit_findings(analyses, data, structured_outputs=None, valuation_agent=4):
    quant = data.get("quant_metrics") if isinstance(data, dict) else {}
    quant = quant if isinstance(quant, dict) else {}
    canonical = trusted_dcf_scenarios(quant)
    outputs = structured_outputs if isinstance(structured_outputs, dict) else {}
    structured = outputs.get(valuation_agent, outputs.get(str(valuation_agent), {}))
    structured = structured if isinstance(structured, dict) else {}
    text = strip_generated_audit_sections(str((analyses or {}).get(valuation_agent, (analyses or {}).get(str(valuation_agent), ""))))
    claims = _structured_claims(structured)
    # Only an explicit local DCF price is a prose claim; unrelated target prices are never read.
    prose = _explicit_prose_claims(text)
    claims.extend(prose)
    findings = []
    for row in claims:
        scenario = row["scenario"]
        value = row["intrinsic_value"]
        method, unit = row["method"], row["unit"]
        target = canonical.get(scenario)
        base = {"agent": valuation_agent, "scenario": scenario, "method": method, "unit": unit,
                "claimed_value": value, "canonical_value": target["intrinsic_value"] if target else None}
        label = SCENARIO_LABELS.get(scenario, "未指明情境")
        if not _method_matches(row, quant) or unit != "twd_per_share":
            findings.append({**base, "severity": "critical", "code": "dcf_unverified_method",
                "message": f"DCF 方法未驗證（{label}）：Agent {valuation_agent} 的方法或單位缺少同口徑、可重現工具來源；正規化名稱不能作為證據。"})
        elif scenario is None and canonical:
            findings.append({**base, "severity": "warning", "code": "dcf_scenario_unspecified",
                "message": f"DCF 情境未指明：Agent {valuation_agent} 的每股值 NT${value:g} 無法對應同一情境，未完成數值核驗。"})
        elif target is None:
            # Old unversioned numerical annotations are not upgraded to a canonical claim.
            if quant.get("contract_version") != CONTRACT_VERSION and not row.get("explicit_system_claim"):
                continue
            findings.append({**base, "severity": "critical", "code": "dcf_unavailable_claim",
                "message": f"DCF 來源不可用（{label}）：Agent {valuation_agent} 聲稱系統 DCF NT${value:g}，但該情境沒有可信計算來源；須移除不實來源主張。"})
        else:
            reference = target["intrinsic_value"]
            if abs(value - reference) / max(value, reference) > 0.30:
                findings.append({**base, "severity": "warning", "code": "dcf_source_mismatch",
                    "message": f"DCF 來源衝突（{label}）：Agent {valuation_agent} DCF NT${value:g} 與系統情境 DCF NT${reference:g} 差距超過 30%，應說明假設差異。"})
    return list({(row["agent"], row["code"], row["scenario"], row["claimed_value"]): row for row in findings}.values())


def _method_matches(row, quant):
    scenario = row["scenario"]
    source = row.get("source_ref")
    valid_sources = {f"quant_metrics.dcf_scenarios.{scenario}", f"data.quant_metrics.dcf_scenarios.{scenario}",
                     f"deterministic_financial_tool_results.calculations.dcf_scenarios_default.scenarios.{scenario}"}
    if source and (not isinstance(source, str) or source not in valid_sources):
        return False
    if row["method"] == DCF_METHOD:
        return True
    if row["method"] != "normalized_dcf" or not isinstance(source, str) or source not in valid_sources:
        return False
    provenance = quant.get("input_provenance", {})
    assumptions = quant.get("assumptions")
    assumptions = assumptions.get("dcf", {}) if isinstance(assumptions, dict) else {}
    assumptions = assumptions if isinstance(assumptions, dict) else {}
    return (bool(trusted_dcf_scenarios(quant).get(scenario))
            and all(isinstance(provenance.get(key), dict) and finite_number(provenance[key].get("value")) is not None
                    for key in ("normalization_net_income", "normalization_fcf"))
            and str(assumptions.get("base_fcf_note", "")).startswith("normalized to 80%"))


def _structured_claims(structured):
    raw = structured.get("dcf_scenarios")
    if isinstance(raw, dict):
        raw = [{"scenario": name, **value} if isinstance(value, dict)
               else {"scenario": name, "intrinsic_value": value} for name, value in raw.items()]
    if not isinstance(raw, list):
        return []
    claims = []
    for row in raw:
        if not isinstance(row, dict) or row.get("scenario") not in SCENARIO_LABELS:
            continue
        value = finite_number(row.get("intrinsic_value", row.get("price_per_share_twd")))
        if value is None or value <= 0:
            continue
        # DcfScenarioOutput defines intrinsic_value as a per-share DCF result.
        claims.append({**row, "intrinsic_value": value, "method": row.get("method", DCF_METHOD),
                       "unit": row.get("unit", "twd_per_share"),
                       "explicit_system_claim": row.get("method") == DCF_METHOD or str(row.get("source_ref", "")).startswith("quant_metrics.")})
    return claims


def _explicit_prose_claims(text):
    claims = []
    for sentence in re.split(r"[\n。；;]", text):
        if "DCF" not in sentence.upper() or re.search(r"不可用|不採用|不適用|無法|未驗證|資料不足|不作|not available|unavailable", sentence, re.I):
            continue
        # The currency amount must follow the DCF term within this sentence.
        tail = re.split(r"DCF", sentence, maxsplit=1, flags=re.I)[-1]
        match = re.search(r"(?:NT\$\s*(?P<prefix>\d[\d,]*(?:\.\d+)?)|(?P<suffix>\d[\d,]*(?:\.\d+)?)\s*(?:元|TWD))", tail, re.I)
        if match is None:
            continue
        if re.search(r"相對|P/E|P/B|倍數|市價|收盤", tail[:match.start()], re.I):
            continue
        scenario = next((key for key, pattern in (("bear", r"熊|悲觀|bear"), ("base", r"基本|基準|base"), ("bull", r"牛|樂觀|bull")) if re.search(pattern, sentence, re.I)), None)
        claims.append({"scenario": scenario, "intrinsic_value": float((match.group("prefix") or match.group("suffix")).replace(",", "")),
                       "method": "normalized_dcf" if re.search(r"正規化|normalized", sentence, re.I) else DCF_METHOD,
                       "unit": "twd_per_share", "explicit_system_claim": "系統" in sentence or "quant_metrics" in sentence})
    return claims
