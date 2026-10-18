"""Insurer-specific facts from official individual/standalone annual iXBRL.

Only an issuer-bound, affirmative annual note proves no subsidiaries. Standalone
projections retain insurance statement labels and never become bank net revenue
or consolidated group statements.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from xml.etree import ElementTree as ET

from .official_xbrl_financial import MAX_BYTES, NUMBER_RE, FilingError, _context_period


SCHEMA = "insurer_individual.v1"
STANDALONE_SCHEMA = "insurer_standalone.v1"
SCOPE_FACT = "tifrs-notes:BasisOfPreparation"
NO_SUBSIDIARIES = "本公司並無子公司，故本財務報告係個別財務報告"
XBRLI = "{http://www.xbrl.org/2003/instance}"
IX = "{http://www.xbrl.org/2013/inlineXBRL}"
FIELDS = {
    "tifrs-bsci-ins:OperatingRevenue": "insurance_operating_revenue",
    "tifrs-bsci-ins:NetOperatingIncomeLoss": "net_operating_income",
    "ifrs-full:ProfitLoss": "profit_loss",
    "ifrs-full:Assets": "assets",
    "ifrs-full:Equity": "equity",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "operating_cash_flow",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "ppe_purchase",
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "intangible_purchase",
}
INSTANT_FIELDS = {"ifrs-full:Assets", "ifrs-full:Equity"}
OUTFLOWS = {"ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"}
INSURER_MARKER = b'name="tifrs-bsci-ins:OperatingRevenue"'


def insurer_taxonomy_present(raw: bytes) -> bool:
    """Only a routing hint; the parser still verifies all exact facts."""
    return isinstance(raw, bytes) and INSURER_MARKER in raw


def _unambiguous_standalone_note(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text)
    # Admit the observed affirmative opening, not a quotation/prior-period
    # mention embedded somewhere in the note. Unknown wording stays individual.
    opening = r"^(?:1[.．、])?" + re.escape(NO_SUBSIDIARIES) + r"(?:[，,。；;]|$)"
    contradiction = r"(?:本公司|本期|本年度)[^。；;]{0,24}(?:有|新增|設立|持有|控制)[^。；;]{0,12}子公司"
    return bool(re.match(opening, normalized)) and not re.search(contradiction, normalized)


def standalone_scope_evidence(raw: bytes, issuer: str, year: int) -> dict | None:
    """An A-scope URL alone cannot prove an insurer has no subsidiaries."""
    if (not isinstance(raw, bytes) or len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper()
            or b"<!ENTITY" in raw.upper()):
        return None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    if root.tag != "{http://www.w3.org/1999/xhtml}html":
        return None
    contexts = {}
    for context in root.iter(f"{XBRLI}context"):
        cid = context.get("id")
        if cid in contexts:
            return None
        contexts[cid] = _context_period(context, issuer)
    target = ("duration", f"{year}-01-01", f"{year}-12-31")
    notes = [fact for fact in root.iter(f"{IX}nonNumeric")
             if fact.get("name") == SCOPE_FACT and contexts.get(fact.get("contextRef")) == target]
    if len(notes) != 1:
        return None
    text = "".join(notes[0].itertext()).strip()
    if len(text) > 12000 or not _unambiguous_standalone_note(text):
        return None
    return {"fact": SCOPE_FACT, "issuer": issuer, "year": year, "text": text,
            "document_sha256": sha256(raw).hexdigest()}


def standalone_evidence_valid(evidence, *, issuer: str, year: int, document_sha256: str) -> bool:
    """Recheck preserved scope evidence against its containing document receipt."""
    return (isinstance(evidence, dict) and evidence.get("fact") == SCOPE_FACT
            and evidence.get("issuer") == issuer and type(evidence.get("year")) is int
            and evidence["year"] == year and evidence.get("document_sha256") == document_sha256
            and isinstance(evidence.get("text"), str) and len(evidence["text"]) <= 12000
            and _unambiguous_standalone_note(evidence["text"]))


def parse_filing(raw: bytes, issuer: str, year: int, *, allow_missing: bool = False) -> dict[str, int]:
    if (not isinstance(raw, bytes) or len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper()
            or b"<!ENTITY" in raw.upper()):
        raise FilingError("insurer XBRL exceeds limit or includes external declarations")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FilingError("insurer XBRL is not well-formed XML") from exc
    if root.tag != "{http://www.w3.org/1999/xhtml}html":
        raise FilingError("insurer XBRL root is not official inline XHTML")
    units = {}
    for unit in root.iter(f"{XBRLI}unit"):
        uid = unit.get("id")
        if uid in units:
            raise FilingError("duplicate insurer XBRL unit")
        units[uid] = unit.findtext(f"{XBRLI}measure")
    periods = {}
    for context in root.iter(f"{XBRLI}context"):
        cid = context.get("id")
        if cid in periods:
            raise FilingError("duplicate insurer XBRL context")
        periods[cid] = _context_period(context, issuer)
    duration = ("duration", f"{year}-01-01", f"{year}-12-31")
    instant = ("instant", f"{year}-12-31")
    values = {}
    for fact in root.iter(f"{IX}nonFraction"):
        tag = fact.get("name", "")
        if tag not in FIELDS or periods.get(fact.get("contextRef")) != (instant if tag in INSTANT_FIELDS else duration):
            continue
        if tag in values:
            raise FilingError(f"duplicate insurer {tag} for {year}")
        if units.get(fact.get("unitRef")) != "iso4217:TWD":
            raise FilingError(f"wrong insurer currency for {tag} {year}")
        if (fact.get("format") != "ixt:numdotdecimal" or fact.get("scale") != "3"
                or fact.get("decimals") not in {"-3", "INF"}):
            raise FilingError(f"unsupported insurer number format for {tag} {year}")
        sign = fact.get("sign")
        if sign not in (None, "-"):
            raise FilingError(f"unsupported insurer sign for {tag} {year}")
        value_text = "".join(fact.itertext()).strip()
        if len(value_text) > 40 or not NUMBER_RE.fullmatch(value_text):
            raise FilingError(f"non-numeric insurer fact for {tag} {year}")
        try:
            number = Decimal(value_text.replace(",", "")) * 1000
        except InvalidOperation as exc:
            raise FilingError(f"invalid insurer fact for {tag} {year}") from exc
        if number != number.to_integral_value():
            raise FilingError(f"non-integral insurer TWD fact for {tag} {year}")
        values[tag] = int(number) * (-1 if sign == "-" else 1)
        if tag in OUTFLOWS and values[tag] > 0:
            raise FilingError(f"cash outflow sign is ambiguous for insurer {tag} {year}")
    if not allow_missing and set(values) != set(FIELDS):
        raise FilingError(f"missing insurer facts for {year}: {','.join(sorted(set(FIELDS)-set(values)))}")
    return values


def reconcile_comparatives(rows: dict[int, dict[str, int]], comparatives: dict[int, dict[str, int]]) -> tuple[dict, list]:
    resolved = {year: dict(values) for year, values in rows.items()}
    revisions = []
    for year, comparative in comparatives.items():
        original = resolved[year]
        conflicts = {tag: (original[tag], value) for tag, value in comparative.items()
                     if tag in original and original[tag] != value}
        if conflicts and set(comparative) != set(FIELDS):
            raise FilingError(f"conflicting incomplete insurer comparative for {year}")
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
        raise FilingError("insurer year coverage is incomplete")
    result = {"schema": SCHEMA, "report_scope": "individual", "years": [str(y) for y in years],
              "raw_twd_by_year": {}}
    for year in years:
        facts = facts_by_year[year]
        if set(facts) != set(FIELDS):
            raise FilingError(f"insurer facts are incomplete for {year}")
        row = {field: facts[tag] for tag, field in FIELDS.items()}
        row["free_cash_flow"] = row["operating_cash_flow"] + row["ppe_purchase"] + row["intangible_purchase"]
        result["raw_twd_by_year"][str(year)] = row
    return result
