"""Auditable annual consolidated financial histories from public MOPS iXBRL filings.

Only explicit monetary facts with the requested issuer, period and currency are
admitted. A comparative filing may fill an absent cell, but absence is never 0.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
import re
import time
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

import httpx

from .official_mopsfin_financial import (
    MopsFinError, PROVIDER as COMPARISON_PROVIDER, fetch_official_comparison_year,
)


BASE = "https://mopsov.twse.com.tw"
INDEX_URL = f"{BASE}/mops/web/ajax_t203sb01"
PROVIDER = "TWSE MOPS official consolidated iXBRL"
XBRLI = "{http://www.xbrl.org/2003/instance}"
IX = "{http://www.xbrl.org/2013/inlineXBRL}"
MAX_BYTES = 6_000_000
FIELDS = {
    "Revenue": "revenue_history",
    "ProfitLossAttributableToOwnersOfParent": "net_income_history",
    "GrossProfit": "gross_profit_history",
    "ProfitLossFromOperatingActivities": "operating_income_history",
    "Assets": "total_assets_history",
    "EquityAttributableToOwnersOfParent": "total_equity_history",
    "CashFlowsFromUsedInOperatingActivities": "operating_cash_flow",
    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "property_purchase",
    "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "intangible_purchase",
}
INSTANT_FIELDS = {"Assets", "EquityAttributableToOwnersOfParent"}
HISTORY_FIELDS = tuple(value for value in FIELDS.values() if value.endswith("_history")) + ("fcf_history",)
DOWNLOAD_RE = re.compile(r"/server-java/FileDownLoad\?[^'\"<>\s]+")
NUMBER_RE = re.compile(r"(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*|[1-9][0-9]*)(?:\.[0-9]+)?")


class FilingError(ValueError):
    retryable = False
    circuit_failure = False


class FilingTransportError(FilingError):
    """A host-level failure; keep the shared circuit available for protection."""
    circuit_failure = True


class FilingTransientResponseError(FilingTransportError):
    """A retryable-in-place MOPS server response, bounded by one local retry."""


class FilingUnexpectedResponseError(FilingError):
    """A transient HTTP-200 interstitial, not an issuer's XBRL document."""
    retryable = True
    circuit_failure = False


def _context_period(context, issuer: str):
    entity = context.find(f"{XBRLI}entity")
    identifier = entity.find(f"{XBRLI}identifier") if entity is not None else None
    if (identifier is None or identifier.text != issuer
            or identifier.get("scheme") != "http://www.twse.com.tw"
            or entity.find(f"{XBRLI}segment") is not None
            or context.find(f"{XBRLI}scenario") is not None):
        return None
    period = context.find(f"{XBRLI}period")
    if period is None:
        return None
    instant = period.findtext(f"{XBRLI}instant")
    start = period.findtext(f"{XBRLI}startDate")
    end = period.findtext(f"{XBRLI}endDate")
    return ("instant", instant) if instant and not start and not end else (
        ("duration", start, end) if start and end and not instant else None
    )


