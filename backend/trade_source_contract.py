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
CONTRACT_VERSION = "trade-sources:v1"
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


def missing_trade_fields(payload):
    if not isinstance(payload, dict):
        return list(TEXT_FIELDS + REF_FIELDS)
    return [key for key in TEXT_FIELDS if not isinstance(payload.get(key), str) or not payload[key].strip()] + [
        key for key in REF_FIELDS if not isinstance(payload.get(key), list)
    ]


def source_catalog(data):
    # Use the existing pure projection; no provider calls, invented events or prices.
    value = build_short_term_market_context(data, compact=True)
    return {"short_term_market_context": value}


def source_block(data):
    catalog = source_catalog(data)
    encoded = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
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
    allowed = {role: [path for path in paths if reference_is_evidence(catalog, path, role)] for role in REF_FIELDS}
    text = ("【trade-source:" + fingerprint + "】\n" + encoded +
            "\n可引用路徑：" + json.dumps(allowed, ensure_ascii=False, separators=(",", ":")) +
            "\n【/trade-source】\n來源引用只使用以上完整區塊中實際存在且非空的 short_term_market_context 路徑；"
            "不得自行補造路徑。三組 source_refs 均須輸出。Long/Short 缺少支撐、壓力或催化證據時明示資料限制，"
            "K 線與均線只能支持價格、成交量與技術條件，不能支持外資、法人、大戶買賣或持股主張；"
            "core_catalyst 必須使用引用本身可支持的條件，其他未有對應來源的主張不可冒充催化證據。"
            "Neutral 必須說明觀望及重新評估條件；禁止為通過檢查強迫方向。")
    return text, catalog, fingerprint


def bind_source_prompt(context, prompt, block, catalog, fingerprint):
    context["_trade_source_manifest"] = {
        "version": CONTRACT_VERSION, "visible": bool(block and block in prompt),
        "catalog": catalog if block and block in prompt else {},
        "fingerprint": fingerprint,
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
        if not re.fullmatch(r"(?:sma|ema)_\d+|atr_\d+|(?:high|low)_\d+d", field):
            return False
        return (indicators.get("availability") in {"available", "partial"} and
                bool(indicators.get("source")) and bool(indicators.get("as_of")) and
                isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0)
    if re.fullmatch(r"short_term_market_context.daily_market_data.bars\[\d+\](?:\.(?:high|low|close))?", ref):
        daily = root.get("daily_market_data", {})
        return (daily.get("availability") in {"available", "partial"} and bool(daily.get("source")) and
                bool(daily.get("as_of")) and
                (isinstance(value, dict) and bool(value.get("date")) or
                 isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0))
    if role == "catalyst_source_refs" and re.fullmatch(r"short_term_market_context.event_calendar.events\[\d+\]", ref):
        return isinstance(value, dict) and bool(value.get("date")) and bool(value.get("source")) and bool(value.get("label"))
    return False


def bind_trade_payload(payload, context):
    """Check refs before normalization; never populate a missing model assertion."""
    result = dict(payload)
    manifest = context.get("_trade_source_manifest")
    reasons = []
    bound = isinstance(manifest, dict) and manifest.get("version") == CONTRACT_VERSION
    for key in REF_FIELDS:
        refs = payload.get(key)
        if bound:
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
    if bound and payload.get("trade_direction") in {"Long", "Short"} and _INSTITUTIONAL_CATALYST.search(payload.get("core_catalyst", "")):
        # This bounded catalog has no institutional-flow/ownership records.
        reasons.append("catalyst_evidence_scope_mismatch")
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
    return result, assessment
