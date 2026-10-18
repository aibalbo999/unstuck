"""MOPS investor-conference metadata adapter."""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from io import StringIO
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd
from bs4 import BeautifulSoup

from external_http_client import sync_post
from search_provider_runtime import SourceResponseError, scope_key, cooldown_state, remember_failure, remember_success, record_observation


LOGGER = logging.getLogger(__name__)
MOPS_BASE_URL = "https://mopsov.twse.com.tw"
MOPS_INVESTOR_CONFERENCE_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1"
CONFERENCE_PARSER_VERSION = "mops-conference-v3"
# The MOPS conference response can exceed 384 KiB and time out after a partial
# HTTP 200 at 15s. Keep connection establishment bounded while allowing the
# buffered response enough time to finish before the shared endpoint cooldown.
REQUEST_TIMEOUT = (5, 30)
MONTHLY_REQUEST_TIMEOUT = (3, 12)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}
CONFERENCE_ALIASES = {
    "ticker": ("公司代號", "股票代號", "co_id"),
    "company_name": ("公司名稱", "公司簡稱"),
    "date": ("召開法人說明會日期", "法人說明會日期", "召開日期", "日期"),
    "time": ("召開法人說明會時間", "法人說明會時間", "召開時間", "時間"),
    "location": ("召開法人說明會地點", "法人說明會地點", "地點"),
    "summary": ("相關資訊", "說明", "備註", "其他應敘明事項"),
    "presentation": ("簡報檔案", "簡報", "簡報資料", "簡報下載"),
    "video": ("影音連結", "影音資訊", "影音", "完整影音連結"),
}


def fetch_mops_investor_conference_events(
    ticker: str,
    *,
    year: int | None = None,
    month: int | str | None = None,
    limit: int = 3,
    session: Any | None = None,
    use_cache: bool = False,
    force_refresh: bool = False,
    diagnostics: dict | None = None,
) -> list[dict[str, Any]]:
    """Fetch free MOPS investor-conference metadata and material links."""
    month_int = None
    if month is not None:
        if isinstance(month, bool):
            raise ValueError("invalid MOPS conference month")
        try:
            month_int = int(month)
        except (TypeError, ValueError):
            raise ValueError("invalid MOPS conference month") from None
        if not 1 <= month_int <= 12:
            raise ValueError("invalid MOPS conference month")
    if use_cache and session is None:
        from mops_conference_cache import fetch_cached_events
        return fetch_cached_events(ticker, year=year, limit=limit,
                                   month=month_int, force_refresh=force_refresh, diagnostics=diagnostics)
    return _fetch_uncached_events(ticker, year=year, month=month_int, limit=limit,
                                  session=session, diagnostics=diagnostics)


