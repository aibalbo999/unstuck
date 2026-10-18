"""Official TPEx Market InfoHub index with checked MOPS announcement originals."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import re
import time
import unicodedata
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from search_provider_runtime import SourceResponseError

from .twse_history_transport import BoundedHistoryHttp
from .twse_company_history import _english_detail_fields, _english_detail_identity, _text


PROVIDER = "TPEx Market InfoHub company disclosures"
API_URL = "https://info.tpex.org.tw/api/stkInfo"
TAIPEI = ZoneInfo("Asia/Taipei")
MAX_INDEX_BYTES = 256_000
MAX_NEWS_ROWS = 10
MAX_DETAIL_FETCHES = 6
MAX_DETAIL_BYTES = 256_000
PARSER_VERSION = "tpex-infohub-company-disclosures-v1"
CONFERENCE_RE = re.compile(
    r"investor.?s? conference|analyst.?s? meeting|earnings\s+(?:call|meeting)|"
    r"results meeting|法人說明會|法人會議|法說會|法說", re.I
)
EVENT_DATE_RE = re.compile(
    r"(?:date of (?:institutional )?investor conference|date of conference|"
    r"date of earnings (?:meeting|call)|conference date|法說會日期|活動日期)"
    r"\s*[:：]\s*(20\d{2}/\d{1,2}/\d{1,2})", re.I
)
EVENT_TIME_RE = re.compile(
    r"(?:time of (?:institutional )?investor conference|time of conference|"
    r"time of earnings (?:meeting|call)|conference time|法說會時間|活動時間)"
    r"\s*[:：]\s*(\d{1,2}:\d{2})", re.I
)


def _ticker_code(ticker: str) -> str:
    match = re.fullmatch(r"([1-9]\d{3,5})\.TWO", str(ticker or "").strip().upper())
    if not match:
        raise ValueError("tpex_infohub_ticker_unverified")
    return match.group(1)


def infohub_api_url(ticker: str) -> str:
    code = _ticker_code(ticker)
    return f"{API_URL}?{urlencode({'query': code, 'lang': 'en-us'})}"


def _taipei_now(now: datetime | None) -> datetime:
    now = now or datetime.now(TAIPEI)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(TAIPEI)


def _parse_index_time(value: object) -> datetime | None:
    try:
        return datetime.strptime(str(value or "").strip(), "%Y/%m/%d %H:%M").replace(tzinfo=TAIPEI)
    except (TypeError, ValueError):
        return None


def _parse_detail_time(day: object, clock: object) -> datetime | None:
    try:
        return datetime.strptime(f"{str(day or '').strip()} {str(clock or '').strip()}",
                                 "%Y/%m/%d %H:%M:%S").replace(tzinfo=TAIPEI)
    except (TypeError, ValueError):
        return None


def _identity_key(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"[^A-Z0-9\u3400-\u9fff]", "", normalized)


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_infohub_json_key")
        result[key] = value
    return result


def _record_acquisition(source: str, started: float, details: dict, count: int) -> None:
    from search_provider_runtime import record_observation

    record_observation(PROVIDER, started, outcome="results" if count else "failure",
                       count=count, details=details, source=source,
                       sent=details.get("http_request_sent") is True)
    details["observation_recorded"] = True


def parse_infohub_index(payload: object, ticker: str, *, now: datetime | None = None) -> dict:
    """Validate InfoHub's exact TPEx issuer envelope and recent MOPS links."""
    code = _ticker_code(ticker)
    now = _taipei_now(now)
    if not isinstance(payload, dict):
        raise SourceResponseError("invalid_infohub_envelope")
    info = payload.get("info")
    rows = payload.get("news")
    if (not isinstance(info, dict) or str(info.get("stkNo") or "").strip() != code
            or not isinstance(info.get("name"), str) or not _text(info.get("name"))
            or len(_text(info.get("name"))) > 256
            or not isinstance(info.get("shortName"), str) or not _text(info.get("shortName"))
            or not isinstance(rows, list) or len(rows) > MAX_NEWS_ROWS):
        raise SourceResponseError("issuer_identity_mismatch")
    issuer_name = _text(info["name"])
    candidates, rejected, outside_window = [], 0, 0
    lower = now - timedelta(days=30)
    for row in rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        published = _parse_index_time(row.get("datetime"))
        title = _text(row.get("title"))
        url = row.get("link")
        if (published is None or not title or len(title) > 400
                or not _english_detail_identity(url, code, published)):
            rejected += 1
            continue
        if published < lower or published > now:
            outside_window += 1
            continue
        candidates.append({"ticker": ticker, "published_at": published.isoformat(),
                           "title": title, "source_url": url})
    candidates.sort(key=lambda row: row["published_at"], reverse=True)
    return {"issuer_name": issuer_name, "short_name": _text(info["shortName"]),
            "candidates": candidates[:MAX_DETAIL_FETCHES],
            "rejected_index_rows": rejected, "outside_window_rows": outside_window,
            "index_row_count": len(rows)}


