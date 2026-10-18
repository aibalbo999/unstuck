"""Current-session TPEx institutional rows from its public OpenAPI.

The endpoint publishes only the latest session. The similar-looking
``Dealers -TotalSell`` column is a separate field, not the dealer total sell
used for the reported net; its meaning is deliberately not inferred here.
"""

from __future__ import annotations

from datetime import date
import json
import re


URL = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading"
SOURCE = "TPEx institutional OpenAPI"
MAX_BYTES = 2_000_000
MAX_ROWS = 2_000

EX_BUY = "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Buy"
EX_SELL = " Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Total Sell"
EX_NET = "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference"
FOREIGN_DEALER_BUY = "Foreign Dealers-Total Buy"
FOREIGN_DEALER_SELL = "Foreign Dealers-TotalSell"
FOREIGN_DEALER_NET = "ForeignDealers-Difference"
FOREIGN_BUY = "ForeignInvestorsIncludeMainlandAreaInvestors-TotalBuy"
FOREIGN_SELL = "ForeignInvestorsIncludeMainlandAreaInvestors-TotalSell"
FOREIGN_NET = "ForeignInvestorsInclude MainlandAreaInvestors-Difference"
TRUST_BUY = "SecuritiesInvestmentTrustCompanies-TotalBuy"
TRUST_SELL = "SecuritiesInvestmentTrustCompanies-TotalSell"
TRUST_NET = "SecuritiesInvestmentTrustCompanies-Difference"
DEALER_BUY = "Dealers-TotalBuy"
DEALER_SELL = "Dealers-TotalSell"
DEALER_NET = "Dealers-Difference"
OTHER_DEALER_SELL = "Dealers -TotalSell"
TOTAL_NET = "TotalDifference"
FIELDS = frozenset({
    "Date", "SecuritiesCompanyCode", "CompanyName", EX_BUY, EX_SELL, EX_NET,
    FOREIGN_DEALER_BUY, FOREIGN_DEALER_SELL, FOREIGN_DEALER_NET,
    FOREIGN_BUY, FOREIGN_SELL, FOREIGN_NET, TRUST_BUY, TRUST_SELL, TRUST_NET,
    DEALER_BUY, DEALER_SELL, DEALER_NET, OTHER_DEALER_SELL, TOTAL_NET,
})
PAIRS = (
    (EX_BUY, EX_SELL, EX_NET),
    (FOREIGN_DEALER_BUY, FOREIGN_DEALER_SELL, FOREIGN_DEALER_NET),
    (FOREIGN_BUY, FOREIGN_SELL, FOREIGN_NET),
    (TRUST_BUY, TRUST_SELL, TRUST_NET),
    (DEALER_BUY, DEALER_SELL, DEALER_NET),
)


def _roc_day(value: object) -> date | None:
    stamp = str(value or "").strip()
    if not re.fullmatch(r"\d{7}", stamp):
        return None
    try:
        return date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:]))
    except ValueError:
        return None


def _shares(value: object) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"-?\d{1,20}", str(value or "")):
        raise ValueError("invalid TPEx institutional share quantity")
    return int(value)


def parse_latest_report(raw: bytes, requested_day: str) -> dict:
    """Accept one exact session with fully reconciled per-security share totals."""
    try:
        expected = date.fromisoformat(requested_day)
    except ValueError as exc:
        raise ValueError("invalid TPEx requested date") from exc
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("TPEx OpenAPI response size invalid")
    try:
        records = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("TPEx OpenAPI JSON invalid") from exc
    if not isinstance(records, list) or not 0 < len(records) <= MAX_ROWS:
        raise ValueError("TPEx OpenAPI report shape invalid")
    rows = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != FIELDS:
            raise ValueError("TPEx OpenAPI schema changed")
        if any(not isinstance(record[field], str) for field in ("Date", "SecuritiesCompanyCode", "CompanyName")):
            raise ValueError("TPEx OpenAPI identity types changed")
        if _roc_day(record["Date"]) != expected:
            raise ValueError("TPEx OpenAPI observation date does not match query")
        code = str(record["SecuritiesCompanyCode"] or "").strip()
        name = str(record["CompanyName"] or "").strip()
        if not re.fullmatch(r"[0-9A-Z]{4,8}", code) or code in rows or not 0 < len(name) <= 100:
            raise ValueError("TPEx OpenAPI security identity invalid or duplicated")
        values = {field: _shares(record[field]) for field in FIELDS - {"Date", "SecuritiesCompanyCode", "CompanyName"}}
        if values[OTHER_DEALER_SELL] < 0 or any(values[buy] < 0 or values[sell] < 0 for buy, sell, _ in PAIRS):
            raise ValueError("TPEx OpenAPI gross trading quantity invalid")
        if any(values[buy] - values[sell] != values[net] for buy, sell, net in PAIRS):
            raise ValueError("TPEx OpenAPI category shares do not reconcile")
        if (values[EX_BUY] + values[FOREIGN_DEALER_BUY] != values[FOREIGN_BUY]
                or values[EX_SELL] + values[FOREIGN_DEALER_SELL] != values[FOREIGN_SELL]
                or values[EX_NET] + values[FOREIGN_DEALER_NET] != values[FOREIGN_NET]
                or values[FOREIGN_NET] + values[TRUST_NET] + values[DEALER_NET] != values[TOTAL_NET]):
            raise ValueError("TPEx OpenAPI institutional totals conflict")
        rows[code] = {
            "company_name": name, "foreign": values[FOREIGN_NET],
            "investment_trust": values[TRUST_NET], "dealer": values[DEALER_NET],
        }
    return {"date": expected.isoformat(), "rows": rows, "report_status": "available",
            "market": "TPEX", "source": SOURCE}
