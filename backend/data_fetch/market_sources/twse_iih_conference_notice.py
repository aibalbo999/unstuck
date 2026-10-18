"""Official TWSE investor-conference notice text, without downloading materials."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import re
import time
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from search_provider_runtime import SourceResponseError, record_observation
from .twse_history_transport import BoundedHistoryHttp

PROVIDER = "TWSE IIH/MOPS official conference notice"
MONTH_INDEX_PROVIDER = "TWSE IIH/MOPS monthly conference index"
INDEX_URL = "https://wwwc.twse.com.tw/rwd/en/IIH/company/events"
NOTE = "只取得交易所法說會公告文字與場次日期；未取得或驗證逐字稿、簡報或影音，不代表完整會議內容。"
_TAIPEI = ZoneInfo("Asia/Taipei")
_CODE = re.compile(r"\d{4,6}\Z")
_NOTICE_KEYS = {"isNew", "seq_no", "spoke_time", "spoke_date", "co_id"}


def _ticker_code(ticker: str) -> str:
    code = str(ticker or "").strip().upper().removesuffix(".TW")
    if not _CODE.fullmatch(code):
        raise SourceResponseError("invalid_ticker")
    return code


def _date(value: object) -> date | None:
    raw = str(value or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _name_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9\u3400-\u9fff]", "", str(value or "").upper())


def _issuer_name_key(value: object) -> str:
    """Treat the official Corporation/Corp. terminal-name variants as equivalent."""
    key = _name_key(value)
    if key.endswith("CORPORATION"):
        return key[:-len("CORPORATION")] + "CORP"
    return key


def _clean_cell(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _validated_notice_url(raw: object, code: str, announcement_date: date) -> tuple[str, dict] | None:
    if not isinstance(raw, str) or len(raw) > 2048:
        return None
    try:
        parsed = urlsplit(raw)
        query_text = parsed.query[1:] if parsed.query.startswith("&") else parsed.query
        pairs = parse_qsl(query_text, keep_blank_values=False, strict_parsing=True)
    except ValueError:
        return None
    query = dict(pairs)
    if (parsed.scheme != "https" or parsed.hostname != "emops.twse.com.tw"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.path != "/server-java/t05sr01_1_e" or parsed.fragment
            or len(query) != len(pairs) or set(query) - _NOTICE_KEYS
            or not {"seq_no", "spoke_time", "spoke_date", "co_id"}.issubset(query)
            or query.get("isNew", "Y") != "Y" or query.get("co_id") != code
            or not re.fullmatch(r"\d{1,6}", query.get("seq_no", ""))
            or not re.fullmatch(r"\d{6}", query.get("spoke_time", ""))
            or _date(query.get("spoke_date")) != announcement_date):
        return None
    return raw, query


def _validated_month_index_url(raw: object, code: str, announced: date) -> tuple[str, dict] | None:
    if not isinstance(raw, str) or len(raw) > 2048:
        return None
    try:
        parsed = urlsplit(raw)
        pairs = parse_qsl(parsed.query, keep_blank_values=False, strict_parsing=True)
        port = parsed.port
    except (TypeError, ValueError):
        return None
    query = dict(pairs)
    year, month = query.get("LPSHOW_DATE_YY", ""), query.get("LPSHOW_DATE_MM", "")
    if (parsed.scheme != "https" or parsed.hostname != "emops.twse.com.tw"
            or port not in (None, 443) or parsed.username or parsed.password
            or parsed.path != "/server-java/t100sb07_1_e" or parsed.fragment
            or len(query) != len(pairs)
            or set(query) != {"TYPEK", "step", "code", "LPSHOW_DATE_YY", "LPSHOW_DATE_MM"}
            or query.get("TYPEK") != "all" or query.get("step") != "show"
            or query.get("code") != code or not re.fullmatch(r"20\d{2}", year)
            or not re.fullmatch(r"0[1-9]|1[0-2]", month)
            or (int(year), int(month)) != (announced.year, announced.month)):
        return None
    return raw, query


def parse_iih_candidates(payload: object, ticker: str, *, today: date | None = None) -> dict:
    """Validate the issuer envelope and select official MOPS notices and month pages."""
    code = _ticker_code(ticker)
    today = today or datetime.now(_TAIPEI).date()
    try:
        info = payload["info"]["data"]
        conferences = payload["conference"]
    except (TypeError, KeyError):
        raise SourceResponseError("invalid_iih_envelope") from None
    issuer_name = str(info.get("name") or "").strip() if isinstance(info, dict) else ""
    short_name = str(info.get("shortName") or "").strip() if isinstance(info, dict) else ""
    envelope = payload.get("info") if isinstance(payload, dict) else None
    if (not isinstance(payload, dict) or not isinstance(envelope, dict)
            or envelope.get("status") != "success"
            or not isinstance(info, dict) or str(info.get("code") or "").strip() != code
            or not issuer_name or not isinstance(conferences, list)):
        raise SourceResponseError("issuer_identity_mismatch")

    candidates = []
    month_candidates = []
    for row in conferences:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject") or "").strip()
        announced = _date(row.get("date"))
        if (str(row.get("companyId") or "").strip() == code
                and str(row.get("companyName") or "").strip()
                and announced is not None and announced <= today):
            month_url = _validated_month_index_url(row.get("link"), code, announced)
            period = re.search(r"\b(20\d{2})\s*/\s*(0?[1-9]|1[0-2])\s+Investor Conferences?\b", subject, re.I)
            if month_url and period and (int(period.group(1)), int(period.group(2))) == (announced.year, announced.month):
                month_candidates.append({
                    "ticker": code + ".TW", "issuer_name": issuer_name,
                    "company_name": str(row.get("companyName") or "").strip(),
                    "subject": subject, "announcement_date": announced.isoformat(),
                    "year": int(month_url[1]["LPSHOW_DATE_YY"]),
                    "month": int(month_url[1]["LPSHOW_DATE_MM"]),
                    "month_index_url": month_url[0],
                })
        row_name = _name_key(row.get("companyName"))
        issuer_key = _name_key(issuer_name)
        short_key = _name_key(short_name)
        row_identity_matches = (row_name == issuer_key or bool(short_key and row_name == short_key)
                                or bool(issuer_key and issuer_key in _name_key(subject)))
        if (str(row.get("companyId") or "").strip() != code
                or not row_identity_matches
                or not re.search(r"conference|analyst.?s? meeting|法說|法人說明會", subject, re.I)):
            continue
        if announced is None or announced > today:
            continue
        validated = _validated_notice_url(row.get("link"), code, announced)
        if not validated:
            continue
        notice_url, query = validated
        candidates.append({
            "ticker": code + ".TW", "issuer_name": issuer_name,
            "subject": subject, "announcement_date": announced.isoformat(),
            "announcement_time": str(row.get("time") or "").strip(),
            "sequence": query["seq_no"], "notice_url": notice_url,
        })
    candidates.sort(key=lambda item: (item["announcement_date"], item["sequence"]), reverse=True)
    month_candidates.sort(key=lambda item: (item["year"], item["month"], item["announcement_date"]), reverse=True)
    return {"issuer_name": issuer_name, "candidates": candidates,
            "month_candidates": month_candidates}


def _cell_value(soup: BeautifulSoup, label: str) -> str:
    wanted = re.sub(r"[^a-z0-9]", "", label.lower())
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        for index, cell in enumerate(cells[:-1]):
            current = re.sub(r"[^a-z0-9]", "", cell.get_text(" ", strip=True).lower())
            if current == wanted:
                return cells[index + 1].get_text(" ", strip=True)
    return ""


def _decode_page(value: str | bytes) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, bytes) or not 0 < len(value) <= 256_000:
        raise SourceResponseError("notice_page_size_invalid")
    for encoding in ("utf-8-sig", "big5", "cp950"):
        try:
            return value.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
    raise SourceResponseError("notice_page_encoding_invalid")


def parse_notice_page(html: str | bytes, *, ticker: str, issuer_name: str,
                      candidate: dict, now: datetime | None = None) -> dict:
    """Extract and cross-check actual MOPS notice text; never implies a transcript."""
    code = _ticker_code(ticker)
    raw = _decode_page(html)
    if len(raw) > 256_000:
        raise SourceResponseError("notice_page_size_invalid")
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text("\n", strip=True)
    provided = re.search(r"Provided\s+by\s*:\s*([^\n]+)", text, re.I)
    actual_issuer = provided.group(1).strip() if provided else ""
    page_subject = _cell_value(soup, "Subject")
    announcement_date = _date(_cell_value(soup, "Date of announcement"))
    announcement_time = _cell_value(soup, "Time of announcement")
    sequence = _cell_value(soup, "SEQ_NO")
    event_date = _date(_cell_value(soup, "Date of events"))
    statement = _cell_value(soup, "Statement")
    now = now or datetime.now(_TAIPEI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_TAIPEI)
    expected_date = _date(candidate.get("announcement_date"))
    expected_time = str(candidate.get("announcement_time") or "").strip()
    url = str(candidate.get("notice_url") or "")
    validated = _validated_notice_url(url, code, expected_date) if expected_date else None
    if (not validated or not actual_issuer or _name_key(actual_issuer) != _name_key(issuer_name)
            or announcement_date != expected_date or sequence != str(candidate.get("sequence") or "")
            or (expected_time and announcement_time and announcement_time[:5] != expected_time[:5])
            or _name_key(page_subject) != _name_key(candidate.get("subject"))
            or not event_date or event_date > now.date()
            or not re.search(r"conference|analyst.?s? meeting|法說|法人說明會", page_subject, re.I)
            or len(statement) < 20):
        raise SourceResponseError("official_notice_identity_or_content_mismatch")

    event_time = ""
    for pattern in (
        r"(?:time\s+of\s+institutional\s+investor\s+conference|time\s+of\s+(?:the\s+)?(?:conference|event))\s*[:：]\s*(\d{1,2}:\d{2})",
        r"(?:法說會時間|活動時間)\s*[:：]\s*(\d{1,2}:\d{2})",
    ):
        match = re.search(pattern, statement, re.I)
        if match:
            hour, minute = map(int, match.group(1).split(":"))
            if hour < 24 and minute < 60:
                event_time = f"{hour:02d}:{minute:02d}"
                break
    return {
        "ticker": code + ".TW", "announcement_date": announcement_date.isoformat(),
        "event_date": event_date.isoformat(), "event_time": event_time,
        "title": page_subject, "statement": statement,
        "transcript_available": False,
        "coverage_status": "official_notice_text_only",
        "source_url": url,
    }


def parse_month_index_page(html: str | bytes, *, ticker: str, issuer_name: str,
                           candidate: dict, today: date | None = None) -> list[dict]:
    """Extract completed company events and exact MOPS presentation links."""
    code = _ticker_code(ticker)
    raw = _decode_page(html)
    if len(raw.encode("utf-8")) > 256_000:
        raise SourceResponseError("conference_month_page_size_invalid")
    if re.search(r"FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|因為安全性考量|驗證碼|captcha|access denied", raw, re.I):
        raise SourceResponseError("access_denied")
    validated = _validated_month_index_url(candidate.get("month_index_url"), code,
                                           _date(candidate.get("announcement_date"))) if _date(candidate.get("announcement_date")) else None
    if (not validated or validated[1].get("LPSHOW_DATE_YY") != str(candidate.get("year"))
            or validated[1].get("LPSHOW_DATE_MM") != f"{int(candidate.get('month') or 0):02d}"):
        raise SourceResponseError("conference_month_candidate_mismatch")
    today = today or datetime.now(_TAIPEI).date()
    soup = BeautifulSoup(raw, "html.parser")
    recognized_table = None
    for table in soup.find_all("table"):
        headers = _name_key(table.get_text(" ", strip=True))
        if "CODE" in headers and "COMPANYNAME" in headers and "INVESTORCONFERENCE" in headers:
            recognized_table = table
            break
    if recognized_table is None:
        raise SourceResponseError("conference_month_page_unrecognized")

    rows = recognized_table.find_all("tr")
    event_rows = []
    for index, row in enumerate(rows):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != 5:
            continue
        market = _clean_cell(cells[0].get_text(" ", strip=True)).lower()
        row_code = _clean_cell(cells[1].get_text(" ", strip=True))
        company = _clean_cell(cells[2].get_text(" ", strip=True))
        date_text = _clean_cell(cells[3].get_text(" ", strip=True))
        event_date = _date(date_text)
        if not event_date or row_code != code:
            continue
        if (market not in {"listed company", "上櫃公司", "上市公司"}
                or _issuer_name_key(company) != _issuer_name_key(issuer_name)
                or event_date.year != int(candidate["year"])
                or event_date.month != int(candidate["month"])):
            raise SourceResponseError("conference_month_issuer_or_period_mismatch")
        materials = []
        for following in rows[index + 1:]:
            next_cells = following.find_all(["td", "th"], recursive=False)
            if len(next_cells) == 5 and _clean_cell(next_cells[1].get_text(" ", strip=True)):
                break
            for anchor in following.find_all("a", href=True):
                href = str(anchor.get("href") or "")
                match = re.fullmatch(rf"/nas/STR/{re.escape(code)}(\d{{8}})([ME])(\d{{3}})\.pdf", href)
                if not match:
                    continue
                file_date = _date(match.group(1))
                if file_date is None or file_date > today:
                    continue
                materials.append({
                    "label": "英文簡報檔案" if match.group(2) == "E" else "中文簡報檔案",
                    "url": "https://emops.twse.com.tw" + href,
                })
        event_rows.append({
            "ticker": code + ".TW", "company_name": company,
            "date": event_date.isoformat(), "time": _clean_cell(cells[4].get_text(" ", strip=True)),
            "title": f"{company} Investor Conference", "summary": "",
            "materials": materials, "source": MONTH_INDEX_PROVIDER,
            "source_url": candidate["month_index_url"],
        })
    if not event_rows:
        return []
    return sorted((row for row in event_rows if row["date"] <= today.isoformat()),
                  key=lambda row: row["date"], reverse=True)


def fetch_twse_iih_conference_notice(ticker: str, *, diagnostics: dict | None = None,
                                    now: datetime | None = None) -> dict:
    """Fetch a verified IIH notice or the official event-month presentation index."""
    diagnostics = diagnostics if diagnostics is not None else {}
    started = time.monotonic()
    deadline = started + 12.0
    http = BoundedHistoryHttp(deadline)
    code = _ticker_code(ticker)
    details = {"actual_provider": PROVIDER, "http_request_sent": False,
               "http_request_count": 0, "coverage_status": "official_notice_text_only"}
    try:
        response = http.get(INDEX_URL, params={"code": code})
        payload = response.json()
        parsed = parse_iih_candidates(payload, code + ".TW", today=(now or datetime.now(_TAIPEI)).date())
        if not parsed["candidates"] and not parsed["month_candidates"]:
            details.update(status="degraded_enrichment", record_count=0,
                           message="官方 IIH 沒有可核對的已公告法說會場次。")
            diagnostics.update(details, http_request_count=http.http_request_count,
                               http_request_sent=http.http_request_count > 0)
            record_observation(PROVIDER, started, outcome="valid_empty", count=0,
                               details=details, source="earnings_call", sent=http.http_request_count > 0)
            return {}
        month_errors = []
        for month_candidate in parsed["month_candidates"][:3]:
            try:
                month_page = http.get(month_candidate["month_index_url"])
                records = parse_month_index_page(
                    month_page.content, ticker=code + ".TW", issuer_name=parsed["issuer_name"],
                    candidate=month_candidate,
                    today=(now or datetime.now(_TAIPEI)).date(),
                )
                if records:
                    selected = records[0]
                    month_digest = sha256(month_page.content).hexdigest()
                    provider_details = {
                        **details, "actual_provider": MONTH_INDEX_PROVIDER,
                        "status": "success", "record_count": 1,
                        "announcement_date": month_candidate["announcement_date"],
                        "event_date": selected["date"], "source_url": month_candidate["month_index_url"],
                        "coverage_status": "official_monthly_event_metadata_with_material_links" if selected["materials"] else "official_monthly_event_metadata",
                        "monthly_page_response_sha256": month_digest,
                        "presentation_link_count": len(selected["materials"]),
                        "source_response_observations": [
                            {key: item.get(key) for key in (
                                "url", "http_status", "http_status_observed", "response_complete",
                                "response_bytes", "response_sha256", "response_retrieved_at_epoch")}
                            for item in getattr(http, "request_observations", [])
                        ],
                        "fetched_at_epoch": time.time(),
                        "http_request_count": http.http_request_count,
                        "http_request_sent": http.http_request_count > 0,
                        "message": "只核對已完成場次的 MOPS 月頁及簡報連結；未下載或解析簡報內容、未宣稱取得逐字稿。",
                    }
                    notice = {**selected, "transcript_excerpt": "", "transcript_available": False,
                              "coverage_status": provider_details["coverage_status"],
                              "coverage_notes": [NOTE],
                              "monthly_page_response_sha256": month_digest}
                    diagnostics.update(provider_details)
                    record_observation(MONTH_INDEX_PROVIDER, started, outcome="results", count=1,
                                       details=provider_details, source="earnings_call",
                                       sent=http.http_request_count > 0)
                    return notice
            except SourceResponseError as exc:
                month_errors.append({"event_month": f"{month_candidate['year']}-{month_candidate['month']:02d}",
                                     "status": "error", "error_kind": exc.error_kind,
                                     **exc.diagnostic})
                if time.monotonic() >= deadline:
                    break
        if not parsed["candidates"]:
            if month_errors:
                details.update(status="error", error_kind=month_errors[-1]["error_kind"],
                               component_statuses={"MOPS_month_index": month_errors},
                               http_request_count=http.http_request_count,
                               http_request_sent=http.http_request_count > 0)
                diagnostics.update(details)
                record_observation(PROVIDER, started, outcome="failure", count=0,
                                   details=details, source="earnings_call", sent=http.http_request_count > 0)
                raise SourceResponseError(details["error_kind"], **{
                    key: value for key, value in month_errors[-1].items()
                    if key in {"status_code", "parser_version"}
                })
            details.update(status="degraded_enrichment", record_count=0,
                           component_statuses={"MOPS_month_index": {"status": "valid_empty"}},
                           http_request_count=http.http_request_count,
                           http_request_sent=http.http_request_count > 0,
                           message="官方月頁未列出已完成法說場次；不推論沒有公告或資料。")
            diagnostics.update(details)
            record_observation(PROVIDER, started, outcome="valid_empty", count=0,
                               details=details, source="earnings_call", sent=http.http_request_count > 0)
            return {}
        candidate = parsed["candidates"][0]
        page = http.get(candidate["notice_url"])
        notice = parse_notice_page(page.content, ticker=code + ".TW",
                                   issuer_name=parsed["issuer_name"], candidate=candidate, now=now)
        if time.monotonic() >= deadline:
            raise SourceResponseError("timeout")
        context = {
            "ticker": code + ".TW", "date": notice["event_date"],
            "period": notice["event_date"], "title": notice["title"],
            "summary": notice["statement"], "transcript_excerpt": "",
            "transcript_available": False, "materials": [],
            "source": PROVIDER, "source_url": notice["source_url"],
            "coverage_notes": [NOTE], "coverage_status": notice["coverage_status"],
            "notice_response_sha256": sha256(page.content).hexdigest(),
            "conference_notice": notice,
        }
        details.update(status="success", record_count=1,
                       announcement_date=notice["announcement_date"],
                       event_date=notice["event_date"],
                       source_url=notice["source_url"],
                       notice_response_sha256=sha256(page.content).hexdigest(),
                       source_response_observations=[
                           {key: item.get(key) for key in (
                               "url", "http_status", "http_status_observed", "response_complete",
                               "response_bytes", "response_sha256", "response_retrieved_at_epoch")}
                           for item in getattr(http, "request_observations", [])
                       ],
                       fetched_at_epoch=time.time(),
                       http_request_count=http.http_request_count,
                       http_request_sent=http.http_request_count > 0,
                       message=NOTE)
        diagnostics.update(details)
        record_observation(PROVIDER, started, outcome="results", count=1,
                           details=details, source="earnings_call", sent=http.http_request_count > 0)
        return context
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError("parse_error")
        details.update(status="error", error_kind=exc.error_kind,
                       http_request_count=http.http_request_count,
                       http_request_sent=http.http_request_count > 0)
        diagnostics.update(details)
        record_observation(PROVIDER, started, outcome="failure", count=0,
                           details=details, source="earnings_call", sent=http.http_request_count > 0)
        if exc is original:
            exc.diagnostic.update(details)
            raise
        raise exc from original