def _event_fields(statement: str) -> tuple[str | None, str | None]:
    date_match = EVENT_DATE_RE.search(statement)
    time_match = EVENT_TIME_RE.search(statement)
    event_date = None
    event_time = None
    if date_match:
        try:
            event_date = datetime.strptime(date_match.group(1), "%Y/%m/%d").date().isoformat()
        except ValueError:
            pass
    if time_match:
        try:
            hour, minute = map(int, time_match.group(1).split(":"))
            if hour < 24 and minute < 60:
                event_time = f"{hour:02d}:{minute:02d}"
        except ValueError:
            pass
    return event_date, event_time


def parse_infohub_detail(html: str | bytes, ticker: str, issuer_name: str,
                         candidate: dict) -> dict:
    """Admit only a same-issuer, same-subject, same-minute MOPS original."""
    code = _ticker_code(ticker)
    if not isinstance(candidate, dict):
        raise SourceResponseError("infohub_candidate_invalid")
    published = datetime.fromisoformat(str(candidate.get("published_at") or ""))
    if published.tzinfo is None or not _english_detail_identity(
            candidate.get("source_url"), code, published.astimezone(TAIPEI)):
        raise SourceResponseError("infohub_detail_url_mismatch")
    try:
        header, fields = _english_detail_fields(html)
    except (TypeError, ValueError) as exc:
        raise SourceResponseError("infohub_detail_unrecognized") from exc
    announced = _parse_detail_time(fields.get("date of announcement"),
                                   fields.get("time of announcement"))
    subject = _text(fields.get("subject"))
    statement = str(fields.get("statement") or "").strip()
    if (not header or _identity_key(header) != _identity_key(issuer_name)
            or announced is None or announced.date() != published.date()
            or announced.strftime("%H:%M") != published.strftime("%H:%M")
            or _identity_key(subject) != _identity_key(candidate.get("title"))
            or len(statement) < 20 or "<" in statement or "\ufffd" in statement):
        raise SourceResponseError("infohub_detail_identity_or_content_mismatch")
    event_date, event_time = _event_fields(statement)
    is_conference = bool(CONFERENCE_RE.search(subject) or CONFERENCE_RE.search(statement))
    full_text = f"{issuer_name}（{code}） {subject}\n{statement}"
    return {"ticker": ticker, "date": event_date or announced.date().isoformat(),
            "published_at": announced.isoformat(), "announcement_date": announced.date().isoformat(),
            "title": subject, "summary": full_text[:1500], "text": full_text[:12_000],
            "source": PROVIDER, "publisher": "TPEx／公開資訊觀測站",
            "source_type": "official_disclosure", "link": candidate["source_url"],
            "source_url": candidate["source_url"], "issuer_identity_basis":
            "TPEx InfoHub exact issuer code + MOPS original issuer name, subject and timestamp",
            "content_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
            "content_coverage": "text_available", "transcript_available": False,
            "is_investor_conference": is_conference,
            "event_date": event_date, "event_time": event_time,
            "coverage_notes": ["僅取得 MOPS 公告原文；公告或會議資訊不代表取得逐字稿、簡報內容或影音。"]}


