"""TPEx's free quarterly financial summary, kept separate from full statements.

The exchange file contains one current-period/YTD row and a same-period prior
year comparison. It is not a balance sheet, cash-flow statement, or annual
history. The raw index and workbook are retained and re-parsed at admission.
"""
from __future__ import annotations

import base64
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
import os
import re
import time
from zoneinfo import ZoneInfo

import httpx

from bounded_curl_process import collect_capped_process
from data_trust import build_source_audit_entry, iso_from_epoch
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from provider_correlation import current_audit_correlation, source_operation
from search_provider_runtime import (
    SourceResponseError, cooldown_state, observe_http_response, remember_failure, scope_key,
)
from shared_provider_cache import shared_fetch

PROVIDER = "TPEx official quarterly financial summary"
SCHEMA = "tpex_quarterly_summary.v1"
POLICY = "tpex-quarterly-summary-v1"
INDEX_URL = "https://www.tpex.org.tw/www/en-us/statistics/financial"
FILE_BASE = "https://www.tpex.org.tw/storage/statistic/financial/en-us"
TAIPEI = ZoneInfo("Asia/Taipei")
INDEX_MAX_BYTES = 200_000
FILE_MAX_BYTES = 2_500_000
INDEX_FRESH_SECONDS = 900
FILE_FRESH_SECONDS = 6 * 60 * 60
MAX_PERIOD_AGE_DAYS = 220
MAX_REQUEST_SECONDS = 5.0
MAX_OPERATION_SECONDS = 16.0
MAX_HTTP_REQUESTS = 3
PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
INDEX_FIELDS = ["Quarter/Year", "XLS Download", "ODS Download"]
SHEET_NAMES = ["DOMESTIC COMPANIES", "FOREIGN ISSUERS' COMPANIES"]
HEADER_FIELDS = {
    0: "Security's Code & Name",
    2: "Operating Revenues",
    5: "Income(Lose) from Operation",
    7: "Total Non-Operating Income",
    9: "Net Income after Tax",
    12: "Capital Stock End of Period",
    13: "Net Income Per Share",
    15: "Net Value Per Share (NT$) (A)",
    16: "Ratio of net worth to total assets(%) (B)",
    17: "Current Ratio (%) (C)",
    18: "Quick Ratio (%) (D)",
}
AMOUNT_METRICS = {
    "operating_revenue_ytd_thousands": 2,
    "operating_income_ytd_thousands": 5,
    "nonoperating_income_ytd_thousands": 7,
    "net_income_after_tax_ytd_thousands": 9,
    "capital_stock_thousands": 12,
}
COMPARABLE_METRICS = {
    "operating_revenue_ytd_thousands": 3,
    "operating_income_ytd_thousands": 6,
    "nonoperating_income_ytd_thousands": 8,
    "net_income_after_tax_ytd_thousands": 10,
}
SINGLE_OR_SHARE_METRICS = {
    "eps_ytd_twd_per_share": 13,
    "net_asset_value_per_share_twd": 15,
    "equity_to_assets_pct": 16,
    "current_ratio_pct": 17,
    "quick_ratio_pct": 18,
}
COMPARISON_EPS_COL = 14
NUMBER_RE = re.compile(r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?")
TICKER_RE = re.compile(r"([0-9]{4,6})\.TWO\Z")
INDEX_LINK_RE = re.compile(r"/storage/statistic/financial/en-us/O_(20[0-9]{2})Q([1-4])\.xls\Z")
MONTH_LABELS = {1: "Jan.-Mar.", 2: "Jan.-Jun.", 3: "Jan.-Sep.", 4: "Jan.-Dec."}
EMPTY_SYMBOLS = {"", "NA", "N/A", "-----", "+++++", "<<<<<", "-"}


def _today() -> date:
    return datetime.now(TAIPEI).date()


def supports_ticker(ticker: str) -> bool:
    return isinstance(ticker, str) and TICKER_RE.fullmatch(ticker) is not None


def quarter_file_url(year: int, quarter: int) -> str:
    if (type(year) is not int or type(quarter) is not int or not 2009 <= year <= 2099
            or quarter not in (1, 2, 3, 4)):
        raise ValueError("tpex_quarter_file_period_invalid")
    return f"{FILE_BASE}/O_{year}Q{quarter}.xls"


def _quarter_end(year: int, quarter: int) -> date:
    month = quarter * 3
    return date(year, month, (date(year + (month == 12), month % 12 + 1, 1) - date.resolution).day)


def _quarter_start(year: int) -> date:
    return date(year, 1, 1)


def _normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strict_json(raw: bytes):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("tpex_index_duplicate_json_key")
            result[key] = value
        return result

    try:
        return json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("tpex_index_json_invalid") from exc


def parse_report_index(raw: bytes, *, requested_year: int) -> list[dict]:
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= INDEX_MAX_BYTES
            or type(requested_year) is not int or not 2009 <= requested_year <= 2099):
        raise ValueError("tpex_index_response_invalid")
    payload = _strict_json(raw)
    if not isinstance(payload, dict):
        raise ValueError("tpex_index_table_invalid")
    tables = payload.get("tables")
    if payload.get("stat") != "ok" or not isinstance(tables, list) or len(tables) != 2:
        raise ValueError("tpex_index_table_invalid")
    titles = [table.get("title") if isinstance(table, dict) else None for table in tables]
    if sorted(titles) != sorted(["Mainboard Companies", "Emerging Stock Board Companies"]):
        raise ValueError("tpex_index_market_scope_invalid")
    mainboard = next(table for table in tables if table.get("title") == "Mainboard Companies")
    if (mainboard.get("date") != str(requested_year) or mainboard.get("fields") != INDEX_FIELDS
            or not isinstance(mainboard.get("data"), list)
            or type(mainboard.get("totalCount")) is not int
            or mainboard["totalCount"] != len(mainboard["data"])
            or len(mainboard["data"]) > 4):
        raise ValueError("tpex_index_mainboard_contract_invalid")
    reports = []
    seen = set()
    for row in mainboard["data"]:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("tpex_index_row_invalid")
        match = re.fullmatch(r"Q([1-4]) (20[0-9]{2})", row[0]) if isinstance(row[0], str) else None
        xls_path = row[1]
        ods_path = row[2]
        if not match:
            raise ValueError("tpex_index_period_invalid")
        quarter, year = int(match[1]), int(match[2])
        expected_path = f"/storage/statistic/financial/en-us/O_{year}Q{quarter}.xls"
        expected_ods = f"/en-us/api/convertToOds?f=/statistic/financial/en-us/O_{year}Q{quarter}.xls"
        url_match = INDEX_LINK_RE.fullmatch(xls_path) if isinstance(xls_path, str) else None
        if (year != requested_year or xls_path != expected_path or ods_path != expected_ods
                or not url_match or (year, quarter) in seen):
            raise ValueError("tpex_index_download_identity_invalid")
        seen.add((year, quarter))
        reports.append({"year": year, "quarter": quarter, "url": quarter_file_url(year, quarter)})
    return reports


