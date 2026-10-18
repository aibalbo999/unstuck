"""Annual TWSE/TPEx workforce disclosures, independent of current job counts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
import re
from zoneinfo import ZoneInfo

from external_http_client import sync_get
from shared_provider_cache import shared_fetch

from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult


URLS = {
    ".TW": "https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5",
    ".TWO": "https://www.tpex.org.tw/openapi/v1/t187ap46_O_5",
}
MAX_BYTES = 2_000_000
PROVIDER = "TWSE/TPEx annual workforce OpenAPI"
_NUMBER = re.compile(r"(?:0|[1-9]\d*)(?:\.\d+)?")


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def _number(value: object, *, percent: bool = False) -> float | int | None:
    raw = str(value if value is not None else "").strip().replace(",", "")
    if percent and raw.endswith("%"):
        raw = raw[:-1]
    if not _NUMBER.fullmatch(raw):
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or (percent and number > 100):
        return None
    converted = int(number) if number == number.to_integral_value() else float(number)
    try:
        return converted if math.isfinite(converted) else None
    except OverflowError:
        return None


def parse_workforce_dataset(raw: bytes | str, ticker: str, *, today: date | None = None) -> dict | None:
    """Only an exact issuer's current annual observation is usable."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        return None
    ticker = str(ticker or "").strip().upper()
    suffix = ".TWO" if ticker.endswith(".TWO") else ".TW" if ticker.endswith(".TW") else ""
    if not suffix or not re.fullmatch(r"\d{4,6}", ticker[:-len(suffix)]):
        return None
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(rows, list) or not 0 < len(rows) <= 5000:
        return None
    matches = [row for row in rows if isinstance(row, dict) and str(row.get("公司代號") or "").strip() == ticker[:-len(suffix)]]
    if len(matches) != 1:
        return None
    row = {str(key).strip(): value for key, value in matches[0].items()}
    if not str(row.get("公司名稱") or "").strip():
        return None
    as_of = today or _today()
    report = str(row.get("報告年度") or "").strip()
    published = str(row.get("出表日期") or "").strip()
    if not re.fullmatch(r"\d{3}", report) or not re.fullmatch(r"\d{7}", published):
        return None
    report_year = int(report) + 1911
    try:
        published_on = date(int(published[:3]) + 1911, int(published[3:5]), int(published[5:]))
    except ValueError:
        return None
    if not as_of.year - 2 <= report_year <= as_of.year or not date(report_year, 12, 31) < published_on <= as_of:
        return None
    average_raw = row.get("員工薪資平均數(仟元/人)")
    average = _number(average_raw)
    median = _number(row.get("非擔任主管之全時員工薪資中位數(仟元/人)"))
    female = _number(row.get("管理職女性主管佔比"), percent=True)
    # Foreign issuers may explicitly withhold salary while publishing another
    # workforce fact. Preserve that fact as partial, without turning N/A into
    # zero or accepting malformed/nonpositive salary as a missing disclosure.
    average_missing = average_raw is None or (
        isinstance(average_raw, str) and average_raw.strip().upper() in {"", "N/A", "-", "—"}
    )
    if (average is None and not average_missing) or (average is not None and average <= 0):
        return None
    metrics = {
        "employee_average_salary_thousand_twd": average,
        "nonmanager_median_salary_thousand_twd": median,
        "female_manager_percent": female,
    }
    missing_metrics = [key for key, value in metrics.items() if value is None]
    if len(missing_metrics) == len(metrics):
        return None
    return {
        "ticker": ticker,
        "official_company_name": str(row["公司名稱"]).strip(),
        "report_year": report_year,
        "published_on": published_on.isoformat(),
        "metrics": metrics,
        "available_metric_count": len(metrics) - len(missing_metrics),
        "missing_metric_fields": missing_metrics,
        "job_openings_count": None,
        "observation_kind": "annual_workforce_disclosure",
        "response_sha256": sha256(raw).hexdigest(),
        "source_url": URLS[suffix],
        "source": PROVIDER,
        "coverage_status": "partial" if missing_metrics else "complete",
    }


def _fetch_dataset(url: str) -> str:
    transport_provider = ("TWSE/TPEx annual ESG occupational safety OpenAPI" if "_21" in url else PROVIDER)
    response = sync_get(url, headers={"User-Agent": "stock-agent/1.0"}, timeout=8, provider=transport_provider)
    raw = response.content
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("annual workforce response size invalid")
    return raw.decode("utf-8")


def _tracked_dataset_fetch(url: str, request_evidence: dict) -> str:
    """Bind native HTTP activity to the shared-cache callback that caused it."""
    request_evidence.update(http_request_sent=True, http_request_count=1)
    return _fetch_dataset(url)