def fetch_tpex_infohub_records(ticker: str, *, now: datetime | None = None,
                               post=None, get=None, acquisition_source: str = "recent_catalysts",
                               observe: bool = True) -> tuple[list[dict], dict]:
    """Fetch at most six exact-issuer originals through TPEx InfoHub's index."""
    try:
        api_url = infohub_api_url(ticker)
    except ValueError:
        return [], {"status": "not_applicable", "record_count": 0,
                    "provider": PROVIDER, "parser_version": PARSER_VERSION,
                    "http_request_sent": False, "http_request_count": 0}
    now = _taipei_now(now)
    started = time.monotonic()
    deadline = started + 16.0
    http = BoundedHistoryHttp(deadline, provider=PROVIDER)
    injected = post is not None or get is not None
    request_count = 0
    post_impl = post or http.post
    get_impl = get or http.get

    def counted_post(url, **kwargs):
        nonlocal request_count
        request_count += 1
        return post_impl(url, **kwargs)

    def counted_get(url, **kwargs):
        nonlocal request_count
        request_count += 1
        return get_impl(url, **kwargs)
    details = {"provider": PROVIDER, "actual_provider": PROVIDER,
               "source_url": api_url, "parser_version": PARSER_VERSION,
               "coverage_status": "latest_10_index", "http_request_sent": False,
               "http_request_count": 0, "record_count": 0}
    candidates = []
    rejected = 0
    errors = []
    try:
        response = counted_post(api_url, data={})
        response.raise_for_status()
        raw = getattr(response, "content", b"")
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_INDEX_BYTES:
            raise SourceResponseError("infohub_index_size_invalid")
        try:
            payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_json_object)
        except (TypeError, UnicodeDecodeError, ValueError) as exc:
            raise SourceResponseError("infohub_index_json_invalid") from exc
        parsed = parse_infohub_index(payload, ticker, now=now)
        candidates = parsed["candidates"]
        rejected = parsed["rejected_index_rows"]
        details.update(issuer_name=parsed["issuer_name"], index_row_count=parsed["index_row_count"],
                       outside_window_rows=parsed["outside_window_rows"],
                       rejected_index_rows=rejected)
    except Exception as exc:
        kind = getattr(exc, "error_kind", type(exc).__name__)
        count = request_count if injected else http.http_request_count
        details.update(status="error", error_kind=kind,
                       http_request_count=count,
                       http_request_sent=count > 0,
                       source_response_observations=list(http.request_observations),
                       message="TPEx InfoHub 索引取得或驗證失敗。")
        if observe:
            _record_acquisition(acquisition_source, started, details, 0)
        return [], details

    records = []
    for candidate in candidates:
        try:
            response = counted_get(candidate["source_url"])
            response.raise_for_status()
            raw = getattr(response, "content", b"")
            if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_DETAIL_BYTES:
                raise SourceResponseError("infohub_detail_size_invalid")
            records.append(parse_infohub_detail(raw, ticker, parsed["issuer_name"], candidate))
        except Exception as exc:
            errors.append(getattr(exc, "error_kind", type(exc).__name__))
        if time.monotonic() >= deadline:
            errors.append("timeout")
            break
    transport_count = request_count if injected else http.http_request_count
    has_rejected = rejected > 0 or bool(errors)
    if records:
        status = "degraded_enrichment" if has_rejected else "success"
        message = "已核對 TPEx InfoHub 最近公告索引中的 MOPS 原文；十筆索引不保證涵蓋完整三十日窗口。"
    else:
        status = "degraded_enrichment"
        message = "TPEx InfoHub 最近十筆索引未回傳可核對的三十日內公告；不代表沒有公告。"
    details.update(status=status, error_kind=(errors[0] if errors else
                    "infohub_index_rows_rejected" if rejected else
                    "does_not_prove_no_recent_disclosures" if not records else None),
                    record_count=len(records), detail_attempt_count=len(candidates),
                    detail_errors=errors, http_request_count=transport_count,
                    http_request_sent=transport_count > 0,
                    source_response_observations=list(http.request_observations),
                    fetched_at_epoch=time.time(), duration_ms=max(0, int((time.monotonic()-started)*1000)),
                    message=message)
    if observe:
        _record_acquisition(acquisition_source, started, details, len(records))
    return records, details


def fetch_tpex_infohub_earnings_call(ticker: str, *, now: datetime | None = None,
                                     post=None, get=None) -> tuple[dict, dict]:
    """Return a verified conference invitation notice, never a transcript claim."""
    started = time.monotonic()
    records, details = fetch_tpex_infohub_records(
        ticker, now=now, post=post, get=get, acquisition_source="earnings_call", observe=False)
    selected = next((row for row in records if row.get("is_investor_conference")
                     and row.get("event_date")), None)
    if not selected:
        details = {**details, "status": "degraded_enrichment", "record_count": 0,
                   "error_kind": details.get("error_kind") or "no_verified_conference_notice",
                   "coverage_status": "official_notice_only",
                   "message": "TPEx InfoHub 最近公告沒有可核對的法說會通知；不代表沒有法說資料。"}
        if details.get("status") != "not_applicable":
            _record_acquisition("earnings_call", started, details, 0)
        return {}, details
    context = {"ticker": ticker, "date": selected["event_date"],
               "period": selected["event_date"], "title": selected["title"],
               "summary": selected["text"], "transcript_excerpt": "",
               "transcript_available": False, "materials": [],
               "source": PROVIDER, "source_url": selected["source_url"],
               "coverage_status": "official_notice_text_only",
               "coverage_notes": list(selected["coverage_notes"]),
               "conference_notice": selected}
    details.update(status="success", record_count=1,
                   coverage_status="official_notice_text_only",
                   event_date=selected["event_date"], event_time=selected.get("event_time"),
                   message="已核對 TPEx 公司法說會通知與 MOPS 原文；未取得逐字稿、簡報內容或影音。")
    _record_acquisition("earnings_call", started, details, 1)
    return context, details