def select_latest_report(index_results: list[list[dict]], *, today: date) -> dict | None:
    if not isinstance(index_results, list):
        raise ValueError("tpex_index_results_invalid")
    reports = [report for result in index_results for report in result]
    if any(not isinstance(report, dict) or type(report.get("year")) is not int
           or type(report.get("quarter")) is not int
           or report.get("url") != quarter_file_url(report["year"], report["quarter"])
           for report in reports):
        raise ValueError("tpex_index_result_identity_invalid")
    keys = [(report["year"], report["quarter"]) for report in reports]
    if len(keys) != len(set(keys)):
        raise ValueError("tpex_index_result_ambiguous")
    eligible = []
    for report in reports:
        end = _quarter_end(report["year"], report["quarter"])
        age = (today - end).days
        if 0 <= age <= MAX_PERIOD_AGE_DAYS:
            eligible.append((end, report))
    return max(eligible, key=lambda item: item[0])[1] if eligible else None


def _period_headers(year: int, quarter: int) -> tuple[str, str]:
    current = f"{MONTH_LABELS[quarter]} {year}"
    prior = f"{MONTH_LABELS[quarter]} {year - 1}"
    return current, prior


def _header(sheet, row_index: int, column: int) -> str:
    if row_index >= sheet.nrows or column >= sheet.ncols:
        return ""
    return _normalize_text(sheet.cell_value(row_index, column))