def parse_annual_filing(raw: bytes, issuer: str, year: int, *, allow_missing: bool = False) -> dict[str, int]:
    """Return raw TWD facts for one calendar year from one official filing."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise FilingError("XBRL document exceeds limit or includes external declarations")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FilingError("XBRL is not well-formed XML") from exc
    if root.tag != "{http://www.w3.org/1999/xhtml}html":
        raise FilingError("XBRL root is not official inline XHTML")
    units = {}
    for unit in root.iter(f"{XBRLI}unit"):
        uid = unit.get("id")
        if uid in units:
            raise FilingError("duplicate XBRL unit")
        units[uid] = unit.findtext(f"{XBRLI}measure")
    periods = {}
    for context in root.iter(f"{XBRLI}context"):
        cid = context.get("id")
        if cid in periods:
            raise FilingError("duplicate XBRL context")
        periods[cid] = _context_period(context, issuer)
    target_duration = ("duration", f"{year}-01-01", f"{year}-12-31")
    target_instant = ("instant", f"{year}-12-31")
    values = {}
    for fact in root.iter(f"{IX}nonFraction"):
        name = fact.get("name", "")
        if not name.startswith("ifrs-full:"):
            continue
        tag = name.split(":", 1)[1]
        if tag not in FIELDS:
            continue
        expected = target_instant if tag in INSTANT_FIELDS else target_duration
        if periods.get(fact.get("contextRef")) != expected:
            continue
        if tag in values:
            raise FilingError(f"duplicate {tag} for {year}")
        if units.get(fact.get("unitRef")) != "iso4217:TWD":
            raise FilingError(f"wrong currency for {tag} {year}")
        if (fact.get("format") != "ixt:numdotdecimal" or fact.get("scale") != "3"
                or fact.get("decimals") not in {"-3", "INF"}):
            raise FilingError(f"unsupported XBRL number format for {tag} {year}")
        sign = fact.get("sign")
        if sign not in (None, "-"):
            raise FilingError(f"unsupported XBRL sign for {tag} {year}")
        value_text = "".join(fact.itertext()).strip()
        if len(value_text) > 40 or not NUMBER_RE.fullmatch(value_text):
            raise FilingError(f"non-numeric XBRL fact for {tag} {year}")
        try:
            number = Decimal(value_text.replace(",", "")) * 1000
        except InvalidOperation as exc:
            raise FilingError(f"invalid XBRL number for {tag} {year}") from exc
        if number != number.to_integral_value():
            raise FilingError(f"non-integral TWD value for {tag} {year}")
        values[tag] = int(number) * (-1 if sign == "-" else 1)
        if tag.startswith("PurchaseOf") and values[tag] > 0:
            raise FilingError(f"cash outflow sign is ambiguous for {tag} {year}")
    if not allow_missing and set(values) != set(FIELDS):
        raise FilingError(f"missing annual XBRL facts for {year}: {','.join(sorted(set(FIELDS) - set(values)))}")
    return values


def assemble_annual_histories(facts_by_year: dict[int, dict[str, int]], *, expected_years: list[int]) -> dict:
    years = sorted(expected_years)
    if len(years) != len(set(years)) or set(years) != set(facts_by_year):
        raise FilingError("annual XBRL year coverage is incomplete")
    result = {"years": [str(year) for year in years], "raw_twd_by_year": {}}
    for key in HISTORY_FIELDS:
        result[key] = []
    for year in years:
        row = facts_by_year[year]
        if set(row) != set(FIELDS):
            raise FilingError(f"annual XBRL facts are incomplete for {year}")
        raw = {name: row[tag] for tag, name in FIELDS.items()}
        raw["free_cash_flow"] = raw["operating_cash_flow"] + raw["property_purchase"] + raw["intangible_purchase"]
        result["raw_twd_by_year"][str(year)] = raw
        for tag, name in FIELDS.items():
            if name.endswith("_history"):
                result[name].append(raw[name] / 1e9)
        result["fcf_history"].append(raw["free_cash_flow"] / 1e9)
    return result


def reconcile_comparative_rows(rows: dict[int, dict[str, int]], comparatives: dict[int, dict[str, int]]) -> tuple[dict, list]:
    """Prefer a complete later comparative statement and retain every revision."""
    resolved = {year: dict(values) for year, values in rows.items()}
    revisions = []
    for year, comparative in comparatives.items():
        original = resolved[year]
        conflicts = {tag: (original[tag], value) for tag, value in comparative.items()
                     if tag in original and original[tag] != value}
        if conflicts and set(comparative) != set(FIELDS):
            raise FilingError(f"conflicting incomplete comparative statement for {year}")
        for tag, value in comparative.items():
            if tag not in original:
                revisions.append({"year": year, "fact": tag, "original_twd": None, "revised_twd": value,
                                  "original_filing_year": year, "comparative_filing_year": year + 1,
                                  "kind": "missing_fact_fill"})
        for tag, (old, new) in conflicts.items():
            revisions.append({"year": year, "fact": tag, "original_twd": old, "revised_twd": new,
                              "original_filing_year": year, "comparative_filing_year": year + 1,
                              "kind": "restatement"})
        if set(comparative) == set(FIELDS):
            resolved[year] = dict(comparative)
        else:
            for tag, value in comparative.items():
                original.setdefault(tag, value)
    return resolved, revisions


def _bounded_request(client: httpx.Client, method: str, url: str, *, data: dict | None = None,
                     request_observer=None) -> bytes:
    if not url.startswith(BASE + "/"):
        raise FilingError("XBRL URL is not on the official host")
    observation = {"provider": PROVIDER, "url": url, "request_method": method, "http_request_sent": False}
    chunks = []
    size = 0
    try:
        observation["http_request_sent"] = True
        with client.stream(method, url, data=data) as response:
            observation["http_status"] = response.status_code
            if response.status_code != 200:
                error = (FilingTransientResponseError if response.status_code in (500, 502, 503, 504)
                         else FilingTransportError if response.status_code in (403, 429) or response.status_code >= 500
                         else FilingError)
                raise error(f"MOPS HTTP {response.status_code}")
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FilingError("MOPS response exceeds XBRL size limit")
                chunks.append(chunk)
    except Exception as exc:
        observation["error_kind"] = ("timeout" if isinstance(exc, httpx.TimeoutException) else
                                     "transport_error" if isinstance(exc, httpx.HTTPError) else
                                     type(exc).__name__)
        if request_observer is not None:
            request_observer(dict(observation))
        raise
    raw = b"".join(chunks)
    observation.update(status="received", response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
    if request_observer is not None:
        request_observer(dict(observation))
    if urlsplit(url).path == "/server-java/FileDownLoad":
        # MOPS occasionally replies with an HTML security/interstitial page and
        # HTTP 200. Retrying the document can recover without relaxing the
        # XML, issuer, period, or currency gates below.
        if not raw.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<?xml"):
            raise FilingUnexpectedResponseError("MOPS returned non-XBRL content with HTTP 200")
        # An interstitial can also prepend an XML declaration to a DOCTYPE
        # page. It is still never parsed as a filing; retry this one document
        # once, then preserve the original fail-closed declaration rule.
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise FilingUnexpectedResponseError("MOPS returned prohibited XML declarations")
    return raw


_TRANSIENT_NETWORK_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                             httpx.ReadError, httpx.RemoteProtocolError)
_LOCAL_RETRY_ERRORS = (FilingTransientResponseError, *_TRANSIENT_NETWORK_ERRORS)
_FILING_RETRY_ERRORS = (FilingUnexpectedResponseError, *_LOCAL_RETRY_ERRORS)


def _fetch_index_response(client: httpx.Client, data: dict, *, request=None) -> bytes:
    """Retry the official filing index once after a transient host failure."""
    request = request or _bounded_request
    for attempt in range(2):
        try:
            return request(client, "POST", INDEX_URL, data=data)
        except _LOCAL_RETRY_ERRORS:
            if attempt:
                raise
            time.sleep(0.25)
    raise AssertionError("unreachable index retry state")


def _fetch_filing_document(client: httpx.Client, url: str, *, request=None) -> bytes:
    """Retry one transient document failure without re-downloading other years."""
    request = request or _bounded_request
    for attempt in range(2):
        try:
            return request(client, "GET", url)
        except _FILING_RETRY_ERRORS:
            if attempt:
                raise
            time.sleep(0.25)
    raise AssertionError("unreachable filing retry state")


def _filing_urls(index_html: bytes, issuer: str, *, report_id: str = "C") -> dict[int, str]:
    if report_id not in {"A", "C"}:
        raise FilingError("unsupported MOPS annual report scope")
    html = index_html.decode("utf-8", errors="replace").replace("&amp;", "&")
    urls = {}
    for relative in DOWNLOAD_RE.findall(html):
        parsed = urlsplit(relative)
        params = parse_qs(parsed.query)
        if (parsed.path != "/server-java/FileDownLoad" or params.get("functionName") != ["t164sb01"]
                or params.get("step") != ["9"] or params.get("co_id") != [issuer]
                or params.get("season") != ["4"] or params.get("report_id") != [report_id]):
            continue
        year = params.get("year", [""])[0]
        if not re.fullmatch(r"20\d{2}", year):
            continue
        if int(year) in urls and urls[int(year)] != BASE + relative:
            raise FilingError(f"ambiguous MOPS annual filing for {year}")
        urls[int(year)] = BASE + relative
    return urls


def confirmed_annual_gap(message, issuer, rows, comparatives, documents):
    """Prove a narrow missing-fact gap from five parsed official originals.

    An error string, security page or empty/wrong-issuer XHTML is not proof.
    Only otherwise complete TWD rows missing explicit intangible purchases
    qualify. Preserve every missing fact and original validation error.
    """
    match = re.fullmatch(r"(annual XBRL facts are incomplete|conflicting incomplete comparative statement) for (20\d{2})", str(message))
    if not match or not isinstance(rows, dict) or not isinstance(comparatives, dict) or not isinstance(documents, list):
        return None
    year = int(match[2])
    years = sorted(rows) if all(type(y) is int for y in rows) else []
    missing_tag = "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"
    partial_fields = set(FIELDS) - {missing_tag}
    if (len(years) != 5 or years != list(range(years[0], years[0] + 5))
            or year not in rows or len(documents) != 5):
        return None
    for values in rows.values():
        if (not isinstance(values, dict) or set(values) not in (set(FIELDS), partial_fields)
                or any(type(v) is not int for v in values.values())):
            return None
    for y, document in zip(years, documents):
        if not isinstance(document, dict) or document.get("year") != y:
            return None
        url = document.get("url")
        if (not isinstance(url, str) or not url.startswith(BASE + "/server-java/FileDownLoad?")
                or _filing_urls(url.encode(), issuer) != {y: url}
                or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("sha256", "")))):
            return None
    comparative = comparatives.get(year, {})
    if match[1] == "annual XBRL facts are incomplete":
        if set(rows[year]) != partial_fields:
            return None
        comparative = {}
    elif (not isinstance(comparative, dict) or set(comparative) != partial_fields
            or any(type(v) is not int for v in comparative.values())
            or not any(tag in rows[year] and rows[year][tag] != value for tag, value in comparative.items())):
        return None
    return {
        "schema": "mops-five-originals-validated-gap.v1", "issuer": issuer,
        "year": year, "message": message,
        "raw_twd_by_year": {str(y): dict(rows[y]) for y in years},
        "comparative_raw_twd": dict(comparative),
        "documents": [dict(document) for document in documents],
    }


def fetch_official_annual_histories(ticker: str, *, client: httpx.Client | None = None,
                                    request_observer=None) -> dict:
    """Fetch five contiguous Q4 consolidated filings for one Taiwan stock."""
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1" and client is None:
        raise FilingError("network is disabled for tests")
    match = re.fullmatch(r"(\d{4})\.TW(?:O)?", ticker)
    if not match:
        raise FilingError("official XBRL requires a Taiwan stock ticker")
    issuer = match.group(1)
    owns_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False)
    observed_request = None
    if request_observer is not None:
        def observed_request(active_client, method, url, *, data=None):
            return _bounded_request(active_client, method, url, data=data, request_observer=request_observer)
    try:
        index_request = {
            "step": "1", "firstin": "ture", "off": "1", "queryName": "co_id",
            "inpuType": "co_id", "TYPEK": "all", "co_id": issuer,
        }
        index = (_fetch_index_response(client, index_request, request=observed_request)
                 if observed_request is not None else _fetch_index_response(client, index_request))
        urls = _filing_urls(index, issuer)
        if len(urls) < 5:
            from .annual_filing_index_gap import confirmed_short_annual_index
            error = FilingError("fewer than five consolidated annual filings")
            proof = confirmed_short_annual_index(index, issuer, str(error))
            if proof is not None:
                error.validation_gap = proof
            raise error
        years = sorted(urls)[-5:]
        if years != list(range(years[0], years[0] + 5)):
            raise FilingError("annual filing years are not contiguous")
        rows, comparatives, documents, recovered_documents = {}, {}, [], []
        for year in years:
            try:
                raw = (_fetch_filing_document(client, urls[year], request=observed_request)
                       if observed_request is not None else _fetch_filing_document(client, urls[year]))
            except _FILING_RETRY_ERRORS as original_error:
                # Only a temporary download failure may use the comparison site.
                # Issuer-specific missing facts, 403 and 429 remain fail-closed.
                try:
                    alternative = (fetch_official_comparison_year(issuer, year)
                                   if request_observer is None else
                                   fetch_official_comparison_year(issuer, year, request_observer=request_observer))
                except MopsFinError as fallback_error:
                    error_type = (FilingError if isinstance(original_error, FilingUnexpectedResponseError)
                                  else FilingTransportError)
                    raise error_type(
                        f"MOPS filing {year} temporarily unreadable; comparison recovery failed: "
                        f"{str(fallback_error)[:100]}"
                    ) from fallback_error
                parts = alternative.get("documents") if isinstance(alternative, dict) else None
                facts = alternative.get("facts") if isinstance(alternative, dict) else None
                if (not isinstance(parts, list) or len(parts) != 3
                        or not isinstance(facts, dict) or set(facts) != set(FIELDS)
                        or any(not isinstance(part, dict) or part.get("year") != year
                               or not part.get("url") or not part.get("sha256") for part in parts)):
                    raise FilingError(f"MOPS filing {year} comparison recovery has incomplete receipts") from original_error
                rows[year] = facts
                digest = sha256(";".join(part["sha256"] for part in parts).encode()).hexdigest()
                documents.append({
                    "year": year, "url": parts[0]["url"], "sha256": digest,
                    "provider": COMPARISON_PROVIDER, "period_end": f"{year}-12-31",
                    "requested_xbrl_url": urls[year], "components": parts,
                })
                recovered_documents.append({
                    "year": year, "failed_xbrl_url": urls[year],
                    "error_kind": type(original_error).__name__, "documents": parts,
                })
                continue
            documents.append({"year": year, "url": urls[year], "sha256": sha256(raw).hexdigest()})
            rows[year] = parse_annual_filing(raw, issuer, year, allow_missing=True)
            if year > years[0]:
                comparatives[year - 1] = parse_annual_filing(raw, issuer, year - 1, allow_missing=True)
        # The comparison site can retain original-year figures after a later
        # filing revised them. Require the next iXBRL's full comparative row
        # for every recovered year except the newest year, which has no next
        # annual filing yet.
        for recovery in recovered_documents:
            year = recovery["year"]
            if year != years[-1] and set(comparatives.get(year, {})) != set(FIELDS):
                raise FilingError(f"comparison year {year} lacks a complete next-year XBRL comparative")
        try:
            rows, revisions = reconcile_comparative_rows(rows, comparatives)
            histories = assemble_annual_histories(rows, expected_years=years)
        except FilingError as exc:
            proof = confirmed_annual_gap(str(exc), issuer, rows, comparatives, documents)
            if proof is not None:
                exc.validation_gap = proof
            raise
        histories["documents"] = documents
        histories["source_url"] = INDEX_URL
        histories["comparative_revisions"] = revisions
        histories["recovered_documents"] = recovered_documents
        return histories
    except httpx.HTTPError as exc:
        # Retrying the whole multi-document operation multiplies public-site load.
        raise FilingTransportError(f"MOPS transport error: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            client.close()