def _fetch_uncached_events(ticker, *, year=None, month=None, limit=3, session=None,
                           source_capture=None, diagnostics=None):
    diagnostics = diagnostics if diagnostics is not None else {}
    if month is not None:
        if isinstance(month, bool):
            raise ValueError("invalid MOPS conference month")
        try:
            month = int(month)
        except (TypeError, ValueError):
            raise ValueError("invalid MOPS conference month") from None
        if not 1 <= month <= 12:
            raise ValueError("invalid MOPS conference month")
    month_int = month
    symbol, typek = _mops_symbol_and_type(ticker)
    if symbol is None:
        return []
    year_int = int(year) if year is not None else date.today().year
    data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": typek,
        "co_id": symbol,
        "year": str(year_int - 1911),
        "month": f"{int(month):02d}" if month is not None else "",
    }
    started = time.monotonic()
    # The public MOPS mirror has an independent admission boundary from the
    # security-rejected mops.twse.com.tw endpoint used by older workers.
    # A single-month response is much smaller than the annual page and gets an
    # independent retry window; repeating the same monthly query still cools
    # down normally.
    endpoint_scope = ("mopsov_investor_conference_monthly" if month is not None
                     else "mopsov_investor_conference")
    cooldown_key = scope_key("MOPS", endpoint=endpoint_scope)
    issuer_cooldown_key = scope_key("MOPS", endpoint=f"{endpoint_scope}:{symbol}")
    shared_blocked = cooldown_state(cooldown_key) if session is None else {}
    # A partial body timeout on the public annual page is issuer-specific. Old
    # releases stored it under the shared endpoint key, so ignore only that
    # legacy shape while keeping endpoint-wide access/rate/server guards intact.
    legacy_http_200_timeout = (
        shared_blocked.get("error_kind") == "timeout"
        and shared_blocked.get("http_status") == 200
    )
    blocked = cooldown_state(issuer_cooldown_key) if session is None else {}
    if not blocked and not legacy_http_200_timeout:
        blocked = shared_blocked
    if blocked:
        diagnostics.update(blocked, status="unavailable", http_request_sent=False,
                           http_request_count=0, source_query_year=year_int,
                           source_query_month=month_int)
        record_observation("MOPS", started, outcome="cooldown", source="earnings_call", details=blocked, sent=False)
        raise SourceResponseError(blocked.get("error_kind", "cooldown"), status_code=blocked.get("http_status"), parser_version=CONFERENCE_PARSER_VERSION)
    if legacy_http_200_timeout:
        diagnostics["legacy_shared_http_200_timeout_ignored"] = True
    request_started_at = time.time()
    try:
        response = _http_post(
            MOPS_INVESTOR_CONFERENCE_URL,
            data=data,
            session=session,
            headers=HEADERS,
            timeout=MONTHLY_REQUEST_TIMEOUT if month is not None else REQUEST_TIMEOUT,
            provider="MOPS",
        )
    except Exception as exc:
        exc_diagnostic = getattr(exc, "diagnostic", {})
        exc_status = getattr(exc, "status_code", None)
        if exc_status is None:
            exc_status = getattr(getattr(exc, "response", None), "status_code", None)
        if exc_status is None and isinstance(exc_diagnostic, dict):
            exc_status = exc_diagnostic.get("http_status")
        exc_kind = getattr(exc, "error_kind", None)
        if not exc_kind and "timeout" in type(exc).__name__.lower():
            exc_kind = "timeout"
        issuer_partial_timeout = (
            exc_kind == "timeout" and exc_status == 200
        )
        failure_key = issuer_cooldown_key if issuer_partial_timeout else cooldown_key
        details = remember_failure(failure_key, exc) if session is None else {}
        diagnostics.update(details, status="error", http_request_sent=True,
                           http_request_count=1, source_query_year=year_int,
                           source_query_month=month_int)
        record_observation("MOPS", started, outcome="failure", source="earnings_call", details=details)
        raise SourceResponseError(details.get("error_kind", "transport_error"), status_code=details.get("http_status"), parser_version=CONFERENCE_PARSER_VERSION) from exc
    text = str(response.text or "")
    if re.search(r"FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|因為安全性考量|驗證碼|captcha|access denied", text, re.IGNORECASE):
        exc = SourceResponseError("access_denied", status_code=getattr(response, "status_code", None), response_text=text, parser_version=CONFERENCE_PARSER_VERSION)
        if session is None:
            remember_failure(cooldown_key, exc)
        diagnostics.update(exc.diagnostic, status="error", http_request_sent=True,
                           http_request_count=1, source_query_year=year_int,
                           source_query_month=month_int)
        record_observation("MOPS", started, outcome="failure", source="earnings_call", details=exc.diagnostic)
        raise exc
    stamp = time.time()
    try:
        records = parse_conference_response(text, symbol, http_status=getattr(response, 'status_code', None))
    except SourceResponseError as exc:
        if session is None:
            remember_failure(cooldown_key, exc)
        diagnostics.update(exc.diagnostic, status="error", http_request_sent=True,
                           http_request_count=1, source_query_year=year_int,
                           source_query_month=month_int)
        record_observation('MOPS', started, outcome='failure', source='earnings_call', details=exc.diagnostic)
        raise
    if source_capture is not None:
        source_capture.update(raw=getattr(response, 'content', None), text=text,
                              encoding=getattr(response, 'encoding', None),
                              http_status=getattr(response, 'status_code', None),
                              fetched_at_epoch=stamp, records=records)
    if session is None and getattr(response, 'status_code', None) == 200:
        remember_success(cooldown_key, request_started_at=request_started_at)
        remember_success(issuer_cooldown_key, request_started_at=request_started_at)
    outcome = "results" if records else "valid_empty"
    details = {"parser_version": CONFERENCE_PARSER_VERSION,
               "http_status": getattr(response, "status_code", None),
               "source_query_year": year_int, "source_query_month": month_int,
               "http_request_sent": True, "http_request_count": 1,
               "fetched_at_epoch": stamp, "status": "success" if records else "degraded_enrichment",
               "record_count": len(records)}
    diagnostics.update(details)
    record_observation("MOPS", started, outcome=outcome, source="earnings_call", count=len(records), details=details)
    return records[: max(1, int(limit or 3))]