def _validate_workbook_headers(sheet, year: int, quarter: int) -> None:
    if not (sheet.nrows >= 20 and sheet.nrows <= 2000 and sheet.ncols == 19):
        raise ValueError("tpex_workbook_shape_invalid")
    unit_row = [_normalize_text(sheet.cell_value(2, col)) for col in range(sheet.ncols)]
    current, prior = _period_headers(year, quarter)
    if current not in unit_row or "Unit:NT$ 1,000" not in unit_row:
        raise ValueError("tpex_workbook_period_or_unit_invalid")
    for column, label in HEADER_FIELDS.items():
        if _header(sheet, 4, column) != label:
            raise ValueError("tpex_workbook_metric_contract_invalid")
    expected = {2: current, 3: prior, 4: "changed (%)", 5: current, 6: prior,
                7: current, 8: prior, 9: current, 10: prior, 11: "changed (%)",
                13: current, 14: prior}
    if any(_header(sheet, 6, column) != label for column, label in expected.items()):
        raise ValueError("tpex_workbook_comparison_period_invalid")


def _number(value, *, integer: bool) -> tuple[int | float | None, str]:
    if isinstance(value, bool):
        raise ValueError("tpex_workbook_boolean_value_invalid")
    if value is None:
        return None, "not_reported"
    if isinstance(value, str):
        text = value.strip()
        if text.upper() in EMPTY_SYMBOLS:
            return None, "reported_unavailable_symbol" if text else "not_reported"
        if not NUMBER_RE.fullmatch(text):
            raise ValueError("tpex_workbook_numeric_value_invalid")
        decimal = Decimal(text.replace(",", ""))
    elif type(value) in (int, float):
        if not math.isfinite(value):
            raise ValueError("tpex_workbook_nonfinite_value_invalid")
        decimal = Decimal(str(value))
    else:
        raise ValueError("tpex_workbook_numeric_type_invalid")
    if integer:
        if decimal != decimal.to_integral_value():
            raise ValueError("tpex_workbook_amount_not_integral")
        return int(decimal), "reported_numeric"
    number = float(decimal)
    if not math.isfinite(number):
        raise ValueError("tpex_workbook_nonfinite_value_invalid")
    return number, "reported_numeric"


def _decode_xls(raw: bytes):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= FILE_MAX_BYTES:
        raise ValueError("tpex_workbook_response_size_invalid")
    try:
        import xlrd
        book = xlrd.open_workbook(file_contents=raw, on_demand=True)
    except Exception as exc:
        raise ValueError("tpex_workbook_xls_invalid") from exc
    try:
        if book.sheet_names() != SHEET_NAMES:
            raise ValueError("tpex_workbook_sheet_contract_invalid")
        return book, book.sheet_by_name("DOMESTIC COMPANIES")
    except Exception:
        book.release_resources()
        raise


