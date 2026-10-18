"""Official annual listed/OTC issuer occupational-safety disclosures."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
import re
from zoneinfo import ZoneInfo

URLS = {
    ".TW": "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_21",
    ".TWO": "https://www.tpex.org.tw/openapi/v1/t187ap46_O_21",
}
PROVIDER = "TWSE/TPEx annual ESG occupational safety OpenAPI"
MAX_BYTES = 2_000_000
NUMBER = re.compile(r"(?:0|[1-9]\d*)(?:\.\d+)?")
COUNT_FIELDS = {
    "occupational_injury_count": "職業災害人數及比率-人數",
    "fire_incident_count": "火災件數(件)",
    "fire_casualty_count": "火災死傷人數(人)",
}
PERCENT_FIELDS = {
    "occupational_injury_rate_percent": "職業災害人數及比率-比率",
    "fire_casualty_rate_percent": "火災死傷人數占員工總人數比率",
}


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def _number(value: object, *, percent: bool = False, integer: bool = False):
    raw = str(value if value is not None else "").strip().replace(",", "")
    if percent and raw.endswith("%"):
        raw = raw[:-1].strip()
    if raw.upper() in {"", "N/A", "NA", "-", "—", "–"}:
        return None
    if not NUMBER.fullmatch(raw):
        raise ValueError("invalid numeric disclosure")
    try:
        parsed = Decimal(raw)
    except InvalidOperation:
        raise ValueError("invalid numeric disclosure") from None
    if not parsed.is_finite() or parsed < 0 or (percent and parsed > 100):
        raise ValueError("numeric disclosure outside permitted range")
    if integer and parsed != parsed.to_integral_value():
        raise ValueError("count disclosure must be an integer")
    result = int(parsed) if integer or parsed == parsed.to_integral_value() else float(parsed)
    if isinstance(result, float) and not math.isfinite(result):
        raise ValueError("non-finite disclosure")
    return result


def parse_occupational_safety_dataset(raw: bytes | str, ticker: str, *, today: date | None = None) -> dict | None:
    """Select a current-year exact-issuer row; blank metrics remain unknown."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        return None
    ticker = str(ticker or "").strip().upper()
    suffix = ".TWO" if ticker.endswith(".TWO") else ".TW" if ticker.endswith(".TW") else ""
    if not suffix or not re.fullmatch(r"\d{4,6}", ticker[:-len(suffix)]):
        return None
    try:
        rows = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(rows, list) or not 0 < len(rows) <= 5000:
        return None
    matches = [row for row in rows if isinstance(row, dict)
               and str(row.get("公司代號") or "").strip() == ticker[:-len(suffix)]]
    if len(matches) != 1:
        return None
    row = {str(key).strip(): value for key, value in matches[0].items()}
    name = str(row.get("公司名稱") or "").strip()
    report = str(row.get("報告年度") or "").strip()
    published = str(row.get("出表日期") or "").strip()
    if not name or not re.fullmatch(r"\d{3}", report) or not re.fullmatch(r"\d{7}", published):
        return None
    report_year = int(report) + 1911
    try:
        published_on = date(int(published[:3]) + 1911, int(published[3:5]), int(published[5:]))
    except ValueError:
        return None
    current = today or _today()
    if (not current.year - 2 <= report_year <= current.year
            or not date(report_year, 12, 31) < published_on <= current):
        return None
    metrics = {}
    try:
        metrics.update({key: _number(row.get(field), integer=True) for key, field in COUNT_FIELDS.items()})
        metrics.update({key: _number(row.get(field), percent=True) for key, field in PERCENT_FIELDS.items()})
    except ValueError:
        return None
    available = sum(value is not None for value in metrics.values())
    if not available:
        return None
    return {
        "ticker": ticker,
        "official_company_name": name,
        "report_year": report_year,
        "published_on": published_on.isoformat(),
        "metrics": metrics,
        "available_metric_count": available,
        "missing_metric_fields": [key for key, value in metrics.items() if value is None],
        "observation_kind": "annual_esg_occupational_safety_disclosure",
        "response_sha256": sha256(raw).hexdigest(),
        "source_url": URLS[suffix],
        "source": PROVIDER,
        "coverage_status": "partial" if available < len(metrics) else "complete",
    }


def verified_occupational_safety_observation(value: object, ticker: str, *, today: date | None = None) -> bool:
    if not isinstance(value, dict):
        return False
    ticker = str(ticker or "").strip().upper()
    suffix = ".TWO" if ticker.endswith(".TWO") else ".TW" if ticker.endswith(".TW") else ""
    if (not suffix or not re.fullmatch(r"\d{4,6}\.(?:TW|TWO)", ticker) or value.get("ticker") != ticker
            or value.get("observation_kind") != "annual_esg_occupational_safety_disclosure"
            or value.get("source") != PROVIDER or value.get("source_url") != URLS[suffix]
            or value.get("status") not in {"success", "partial", "stale"}
            or not isinstance(value.get("official_company_name"), str) or not value["official_company_name"].strip()
            or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("response_sha256") or ""))):
        return False
    year, published = value.get("report_year"), value.get("published_on")
    if type(year) is not int:
        return False
    try:
        published_on = date.fromisoformat(published)
        current = today or _today()
        if not current.year - 2 <= year <= current.year or not date(year, 12, 31) < published_on <= current:
            return False
    except (ValueError, TypeError):
        return False
    metrics = value.get("metrics")
    if not isinstance(metrics, dict):
        return False
    available = 0
    for field in (*COUNT_FIELDS, *PERCENT_FIELDS):
        number = metrics.get(field)
        if number is None:
            continue
        if (isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number)
                or number < 0 or field in COUNT_FIELDS and type(number) is not int
                or field in PERCENT_FIELDS and number > 100):
            return False
        available += 1
    return (available > 0 and type(value.get("available_metric_count")) is int
            and value.get("available_metric_count") == available)
