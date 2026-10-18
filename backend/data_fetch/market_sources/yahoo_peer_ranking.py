"""Published Taiwan industry peers, explicitly short of business comparability.

Yahoo's compare page names an industry cohort. The current exchange stock master
must independently confirm every exact stock code, market, name and specific
industry before a row becomes a discovery candidate. No ranking number is used
as a peer valuation or as proof that two businesses are comparable.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import math
import os
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import httpx
from official_response_evidence import archive_response, read_response

from .peer_recovery import NON_SPECIFIC_CATEGORIES, current_master_industry_categories, load_peer_stock_master


POLICY = "published-industry-peer-ranking-v1"
PROVIDER = "Yahoo Taiwan published industry ranking"
MAX_BYTES = 1_000_000
TICKER_RE = re.compile(r"[1-9]\d{3,5}\.TW(?:O)?")
ROW_RE = re.compile(r"^(\d{1,3})\s+(.+?)\s+([1-9]\d{3,5}\.TW(?:O)?)\b")


class RankingError(ValueError):
    pass


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


def _current_names(ticker: str, rows: list[dict], categories: set[str], today: date) -> set[str]:
    code, market = ticker.split(".")
    expected_type = "tpex" if market == "TWO" else "twse"
    eligible = []
    for row in rows:
        if (str(row.get("stock_id") or "") != code or str(row.get("type") or "").lower() != expected_type
                or row.get("industry_category") not in categories):
            continue
        try:
            observed = date.fromisoformat(str(row.get("date") or ""))
        except ValueError:
            continue
        if 0 <= (today - observed).days <= 7:
            eligible.append((observed, str(row.get("stock_name") or "").strip()))
    latest = max((day for day, _ in eligible), default=None)
    return {name.strip("*") for day, name in eligible if day == latest and name} if latest else set()


def _specific_categories(ticker: str, rows: list[dict], today: date) -> set[str]:
    return set(current_master_industry_categories(ticker, rows, today=today)) - NON_SPECIFIC_CATEGORIES


def parse_ranking_page(raw: bytes, ticker: str, master_rows: list[dict], *, today: date | None = None) -> dict:
    """Return only exact, current industry cohort rows from one bounded page."""
    today = today or _today()
    ticker = str(ticker or "").strip().upper()
    if not TICKER_RE.fullmatch(ticker) or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise RankingError("invalid ticker or published ranking size")
    categories = _specific_categories(ticker, master_rows, today)
    if not categories:
        raise RankingError("target has no current specific exchange industry")
    soup = BeautifulSoup(raw, "html.parser")
    url = f"https://tw.stock.yahoo.com/quote/{ticker}/compare"
    title = soup.find("meta", attrs={"property": "og:title"})
    canonical = soup.find("meta", attrs={"property": "og:url"})
    title_text = str(title.get("content") or "") if title else ""
    issuer_name = title_text.split(f"({ticker}) 同業比較 - Yahoo股市")[0] if title_text.endswith(
        f"({ticker}) 同業比較 - Yahoo股市") else ""
    if not issuer_name or canonical is None or canonical.get("content") != url:
        raise RankingError("published ranking issuer or URL mismatch")
    if issuer_name.strip("*") not in _current_names(ticker, master_rows, categories, today):
        raise RankingError("published ranking issuer name disagrees with current stock master")
    table = soup.find(id="quote-compare-tables")
    section = table.find(id="qsp-compare-rank-symbols") if table else None
    if section is None:
        raise RankingError("published industry ranking table is missing")
    table_text = table.get_text(" ", strip=True)
    date_match = re.search(r"資料時間[：:]\s*(\d{4})/(\d{2})/(\d{2})", table_text)
    industry_match = re.match(r"\s*(.{1,24}?)業各類指標排名", table_text)
    if not date_match or not industry_match:
        raise RankingError("published industry or observation date is missing")
    try:
        observed_at = date(*map(int, date_match.groups()))
    except ValueError as exc:
        raise RankingError("invalid published observation date") from exc
    if not 0 <= (today - observed_at).days <= 7:
        raise RankingError("published industry ranking is stale or future-dated")
    publisher_industry = industry_match.group(1).strip()
    if publisher_industry in {"其他", "櫃其他", "電子工業", "上市股票", "上櫃股票"}:
        raise RankingError("publisher industry is too broad for a peer candidate")
    digest = sha256(raw).hexdigest()
    records = []
    seen = {ticker}
    raw_count = 0
    for row in section.select(".table-row"):
        match = ROW_RE.match(" ".join(row.get_text(" ", strip=True).split()))
        if not match:
            continue
        rank, name, candidate = match.groups()
        link = row.find("a", href=True)
        if not link or link["href"] != f"https://tw.stock.yahoo.com/quote/{candidate}":
            continue
        raw_count += 1
        if candidate in seen:
            continue
        seen.add(candidate)
        peer_categories = _specific_categories(candidate, master_rows, today)
        shared = sorted(categories & peer_categories)
        if not shared or name.strip("*") not in _current_names(candidate, master_rows, peer_categories, today):
            continue
        records.append({
            "title": f"Yahoo 股市產業排名：{issuer_name}、{name}",
            "source": "Yahoo 股市", "source_type": "published_industry_peer_ranking",
            "link": url, "selection_policy": POLICY,
            "relationship_kind": "publisher_ranked_industry_peer",
            "relationship_basis": "published_industry_ranking_and_current_exchange_master",
            "numeric_comparability_verified": False, "business_comparability_verified": False,
            "industry_category": shared[0], "publisher_industry": publisher_industry,
            "observed_at": observed_at.isoformat(), "response_sha256": digest,
            "ranking_position": int(rank),
            "issuer": {"ticker": ticker, "official_name": issuer_name},
            "counterparty": {"ticker": candidate, "official_name": name,
                             "quote_url": link["href"]},
        })
        if len(records) >= 5:
            break
    if raw_count and not records:
        raise RankingError("published ranking has no independently verified industry peers")
    return {"records": records, "source_url": url, "observed_at": observed_at.isoformat(),
            "publisher_industry": publisher_industry, "response_sha256": digest,
            "raw_count": raw_count, "usable_count": len(records)}


def is_published_peer_record(record: dict, ticker: str, *, today: date | None = None) -> bool:
    if not isinstance(record, dict):
        return False
    today = today or _today()
    issuer, peer = record.get("issuer"), record.get("counterparty")
    if not isinstance(issuer, dict) or not isinstance(peer, dict):
        return False
    candidate = str(peer.get("ticker") or "")
    try:
        observed = date.fromisoformat(str(record.get("observed_at") or ""))
    except ValueError:
        return False
    return bool(
        TICKER_RE.fullmatch(ticker) and TICKER_RE.fullmatch(candidate) and candidate != ticker
        and issuer.get("ticker") == ticker and issuer.get("official_name")
        and peer.get("official_name") and peer.get("quote_url") == f"https://tw.stock.yahoo.com/quote/{candidate}"
        and record.get("selection_policy") == POLICY
        and record.get("relationship_kind") == "publisher_ranked_industry_peer"
        and record.get("relationship_basis") == "published_industry_ranking_and_current_exchange_master"
        and record.get("source_type") == "published_industry_peer_ranking"
        and record.get("link") == f"https://tw.stock.yahoo.com/quote/{ticker}/compare"
        and record.get("industry_category") not in NON_SPECIFIC_CATEGORIES
        and record.get("publisher_industry") not in {"其他", "櫃其他", "電子工業", ""}
        and re.fullmatch(r"[0-9a-f]{64}", str(record.get("response_sha256") or ""))
        and record.get("numeric_comparability_verified") is False
        and record.get("business_comparability_verified") is False
        and isinstance(record.get("ranking_position"), int) and record["ranking_position"] > 0
        and 0 <= (today - observed).days <= 7
    )


def fetch_published_industry_peers(ticker: str, *, today: date | None = None,
                                   master_rows: list[dict] | None = None,
                                   client: httpx.Client | None = None) -> dict:
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1" and client is None:
        raise RankingError("network is disabled for tests")
    today = today or _today()
    rows = master_rows if master_rows is not None else load_peer_stock_master()
    if not _specific_categories(ticker, rows, today):
        raise RankingError("target has no current specific exchange industry")
    url = f"https://tw.stock.yahoo.com/quote/{ticker}/compare"
    owns_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(9, connect=4), follow_redirects=False,
                                   headers={"User-Agent": "Mozilla/5.0 (compatible; StockAgent/1.0)"})
    try:
        chunks, size = [], 0
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise RankingError(f"Yahoo peer ranking HTTP {response.status_code}")
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise RankingError("published ranking exceeds size limit")
                chunks.append(chunk)
        raw = b"".join(chunks)
        received_at = time.time()
        parsed = parse_ranking_page(raw, ticker, rows, today=today)
        receipt = archive_response(raw, source_url=url, retrieved_at=received_at,
                                   http_status=200, evidence_kind="decoded_complete_http_response_body")
        try:
            if (receipt.get("status") != "archived" or receipt.get("source_url") != url
                    or receipt.get("raw_response_sha256") != parsed["response_sha256"]
                    or receipt.get("raw_response_bytes") != len(raw)
                    or read_response(receipt) != raw):
                raise ValueError("source archive differs from the parsed page")
        except (OSError, ValueError, EOFError):
            raise RankingError("source_archive_unavailable") from None
        parsed["raw_http_receipt"] = receipt
        return parsed
    finally:
        if owns_client:
            client.close()


def validate_stored_ranking_body(value: dict, ticker: str, master_rows: list[dict], *, today: date):
    """Recheck a supplied original; legacy metadata never gains a receipt."""
    if "raw_http_receipt" not in value:
        return
    try:
        receipt = value["raw_http_receipt"]
        url = f"https://tw.stock.yahoo.com/quote/{ticker}/compare"
        stamp = receipt.get("retrieved_at") if isinstance(receipt, dict) else None
        if (not isinstance(receipt, dict) or receipt.get("status") != "archived"
                or receipt.get("source_url") != url or value.get("source_url") != url
                or receipt.get("http_status") != 200
                or receipt.get("evidence_kind") != "decoded_complete_http_response_body"
                or type(stamp) not in (int, float) or not math.isfinite(stamp)
                or stamp <= 0 or not 0 <= time.time() - stamp <= 4 * 3600
                or receipt.get("raw_response_sha256") != value.get("response_sha256")
                or type(receipt.get("raw_response_bytes")) is not int):
            raise ValueError("source receipt identity or age invalid")
        raw = read_response(receipt)
        if not 0 < len(raw) <= MAX_BYTES or len(raw) != receipt["raw_response_bytes"]:
            raise ValueError("source receipt size invalid")
        parsed = parse_ranking_page(raw, ticker, master_rows, today=today)
        for key, expected in parsed.items():
            if json.dumps(value.get(key), sort_keys=True, ensure_ascii=False) != json.dumps(
                    expected, sort_keys=True, ensure_ascii=False):
                raise ValueError("cached candidate fields differ from the original")
    except (OSError, ValueError, TypeError, KeyError, EOFError, OverflowError):
        raise RankingError("source_receipt_invalid") from None