def parse_quarterly_summary(raw: bytes, *, ticker: str, year: int, quarter: int,
                            today: date) -> dict:
    if (not supports_ticker(ticker) or type(year) is not int or type(quarter) is not int
            or not 2009 <= year <= today.year or quarter not in (1, 2, 3, 4)):
        raise ValueError("tpex_summary_request_identity_invalid")
    end = _quarter_end(year, quarter)
    if not 0 <= (today - end).days <= MAX_PERIOD_AGE_DAYS:
        raise ValueError("tpex_summary_period_expired_or_future")
    book, sheet = _decode_xls(raw)
    try:
        _validate_workbook_headers(sheet, year, quarter)
        matches = []
        seen = set()
        for index in range(7, sheet.nrows):
            raw_code = sheet.cell_value(index, 0)
            code = raw_code.strip() if isinstance(raw_code, str) else ""
            if not re.fullmatch(r"[0-9]{4,6}", code):
                continue  # blank rows, section labels, and footnotes are not issuers
            if code in seen:
                raise ValueError("tpex_workbook_duplicate_issuer")
            seen.add(code)
            name = sheet.cell_value(index, 1)
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                raise ValueError("tpex_workbook_issuer_name_invalid")
            if code == ticker.split(".")[0]:
                matches.append((index, name.strip()))
        if len(matches) != 1:
            raise ValueError("tpex_issuer_missing_or_ambiguous")
        row_index, issuer_name = matches[0]
        row = {"issuer_code": ticker.split(".")[0], "issuer_name": issuer_name}
        metrics, comparison, field_status = {}, {}, {}
        for key, column in AMOUNT_METRICS.items():
            parsed, status = _number(sheet.cell_value(row_index, column), integer=True)
            if key != "capital_stock_thousands":
                metrics[key] = parsed
                field_status[key] = status
            else:
                metrics[key] = parsed
                field_status[key] = status
        for key, column in COMPARABLE_METRICS.items():
            parsed, status = _number(sheet.cell_value(row_index, column), integer=True)
            comparison[key] = parsed
            field_status["comparison." + key] = status
        for key, column in SINGLE_OR_SHARE_METRICS.items():
            parsed, status = _number(sheet.cell_value(row_index, column), integer=False)
            metrics[key] = parsed
            field_status[key] = status
        eps_prior, eps_status = _number(sheet.cell_value(row_index, COMPARISON_EPS_COL), integer=False)
        comparison["eps_ytd_twd_per_share"] = eps_prior
        field_status["comparison.eps_ytd_twd_per_share"] = eps_status
        usable = sum(metrics.get(key) is not None for key in (
            "operating_revenue_ytd_thousands", "operating_income_ytd_thousands",
            "net_income_after_tax_ytd_thousands", "eps_ytd_twd_per_share"))
        if usable < 2:
            raise ValueError("tpex_summary_usable_metric_count_insufficient")
        start = _quarter_start(year)
        prior_start = _quarter_start(year - 1)
        return {
            "schema": SCHEMA,
            "policy": POLICY,
            "coverage_status": "period_comparison_summary_only",
            "ticker": ticker,
            **row,
            "market_scope": "tpex_mainboard",
            "period": {
                "year": year, "quarter": quarter,
                "period_start": start.isoformat(), "period_end": end.isoformat(),
                "comparison_period_start": prior_start.isoformat(),
                "comparison_period_end": _quarter_end(year - 1, quarter).isoformat(),
                "income_period_basis": "year_to_date_cumulative",
                "comparison_basis": "same_period_previous_year",
            },
            "currency": "TWD",
            "amount_unit": "thousands",
            "per_share_unit": "TWD_per_share",
            "ratio_unit": "percentage_points",
            "scope": "tpex_mainboard_summary_not_complete_financial_statements",
            "cash_flow_statement_available": False,
            "historical_point_in_time_verified": False,
            "finality_guaranteed": False,
            "metrics": metrics,
            "comparison": comparison,
            "field_status": field_status,
        }
    finally:
        book.release_resources()


