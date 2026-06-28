"""Deterministic sampled evidence checks for rendered reports."""

from __future__ import annotations

import math
import re
from random import Random
from typing import Any


_KV_RE = re.compile(
    r"(?P<label>[\u4e00-\u9fffA-Za-z][^:\n：|]{0,30})[:：]\s*[~約]?(?:NT\$|\$)?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>%|x|X|倍|億|B|M|T|元|TWD)?"
)
_TABLE_CELL_RE = re.compile(r"\|\s*(?P<label>[^|\n]{1,30})\s*\|\s*[~約]?(?:NT\$|\$)?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>%|x|X|倍|億|B|M|T|元|TWD)?\s*\|")
_NUMBER_IN_STRING_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def extract_numeric_claims(markdown: str) -> list[dict[str, Any]]:
    """Extract labelled numeric claims from rendered Markdown."""
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, float, int]] = set()
    in_code = False
    for line_number, raw_line in enumerate(str(markdown or "").splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith("#"):
            continue
        for match in list(_KV_RE.finditer(line)) + list(_TABLE_CELL_RE.finditer(line)):
            label = _clean_label(match.group("label"))
            number = _clean_number(match.group("num"))
            if not label or number is None or not _valid_claim_number(number):
                continue
            key = (label, round(number, 6), line_number)
            if key in seen:
                continue
            seen.add(key)
            claims.append({
                "id": len(claims) + 1,
                "label": label,
                "reported_value": number,
                "unit": (match.group("unit") or "").strip(),
                "line_number": line_number,
                "raw_text": line[:160],
            })
    return claims


def evaluate_report_evidence(
    markdown: str,
    snapshot: dict[str, Any],
    *,
    sample_ratio: float = 0.15,
    min_sample: int = 3,
    max_sample: int = 30,
    tolerance_pct: float = 1.0,
    seed: int = 17,
) -> dict[str, Any]:
    """Sample report numeric claims and verify them against snapshot values."""
    claims = extract_numeric_claims(markdown)
    sample = sample_numeric_claims(claims, sample_ratio=sample_ratio, min_sample=min_sample, max_sample=max_sample, seed=seed)
    snapshot_values = flatten_snapshot_numbers(snapshot)
    checked = [_check_claim(claim, snapshot_values, tolerance_pct=tolerance_pct) for claim in sample]
    failed_count = sum(1 for item in checked if item["status"] != "verified")
    if not checked:
        verdict = "caution"
        summary = "報告中未抽取到足夠可核驗數字。"
    else:
        failure_rate = failed_count / len(checked)
        if failed_count == 0:
            verdict = "approved"
            summary = "抽樣數字均可在資料快照中找到對應值。"
        elif failure_rate >= 0.5:
            verdict = "rejected"
            summary = "超過半數抽樣數字無法對上資料快照。"
        else:
            verdict = "caution"
            summary = "部分抽樣數字無法對上資料快照，需人工確認。"
    return {
        "schema_version": 1,
        "verdict": verdict,
        "summary": summary,
        "claim_count": len(claims),
        "sampled_count": len(checked),
        "failed_count": failed_count,
        "tolerance_pct": tolerance_pct,
        "sampled_claims": checked,
    }


def sample_numeric_claims(
    claims: list[dict[str, Any]],
    *,
    sample_ratio: float = 0.15,
    min_sample: int = 3,
    max_sample: int = 30,
    seed: int = 17,
) -> list[dict[str, Any]]:
    if not claims:
        return []
    sample_size = max(min_sample, math.ceil(len(claims) * max(sample_ratio, 0.0)))
    sample_size = min(max_sample, len(claims), sample_size)
    if sample_size >= len(claims):
        return list(claims)
    sampled = Random(seed).sample(claims, sample_size)
    return sorted(sampled, key=lambda item: int(item.get("line_number") or 0))


def flatten_snapshot_numbers(snapshot: Any) -> list[dict[str, Any]]:
    """Collect numeric values from a sanitized snapshot."""
    values: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            if _valid_claim_number(float(value)):
                values.append({"path": path, "value": float(value)})
            return
        if isinstance(value, str):
            for match in _NUMBER_IN_STRING_RE.finditer(value):
                number = _clean_number(match.group(0))
                if number is not None and _valid_claim_number(number):
                    values.append({"path": path, "value": number})
            return
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(snapshot, "")
    return values


def _check_claim(claim: dict[str, Any], snapshot_values: list[dict[str, Any]], *, tolerance_pct: float) -> dict[str, Any]:
    reported = float(claim.get("reported_value") or 0)
    best = _best_match(reported, snapshot_values)
    if best and best["diff_pct"] <= tolerance_pct:
        status = "verified"
    else:
        status = "mismatch"
    return {
        **claim,
        "status": status,
        "matched_path": best.get("path") if best else "",
        "matched_value": best.get("value") if best else None,
        "diff_pct": round(best.get("diff_pct", 0.0), 4) if best else None,
    }


def _best_match(reported: float, snapshot_values: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for item in snapshot_values:
        candidate = float(item["value"])
        if reported == 0:
            diff_pct = 0.0 if candidate == 0 else 100.0
        else:
            diff_pct = abs(candidate - reported) / abs(reported) * 100
        if best is None or diff_pct < best["diff_pct"]:
            best = {"path": item["path"], "value": candidate, "diff_pct": diff_pct}
    return best


def _clean_label(value: str) -> str:
    label = re.sub(r"^[\-\*\s|]+", "", str(value or ""))
    label = re.sub(r"[\*_`]+", "", label).strip()
    if len(label) < 2:
        return ""
    if re.fullmatch(r"\d{4}|Q[1-4]|\d+", label):
        return ""
    return label[:40]


def _clean_number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _valid_claim_number(value: float) -> bool:
    return math.isfinite(value) and abs(value) < 1e15
