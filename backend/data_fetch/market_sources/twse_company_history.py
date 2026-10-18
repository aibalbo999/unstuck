"""Public TWSE company-history announcements with checked MOPS original text.

IIH's latest-ten index expands through EZSearch and the public monthly MOPS
index. Every admitted record still needs a checked original announcement.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import re
import time
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

INDEX_URL = "https://wwwc.twse.com.tw/rwd/zh/IIH/company/events"
EN_INDEX_URL = "https://wwwc.twse.com.tw/rwd/en/IIH/company/events"
PROVIDER = "TWSE company announcement history"
PARSER_VERSION = "twse-company-history-v3"
TAIPEI = ZoneInfo("Asia/Taipei")
MAX_INDEX_BYTES = 256_000
MAX_DETAIL_BYTES = 256_000
MAX_DETAIL_FETCHES = 10
MAX_EZ_DETAIL_FETCHES = 30
MAX_MONTHLY_DETAIL_FETCHES = 64
FETCH_BUDGET_SECONDS = 20


def _roc_day(value: str):
    match = re.fullmatch(r"(\d{3})/(\d{2})/(\d{2})", str(value or "").strip())
    if not match:
        raise ValueError("invalid ROC day")
    return datetime(int(match[1]) + 1911, int(match[2]), int(match[3]), tzinfo=TAIPEI)


def _english_day(value: str):
    match = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", str(value or "").strip())
    if not match:
        raise ValueError("invalid English IIH day")
    return datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=TAIPEI)


def _detail_identity(url: str, stock_id: str, published: datetime) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "mopsov.twse.com.tw" or parsed.port is not None:
        return False
    if parsed.path != "/mops/web/ajax_t05sr01_1":
        return False
    params = parse_qs(parsed.query, keep_blank_values=True)
    for key in ("COMPANY_ID", "SPOKE_DATE", "SPOKE_TIME", "SEQ_NO"):
        if len(params.get(key, [])) != 1:
            return False
    return (params["COMPANY_ID"][0] == stock_id
            and params["SPOKE_DATE"][0] == published.strftime("%Y%m%d")
            and re.fullmatch(r"\d{1,6}", params["SPOKE_TIME"][0]) is not None
            and re.fullmatch(r"\d+", params["SEQ_NO"][0]) is not None
            and int(params["SEQ_NO"][0]) > 0)


def _english_detail_identity(url: str, stock_id: str, published: datetime) -> bool:
    try:
        parsed = urlsplit(url)
        query_text = parsed.query[1:] if parsed.query.startswith("&") else parsed.query
        params = parse_qs(query_text, keep_blank_values=False, strict_parsing=True)
        if (parsed.scheme != "https" or parsed.hostname != "emops.twse.com.tw" or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.path != "/server-java/t05sr01_1_e"
                or parsed.fragment or set(params) != {"isNew", "seq_no", "spoke_time", "spoke_date", "co_id"}
                or any(len(values) != 1 for values in params.values())):
            return False
        stamp = params["spoke_time"][0].zfill(6)
        hour, minute, second = int(stamp[:2]), int(stamp[2:4]), int(stamp[4:])
        return (params["isNew"][0] == "Y" and params["co_id"][0] == stock_id
                and params["spoke_date"][0] == published.strftime("%Y%m%d")
                and re.fullmatch(r"\d{1,6}", params["spoke_time"][0]) is not None
                and stamp[:4] == published.strftime("%H%M")
                and hour < 24 and minute < 60 and second < 60
                and re.fullmatch(r"\d{1,6}", params["seq_no"][0]) is not None
                and int(params["seq_no"][0]) > 0)
    except (TypeError, ValueError, OverflowError):
        return False


def _announcement_key(url):
    params = parse_qs(urlsplit(url).query)
    if "COMPANY_ID" in params:
        return (params["COMPANY_ID"][0], params["SPOKE_DATE"][0],
                params["SPOKE_TIME"][0].zfill(6), int(params["SEQ_NO"][0]))
    return (params["co_id"][0], params["spoke_date"][0],
            params["spoke_time"][0].zfill(6), int(params["seq_no"][0]))


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _detail_fields(html: str) -> tuple[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one("table.noBorder .compName")
    table = soup.select_one("table.hasBorder")
    if header is None or table is None:
        raise ValueError("missing MOPS announcement table")
    fields = {}
    for row in table.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        for index in range(len(cells) - 1):
            if cells[index].name == "th" and cells[index + 1].name == "td":
                key = _text(cells[index].get_text(" ", strip=True))
                if key:
                    fields[key] = cells[index + 1].get_text("\n", strip=True).strip()
    return _text(header.get_text(" ", strip=True)), fields


def _english_detail_fields(html: str) -> tuple[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.title.get_text(" ", strip=True) if soup.title else "").casefold()
    if title != "today's information":
        raise ValueError("unknown English MOPS announcement page")
    header = None
    fields = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        values = [_text(cell.get_text(" ", strip=True)) for cell in cells]
        if len(values) == 1 and values[0].startswith("Provided by:"):
            header = _text(values[0][len("Provided by:"):])
        for index in range(0, len(cells) - 1):
            label = values[index].rstrip(":").casefold()
            if label in {"date of announcement", "time of announcement", "subject", "statement"}:
                fields[label] = cells[index + 1].get_text("\n", strip=True).strip()
    if not header or not {"date of announcement", "time of announcement", "subject", "statement"} <= fields.keys():
        raise ValueError("missing English MOPS announcement fields")
    return header, fields


def _listed_header_matches(header: str, stock_id: str, company: str) -> bool:
    # Token equality matters: neither 非上市公司 nor a longer company name
    # containing the expected abbreviation establishes this issuer's market.
    if header.startswith('本資料由'):
        wrapper = re.fullmatch(r'本資料由\s*(.+?)\s+公司提供', header)
        if not wrapper:
            return False
        header = wrapper[1]
    match = re.fullmatch(r"[(（]\s*上市公司\s*[)）]\s+(\d+)\s+(.+)", header)
    return bool(match and match[1] == stock_id and match[2] == company)


def _iih_names(payload, stock_id):
    info = payload.get('info') if isinstance(payload, dict) else None
    data = info.get('data') if isinstance(info, dict) else None
    if (not isinstance(data, dict) or info.get('status') != 'success'
            or str(data.get('code')) != stock_id):
        raise ValueError('native IIH issuer mismatch')
    names = []
    for key in ('shortName', 'name'):
        value = data.get(key)
        # Historical IIH fixtures and some responses omit these fields. The
        # row + exact detail header remains required; no name is fabricated.
        if key in data and (not isinstance(value, str) or not _text(value)):
            raise ValueError('native IIH name invalid')
        names.append(_text(value) if value is not None else None)
    return tuple(names)


def _english_iih_name(payload, stock_id):
    info = payload.get("info") if isinstance(payload, dict) else None
    data = info.get("data") if isinstance(info, dict) else None
    name = _text(data.get("name")) if isinstance(data, dict) else ""
    if (not isinstance(data, dict) or info.get("status") != "success"
            or str(data.get("code")) != stock_id or not name or len(name) > 256
            or not isinstance(payload.get("news"), list) or len(payload["news"]) > 10):
        raise ValueError("native English IIH issuer mismatch")
    return name


def fetch_recent_company_announcements(ticker: str, *, now: datetime | None = None, get=None, post=None) -> tuple[list[dict], dict]:
    """Return checked 30-day announcements, expanding an incomplete ten-item index."""
    ticker = str(ticker or "").strip().upper()
    if not re.fullmatch(r"[1-9]\d{3,5}\.TW", ticker):
        return [], {"status": "not_applicable", "record_count": 0, "parser_version": PARSER_VERSION}
    now = now or datetime.now(TAIPEI)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(TAIPEI)
    deadline = time.monotonic() + FETCH_BUDGET_SECONDS
    from .twse_history_transport import BoundedHistoryHttp
    transport = BoundedHistoryHttp(deadline)
    injected = get is not None or post is not None
    get = get or transport.get
    post = post or transport.post
    from .mops_json_company_history import TICKERS, fetch_json_announcements
    if ticker in TICKERS:
        records, diagnostic = fetch_json_announcements(ticker, now=now, post=post, deadline=deadline)
        if not injected:
            diagnostic.update(http_request_sent=transport.http_request_count > 0,
                              http_request_count=transport.http_request_count)
        return records, diagnostic
    if ticker == "9103.TW":
        from .tdr_mops_history import fetch_tdr_announcements
        records, diagnostic = fetch_tdr_announcements(ticker, now=now, get=get, post=post, deadline=deadline)
        if not injected:
            diagnostic.update(http_request_sent=transport.http_request_count > 0,
                              http_request_count=transport.http_request_count)
        return records, diagnostic
    from official_announcement_source_refresh import supports as supports_ordinary
    index_originals = []
    if supports_ordinary(ticker) and not injected:
        from official_announcement_source_refresh import archive_index_response
        native_get, native_post = get, post

        def capture(call, method, url, **kwargs):
            response = call(url, **kwargs)
            from .twse_history_transport import IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL
            if url in {IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL}:
                index_originals.append(archive_index_response(response, method, url, kwargs, deadline=deadline, ticker=ticker))
            return response

        get = lambda url, **kwargs: capture(native_get, "GET", url, **kwargs)
        post = lambda url, **kwargs: capture(native_post, "POST", url, **kwargs)
    stock_id = ticker.split(".", 1)[0]
    rejected = Counter()
    diagnostic = {"status": "unavailable", "record_count": 0, "parser_version": PARSER_VERSION,
                  "index_url": INDEX_URL, "index_limit": 10, "detail_limit": MAX_DETAIL_FETCHES,
                  "coverage_status": "partial", "rejected_reason_counts": {}}
    payload = None
    index_short_name = None
    index_english_name = None
    index_language = "zh"
    primary_refused = None
    try:
        response = get(INDEX_URL, params={"code": stock_id}, timeout=(5, 15), provider=PROVIDER)
        response.raise_for_status()
        if len(response.content) > MAX_INDEX_BYTES:
            raise ValueError("oversized issuer history")
        payload = response.json()
        if (not isinstance(payload, dict) or payload.get("info", {}).get("status") != "success"
                or str(payload.get("info", {}).get("data", {}).get("code")) != stock_id
                or not isinstance(payload.get("news"), list) or len(payload["news"]) > 10):
            raise ValueError("issuer history envelope mismatch")
        try:
            index_short_name, _ = _iih_names(payload, stock_id)
        except ValueError:
            primary_refused = 'issuer_identity_conflict'
            raise
    except Exception as exc:
        # EZSearch is an independent official issuer/date index. A failed IIH
        # request must not prevent it from recovering checked MOPS originals.
        diagnostic.update(primary_index_status="error", primary_index_error_kind=type(exc).__name__,
                          primary_index_transport_error_kind=getattr(exc, "error_kind", type(exc).__name__))
        status = getattr(getattr(exc, "response", None), "status_code", getattr(exc, "status_code", None))
        if status in {401, 403, 429} or status and status >= 500 or getattr(exc, "error_kind", "") == "cooldown":
            primary_refused = getattr(exc, "error_kind", "") or f"http_{status}"
        payload = None
        if primary_refused is None and time.monotonic() < deadline:
            from .twse_history_transport import IIH_EN_URL
            try:
                english_response = get(IIH_EN_URL, params={"code": stock_id}, timeout=(5, 15), provider=PROVIDER)
                english_response.raise_for_status()
                if len(english_response.content) > MAX_INDEX_BYTES:
                    raise ValueError("oversized English issuer history")
                english_payload = english_response.json()
                index_english_name = _english_iih_name(english_payload, stock_id)
                payload = english_payload
                index_language = "en"
                diagnostic.update(english_index_status="success", english_index_name=index_english_name,
                                  index_url=IIH_EN_URL, index_language="en")
            except Exception as english_exc:
                diagnostic.update(english_index_status="error",
                                  english_index_error_kind=getattr(english_exc, "error_kind", type(english_exc).__name__))
                payload = None
    candidates = []
    index_dates = []
    for row in payload["news"] if payload is not None else []:
        if not isinstance(row, dict) or str(row.get("companyId")) != stock_id:
            rejected["issuer_mismatch"] += 1
            continue
        try:
            published = _english_day(row.get("date")) if index_language == "en" else _roc_day(row.get("date"))
            clock = re.fullmatch(r"(\d{1,2}):(\d{2})", str(row.get("time") or "").strip())
            if not clock:
                raise ValueError("missing time")
            published = published.replace(hour=int(clock[1]), minute=int(clock[2]))
        except (ValueError, TypeError):
            rejected["invalid_publication_time"] += 1
            continue
        index_dates.append(published)
        if not now - timedelta(days=30) <= published <= now:
            rejected["outside_window"] += 1
            continue
        link = str(row.get("link") or "").strip()
        valid_detail_link = (_english_detail_identity(link, stock_id, published) if index_language == "en"
                             else _detail_identity(link, stock_id, published))
        if not valid_detail_link:
            rejected["invalid_detail_url"] += 1
            continue
        title = _text(row.get("subject"))
        row_company = _text(row.get("companyName"))
        company = index_english_name if index_language == "en" else row_company
        if not title or not row_company or not company:
            rejected["missing_subject_or_company"] += 1
            continue
        candidates.append((published, title, company, link))
    window_covered = (payload is not None and
                      (len(index_dates) < 10 or bool(index_dates and min(index_dates) <= now - timedelta(days=30))))
    detail_limit = MAX_DETAIL_FETCHES
    added_links = set()
    index_refused = primary_refused
    if not window_covered and not index_refused:
        from .twse_ezsearch_history import fetch_ezsearch_candidates
        if time.monotonic() < deadline:
            expanded, expansion = fetch_ezsearch_candidates(stock_id, now=now, post=post)
        else:
            expanded, expansion = [], {"status": "error", "coverage_status": "partial", "error_kind": "timeout"}
        diagnostic["ezsearch"] = expansion
        refusal_status = expansion.get("http_status")
        if refusal_status in {401, 403, 429} or refusal_status and refusal_status >= 500 or expansion.get("error_kind") == "cooldown":
            index_refused = expansion.get("error_kind") or f"http_{refusal_status}"
        # A crowded issuer's monthly official index is independent of EZSearch's
        # 30-candidate safety cap. Do not merely raise that cap or claim that ten
        # checked originals cover the missing part of the window.
        if (expansion.get("candidate_count", 0) > MAX_EZ_DETAIL_FETCHES
                and not expansion.get("rejected_reason_counts") and not index_refused and time.monotonic() < deadline):
            from .twse_json_history import fetch_monthly_candidates
            monthly, monthly_audit = fetch_monthly_candidates(stock_id, now=now, post=post, deadline=deadline)
            diagnostic["monthly_index"] = monthly_audit
            refusal_status = monthly_audit.get("http_status")
            if refusal_status in {401, 403, 429} or refusal_status and refusal_status >= 500 or monthly_audit.get("error_kind") == "cooldown":
                index_refused = monthly_audit.get("error_kind") or f"http_{refusal_status}"
            known = {_announcement_key(item[3]) for item in candidates + expanded}
            monthly_keys = {_announcement_key(item[3]) for item in monthly}
            if (monthly_audit.get("coverage_status") == "window_complete" and known <= monthly_keys
                    and len(monthly) == expansion["candidate_count"]):
                expanded = monthly
                expansion = {**monthly_audit, "candidate_source": "monthly_index"}
            elif monthly_audit.get("coverage_status") == "window_complete":
                monthly_audit.update(coverage_status="partial", status="degraded_enrichment", index_disagreement=True)
        original_links = {item[3] for item in candidates}
        expanded_links = {item[3] for item in expanded}
        original_keys = {_announcement_key(url) for url in original_links}
        expanded_keys = {_announcement_key(url) for url in expanded_links}
        expansion_detail_limit = (MAX_MONTHLY_DETAIL_FETCHES if expansion.get("candidate_source") == "monthly_index"
                                  else MAX_EZ_DETAIL_FETCHES)
        if payload is None:
            # Each EZSearch candidate has issuer, market, date and URL checks;
            # admit checked originals even when the index is only partial.
            candidates = expanded
            added_links = expanded_links
            window_covered = expansion.get("coverage_status") == "window_complete"
            detail_limit = expansion_detail_limit
        elif expansion.get("coverage_status") == "window_complete" and original_keys <= expanded_keys:
            added_links = expanded_links - original_links
            candidates = list({_announcement_key(item[3]): item for item in (candidates + expanded)}.values())
            window_covered = True
            detail_limit = expansion_detail_limit
        elif original_keys - expanded_keys:
            diagnostic["ezsearch"]["coverage_status"] = "partial"
            diagnostic["ezsearch"]["index_disagreement_count"] = len(original_keys - expanded_keys)
    diagnostic["detail_limit"] = detail_limit
    if index_short_name is not None:
        mismatched = [item for item in candidates if item[2] != index_short_name]
        if mismatched:
            rejected['issuer_name_mismatch'] += len(mismatched)
            candidates = [item for item in candidates if item[2] == index_short_name]
    from . import twse_announcement_progress as progress
    records, accepted, detail_observations = [], [], []
    permanent_detail_failure = False
    detail_attempts = 0
    if index_refused:
        diagnostic["detail_stop_reason"] = index_refused
        rejected["upstream_refused"] += 1
    for published, title, company, link in sorted(candidates, reverse=True)[:detail_limit]:
        if index_refused:
            break
        if time.monotonic() >= deadline:
            rejected["deadline_exhausted"] += 1
            break
        detail_attempts += 1
        started, request_count = time.monotonic(), transport.http_request_count
        cached, original = False, None
        detail_observation = {"url": link, "request_fingerprint": progress.request_fingerprint("GET", link),
                              "status": "error", "error_kind": None, "cache_hit": False,
                              "http_status": None}
        detail_observations.append(detail_observation)
        try:
            detail = None if injected else progress.read_qualified(link, deadline=deadline)
            cached = detail is not None
            detail = detail if cached else get(link, timeout=(5, 15), provider=PROVIDER)
            detail_observation.update(cache_hit=cached, http_status=None if cached else detail.status_code)
            detail.raise_for_status()
            if len(detail.content) > MAX_DETAIL_BYTES:
                raise ValueError("oversized MOPS detail")
            english_detail = urlsplit(link).path == "/server-java/t05sr01_1_e"
            if english_detail:
                header, fields = _english_detail_fields(detail.text)
                detail_date = datetime.strptime(_text(fields["date of announcement"]), "%Y/%m/%d").date()
                detail_time = _text(fields["time of announcement"])
                observed = datetime.fromisoformat(f"{detail_date.isoformat()}T{detail_time}").replace(tzinfo=TAIPEI)
                body = fields["statement"].strip()
                detail_title = _text(fields["subject"])
                detail_company_matches = header.casefold() == company.casefold()
                detail_clock = parse_qs(urlsplit(link).query)["spoke_time"][0].zfill(6)
            else:
                header, fields = _detail_fields(detail.text)
                detail_date = _roc_day(fields.get("發言日期"))
                detail_time = str(fields.get("發言時間") or "").strip()
                observed = datetime.fromisoformat(f"{detail_date.date().isoformat()}T{detail_time}").replace(tzinfo=TAIPEI)
                body = fields.get("說明", "").strip()
                detail_title = _text(fields.get("主旨"))
                detail_company_matches = _listed_header_matches(header, stock_id, company)
                detail_clock = parse_qs(urlsplit(link).query)["SPOKE_TIME"][0].zfill(6)
            if (not detail_company_matches
                    or detail_title != title
                    or observed.replace(second=0, microsecond=0) != published.replace(second=0, microsecond=0)
                    or observed.strftime("%H%M%S") != detail_clock
                    or len(body) < 20):
                raise ValueError("MOPS detail identity, time or body mismatch")
            if not injected:
                original = progress.qualify(detail, deadline=deadline)
                if cached:
                    original = progress.recheck(original, deadline=deadline, cached=True)
            detail_observation["status"] = "cache_hit" if cached else "success"
        except Exception as exc:
            reason = "detail_mismatch" if isinstance(exc, ValueError) else getattr(exc, "error_kind", type(exc).__name__)
            detail_observation["error_kind"] = reason
            permanent_detail_failure |= reason not in {"timeout", "transport_error", "ConnectError", "ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout"}
            rejected["detail_mismatch" if isinstance(exc, ValueError) else "detail_fetch_error"] += 1
            status = getattr(getattr(exc, "response", None), "status_code",
                             getattr(exc, "status_code", detail_observation["http_status"]))
            detail_observation["http_status"] = status
            if status in {401, 403, 429} or status and status >= 500 or getattr(exc, "error_kind", "") == "cooldown":
                diagnostic["detail_stop_reason"] = getattr(exc, "error_kind", "") or f"http_{status}"
                break
            continue
        finally:
            detail_observation.update(http_request_count=transport.http_request_count-request_count if not injected else None,
                                      elapsed_seconds=max(0., time.monotonic()-started),
                                      remaining_seconds=max(0., deadline-time.monotonic()))
        if time.monotonic() >= deadline:
            detail_observation.update(status="error", error_kind="timeout")
            rejected["deadline_exhausted"] += 1
            break
        full_text = f"{company}（{stock_id}） {title}\n{body}"
        if len(full_text) > 12_000:
            rejected["content_truncated"] += 1
        records.append({"date": observed.isoformat(), "published_at": observed.isoformat(),
                        "title": title, "summary": full_text[:1500], "text": full_text[:12_000],
                        "source": PROVIDER, "publisher": "臺灣證券交易所／公開資訊觀測站",
                        "source_type": "official_disclosure", "link": link,
                        "ticker": ticker,
                        "issuer_identity_basis": ("TWSE English company ID + English MOPS detail header"
                                                  if urlsplit(link).path == "/server-java/t05sr01_1_e"
                                                  else "TWSE company ID + MOPS detail header"),
                        "catalyst_assessment": "not_assessed",
                        "content_coverage": "partial" if len(full_text) > 12_000 else "text_available",
                        "content_truncated": len(full_text) > 12_000,
                        "content_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest()})
        from official_event_identity import bind_collected_event
        bind_collected_event(records[-1])
        accepted.append((records[-1], original, cached))
    if not injected:
        # Retain prior verified bodies on a timed-out partial, but never extend
        # their original or shorter physical cache expiry at the final handoff.
        kept, originals = [], []
        for record, original, cached in accepted:
            if original is None:
                kept.append(record)
                continue
            try:
                current, reusable = progress.current_admission(original, cached=cached)
                originals.append({**current, "cache_hit":cached, "reusable":reusable})
                kept.append(record)
            except Exception:
                rejected["original_expired_or_unavailable"] += 1
                permanent_detail_failure = True
        records = kept
        # No local paths/receipts are inserted into public news record text.
        diagnostic.update(source_record_archive=deepcopy(originals),
                          request_observations=deepcopy(transport.request_observations))
        expired = {item["url"] for item in originals if time.time() >= item["fresh_until_epoch"]}
        if expired:
            records = [r for r in records if r["link"] not in expired]
            originals = [item for item in originals if item["url"] not in expired]
            diagnostic["source_record_archive"] = originals
            rejected["original_expired_or_unavailable"] += len(expired)
            permanent_detail_failure = True
        until = min((item["fresh_until_epoch"] for item in originals), default=None)
        old = sum(item["cache_hit"] for item in originals)
        diagnostic.update(progress_fresh_until_epoch=until,
                          progress_remaining_seconds=max(0., until-time.time()) if until else 0.,
                          progress_missing_count=max(0, len(candidates)-len(records)),
                          detail_cache_hit_count=old, detail_new_body_count=len(records)-old,
                          body_cache_hit=bool(records) and old == len(records),
                          body_fetched_at_epoch=min((item["receipt"]["retrieved_at"] for item in originals), default=None),
                          progress_resume_possible=bool(window_covered and len(records) < len(candidates)
                              and any(item["reusable"] for item in originals) and not index_refused
                              and not diagnostic.get("detail_stop_reason") and not permanent_detail_failure
                              and not any(reason not in {"outside_window", "detail_fetch_error", "deadline_exhausted"}
                                          for reason in rejected)))
    diagnostic["detail_observations"] = detail_observations
    hard_rejections = sum(count for reason, count in rejected.items() if reason != "outside_window")
    complete = (window_covered and not hard_rejections and len(candidates) <= detail_limit
                and len(records) == len(candidates) and time.monotonic() < deadline)
    diagnostic.update(status="error" if index_refused else "success" if records and complete else "degraded_enrichment" if records or hard_rejections
                      else "error" if payload is None and diagnostic.get("ezsearch", {}).get("status") == "error" else "unavailable",
                      record_count=len(records), rejected_reason_counts=dict(rejected),
                      coverage_status="window_complete" if complete else "partial",
                      detail_attempt_count=detail_attempts, deadline_seconds=FETCH_BUDGET_SECONDS,
                      ezsearch_added_count=sum(row["link"] in added_links for row in records),
                      message=("已核對個股公告原文與完整30天索引。" if complete else "已核對部分公告原文；未完整涵蓋30天。") if records
                      else "個股索引未取得可核對的近期公告。")
    if not injected:
        diagnostic["http_request_sent"] = transport.http_request_count > 0
        diagnostic["http_request_count"] = transport.http_request_count
        if supports_ordinary(ticker) and records:
            from official_announcement_source_refresh import bundle
            if index_originals and all(time.time() < x["fresh_until_epoch"] for x in index_originals):
                diagnostic["source_record_archive"].append(bundle(index_originals, cutoff=now,
                    coverage=diagnostic["coverage_status"], ticker=ticker))
                until = min(diagnostic["progress_fresh_until_epoch"],
                            *(x["fresh_until_epoch"] for x in index_originals))
                diagnostic.update(progress_fresh_until_epoch=until,
                                  progress_remaining_seconds=max(0., until-time.time()))
                if time.monotonic() >= deadline:
                    diagnostic.update(status="degraded_enrichment", coverage_status="partial")
                    diagnostic["source_record_archive"][-1]["coverage_status"] = "partial"
            else:
                records = []
                diagnostic.update(status="error", record_count=0, coverage_status="partial",
                                  error_kind="index_original_unavailable", progress_resume_possible=False)
    return records, diagnostic