def _receipt_raw(receipt: dict, url: str, limit: int) -> tuple[bytes, float]:
    if (not isinstance(receipt, dict) or receipt.get("status") != "archived"
            or receipt.get("source_url") != url or receipt.get("http_status") != 200
            or receipt.get("evidence_kind") != "raw_http_response_bytes"
            or receipt.get("historical_point_in_time_verified") is not False
            or receipt.get("finality_guaranteed") is not False):
        raise ValueError("tpex_original_receipt_invalid")
    stamp = receipt.get("retrieved_at")
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0:
        raise ValueError("tpex_original_receipt_time_invalid")
    raw = read_response(receipt, max_bytes=limit)
    if (not 0 < len(raw) <= limit or receipt.get("raw_response_bytes") != len(raw)
            or receipt.get("raw_response_sha256") != sha256(raw).hexdigest()):
        raise ValueError("tpex_original_receipt_body_invalid")
    return raw, float(stamp)


def project_summary(value: dict, ticker: str, *, today: date | None = None) -> dict | None:
    """Re-parse both official originals and re-check the row/period before use."""
    try:
        if (not isinstance(value, dict) or value.get("schema") != SCHEMA or value.get("policy") != POLICY
                or value.get("coverage_status") != "period_comparison_summary_only"
                or value.get("ticker") != ticker or value.get("market_scope") != "tpex_mainboard"):
            return None
        period = value.get("period")
        if not isinstance(period, dict) or type(period.get("year")) is not int or type(period.get("quarter")) is not int:
            return None
        report_url = quarter_file_url(period["year"], period["quarter"])
        raw, stamp = _receipt_raw(value.get("original_receipt"), report_url, FILE_MAX_BYTES)
        index_raw, index_stamp = _receipt_raw(value.get("index_original_receipt"), INDEX_URL, INDEX_MAX_BYTES)
        index_year = value.get("index_year")
        if type(index_year) is not int or index_year != period["year"]:
            return None
        reports = parse_report_index(index_raw, requested_year=index_year)
        if {"year": period["year"], "quarter": period["quarter"], "url": report_url} not in reports:
            return None
        parsed = parse_quarterly_summary(raw, ticker=ticker, year=period["year"],
                                         quarter=period["quarter"], today=today or _today())
        for key, expected in parsed.items():
            if value.get(key) != expected:
                return None
        if (value.get("source_url") != report_url or value.get("response_sha256") != sha256(raw).hexdigest()
                or value.get("response_bytes") != len(raw)
                or type(value.get("fetched_at_epoch")) not in (int, float)
                or not math.isfinite(value["fetched_at_epoch"])
                or abs(value["fetched_at_epoch"] - stamp) > 1
                or abs(value.get("index_fetched_at_epoch", 0) - index_stamp) > 1):
            return None
        return {**parsed, "source_url": report_url, "response_sha256": sha256(raw).hexdigest(),
                "response_bytes": len(raw), "fetched_at_epoch": stamp,
                "fetched_at": iso_from_epoch(stamp), "original_receipt": value["original_receipt"],
                "index_year": index_year, "index_fetched_at_epoch": index_stamp,
                "index_original_receipt": value["index_original_receipt"]}
    except (KeyError, TypeError, ValueError, OverflowError, OSError, EOFError, httpx.HTTPError):
        return None


def _headers(raw: bytes):
    status, headers = None, {}
    for line in raw.replace(b"\r\n", b"\n").splitlines(keepends=True):
        if line.startswith(b"HTTP/"):
            match = re.match(rb"HTTP/\S+ +([2-5]\d{2})(?:[ \n]|$)", line)
            if match:
                status, headers = int(match[1]), {}
        elif status and line.endswith(b"\n"):
            key, sep, value = line.partition(b":")
            name = key.decode("ascii", "ignore").lower()
            if sep and name in {"content-type", "content-encoding", "content-length"}:
                headers[name] = value.decode("latin-1").strip()
    return status, headers


