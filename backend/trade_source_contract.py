"""Mode-D completion and references tied to complete, visible prompt evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from short_term_market_data import build_short_term_market_context

TEXT_FIELDS = ("trade_direction", "entry_zone", "target_price", "stop_loss",
               "support_level", "resistance_level", "core_catalyst", "risk_level")
REF_FIELDS = ("support_source_refs", "resistance_source_refs", "catalyst_source_refs")
CONTRACT_VERSION = "trade-sources:v3"
SUPPORTED_VERSIONS = {"trade-sources:v1", "trade-sources:v2", CONTRACT_VERSION}
# Price/volume observations cannot establish who traded or ownership changes.
_INSTITUTIONAL_CATALYST = re.compile(r"外資|投信|自營商|法人(?!說明會)|大戶|持股|買超|賣超|籌碼|foreign\s+investor|institutional|ownership", re.I)


def trade_json_incomplete(raw_text):
    """Permit a missing final root brace, never invent a cut string/list/object."""
    text = str(raw_text or "")
    start = text.find("{")
    if start < 0:
        return True
    quoted, escaped = None, False
    stack = []
    for character in text[start:]:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quoted:
                quoted = None
        elif character in ('"', "'", "“", "‘"):
            quoted = {"“": "”", "‘": "’"}.get(character, character)
        elif character in "{[":
            stack.append(character)
        elif character in "}]":
            if not stack or stack.pop() != ("{" if character == "}" else "["):
                return True
            if not stack:
                return False
    return quoted or stack != ["{"]


def missing_trade_fields(payload, *, context=None):
    if not isinstance(payload, dict):
        return list(TEXT_FIELDS + REF_FIELDS)
    missing = [key for key in TEXT_FIELDS if not isinstance(payload.get(key), str) or not payload[key].strip()] + [
        key for key in REF_FIELDS if not isinstance(payload.get(key), list)
    ]
    manifest = context.get("_trade_source_manifest") if isinstance(context, dict) else None
    if isinstance(manifest, dict) and manifest.get("version") == CONTRACT_VERSION:
        from trade_catalyst_semantics import SEMANTIC_FIELDS
        missing.extend(key for key in SEMANTIC_FIELDS if key not in payload)
    return missing


def source_catalog(data):
    # Use the existing pure projection; no provider calls, invented events or prices.
    from trade_catalog_evidence import add_catalog_observations
    value = add_catalog_observations(build_short_term_market_context(data, compact=True), data)
    return {"short_term_market_context": value}


def allowed_source_refs(catalog):
    """The prompt and repair admission use the same actually usable references."""
    paths = []
    def walk(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, path + "." + key if path else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, path + "[" + str(index) + "]")
                if isinstance(item, dict):
                    paths.append(path + "[" + str(index) + "]")
        else:
            paths.append(path)
    walk(catalog, "")
    return {role: [path for path in paths if reference_is_evidence(catalog, path, role)] for role in REF_FIELDS}


def source_block(data):
    catalog = source_catalog(data)
    encoded = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    allowed = allowed_source_refs(catalog)
    from trade_source_guidance import source_guidance_text
    text = ("【trade-source:" + fingerprint + "】\n" + encoded +
            "\n可引用路徑：" + json.dumps(allowed, ensure_ascii=False, separators=(",", ":")) +
            source_guidance_text(catalog) + "\n【/trade-source】\n來源引用只使用以上完整區塊中實際存在且非空的 short_term_market_context 路徑；"
            "不得自行補造路徑。三組 source_refs 均須輸出。Long/Short 缺少支撐、壓力或催化證據時明示資料限制，"
            "K 線與均線只支持價格與技術條件；RSI、MACD、量能只能作技術催化，不能作價格支撐壓力。"
            "法人主張須引用 institutional_evidence 中對應單位、統計主體、期間的完整record，不能以合計冒充外資；"
            "具體寫出主體、期間、觀測日、數值與單位；沒有對應record的『外資累積』或『法人買超』不可放進核心催化。"
            "Neutral 也必須遵守相同證據要求；技術觀望可只引用對應技術指標並列出重新評估條件。"
            "現況與未來條件分欄：observed_signal 只寫已觀測事實，observed_source_refs 逐項列其完整來源；"
            "recheck_condition 使用『等待…後再重新評估』表達純未來條件，不能混入已發生主張。"
            "event_catalyst 缺資料為 null；有資料時 description、date、end_date、timezone、status 和 source_refs "
            "必須對應同一完整 event_calendar record。來源沒有時區就用 null，scheduled 不得改成 confirmed；"
            "日期須落在日曆提供的已驗證範圍，新聞出版日不能當事件日。financial_risk_flags 由系統填入，模型輸出空陣列。"
            "以上 observed_signal、observed_source_refs、event_catalyst、recheck_condition、financial_risk_flags 五欄必須明示；未知用 null／空陣列，不可省略。"
            "event_calendar 整個物件及 availability 不可作催化引用；日曆缺資料只能說未知，known_empty只代表提供區間內無紀錄。"
            "recent_news 只支持逐字引用的新聞標題，請明示新聞報導並保留完整標題；出版日期不是未來事件日，不支持確定未來舉行的主張。未知或過期來源不可推定。"
            "core_catalyst 僅原文複述 observed_signal 或完整重新評估條件；財務警示與事件另欄，禁止加入新的無來源主張。"
            "Neutral 必須說明觀望及重新評估條件；禁止為通過檢查強迫方向。")
    return text, catalog, fingerprint


def bind_source_prompt(context, prompt, block, catalog, fingerprint):
    from workflow_trade_evidence import trade_input_fingerprint

    context["_trade_source_manifest"] = {
        "version": CONTRACT_VERSION, "visible": bool(block and block in prompt),
        "catalog": catalog if block and block in prompt else {},
        "fingerprint": fingerprint,
        "input_fingerprint": trade_input_fingerprint(context.get("data", {})),
    }


def resolve_reference(catalog, ref):
    if not isinstance(ref, str) or not re.fullmatch(r"short_term_market_context(?:\.[A-Za-z_][A-Za-z_0-9]*|\[\d+\])+", ref):
        return None
    value = catalog
    for key, index in re.findall(r"([A-Za-z_][A-Za-z_0-9]*)|\[(\d+)\]", ref):
        if key:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        else:
            if not isinstance(value, list) or int(index) >= len(value):
                return None
            value = value[int(index)]
    if value is None or value == "" or value == [] or value == {}:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str) and value.strip().lower() in {"n/a", "null", "unavailable", "unknown"}:
        return None
    return value


def reference_is_evidence(catalog, ref, role):
    value = resolve_reference(catalog, ref)
    if value is None:
        return False
    root = catalog.get("short_term_market_context", {})
    if ref.startswith("short_term_market_context.technical_indicators."):
        indicators = root.get("technical_indicators", {})
        field = ref.rsplit(".", 1)[-1]
        usable = (indicators.get("availability") in {"available", "partial"} and
                  bool(indicators.get("source")) and bool(indicators.get("as_of")) and
                  isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))
        if not usable:
            return False
        if re.fullmatch(r"(?:sma|ema)_\d+|atr_\d+|(?:high|low)_\d+d", field):
            return value > 0
        if role != "catalyst_source_refs":
            return False
        if field in {"macd", "macd_signal", "macd_histogram"}:
            return True  # Signed and zero differences are real observations.
        if field == "rsi_14":
            return 0 <= value <= 100
        if field == "volume_ratio_20":
            return value >= 0
        return field in {"volume_latest", "volume_sma_5", "volume_sma_20"} and value >= 0 and indicators.get("volume_unit") in {"shares", "lots"}
    if re.fullmatch(r"short_term_market_context.daily_market_data.bars\[\d+\](?:\.(?:high|low|close))?", ref):
        daily = root.get("daily_market_data", {})
        return (daily.get("availability") in {"available", "partial"} and bool(daily.get("source")) and
                bool(daily.get("as_of")) and
                (isinstance(value, dict) and bool(value.get("date")) or
                 isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0))
    if role == "catalyst_source_refs" and re.fullmatch(r"short_term_market_context.event_calendar.events\[\d+\]", ref):
        calendar = root.get("event_calendar", {})
        return (not {"event_source_failed", "event_source_date_future"}.intersection(calendar.get("reason_codes") or [])
                and isinstance(value, dict) and bool(value.get("date")) and bool(value.get("source")) and bool(value.get("label")))
    if role == "catalyst_source_refs" and re.fullmatch(r"short_term_market_context.institutional_evidence.records\[\d+\]", ref):
        return (isinstance(value, dict) and value.get("unit") in {"shares", "thousand_shares"}
                and bool(value.get("population")) and bool(value.get("window"))
                and bool(value.get("observed_at")) and bool(value.get("provider"))
                and isinstance(value.get("value"), (int, float)) and not isinstance(value.get("value"), bool)
                and math.isfinite(value["value"]))
    if role == "catalyst_source_refs" and re.fullmatch(r"short_term_market_context.ownership_evidence.records\[\d+\]", ref):
        return (isinstance(value, dict) and value.get("unit") == "percent" and bool(value.get("threshold"))
                and value.get("population") in {"major_holders", "retail_holders"}
                and bool(value.get("observed_at")) and bool(value.get("provider"))
                and isinstance(value.get("value"), (int, float)) and not isinstance(value.get("value"), bool)
                and 0 <= value["value"] <= 100)
    if role == "catalyst_source_refs" and re.fullmatch(r"short_term_market_context.recent_news.items\[\d+\]", ref):
        return (isinstance(value, dict) and value.get("evidence_role") == "reported_news_not_scheduled_event"
                and all(value.get(key) for key in ("title", "provider", "published_at", "url", "ticker")))
    return False


def bind_trade_payload(payload, context):
    """Check refs before normalization; never populate a missing model assertion."""
    result = dict(payload)
    from trade_catalyst_claims import catalyst_observation_text
    from trade_financial_risk import negative_fcf_value
    from trade_catalyst_semantics import trade_semantic_issues, optional_claim_text
    observation = catalyst_observation_text(payload.get("core_catalyst", ""), allow_policy_suffix=negative_fcf_value(context.get("data", {})) is not None)
    manifest = context.get("_trade_source_manifest")
    reasons = trade_semantic_issues(payload, context)
    bound = isinstance(manifest, dict) and manifest.get("version") in SUPPORTED_VERSIONS
    for key in REF_FIELDS:
        refs = payload.get(key)
        if bound:
            refs = refs if isinstance(refs, list) else []
            valid = [ref for ref in refs if reference_is_evidence(manifest.get("catalog", {}), ref, key)]
            if len(valid) != len(refs):
                reasons.append("invalid_" + key)
            # A surviving path cannot stand in for another unsupported assertion.
            # The existing normalizer makes the draft non-executable until repaired.
            result[key] = valid if len(valid) == len(refs) else []
        if payload.get("trade_direction") in {"Long", "Short"} and not result.get(key):
            reasons.append("missing_" + key)
    if bound and not manifest.get("visible"):
        reasons.append("source_block_not_visible")
    if bound:
        claim_issues = catalyst_claim_issues(observation, manifest.get("catalog", {}), result.get("catalyst_source_refs") or [])
        if claim_issues:
            reasons.extend(claim_issues)
            result["catalyst_source_refs"] = []
    observed = optional_claim_text(payload.get("observed_signal"))
    if observed:
        refs = payload.get("observed_source_refs")
        refs = refs if isinstance(refs, list) else []
        catalog = manifest.get("catalog", {}) if bound else {}
        valid = [ref for ref in refs if reference_is_evidence(catalog, ref, "catalyst_source_refs")]
        if not bound or not manifest.get("visible") or not valid or len(valid) != len(refs):
            reasons.append("invalid_observed_source_refs")
            result["observed_source_refs"] = []
        observed_issues = catalyst_claim_issues(observed, catalog, valid)
        if observed_issues:
            reasons.extend("observed_" + issue for issue in observed_issues)
            result["observed_source_refs"] = []
    # New semantic failures cannot leave an executable legacy reference set.
    if reasons:
        result["catalyst_source_refs"] = []
    if payload.get("trade_direction") in {"Long", "Short"} and any(
        payload.get(key, "").strip().upper() in {"N/A", "NA", "資料不足"} for key in ("entry_zone", "target_price", "stop_loss")
    ):
        reasons.append("missing_execution_prices")
    degraded = bool(reasons)
    status = "degraded" if degraded else "observation" if payload.get("trade_direction") == "Neutral" else "source_bound" if bound else "unknown"
    assessment = {"status": status, "reason_codes": list(dict.fromkeys(reasons)),
                  "original_direction": payload.get("trade_direction"),
                  "contract_version": CONTRACT_VERSION, "repair_attempted": bool(context.get("_trade_source_repair_attempted"))}
    if bound:
        assessment["source_fingerprint"] = manifest.get("fingerprint")
        if degraded:
            from trade_source_diagnostics import source_rejection_diagnostics
            assessment["rejection_diagnostics"] = source_rejection_diagnostics(payload, manifest, reasons, result, data=context.get("data", {}))
    return result, assessment


def catalyst_claim_issues(observation, catalog, refs):
    """The same scoped proof applies independently to old and new fact fields."""
    from trade_catalog_evidence import ownership_claim_supported, institutional_catalyst_has_numeric_claim, news_catalyst_supported
    from institutional_evidence import institutional_evidence_issues
    reasons = []
    if _INSTITUTIONAL_CATALYST.search(observation):
        institutional_refs = [ref for ref in refs if ".institutional_evidence.records[" in ref]
        issues = institutional_evidence_issues(observation, catalog, allowed_paths=institutional_refs)
        ownership_refs = [ref for ref in refs if ".ownership_evidence.records[" in ref]
        has_ownership = bool(re.search(r"大戶|散戶|持股|ownership", observation, re.I))
        has_flow = bool(re.search(r"外資|投信|自營商|法人(?!說明會)|買超|賣超|foreign|institutional", observation, re.I))
        ownership_ok = ownership_claim_supported(observation, [resolve_reference(catalog, ref) for ref in ownership_refs]) if has_ownership else True
        if (has_flow and (not institutional_refs or issues or not institutional_catalyst_has_numeric_claim(observation))) or not ownership_ok or (not has_flow and not has_ownership):
            reasons.append("catalyst_evidence_scope_mismatch")
    news_refs = [ref for ref in refs if ".recent_news.items[" in ref]
    if news_refs and not news_catalyst_supported(observation, [resolve_reference(catalog, ref) for ref in news_refs]):
        reasons.append("news_claim_scope_mismatch")
    return reasons