def parse_conference_response(text, symbol, *, http_status=None):
    """Replay the same native page selection; no HTTP or acquisition telemetry."""
    if re.search(r"FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|因為安全性考量|驗證碼|captcha|access denied", text, re.IGNORECASE):
        raise SourceResponseError('access_denied', status_code=http_status, parser_version=CONFERENCE_PARSER_VERSION)
    local_now = datetime.now(ZoneInfo('Asia/Taipei'))
    today = local_now.date().isoformat()
    list_records = _parse_conference_list(text, symbol, today=today)
    detail_records = _parse_conference_detail(text, symbol) if list_records is None else None
    recognized_page = list_records is not None or detail_records is not None
    frames = []
    if not recognized_page:
        try:
            frames = pd.read_html(StringIO(text))
        except (ImportError, ValueError):
            frames = []
        except Exception as exc:
            _warn("MOPS", "investor conference tables", exc)
            frames = []
    parsed_records = _dedupe_conference_records(
        (list_records or []) + (detail_records or []) +
        (_parse_conference_html(text, symbol) + _parse_conference_frames(frames, symbol)
         if not recognized_page else [])
    )
    if not parsed_records and not recognized_page and not re.search(r"查無(?:符合條件之|符合條件的|所需)?資料|沒有符合條件|無符合條件|no data", BeautifulSoup(text, "lxml").get_text(" ", strip=True), re.IGNORECASE):
        raise SourceResponseError("parse_error", status_code=http_status, response_text=text, parser_version=CONFERENCE_PARSER_VERSION)
    # The current day's scheduled time can still be in the future. Keep that
    # announcement distinct from a past-start event; an unknown current-day
    # time cannot establish that its start has passed.
    def past_start(row):
        if row['date'] != today:
            return row['date'] < today
        clock = re.fullmatch(r'([01]\d|2[0-3]):([0-5]\d)', str(row.get('time') or '').strip())
        return bool(clock and tuple(map(int, clock.groups())) <= (local_now.hour, local_now.minute))
    return [row for row in parsed_records if past_start(row)]