class TpexFinancialSummaryHttp:
    def __init__(self, deadline: float):
        self.deadline = deadline
        self.http_request_count = 0
        self.components = []

    def _download(self, url: str, *, method: str, year: int | None, diagnostic: dict,
                   cache_key: str, limit: int, content_types: set[str], freshness: int):
        if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
            raise SourceResponseError("test_network_disabled")
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(name) for name in PROXY_ENV):
            raise SourceResponseError("proxy_configuration_unsupported")
        if method == "POST" and (url != INDEX_URL or year is None):
            raise SourceResponseError("transport_url_invalid")
        if method == "GET" and not re.fullmatch(
                r"https://www\.tpex\.org\.tw/storage/statistic/financial/en-us/O_20[0-9]{2}Q[1-4]\.xls", url):
            raise SourceResponseError("transport_url_invalid")
        key = scope_key(PROVIDER, endpoint="www.tpex.org.tw")
        if cooldown_state(key):
            raise SourceResponseError("cooldown")
        remaining = min(MAX_REQUEST_SECONDS, self.deadline - time.monotonic())
        if remaining <= 0:
            raise SourceResponseError("timeout")
        argv = ["/usr/bin/curl", "--disable", "--silent", "--max-time", str(remaining),
                "--connect-timeout", str(min(2.0, remaining)), "--max-filesize", str(limit),
                "--proto", "=https", "--max-redirs", "0", "--retry", "0",
                "--dump-header", "/dev/fd/{HEADER_FD}", "--write-out", "%{stderr}%{json}"]
        if method == "POST":
            argv.extend(["--data-urlencode", f"date={year}", url])
        else:
            argv.append(url)
        parts, rc, process_error = collect_capped_process(
            argv, min(self.deadline, time.monotonic() + remaining), body_limit=limit, headers=True)
        diagnostic["http_request_sent"] = bool(parts.get("process_started"))
        self.http_request_count += int(diagnostic["http_request_sent"])
        status, headers = _headers(parts["headers"])
        try:
            meta = json.loads(parts["metadata"])
        except (ValueError, UnicodeDecodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get("http_code")) is int and 200 <= meta["http_code"] <= 599:
            status = meta["http_code"]
        response = httpx.Response(status, headers=headers, request=httpx.Request(method, url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic["error_kind"] = kind
            error = SourceResponseError(kind, status_code=status)
            if response is not None:
                error.response = response
            if status in {401, 403, 429} or status is not None and status >= 500:
                remember_failure(key, error)
            raise error

        if status is not None and status != 200:
            fail({401: "authentication", 403: "access_denied", 429: "rate_limited"}.get(
                status, "server_error" if status >= 500 else "http_error"))
        if process_error or rc:
            fail(process_error or ("timeout" if rc == 28 else "response_too_large" if rc == 63 else "transport_error"))
        if (status != 200 or meta.get("http_code") != status or meta.get("url_effective") != url
                or meta.get("num_redirects") != 0):
            fail("transport_metadata_invalid")
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if (headers.get("content-encoding", "identity").lower() not in {"", "identity"}
                or content_type not in content_types):
            fail("unsupported_response_representation")
        raw = parts["body"]
        if not 0 < len(raw) <= limit or time.monotonic() >= self.deadline:
            fail("response_size_or_deadline_invalid")
        receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200,
                                  max_bytes=limit)
        if receipt.get("status") != "archived" or read_response(receipt, max_bytes=limit) != raw:
            fail("original_receipt_unverified")
        diagnostic.update(http_status=200, response_sha256=sha256(raw).hexdigest(),
                          response_bytes=len(raw), original_receipt=receipt)
        return {"url": url, "body_b64": base64.b64encode(raw).decode("ascii"),
                "sha256": sha256(raw).hexdigest(), "original_receipt": receipt}

    def _request(self, url: str, *, method: str, year: int | None, limit: int,
                 content_types: set[str], freshness: int, cache_key: str):
        diagnostic = {"url": url, "method": method, "http_request_sent": False, "cache_hit": False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError("timeout")
        value, metadata = shared_fetch(
            cache_key,
            lambda: self._download(url, method=method, year=year, diagnostic=diagnostic,
                                   cache_key=cache_key, limit=limit, content_types=content_types,
                                   freshness=freshness),
            freshness_seconds=freshness, retention_seconds=freshness,
            error_retry_seconds=120, lock_wait_seconds=min(1.0, max(0.0, self.deadline - time.monotonic())),
        )
        diagnostic.update(cache_hit=bool(metadata.get("cache_hit")),
                          fetched_at_epoch=metadata.get("fetched_at_epoch"),
                          error_kind=metadata.get("error_kind", ""))
        if metadata.get("error_kind") or metadata.get("stale"):
            raise SourceResponseError(metadata.get("error_kind") or "stale_receipt")
        try:
            stamp = metadata.get("fetched_at_epoch")
            receipt = value.get("original_receipt") if isinstance(value, dict) else None
            raw = base64.b64decode(value["body_b64"], validate=True)
            retrieved = receipt.get("retrieved_at") if isinstance(receipt, dict) else None
            if (not isinstance(value, dict) or value.get("url") != url or not 0 < len(raw) <= limit
                    or sha256(raw).hexdigest() != value.get("sha256")
                    or type(stamp) not in (int, float) or not math.isfinite(stamp)
                    or not 0 <= time.time() - stamp < freshness
                    or type(retrieved) not in (int, float) or not math.isfinite(retrieved)
                    or not 0 <= stamp - retrieved <= 10 or not 0 <= time.time() - retrieved < freshness
                    or receipt.get("source_url") != url or receipt.get("http_status") != 200
                    or receipt.get("raw_response_sha256") != value.get("sha256")
                    or receipt.get("raw_response_bytes") != len(raw)
                    or read_response(receipt, max_bytes=limit) != raw):
                raise ValueError("tpex_cached_response_unverified")
        except (ValueError, KeyError, TypeError, OSError, EOFError, OverflowError):
            raise SourceResponseError("cache_receipt_invalid") from None
        diagnostic.update(http_status=200, original_receipt=receipt,
                          response_sha256=value["sha256"], response_bytes=len(raw))
        return raw, receipt

    def post_index(self, year: int):
        if type(year) is not int or not 2009 <= year <= _today().year:
            raise SourceResponseError("tpex_index_year_invalid")
        return self._request(INDEX_URL, method="POST", year=year, limit=INDEX_MAX_BYTES,
                             content_types={"application/json"}, freshness=INDEX_FRESH_SECONDS,
                             cache_key=f"tpex-financial-summary-index:v1:{year}")

    def get_file(self, url: str):
        if not re.fullmatch(r"https://www\.tpex\.org\.tw/storage/statistic/financial/en-us/O_20[0-9]{2}Q[1-4]\.xls", url):
            raise SourceResponseError("transport_url_invalid")
        return self._request(url, method="GET", year=None, limit=FILE_MAX_BYTES,
                             content_types={"application/vnd.ms-excel", "application/octet-stream"},
                             freshness=FILE_FRESH_SECONDS,
                             cache_key="tpex-financial-summary-file:v1:" + sha256(url.encode()).hexdigest())


def fetch_quarterly_summary_result(ticker: str) -> dict:
    started = time.time()
    with source_operation("financial_statements", PROVIDER):
        return _fetch_quarterly_summary_result(ticker, started)


def _fetch_quarterly_summary_result(ticker: str, started: float) -> dict:
    audit = build_source_audit_entry("financial_statements", PROVIDER, "error", record_count=0,
                                     started_at_epoch=started, finished_at_epoch=started)
    audit.update(selection_policy=POLICY, coverage_status="period_comparison_summary_only",
                 cache_hit=False, stale=False, event_kind="aggregate", http_request_sent=False,
                 http_request_count=0, ticker=ticker, cash_flow_statement_available=False)
    http = None
    value = None
    try:
        if not supports_ticker(ticker):
            audit.update(status="not_applicable", event_kind="local_block", error_kind="ticker_not_tpex_mainboard",
                         message="TPEx 季度摘要僅適用 .TWO 上櫃主板；未發出來源請求。")
            return {"value": None, "audit": audit}
        today = _today()
        http = TpexFinancialSummaryHttp(time.monotonic() + MAX_OPERATION_SECONDS)
        selected = None
        selected_index = None
        for year in (today.year, today.year - 1):
            raw_index, receipt = http.post_index(year)
            reports = parse_report_index(raw_index, requested_year=year)
            selected = select_latest_report([reports], today=today)
            if selected is not None:
                selected_index = {"year": year, "receipt": receipt}
                break
            if http.http_request_count >= MAX_HTTP_REQUESTS:
                break
        if selected is None or selected_index is None:
            audit.update(status="degraded_enrichment", record_count=0, ticker=ticker,
                         error_kind="", coverage_status="no_recent_tpex_summary_report",
                         message="TPEx 官方索引沒有 220 日內已發布的季度摘要；空結果不代表公司財務為零。")
            return {"value": None, "audit": audit}
        raw_file, file_receipt = http.get_file(selected["url"])
        value = parse_quarterly_summary(raw_file, ticker=ticker, year=selected["year"],
                                        quarter=selected["quarter"], today=today)
        if selected["url"] not in [row["url"] for row in parse_report_index(
                read_response(selected_index["receipt"], max_bytes=INDEX_MAX_BYTES),
                requested_year=selected_index["year"])]:
            raise ValueError("tpex_selected_file_not_in_verified_index")
        value.update(source_url=selected["url"], response_sha256=sha256(raw_file).hexdigest(),
                     response_bytes=len(raw_file), fetched_at_epoch=file_receipt["retrieved_at"],
                     fetched_at=iso_from_epoch(file_receipt["retrieved_at"]),
                     original_receipt=file_receipt, index_year=selected_index["year"],
                     index_fetched_at_epoch=selected_index["receipt"]["retrieved_at"],
                     index_original_receipt=selected_index["receipt"])
        if project_summary(value, ticker, today=today) is None:
            raise ValueError("tpex_summary_receipt_or_projection_unverified")
        cache_hit = bool(http.components) and all(item.get("cache_hit") is True for item in http.components)
        audit.update(status="skipped_fresh_cache" if cache_hit else "success", record_count=1,
                     ticker=ticker, issuer_code=value["issuer_code"], issuer_name=value["issuer_name"],
                     year=selected["year"], quarter=selected["quarter"],
                     period_end=value["period"]["period_end"], currency="TWD", amount_unit="thousands",
                     source_url=selected["url"], response_sha256=value["response_sha256"],
                     response_bytes=value["response_bytes"], fetched_at_epoch=value["fetched_at_epoch"],
                     fetched_at=value["fetched_at"], index_year=selected_index["year"],
                     cache_hit=cache_hit, event_kind="cache_hit" if cache_hit else "aggregate",
                     message="TPEx 同期財務摘要；損益數值為年初至申報季累計並與去年同期比較，不是完整三表或年度序列。")
    except Exception as exc:
        audit.update(status="error", record_count=0,
                     error_kind=getattr(exc, "error_kind", type(exc).__name__),
                     message="TPEx 官方季度摘要未通過來源、期間、公司或原件核對。")
        value = None
    finally:
        components = http.components if http else []
        audit.update(transport_components=components,
                     component_statuses={str(i): {
                         "status": "success" if item.get("http_status") == 200 else "error",
                         "url": item.get("url"), "http_status": item.get("http_status"),
                         "response_sha256": item.get("response_sha256"),
                         "response_bytes": item.get("response_bytes"),
                         "cache_hit": bool(item.get("cache_hit")),
                         "error_kind": item.get("error_kind", ""),
                     } for i, item in enumerate(components)},
                     http_request_sent=bool(http.http_request_count) if http else False,
                     http_request_count=http.http_request_count if http else 0,
                     duration_ms=max(0, round((time.time() - started) * 1000)))
        if components:
            audit["http_status"] = components[-1].get("http_status")
        audit.update(current_audit_correlation())
    return {"value": value, "audit": audit}
