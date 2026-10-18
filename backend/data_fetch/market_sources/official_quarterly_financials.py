"""Latest filed-quarter balance and income snapshots from official TWSE/MOPS data.

This is deliberately separate from the five-year annual-series contract. The
income statement is cumulative year-to-date; no cash flow statement is supplied.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from hashlib import sha256
import io
import json
import math
import re
import time
from zoneinfo import ZoneInfo

from data_trust import build_source_audit_entry, iso_from_epoch
from provider_correlation import source_operation
from official_response_evidence import read_response

from .official_quarterly_financial_transport import (
    FRESH_SECONDS, MAX_BYTES, OPENAPI_BASE_URL, OPENAPI_MAX_BYTES, PROVIDER,
    QuarterlyFinancialHttp,
)

SCHEMA = "mops_latest_quarter_financials.v1"
POLICY = "twse-official-latest-quarter-v2"
LEGACY_POLICY = "mops-official-latest-quarter-csv-v1"
BASE_URL = "https://mopsfin.twse.com.tw/opendata"
TAIPEI = ZoneInfo("Asia/Taipei")
IDENTITY_FIELDS = ("出表日期", "年度", "季別", "公司代號", "公司名稱")
NUMBER_RE = re.compile(r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?")


def _today():
    return datetime.now(TAIPEI).date()


def _sector_code(data):
    sector_data = data.get("sector_specific_financials")
    basis = data.get("financial_history_basis")
    typed_schema = (sector_data.get("schema") if isinstance(sector_data, dict) else None) or (
        basis.get("statement_schema") if isinstance(basis, dict) else None)
    try:
        from .financial_institution_xbrl import BANK_SCHEMA, HOLDING_SCHEMA
        from .mops_public_holding import SCHEMA as PUBLIC_HOLDING_SCHEMA
        from .tcfhc_annual_financial import SCHEMA as AUDITED_HOLDING_SCHEMA
        from .broker_xbrl import SCHEMA as BROKER_SCHEMA
        from .insurer_xbrl import STANDALONE_SCHEMA as INSURER_SCHEMA
        schemas = {
            BANK_SCHEMA: "basi", HOLDING_SCHEMA: "fh",
            PUBLIC_HOLDING_SCHEMA: "fh", AUDITED_HOLDING_SCHEMA: "fh",
            BROKER_SCHEMA: "bd", INSURER_SCHEMA: "ins",
        }
        if typed_schema in schemas:
            return schemas[typed_schema]
    except ImportError:
        pass
    industry = " ".join(str(data.get(key) or "") for key in ("sector", "industry", "industry_name"))
    if re.search(r"銀行|Bank", industry, re.IGNORECASE):
        return "basi"
    if re.search(r"金控|金融控股|Financial Holding|Financial Conglomerate", industry, re.IGNORECASE):
        return "fh"
    if re.search(r"保險|Insurance", industry, re.IGNORECASE):
        return "ins"
    if re.search(r"證券|券商|Broker", industry, re.IGNORECASE):
        return "bd"
    if re.search(r"投信|投資信託|Investment Trust", industry, re.IGNORECASE):
        return "mim"
    return "ci"


def _market(ticker):
    match = re.fullmatch(r"([0-9]{4,6})(\.TW|\.TWO)", str(ticker or "").upper())
    if not match:
        raise ValueError("quarterly_financial_ticker_unverified")
    return match.group(1), "L" if match.group(2) == ".TW" else "O"


def quarterly_url(statement, market, sector):
    if statement not in {"06", "07"} or market not in {"L", "O"} or sector not in {"ci", "basi", "fh", "ins", "bd", "mim"}:
        raise ValueError("quarterly_financial_route_unverified")
    return f"{BASE_URL}/t187ap{statement}_{market}_{sector}.csv"


def quarterly_openapi_url(statement, sector):
    if statement not in {"06", "07"} or sector not in {"ci", "basi", "fh", "ins", "bd", "mim"}:
        raise ValueError("quarterly_financial_route_unverified")
    return f"{OPENAPI_BASE_URL}/t187ap{statement}_L_{sector}"


def quarterly_source_urls(statement, market, sector):
    primary = quarterly_url(statement, market, sector)
    if market == "L":
        return [primary, quarterly_openapi_url(statement, sector)]
    return [primary]


def _validate_quarterly_rows(rows, fields, today):
    if (not isinstance(fields, list) or len(fields) < 7 or len(fields) > 120
            or any(not isinstance(field, str) for field in fields)
            or len(set(fields)) != len(fields) or not set(IDENTITY_FIELDS).issubset(fields)
            or not isinstance(rows, list) or not 1 <= len(rows) <= 5000):
        raise ValueError("quarterly_financial_table_shape_unverified")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != set(fields)
                or any(not isinstance(value, str) for value in row.values())
                or not re.fullmatch(r"[0-9]{4,6}", row["公司代號"])
                or row["公司代號"] in seen or not 1 <= len(row["公司名稱"].strip()) <= 80
                or not re.fullmatch(r"[0-9]{7}", row["出表日期"])
                or not re.fullmatch(r"[0-9]{3}", row["年度"])
                or not re.fullmatch(r"[1-4]", row["季別"])):
            raise ValueError("quarterly_financial_row_identity_unverified")
        seen.add(row["公司代號"])
        issued = date(int(row["出表日期"][:3]) + 1911,
                      int(row["出表日期"][3:5]), int(row["出表日期"][5:]))
        year = int(row["年度"]) + 1911
        quarter = int(row["季別"])
        quarter_month = quarter * 3
        quarter_end = date(year, quarter_month,
                           (date(year + (quarter_month == 12), quarter_month % 12 + 1, 1)
                            - date.resolution).day)
        if issued > today or issued < quarter_end or year > today.year:
            raise ValueError("quarterly_financial_period_unverified")
    return rows, fields


def parse_quarterly_csv(raw, url, today):
    if (url not in {quarterly_url(s, m, c) for s in ("06", "07")
                    for m in ("L", "O") for c in ("ci", "basi", "fh", "ins", "bd", "mim")}
            or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES):
        raise ValueError("quarterly_financial_response_unverified")
    text = raw.decode("utf-8-sig", errors="strict")
    if "\ufffd" in text:
        raise ValueError("quarterly_financial_encoding_unverified")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    fields = reader.fieldnames
    rows = list(reader)
    return _validate_quarterly_rows(rows, fields, today)


def parse_quarterly_openapi_json(raw, url, today):
    allowed = {
        quarterly_openapi_url(statement, sector)
        for statement in ("06", "07") for sector in ("ci", "basi", "fh", "ins", "bd", "mim")
    }
    if (url not in allowed or not isinstance(raw, bytes)
            or not 0 < len(raw) <= OPENAPI_MAX_BYTES):
        raise ValueError("quarterly_financial_response_unverified")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_openapi_json_key")
            result[key] = value
        return result
    try:
        rows = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("quarterly_financial_json_unverified") from exc
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise ValueError("quarterly_financial_table_shape_unverified")
    fields = list(rows[0])
    return _validate_quarterly_rows(rows, fields, today)


def parse_quarterly_response(raw, url, today):
    if url.startswith(OPENAPI_BASE_URL + "/"):
        return parse_quarterly_openapi_json(raw, url, today)
    return parse_quarterly_csv(raw, url, today)


def _period_key(row, today):
    year = int(row["年度"]) + 1911
    quarter = int(row["季別"])
    current_quarter = (today.month - 1) // 3 + 1
    lag = (today.year - year) * 4 + current_quarter - quarter
    if lag < 0 or lag > 2:
        raise ValueError("quarterly_financial_period_stale_or_future")
    issued = date(int(row["出表日期"][:3]) + 1911,
                  int(row["出表日期"][3:5]), int(row["出表日期"][5:]))
    if (today - issued).days > 220:
        raise ValueError("quarterly_financial_observation_stale")
    return year, quarter, issued


def _numeric_row_field(row, names):
    for name in names:
        value = row.get(name)
        if isinstance(value, str) and NUMBER_RE.fullmatch(value.strip()):
            return name
    return None


def _select_record(rows, ticker, statement, today):
    code, _market_code = _market(ticker)
    matching = [row for row in rows if row["公司代號"] == code]
    if len(matching) != 1:
        raise ValueError("quarterly_financial_issuer_missing_or_ambiguous")
    row = matching[0]
    year, quarter, issued = _period_key(row, today)
    if statement == "07":
        summary_field = _numeric_row_field(row, ("資產總計", "資產總額"))
    else:
        summary_field = _numeric_row_field(row, (
            "本期淨利（淨損）", "本期稅後淨利（淨損）", "淨利（淨損）歸屬於母公司業主",
            "淨利（損）歸屬於母公司業主", "淨收益", "營業收入", "收益", "收入",
            "保險服務結果",
        ))
    if summary_field is None:
        raise ValueError("quarterly_financial_summary_fact_unavailable")
    period_end = date(year, quarter * 3,
                      (date(year + (quarter == 4), (quarter * 3) % 12 + 1, 1)
                       - date.resolution).day)
    return row, {"year": year, "quarter": quarter, "period_end": period_end.isoformat(),
                 "issued_on": issued.isoformat(), "summary_field": summary_field}


def project_latest_quarter(value, ticker):
    """Re-parse both archived official files before a supplemental snapshot is stored."""
    try:
        if (not isinstance(value, dict) or value.get("schema") != SCHEMA
                or value.get("policy") not in {POLICY, LEGACY_POLICY}
                or value.get("coverage_status") != "latest_quarter_only" or value.get("ticker") != ticker
                or value.get("income_period_basis") != "year_to_date_cumulative"
                or value.get("balance_period_basis") != "quarter_end_instant"
                or value.get("currency") != "TWD" or value.get("filed_unit") != "thousands"
                or value.get("scope") != "as_published_scope_not_independently_verified"
                or value.get("cash_flow_statement_available") is not False):
            return None
        code, market = _market(ticker)
        if value.get("issuer_code") != code or value.get("market_code") != market:
            return None
        sector = value.get("sector_code")
        if sector not in {"ci", "basi", "fh", "ins", "bd", "mim"}:
            return None
        tables = value.get("tables")
        if not isinstance(tables, dict) or set(tables) != {"balance_sheet", "income_statement_ytd"}:
            return None
        period = value.get("period")
        if not isinstance(period, dict) or type(period.get("year")) is not int or type(period.get("quarter")) is not int:
            return None
        selected = {}
        for key, statement in (("balance_sheet", "07"), ("income_statement_ytd", "06")):
            table = tables.get(key)
            if not isinstance(table, dict):
                return None
            source_url = table.get("source_url")
            if source_url not in quarterly_source_urls(statement, market, sector):
                return None
            expected_format = "twse_openapi_json" if source_url.startswith(OPENAPI_BASE_URL + "/") else "mopsfin_csv"
            if table.get("source_format") != expected_format:
                return None
            receipt = table.get("original_receipt")
            retrieved = receipt.get("retrieved_at") if isinstance(receipt, dict) else None
            if (type(retrieved) not in (int, float)
                    or not math.isfinite(retrieved) or not 0 <= time.time() - retrieved < FRESH_SECONDS
                    or receipt.get("status") != "archived" or receipt.get("http_status") != 200
                    or receipt.get("source_url") != source_url or receipt.get("historical_point_in_time_verified") is not False
                    or receipt.get("finality_guaranteed") is not False):
                return None
            raw = read_response(receipt, max_bytes=OPENAPI_MAX_BYTES)
            if (sha256(raw).hexdigest() != table.get("response_sha256")
                    or table.get("response_bytes") != len(raw)):
                return None
            rows, fields = parse_quarterly_response(raw, source_url, _today())
            row, row_period = _select_record(rows, ticker, statement, _today())
            if (row != table.get("row") or fields != table.get("columns")
                    or row_period != {key: table.get("period", {}).get(key) for key in row_period}):
                return None
            selected[key] = row_period
        if any(selected["balance_sheet"].get(key) != selected["income_statement_ytd"].get(key)
               for key in ("year", "quarter", "period_end")):
            return None
        if (period.get("year") != selected["balance_sheet"]["year"]
                or period.get("quarter") != selected["balance_sheet"]["quarter"]
                or period.get("period_end") != selected["balance_sheet"]["period_end"]):
            return None
        return value
    except (KeyError, ValueError, TypeError, OverflowError, OSError, EOFError):
        return None


def fetch_latest_quarter_result(ticker, data):
    started = time.time()
    with source_operation("financial_statements", PROVIDER):
        return _fetch_latest_quarter_result(ticker, data, started)


def _fetch_latest_quarter_result(ticker, data, started):
    from provider_correlation import current_audit_correlation

    audit = build_source_audit_entry("financial_statements", PROVIDER, "error", record_count=0,
                                     started_at_epoch=started, finished_at_epoch=started)
    audit.update(selection_policy=POLICY, coverage_status="latest_quarter_only", cache_hit=False,
                 stale=False, event_kind="aggregate", http_request_sent=False, http_request_count=0)
    http = None
    value = None
    try:
        code, market = _market(ticker)
        sector = _sector_code(data if isinstance(data, dict) else {})
        deadline = time.monotonic() + 10.0
        http = QuarterlyFinancialHttp(deadline)
        today = _today()
        tables = {}
        for key, statement in (("balance_sheet", "07"), ("income_statement_ytd", "06")):
            last_error = None
            for url in quarterly_source_urls(statement, market, sector):
                try:
                    raw, receipt = http.get(url)
                    rows, columns = parse_quarterly_response(raw, url, today)
                    row, period = _select_record(rows, ticker, statement, today)
                    break
                except Exception as exc:
                    last_error = exc
            else:
                raise last_error or ValueError("quarterly_financial_source_unavailable")
            tables[key] = {"source_url": url,
                           "source_format":"twse_openapi_json" if url.startswith(OPENAPI_BASE_URL + "/") else "mopsfin_csv",
                           "response_sha256": sha256(raw).hexdigest(),
                           "response_bytes": len(raw), "original_receipt": receipt,
                           "columns": columns, "row": row, "period": period,
                           "cache_hit": next((item.get("cache_hit") for item in http.components
                                              if item.get("url") == url), False)}
        if any(tables["balance_sheet"]["period"].get(key) != tables["income_statement_ytd"]["period"].get(key)
               for key in ("year", "quarter", "period_end")):
            raise ValueError("quarterly_financial_statement_period_mismatch")
        period = tables["balance_sheet"]["period"]
        value = {"schema": SCHEMA, "policy": POLICY, "coverage_status": "latest_quarter_only",
                 "ticker": ticker,
                 "issuer_code": code, "issuer_name": tables["balance_sheet"]["row"]["公司名稱"],
                 "market_code": market, "sector_code": sector,
                 "period": {key: period[key] for key in ("year", "quarter", "period_end")},
                 "income_period_basis": "year_to_date_cumulative",
                 "balance_period_basis": "quarter_end_instant",
                 "currency": "TWD", "filed_unit": "thousands",
                 "scope": "as_published_scope_not_independently_verified",
                 "cash_flow_statement_available": False, "tables": tables}
        if project_latest_quarter(value, ticker) is None:
            raise ValueError("quarterly_financial_receipt_or_identity_unverified")
        components = http.components
        cache_hit = bool(components) and all(item.get("cache_hit") is True for item in components)
        fetched_at = min(table["original_receipt"]["retrieved_at"] for table in tables.values())
        status = "skipped_fresh_cache" if cache_hit else "success"
        audit.update(status=status, record_count=1, ticker=ticker, issuer_code=code,
                     issuer_name=value["issuer_name"], sector_code=sector,
                     fiscal_year=period["year"], fiscal_quarter=period["quarter"],
                     period_end=period["period_end"], income_period_basis=value["income_period_basis"],
                     balance_period_basis=value["balance_period_basis"], currency="TWD", filed_unit="thousands",
                     source_urls=[table["source_url"] for table in tables.values()],
                     response_sha256=[table["response_sha256"] for table in tables.values()],
                     cache_hit=cache_hit, event_kind="cache_hit" if cache_hit else "aggregate",
                     fetched_at_epoch=fetched_at, fetched_at=iso_from_epoch(fetched_at),
                 message="只取得官方最新季末資產負債表及年初至季末累計損益；未取得現金流量表或五年年度序列。")
    except Exception as exc:
        audit.update(status="error", record_count=0,
                     error_kind=getattr(exc, "error_kind", type(exc).__name__),
                     message="官方最新季報來源未通過資料期間、公司代號或原始憑據核對。")
        value = None
    finally:
        components = http.components if http else []
        audit.update(transport_components=components,
                     http_request_sent=bool(http.http_request_count) if http else False,
                     http_request_count=http.http_request_count if http else 0,
                     duration_ms=max(0, round((time.time() - started) * 1000)))
        audit.update(current_audit_correlation())
    return {"value": value, "audit": audit}
