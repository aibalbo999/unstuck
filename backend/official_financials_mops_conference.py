"""MOPS investor-conference metadata adapter."""

from __future__ import annotations

import logging
import re
from datetime import date
from io import StringIO
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from external_http_client import sync_post


LOGGER = logging.getLogger(__name__)
MOPS_BASE_URL = "https://mops.twse.com.tw"
MOPS_INVESTOR_CONFERENCE_URL = "https://mops.twse.com.tw/mops/web/ajax_t100sb07_1"
REQUEST_TIMEOUT = (5, 15)
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
    limit: int = 3,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch free MOPS investor-conference metadata and material links."""
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
    }
    try:
        response = _http_post(
            MOPS_INVESTOR_CONFERENCE_URL,
            data=data,
            session=session,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            provider="MOPS",
        )
    except Exception as exc:
        _warn("MOPS", "investor conference", exc)
        return []
    try:
        frames = pd.read_html(StringIO(response.text))
    except (ImportError, ValueError):
        frames = []
    except Exception as exc:
        _warn("MOPS", "investor conference tables", exc)
        frames = []
    records = _dedupe_conference_records(
        _parse_conference_html(response.text, symbol) + _parse_conference_frames(frames, symbol)
    )
    return records[: max(1, int(limit or 3))]


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
    return f"{year:04d}-{month:02d}-{day:02d}"


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
