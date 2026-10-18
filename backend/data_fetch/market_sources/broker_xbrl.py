"""Reported securities-broker statement lines from official consolidated iXBRL.

Broker revenue and underwriting fees have their own taxonomy. They must never
be relabelled as a bank's net interest or net service-fee revenue.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from .official_xbrl_financial import MAX_BYTES, NUMBER_RE, FilingError, _context_period


SCHEMA = "broker_consolidated.v1"
XBRLI = "{http://www.xbrl.org/2003/instance}"
IX = "{http://www.xbrl.org/2013/inlineXBRL}"
FIELDS = {
    "ifrs-full:Revenue": "reported_revenue",
    "ifrs-full:BrokerageFeeIncome": "brokerage_fee_income",
    "tifrs-bsci-bd:RevenuesFromUnderwritingBusiness": "underwriting_revenue",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent": "net_income_attributable",
    "ifrs-full:Assets": "assets",
    "ifrs-full:EquityAttributableToOwnersOfParent": "equity",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "operating_cash_flow",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "ppe_purchase",
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "intangible_purchase",
}
INSTANT_FIELDS = {"ifrs-full:Assets", "ifrs-full:EquityAttributableToOwnersOfParent"}
OUTFLOWS = {"ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"}
BROKER_MARKER = b'name="tifrs-bsci-bd:RevenuesFromUnderwritingBusiness"'


def broker_taxonomy_present(raw: bytes) -> bool:
    """A routing hint only; parsing below still verifies issuer, period and fact."""
    return isinstance(raw, bytes) and BROKER_MARKER in raw


def parse_filing(raw: bytes, issuer: str, year: int, *, allow_missing: bool = False) -> dict[str, int]:
    if (not isinstance(raw, bytes) or len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper()
            or b"<!ENTITY" in raw.upper()):
        raise FilingError("broker XBRL exceeds limit or includes external declarations")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FilingError("broker XBRL is not well-formed XML") from exc
    if root.tag != "{http://www.w3.org/1999/xhtml}html":
        raise FilingError("broker XBRL root is not official inline XHTML")
    units = {}
    for unit in root.iter(f"{XBRLI}unit"):
        uid = unit.get("id")
        if uid in units:
            raise FilingError("duplicate broker XBRL unit")
        units[uid] = unit.findtext(f"{XBRLI}measure")
    periods = {}
    for context in root.iter(f"{XBRLI}context"):
        cid = context.get("id")
        if cid in periods:
            raise FilingError("duplicate broker XBRL context")
        periods[cid] = _context_period(context, issuer)
    duration = ("duration", f"{year}-01-01", f"{year}-12-31")
    instant = ("instant", f"{year}-12-31")
    values = {}
    for fact in root.iter(f"{IX}nonFraction"):
        tag = fact.get("name", "")
        if tag not in FIELDS or periods.get(fact.get("contextRef")) != (instant if tag in INSTANT_FIELDS else duration):
            continue
        if tag in values:
            raise FilingError(f"duplicate broker {tag} for {year}")
        if units.get(fact.get("unitRef")) != "iso4217:TWD":
            raise FilingError(f"wrong broker currency for {tag} {year}")
        if (fact.get("format") != "ixt:numdotdecimal" or fact.get("scale") != "3"
                or fact.get("decimals") not in {"-3", "INF"}):
            raise FilingError(f"unsupported broker number format for {tag} {year}")
        sign = fact.get("sign")
        if sign not in (None, "-"):
            raise FilingError(f"unsupported broker sign for {tag} {year}")
        value_text = "".join(fact.itertext()).strip()
        if len(value_text) > 40 or not NUMBER_RE.fullmatch(value_text):
            raise FilingError(f"non-numeric broker fact for {tag} {year}")
        try:
            number = Decimal(value_text.replace(",", "")) * 1000
        except InvalidOperation as exc:
            raise FilingError(f"invalid broker fact for {tag} {year}") from exc
        if number != number.to_integral_value():
            raise FilingError(f"non-integral broker TWD fact for {tag} {year}")
        values[tag] = int(number) * (-1 if sign == "-" else 1)
        if tag in OUTFLOWS and values[tag] > 0:
            raise FilingError(f"cash outflow sign is ambiguous for broker {tag} {year}")
    if not allow_missing and set(values) != set(FIELDS):
        raise FilingError(f"missing broker facts for {year}: {','.join(sorted(set(FIELDS)-set(values)))}")
    return values


def reconcile_comparatives(rows: dict[int, dict[str, int]], comparatives: dict[int, dict[str, int]]) -> tuple[dict, list]:
    resolved = {year: dict(values) for year, values in rows.items()}
    revisions = []
    for year, comparative in comparatives.items():
        original = resolved[year]
        conflicts = {tag: (original[tag], value) for tag, value in comparative.items()
                     if tag in original and original[tag] != value}
        if conflicts and set(comparative) != set(FIELDS):
            raise FilingError(f"conflicting incomplete broker comparative for {year}")
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


def assemble_histories(facts_by_year: dict[int, dict[str, int]], *, expected_years: list[int]) -> dict:
    years = sorted(expected_years)
    if len(years) != len(set(years)) or set(years) != set(facts_by_year):
        raise FilingError("broker annual year coverage is incomplete")
    result = {"schema": SCHEMA, "years": [str(year) for year in years], "raw_twd_by_year": {}}
    for year in years:
        facts = facts_by_year[year]
        if set(facts) != set(FIELDS):
            raise FilingError(f"broker facts are incomplete for {year}")
        row = {field: facts[tag] for tag, field in FIELDS.items()}
        row["free_cash_flow"] = row["operating_cash_flow"] + row["ppe_purchase"] + row["intangible_purchase"]
        result["raw_twd_by_year"][str(year)] = row
    return result