def _http_post(
    url: str,
    *,
    data: dict[str, str],
    session: Any | None,
    headers: dict[str, str],
    timeout: Any,
    provider: str,
):
    if session is not None:
        response = session.post(url, data=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    return sync_post(url, data=data, headers=headers, timeout=timeout, provider=provider)


def _parse_conference_frames(frames: list[pd.DataFrame], symbol: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for frame in frames:
        records.extend(_frame_conference_rows(frame, symbol))
    records.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
    return records


def _parse_conference_html(html: str, symbol: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(str(html or ""), "lxml")
    records: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
        if not headers:
            continue
        for table_row in rows[1:]:
            cells = table_row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            row = {}
            for index, cell in enumerate(cells):
                key = headers[index] if index < len(headers) else f"col_{index}"
                value = _clean_text(cell.get_text(" ", strip=True))
                links = [_absolute_mops_url(anchor.get("href")) for anchor in cell.find_all("a", href=True)]
                row[key] = next((link for link in links if link), value)
            record = _conference_record_from_row(row, symbol)
            if record:
                records.append(record)
    records.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
    return records


def _parse_conference_detail(html: str, symbol: str) -> list[dict[str, Any]] | None:
    """Read the public mirror's labeled detail table and exact official PDFs."""
    soup = BeautifulSoup(str(html or ""), "lxml")
    root = soup.select_one("#div01")
    if root is None:
        return None

    def header_value(label: str) -> str:
        for tag in root.find_all("b"):
            if _clean_label(tag.get_text()) != label:
                continue
            parts = []
            for sibling in tag.next_siblings:
                if getattr(sibling, "name", None) in {"b", "br", "table", "form"}:
                    break
                parts.append(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
            return _clean_text(" ".join(parts))
        return ""

    if header_value("公司代號：") != symbol:
        return None
    company_name = header_value("公司名稱：")
    records = []
    for table in root.select("table.hasBorder"):
        rows = table.find_all("tr")
        date_text = ""
        location = ""
        summary = ""
        materials = []
        for row in rows:
            cells = row.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            label = _clean_label(" ".join(cell.get_text(" ", strip=True) for cell in cells[:-1]))
            value = cells[-1]
            if "召開法人說明會日期：" in label:
                date_text = value.get_text(" ", strip=True)
            elif "召開法人說明會地點：" in label:
                location = _clean_text(value.get_text(" ", strip=True))
            elif "法人說明會擇要訊息：" in label:
                summary = _clean_text(value.get_text(" ", strip=True))
            elif "中文檔案：" in label or "英文檔案：" in label:
                kind = "中文" if "中文檔案：" in label else "英文"
                links = [str(a.get("href") or "") for a in value.find_all("a", href=True)]
                valid = [href for href in links if re.fullmatch(
                    rf"/nas/STR/{re.escape(symbol)}\d{{8}}{'M' if kind == '中文' else 'E'}\d{{3}}\.pdf", href)]
                if len(valid) == 1:
                    materials.append({"label": kind + "簡報檔案", "url": urljoin(MOPS_BASE_URL, valid[0])})
        event_date = _normalize_conference_date(date_text)
        if not event_date:
            continue
        records.append({
            "ticker": symbol, "company_name": company_name, "date": event_date,
            "time": "", "location": location, "title": f"{company_name or symbol} 法人說明會",
            "summary": summary, "materials": materials, "source": "MOPS investor conference",
            "source_url": MOPS_INVESTOR_CONFERENCE_URL,
        })
    return sorted(records, key=lambda row: row["date"], reverse=True)


def _parse_conference_list(html: str, symbol: str, *, today: str) -> list[dict[str, Any]] | None:
    """Read the mirror's yearly company rows, including completed past events."""
    soup = BeautifulSoup(str(html or ""), "lxml")
    file_path = soup.select_one('input[name="filePath"]')
    if file_path is None or file_path.get("value") != "/home/html/nas/STR/":
        return None
    records = []
    recognized_table = False
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows or "公司代號" not in rows[0].get_text(" ", strip=True) or "召開法人說明會日期" not in rows[0].get_text(" ", strip=True):
            continue
        recognized_table = True
        for row in rows[1:]:
            cells = row.find_all("td", recursive=False)
            if len(cells) < 8 or _clean_text(cells[0].get_text(" ", strip=True)) != symbol:
                continue
            date_text = cells[2].get_text(" ", strip=True)
            event_date = _normalize_conference_date(date_text)
            # A multi-day roadshow is completed only after its last listed day.
            dates = re.findall(r"\d{2,4}[/.\-]\d{1,2}[/.\-]\d{1,2}", date_text)
            end_date = _normalize_conference_date(dates[-1]) if dates else event_date
            if not event_date or not end_date or end_date > today:
                continue
            materials = []
            for index, language, marker in ((6, "中文", "M"), (7, "英文", "E")):
                valid = []
                for anchor in cells[index].find_all("a", href=True):
                    filename = _clean_text(anchor.get_text(" ", strip=True))
                    if (anchor.get("href") == "#" and re.fullmatch(
                            rf"{re.escape(symbol)}\d{{8}}{marker}\d{{3}}\.pdf", filename)):
                        valid.append(filename)
                if len(valid) == 1:
                    date_digits = valid[0][len(symbol):len(symbol) + 8]
                    material_date = _normalize_conference_date(
                        f"{date_digits[:4]}-{date_digits[4:6]}-{date_digits[6:]}"
                    )
                    material_label = language + "簡報檔案"
                    if material_date and material_date != event_date:
                        material_label += f"（{material_date}）"
                    materials.append({"label": material_label,
                                      "url": MOPS_BASE_URL + "/nas/STR/" + valid[0]})
            company_name = _clean_text(cells[1].get_text(" ", strip=True))
            records.append({
                "ticker": symbol, "company_name": company_name, "date": event_date,
                "time": _clean_text(cells[3].get_text(" ", strip=True)),
                "location": _clean_text(cells[4].get_text(" ", strip=True)),
                "title": f"{company_name or symbol} 法人說明會",
                "summary": _clean_text(cells[5].get_text(" ", strip=True)),
                "materials": materials, "source": "MOPS investor conference",
                "source_url": MOPS_INVESTOR_CONFERENCE_URL,
            })
    return sorted(records, key=lambda record: record["date"], reverse=True) if recognized_table else None


def _dedupe_conference_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in sorted(records, key=lambda row: str(row.get("date") or ""), reverse=True):
        key = (str(record.get("date") or ""), str(record.get("title") or ""))
        if key in seen:
            continue
        kept.append(record)
        seen.add(key)
    return kept


def _frame_conference_rows(frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    work = frame.copy()
    work.columns = [_flatten_column(column) for column in work.columns]
    rows = []
    for _, row in work.iterrows():
        record = _conference_record_from_row(row.to_dict(), symbol)
        if record:
            rows.append(record)
    return rows


def _conference_record_from_row(row: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    row_symbol = _field_text(row, CONFERENCE_ALIASES["ticker"])
    if row_symbol and row_symbol != symbol:
        return None
    event_date = _normalize_conference_date(_field_text(row, CONFERENCE_ALIASES["date"]))
    if not event_date:
        return None
    company_name = _field_text(row, CONFERENCE_ALIASES["company_name"])
    materials = []
    presentation = _field_text(row, CONFERENCE_ALIASES["presentation"])
    video = _field_text(row, CONFERENCE_ALIASES["video"])
    if _looks_like_url(presentation):
        materials.append({"label": "簡報檔案", "url": presentation})
    if _looks_like_url(video):
        materials.append({"label": "影音連結", "url": video})
    title_name = company_name or symbol
    return {
        "ticker": symbol,
        "company_name": company_name,
        "date": event_date,
        "time": _field_text(row, CONFERENCE_ALIASES["time"]),
        "location": _field_text(row, CONFERENCE_ALIASES["location"]),
        "title": f"{title_name} 法人說明會",
        "summary": _field_text(row, CONFERENCE_ALIASES["summary"]),
        "materials": materials,
        "source": "MOPS investor conference",
        "source_url": MOPS_INVESTOR_CONFERENCE_URL,
    }


def _field_text(row: dict[str, Any], aliases: tuple[str, ...]) -> str:
    alias_keys = {_normalize_key(alias) for alias in aliases}
    for key, value in row.items():
        if _normalize_key(key) in alias_keys:
            text = _clean_text(value)
            if text:
                return text
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan" or text in {"-", "--"}:
        return ""
    return re.sub(r"\s+", " ", text)


def _normalize_conference_date(value: str) -> str:
    text = _clean_text(value).replace("/", "-").replace(".", "-")
    match = re.search(r"(\d{2,4})-(\d{1,2})-(\d{1,2})", text)
    if not match:
        return ""
    year = int(match.group(1))
    if year < 1911:
        year += 1911
    month = int(match.group(2))
    day = int(match.group(3))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _looks_like_url(value: str) -> bool:
    return bool(re.match(r"https?://", str(value or "").strip(), re.IGNORECASE))


def _absolute_mops_url(value: Any) -> str:
    text = _clean_text(value)
    if not text or text.startswith("#") or text.lower().startswith("javascript:"):
        return ""
    return urljoin(MOPS_BASE_URL, text)


def _mops_symbol_and_type(ticker: Any) -> tuple[str | None, str | None]:
    raw = str(ticker or "").strip()
    if "." in raw:
        symbol, suffix = raw.split(".", 1)
        suffix = suffix.upper()
        if suffix == "TW":
            typek = "sii"
        elif suffix == "TWO":
            typek = "otc"
        else:
            return None, None
    else:
        symbol = raw
        typek = "sii"
    return (symbol, typek) if re.fullmatch(r"\d{4,6}", symbol) else (None, None)


def _flatten_column(column: Any) -> str:
    if isinstance(column, tuple):
        return " ".join(str(part) for part in column if str(part) != "nan")
    return str(column)


def _clean_label(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _normalize_key(value: Any) -> str:
    return _clean_label(value).replace("　", "").lower()


def _warn(provider: str, operation: str, exc: BaseException | None = None) -> None:
    kind = exc.__class__.__name__ if exc else "Unavailable"
    LOGGER.warning("%s %s failed [%s]", provider, operation, kind)