class AnnualWorkforceProvider(DataProvider):
    name = PROVIDER
    source = "annual_workforce"
    markets = {"tw"}
    capabilities = {"annual_workforce", "esg_human_capital"}
    cost_tier = "free"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        ticker = request.ticker.strip().upper()
        suffix = ".TWO" if ticker.endswith(".TWO") else ".TW" if ticker.endswith(".TW") else ""
        if not suffix or not ticker[:-len(suffix)].isdigit():
            return ProviderResult(source=self.source, provider=self.name, status="not_applicable")
        url = URLS[suffix]
        workforce_request = {}
        raw, meta = shared_fetch(
            "annual-workforce:v1:" + suffix,
            lambda: _tracked_dataset_fetch(url, workforce_request), freshness_seconds=24 * 60 * 60,
            # A report refresh does not change an annual market-wide filing.
            # Retain last-good bytes through short official API outages, while
            # shared_fetch marks such observations stale rather than fresh.
            retention_seconds=7 * 24 * 60 * 60,
            result_ttl=lambda result: 24 * 60 * 60,
            use_cache=True, lock_wait_seconds=10,
        )
        meta = {**meta, "http_request_sent": workforce_request.get("http_request_sent") is True,
                "http_request_count": int(workforce_request.get("http_request_count") or 0)}
        observation = parse_workforce_dataset(raw, ticker) if raw is not None else None
        from .annual_occupational_safety import (
            URLS as SAFETY_URLS,
            parse_occupational_safety_dataset, verified_occupational_safety_observation,
        )
        safety_url = SAFETY_URLS[suffix]
        safety_request = {}
        safety_raw, safety_meta = shared_fetch(
            "annual-occupational-safety:v1:" + suffix,
            lambda: _tracked_dataset_fetch(safety_url, safety_request), freshness_seconds=24 * 60 * 60,
            retention_seconds=7 * 24 * 60 * 60, result_ttl=lambda result: 24 * 60 * 60,
            use_cache=True, lock_wait_seconds=10,
        )
        safety_meta = {**safety_meta, "http_request_sent": safety_request.get("http_request_sent") is True,
                       "http_request_count": int(safety_request.get("http_request_count") or 0)}
        safety = parse_occupational_safety_dataset(safety_raw, ticker) if safety_raw is not None else None
        workforce_salary = observation is not None and observation["metrics"]["employee_average_salary_thousand_twd"] is not None
        workforce_usable = bool(observation)
        if safety:
            safety["status"] = "stale" if safety_meta.get("stale") else "success" if safety["coverage_status"] == "complete" else "partial"
        safety_usable = verified_occupational_safety_observation(safety, ticker)
        if observation is None and safety:
            observation = {
                "ticker": ticker,
                "official_company_name": safety["official_company_name"],
                "report_year": safety["report_year"],
                "published_on": safety["published_on"],
                "metrics": {},
                "available_metric_count": 0,
                "missing_metric_fields": ["employee_average_salary_thousand_twd", "nonmanager_median_salary_thousand_twd", "female_manager_percent"],
                "job_openings_count": None,
                "observation_kind": "annual_workforce_disclosure",
                "response_sha256": safety["response_sha256"],
                "source_url": safety_url,
                "source": PROVIDER,
                "coverage_status": "partial",
            }
        if observation is not None and safety:
            observation["esg_occupational_safety"] = safety
        workforce_status = ("success" if workforce_salary and not meta.get("stale") and observation["coverage_status"] == "complete" else
                            "partial" if workforce_usable else "error" if meta.get("error_kind") else "valid_empty")
        safety_status = ("success" if safety_usable and not safety_meta.get("stale") and safety["coverage_status"] == "complete" else
                         "partial" if safety_usable else "error" if safety_meta.get("error_kind") else "valid_empty")
        available = workforce_salary or safety_usable
        # A complete safety disclosure cannot fill missing workforce metrics
        # (or the reverse). Preserve each component's completeness boundary.
        both_components = workforce_status == "success" and safety_status == "success"
        stale = bool(available and all(
            (meta.get("stale") if workforce_salary else True,
             safety_meta.get("stale") if safety_usable else True)))
        status = ("unavailable" if not available and observation else
                  "success" if "success" in {workforce_status, safety_status} else
                  "degraded_enrichment" if available else
                  "error" if meta.get("error_kind") or safety_meta.get("error_kind") else "unavailable")
        if observation:
            observation["status"] = "stale" if stale else "success" if status == "success" else "partial"
            observation["esg_occupational_safety"] = safety or {}
            observation["coverage_status"] = "complete" if both_components and status == "success" else "partial"
            observation["coverage_notes"] = [
                "年度職安衛揭露包含職災與火災統計；屬公司申報年度資料，不代表即時事故狀態。"
            ] if safety else ["年度職安衛資料本次未取得；不得以缺值解讀為零。"]
        components = {
            "workforce_disclosure": {"status": workforce_status, "stale": bool(meta.get("stale")),
                                     "source_url": url, "error_kind": meta.get("error_kind")},
            "occupational_safety_disclosure": {"status": safety_status, "stale": bool(safety_meta.get("stale")),
                                               "source_url": safety_url, "error_kind": safety_meta.get("error_kind"),
                                               "report_year": safety.get("report_year") if safety else None,
                                               "response_sha256": safety.get("response_sha256") if safety else None},
        }
        safety_audit = {
            "source": "esg_occupational_safety",
            "provider": "TWSE/TPEx annual ESG occupational safety OpenAPI",
            "status": ("success" if safety_usable and safety_status == "success" else
                      "degraded_enrichment" if safety_usable else
                      "error" if safety_meta.get("error_kind") else "unavailable"),
            "event_kind": "fetch",
            "record_count": int(bool(safety_usable)),
            "raw_count": int(bool(safety)),
            "source_url": safety_url,
            "report_year": safety.get("report_year") if safety else None,
            "published_on": safety.get("published_on") if safety else None,
            "response_sha256": safety.get("response_sha256") if safety else None,
            "coverage_status": safety.get("coverage_status") if safety else "unavailable",
            "http_request_sent": bool(safety_meta.get("http_request_sent")),
            "http_request_count": int(safety_meta.get("http_request_count") or int(safety_meta.get("http_request_sent") is True)),
            "cache_hit": bool(safety_meta.get("cache_hit")),
            "stale": bool(safety_meta.get("stale")),
            "fetched_at_epoch": safety_meta.get("fetched_at_epoch"),
            "error_kind": safety_meta.get("error_kind", ""),
            "message": ("年度職災與火災揭露已核對公司代號及申報年度；不是即時事故清單。" if safety_usable else
                        "本次未取得有效的同公司年度職安衛列；缺值不代表零。"),
        }
        fetched_stamps = [stamp for stamp in (meta.get("fetched_at_epoch"), safety_meta.get("fetched_at_epoch"))
                          if isinstance(stamp, (int, float)) and math.isfinite(stamp)]
        http_sent = bool(meta.get("http_request_sent") or safety_meta.get("http_request_sent"))
        workforce_audit_status = {
            "success": "success",
            "partial": "degraded_enrichment" if workforce_salary else "unavailable",
            "valid_empty": "degraded_enrichment",
            "error": "error",
        }.get(workforce_status, "unavailable")
        workforce_coverage = "complete" if workforce_status == "success" else "partial" if workforce_usable else "unavailable"
        audit = {
            "source": self.source, "provider": self.name, "status": workforce_audit_status,
            "event_kind": "fetch",
            "record_count": int(workforce_salary),
            "raw_count": 1 if observation else 0,
            "source_url": url, "coverage_status": workforce_coverage,
            "report_year": observation.get("report_year") if observation else None,
            "published_on": observation.get("published_on") if observation else None,
            "response_sha256": observation.get("response_sha256") if observation else None,
            "component_statuses": {
                "annual_disclosure": {
                    "status": workforce_status,
                    "as_of": f"{observation['report_year']}-12-31" if workforce_usable else None,
                    "series_id": url,
                    "response_sha256": observation.get("response_sha256") if workforce_usable else None,
                },
                **components,
            },
            "related_entries": [safety_audit],
            "error_kind": meta.get("error_kind", ""),
            "message": ("年度人力揭露已核對公司代號及申報年度。" if workforce_status == "success" else
                        "已取得部分年度人力揭露；缺少欄位保持未知。" if workforce_status == "partial" else
                        "年度人力來源未回傳有效的同公司資料；缺值不代表零。" if workforce_status == "valid_empty" else
                        "年度人力資料來源取得失敗。"),
            "http_request_sent": meta.get("http_request_sent") is True,
            "http_request_count": int(meta.get("http_request_count") or 0),
            "cache_hit": bool(meta.get("cache_hit")),
            "stale": bool(meta.get("stale")),
            "fetched_at_epoch": meta.get("fetched_at_epoch"),
        }
        return ProviderResult(source=self.source, provider=self.name, status=status,
                              value=observation or {}, audit=audit,
                              as_of=f"{observation['report_year']}-12-31" if observation else None)
