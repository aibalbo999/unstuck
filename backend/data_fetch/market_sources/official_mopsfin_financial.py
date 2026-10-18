"""Strict one-year facts from TWSE's public financial comparison interface.

The comparison page can recover one temporarily unreadable iXBRL document.
It does not expose later comparative revisions, so callers must reconcile those.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
import re
import time

from bs4 import BeautifulSoup
import httpx


BASE = "https://mopsfin.twse.com.tw"
REPORT_URL = BASE + "/compare/report"
PROVIDER = "TWSE MOPS official financial comparison"
MAX_BYTES = 250_000
DEADLINE_SECONDS = 12
NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*|[1-9][0-9]*)(?:\.[0-9]{1,2})?")
STATEMENT_FIELDS = {
    "IncomeStatement": {
        "Revenue": "營業收入合計",
        "ProfitLossAttributableToOwnersOfParent": "母公司業主（淨利∕損）",
        "GrossProfit": "營業毛利（毛損）淨額",
        "ProfitLossFromOperatingActivities": "營業利益（損失）",
    },
    "BalanceSheet": {
        "Assets": "資產總額",
        "EquityAttributableToOwnersOfParent": "歸屬於母公司業主之權益合計",
    },
    "CashflowStatement": {
        "CashFlowsFromUsedInOperatingActivities": "營業活動之淨現金流入（流出）",
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "取得不動產、廠房及設備",
        "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "取得無形資產",
    },
}


class MopsFinError(ValueError):
    retryable = False
    circuit_failure = False


def _amount(raw: str, *, label: str) -> int:
    if not NUMBER_RE.fullmatch(raw):
        raise MopsFinError(f"invalid or missing monetary value: {label}")
    try:
        amount = Decimal(raw.replace(",", "")) * 1000
    except InvalidOperation as exc:
        raise MopsFinError(f"invalid monetary value: {label}") from exc
    if amount != amount.to_integral_value():
        raise MopsFinError(f"non-integral TWD value: {label}")
    return int(amount)


def parse_statement(raw: bytes, issuer: str, statement: str) -> dict[str, int]:
    """Read exactly one issuer's consolidated Q4 rows from one response."""
    if statement not in STATEMENT_FIELDS or not re.fullmatch(r"\d{4}", issuer):
        raise MopsFinError("unsupported comparison statement or issuer")
    if (not isinstance(raw, bytes) or len(raw) > MAX_BYTES
            or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper()):
        raise MopsFinError("comparison response exceeds limit or contains declarations")
    soup = BeautifulSoup(raw, "html.parser")
    if "金額單位：新台幣仟元" not in soup.get_text(" ", strip=True):
        raise MopsFinError("comparison response does not state TWD thousands")
    tables = soup.find_all("table")
    if len(tables) != 2:
        raise MopsFinError("comparison response has no unambiguous statement tables")
    names = [cell.get_text(" ", strip=True) for cell in tables[1].select("thead th")]
    if len(names) != 2 or names[0] != "合併" or not re.match(rf"^{issuer}(?:\s|$)", names[1]):
        raise MopsFinError("comparison issuer or consolidated scope mismatch")
    label_cells = tables[0].select("tbody tr")
    value_cells = tables[1].select("tbody tr")
    if len(label_cells) != len(value_cells) or not label_cells:
        raise MopsFinError("comparison row alignment mismatch")
    rows: dict[str, list[str]] = {}
    for label_row, value_row in zip(label_cells, value_cells):
        labels, values = label_row.find_all("td", recursive=False), value_row.find_all("td", recursive=False)
        if len(labels) != 1 or len(values) != 1:
            raise MopsFinError("comparison has ambiguous columns")
        label = labels[0].get_text(" ", strip=True)
        rows.setdefault(label, []).append(values[0].get_text(" ", strip=True))
    parsed = {}
    for fact, label in STATEMENT_FIELDS[statement].items():
        matches = rows.get(label, [])
        if len(matches) != 1:
            raise MopsFinError(f"missing or duplicate comparison fact: {label}")
        parsed[fact] = _amount(matches[0], label=label)
        if fact.startswith("PurchaseOf") and parsed[fact] > 0:
            raise MopsFinError(f"cash outflow sign is ambiguous: {label}")
    return parsed


def _request_statement(client: httpx.Client, statement: str, issuer: str, year: int, *, request_observer=None) -> bytes:
    payload = {
        "compareItem": statement, "quarter": "false", "ylabel": "",
        "ys": f"{year}4", "revenue": "false", "bcodeAvg": "false",
        "companyAvg": "false", "qnumber": "", "companyId": issuer,
    }
    observation = {"provider": PROVIDER, "url": REPORT_URL, "request_method": "POST", "http_request_sent": False}
    try:
        observation["http_request_sent"] = True
        response = client.post(REPORT_URL, data=payload, headers={"Referer": BASE + "/"})
    except httpx.HTTPError as exc:
        observation["error_kind"] = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport_error"
        if request_observer is not None:
            request_observer(dict(observation))
        raise MopsFinError(f"comparison transport error: {type(exc).__name__}") from exc
    observation.update(http_status=response.status_code, response_bytes=len(response.content),
                       response_sha256=sha256(response.content).hexdigest())
    if request_observer is not None:
        request_observer(dict(observation))
    if response.status_code != 200:
        raise MopsFinError(f"comparison HTTP {response.status_code}")
    if len(response.content) > MAX_BYTES:
        raise MopsFinError("comparison response exceeds size limit")
    return response.content


def fetch_official_comparison_year(
    issuer: str, year: int, *, client: httpx.Client | None = None, request_observer=None,
) -> dict:
    """Fetch one Q4 consolidated year; every required fact must be explicit."""
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1" and client is None:
        raise MopsFinError("network is disabled for tests")
    if not re.fullmatch(r"\d{4}", issuer) or not isinstance(year, int) or not 2013 <= year <= date.today().year:
        raise MopsFinError("invalid comparison issuer or year")
    owns_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(6, connect=3), follow_redirects=False)
    started = time.monotonic()
    facts, documents = {}, []
    try:
        for statement in STATEMENT_FIELDS:
            if time.monotonic() - started > DEADLINE_SECONDS:
                raise MopsFinError("comparison annual deadline exceeded")
            raw = (_request_statement(client, statement, issuer, year, request_observer=request_observer)
                   if request_observer is not None else _request_statement(client, statement, issuer, year))
            facts.update(parse_statement(raw, issuer, statement))
            documents.append({
                "year": year, "period_end": f"{year}-12-31", "statement": statement,
                "provider": PROVIDER, "url": REPORT_URL,
                "request": {"companyId": issuer, "ys": f"{year}4", "compareItem": statement},
                "sha256": sha256(raw).hexdigest(),
            })
        return {"facts": facts, "documents": documents}
    finally:
        if owns_client:
            client.close()
