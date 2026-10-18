"""Public MOPS historical announcements for exact TPEx issuer codes."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import hashlib
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from external_http_client import sync_get
from .twse_company_history import MAX_DETAIL_BYTES, MAX_DETAIL_FETCHES, TAIPEI, _detail_fields, _roc_day, _text


INDEX_URL = "https://mopsov.twse.com.tw/mops/web/t05st01"
DETAIL_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1"
PROVIDER = "TPEx MOPS company announcement history"
PARSER_VERSION = "tpex-mops-company-history-v1"
MAX_INDEX_BYTES = 2_000_000
MAX_INDEX_ROWS = 2_000
_ONCLICK_FIELDS = ("seq_no", "spoke_time", "spoke_date", "co_id", "TYPEK")


def _index_rows(html: str, stock_id: str, *, lower: datetime, now: datetime) -> tuple[list[tuple], Counter]:
    soup = BeautifulSoup(html, "html.parser")
    table = next((table for table in soup.select("table.hasBorder")
                  if [_text(cell.get_text(" ", strip=True)) for cell in table.select("tr:first-child th")[:5]]
                  == ["公司代號", "公司名稱", "發言日期", "發言時間", "主旨"]), None)
    if table is None:
        if "查無資料" in soup.get_text(" ", strip=True) or "無符合條件" in soup.get_text(" ", strip=True):
            return [], Counter()
        raise ValueError("MOPS historical announcement table unavailable")
    rows = table.select("tr")[1:]
    if len(rows) > MAX_INDEX_ROWS:
        raise ValueError("MOPS historical announcement index exceeds bound")
    parsed, rejected = [], Counter()
    for row in rows:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6:
            rejected["invalid_row"] += 1
            continue
        code, company, day, clock, title = [_text(cell.get_text(" ", strip=True))
                                             for cell in cells[:5]]
        if code != stock_id or not company or not title:
            rejected["issuer_or_subject_mismatch"] += 1
            continue
        try:
            published = datetime.fromisoformat(f"{_roc_day(day).date().isoformat()}T{clock}").replace(tzinfo=TAIPEI)
        except (ValueError, TypeError):
            rejected["invalid_publication_time"] += 1
            continue
        if published < lower:
            rejected["outside_window"] += 1
            continue
        if published > now:
            rejected["future_publication"] += 1
            continue
        button = cells[5].find("input", onclick=True)
        onclick = str(button.get("onclick") or "") if button else ""
        parts = re.findall(r"\.([A-Za-z_]+)\.value='([^']*)'", onclick)
        values = {}
        for key, value in parts:
            if key in _ONCLICK_FIELDS:
                values.setdefault(key, []).append(value)
        if (any(len(values.get(key, [])) != 1 for key in _ONCLICK_FIELDS)
                or values.get("co_id") != [stock_id] or values.get("TYPEK") != ["otc"]
                or values.get("spoke_date") != [published.strftime("%Y%m%d")]
                or values.get("spoke_time") != [published.strftime("%H%M%S")]
                or not re.fullmatch(r"[1-9]\d{0,3}", values["seq_no"][0])):
            rejected["invalid_detail_identity"] += 1
            continue
        params = {"firstin": "true", "stp": "1", "step": "1", "SEQ_NO": values["seq_no"][0],
                  "SPOKE_TIME": values["spoke_time"][0], "SPOKE_DATE": values["spoke_date"][0],
                  "COMPANY_ID": stock_id}
        parsed.append((published, title, company, DETAIL_URL + "?" + urlencode(params)))
    return parsed, rejected


def fetch_recent_tpex_announcements(ticker: str, *, now: datetime | None = None, get=None) -> tuple[list[dict], dict]:
    """Verify original text for recent TPEx announcements in at most two annual indexes."""
    ticker = str(ticker or "").strip().upper()
    if not re.fullmatch(r"[1-9]\d{3,5}\.TWO", ticker):
        return [], {"status": "not_applicable", "record_count": 0, "parser_version": PARSER_VERSION}
    now = now or datetime.now(TAIPEI)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(TAIPEI)
    lower = now - timedelta(days=30)
    get = get or sync_get
    stock_id = ticker.split(".", 1)[0]
    years = sorted({lower.year, now.year}, reverse=True)
    rejected = Counter()
    diagnostic = {"status": "unavailable", "record_count": 0, "parser_version": PARSER_VERSION,
                  "index_url": INDEX_URL, "index_years": years, "detail_limit": MAX_DETAIL_FETCHES,
                  "coverage_status": "partial", "rejected_reason_counts": {}}
    candidates = []
    try:
        for year in years:
            params = {"co_id": stock_id, "year": str(year - 1911), "firstin": "true", "step": "1"}
            response = get(INDEX_URL, params=params, timeout=(5, 15), provider=PROVIDER)
            response.raise_for_status()
            if len(response.content) > MAX_INDEX_BYTES:
                raise ValueError("oversized MOPS historical announcement index")
            rows, rejected_rows = _index_rows(response.text, stock_id, lower=lower, now=now)
            rejected.update(rejected_rows)
            candidates.extend(rows)
    except Exception as exc:
        diagnostic.update(status="error", error_kind=type(exc).__name__,
                          rejected_reason_counts=dict(rejected), message="MOPS 上櫃歷史公告索引取得或驗證失敗。")
        fallback_records, fallback = _fetch_infohub_fallback(ticker, now=now)
        if fallback_records:
            fallback["fallback_from"] = diagnostic
            return fallback_records, fallback
        diagnostic["related_entries"] = [fallback]
        return [], diagnostic
    records = []
    seen = set()
    for published, title, company, link in sorted(candidates, reverse=True)[:MAX_DETAIL_FETCHES]:
        if link in seen:
            rejected["duplicate_detail"] += 1
            continue
        seen.add(link)
        try:
            response = get(link, timeout=(5, 15), provider=PROVIDER)
            response.raise_for_status()
            if len(response.content) > MAX_DETAIL_BYTES:
                raise ValueError("oversized MOPS announcement detail")
            header, fields = _detail_fields(response.text)
            detail_day = _roc_day(fields.get("發言日期"))
            observed = datetime.fromisoformat(f"{detail_day.date().isoformat()}T{fields.get('發言時間', '')}").replace(tzinfo=TAIPEI)
            body = fields.get("說明", "").strip()
            if ("上櫃公司" not in header or not re.search(rf"(?<!\d){stock_id}(?!\d)", header)
                    or company not in header or _text(fields.get("主旨")) != title
                    or observed != published or len(body) < 20):
                raise ValueError("MOPS issuer, subject, timestamp or body mismatch")
        except Exception as exc:
            rejected["detail_mismatch" if isinstance(exc, ValueError) else "detail_fetch_error"] += 1
            continue
        full_text = f"{company}（{stock_id}） {title}\n{body}"
        if len(full_text) > 12_000:
            rejected["content_truncated"] += 1
        records.append({"date": observed.isoformat(), "published_at": observed.isoformat(),
                        "title": title, "summary": full_text[:1500], "text": full_text[:12_000],
                        "source": PROVIDER, "publisher": "櫃買中心／公開資訊觀測站",
                        "source_type": "official_disclosure", "link": link, "ticker": ticker,
                        "issuer_identity_basis": "MOPS OTC company index + original detail header",
                        "catalyst_assessment": "not_assessed",
                        "content_coverage": "partial" if len(full_text) > 12_000 else "text_available",
                        "content_truncated": len(full_text) > 12_000,
                        "content_sha256": hashlib.sha256(full_text.encode("utf-8")).hexdigest()})
    hard_rejections = sum(count for reason, count in rejected.items() if reason != "outside_window")
    complete = not hard_rejections and len(candidates) <= MAX_DETAIL_FETCHES
    diagnostic.update(status="success" if records and complete else "degraded_enrichment" if records or hard_rejections else "unavailable",
                      record_count=len(records), rejected_reason_counts=dict(rejected),
                      coverage_status="window_complete" if complete else "partial",
                      detail_attempt_count=min(len(candidates), MAX_DETAIL_FETCHES),
                      message="已核對上櫃公司歷史重大訊息原文。" if records else "未取得可核對的近期上櫃公告。")
    if not records:
        fallback_records, fallback = _fetch_infohub_fallback(ticker, now=now)
        if fallback_records:
            fallback["fallback_from"] = diagnostic
            return fallback_records, fallback
        diagnostic["related_entries"] = [fallback]
    return records, diagnostic


def _fetch_infohub_fallback(ticker: str, *, now: datetime) -> tuple[list[dict], dict]:
    """Use the independent TPEx InfoHub index only when MOPS yields no originals."""
    from .tpex_infohub import fetch_tpex_infohub_records

    return fetch_tpex_infohub_records(ticker, now=now)
