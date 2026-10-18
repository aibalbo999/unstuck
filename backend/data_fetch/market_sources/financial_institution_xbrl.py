"""Sector-specific financial-institution facts from official consolidated iXBRL.

Net revenue is a financial-institution statement line. It must not be silently
substituted for the general-industry Revenue or GrossProfit histories.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
import re
import math
import time
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

import httpx

from .official_xbrl_financial import (
    INDEX_URL, MAX_BYTES, NUMBER_RE, FilingError, FilingTransportError,
    _bounded_request, _context_period, _fetch_filing_document, _fetch_index_response, _filing_urls,
)
from .broker_xbrl import (
    broker_taxonomy_present, parse_filing as parse_broker_filing,
    assemble_histories as assemble_broker_histories,
    reconcile_comparatives as reconcile_broker_comparatives,
)
from .insurer_xbrl import (
    insurer_taxonomy_present, parse_filing as parse_insurer_filing,
    assemble_histories as assemble_insurer_histories,
    reconcile_comparatives as reconcile_insurer_comparatives,
    standalone_scope_evidence, STANDALONE_SCHEMA,
)


PROVIDER = "TWSE MOPS official financial-institution iXBRL"
XBRLI = "{http://www.xbrl.org/2003/instance}"
IX = "{http://www.xbrl.org/2013/inlineXBRL}"
FIELDS = {
    "ifrs-full:RevenueFromInterest": "interest_income",
    "tifrs-bsci-fh:NetInterestIncomeExpense": "net_interest_revenue",
    "tifrs-bsci-fh:NetServiceFeeChargeAndCommissionsIncomeLoss": "net_fee_revenue",
    "tifrs-bsci-fh:NetIncomeLoss": "net_revenue",
    "ifrs-full:ProfitLossAttributableToOwnersOfParent": "net_income_attributable",
    "ifrs-full:Assets": "assets",
    "ifrs-full:EquityAttributableToOwnersOfParent": "equity",
    "ifrs-full:CashFlowsFromUsedInOperatingActivities": "operating_cash_flow",
    "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "ppe_purchase",
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": "intangible_purchase",
}
BANK_TAGS = {
    "tifrs-bsci-fh:NetInterestIncomeExpense": "tifrs-bsci-basi:NetIncomeLossOfInterest",
    "tifrs-bsci-fh:NetServiceFeeChargeAndCommissionsIncomeLoss": "tifrs-bsci-basi:NetServiceFeeChargeIncomeLosses",
    "tifrs-bsci-fh:NetIncomeLoss": "tifrs-bsci-basi:NetIncome",
}
BANK_FIELDS = {BANK_TAGS.get(tag, tag): field for tag, field in FIELDS.items()}
BANK_SCHEMA = "bank_consolidated.v1"
HOLDING_SCHEMA = "financial_holding_consolidated.v2"


def _fact_fields(names):
    bank = bool(set(names) & set(BANK_TAGS.values()))
    holding = bool(set(names) & set(BANK_TAGS))
    if bank and holding:
        raise FilingError("mixed bank and financial-holding statement facts")
    return BANK_FIELDS if bank else FIELDS
INSTANT_FIELDS = {"ifrs-full:Assets", "ifrs-full:EquityAttributableToOwnersOfParent"}
OUTFLOWS = {"ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
            "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"}
OPTIONAL_BANK_CASHFLOW_FACTS = {
    "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
}


def parse_filing(raw: bytes, issuer: str, year: int, *, allow_missing: bool = False) -> dict[str, int]:
    """Read explicit raw TWD statement facts for one issuer and fiscal year."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise FilingError("financial-institution XBRL exceeds limit or includes external declarations")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FilingError("financial-institution XBRL is not well-formed XML") from exc
    if root.tag != "{http://www.w3.org/1999/xhtml}html":
        raise FilingError("financial-institution XBRL root is not official inline XHTML")
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
    duration = ("duration", f"{year}-01-01", f"{year}-12-31")
    instant = ("instant", f"{year}-12-31")
    facts = list(root.iter(f"{IX}nonFraction"))
    names = {fact.get("name", "") for fact in facts
             if periods.get(fact.get("contextRef")) == (instant if fact.get("name") in INSTANT_FIELDS else duration)}
    fields = _fact_fields(names)
    values = {}
    for fact in facts:
        tag = fact.get("name", "")
        if tag not in fields or periods.get(fact.get("contextRef")) != (instant if tag in INSTANT_FIELDS else duration):
            continue
        if tag in values:
            raise FilingError(f"duplicate {tag} for {year}")
        if units.get(fact.get("unitRef")) != "iso4217:TWD":
            raise FilingError(f"wrong currency for {tag} {year}")
        if (fact.get("format") != "ixt:numdotdecimal" or fact.get("scale") != "3"
                or fact.get("decimals") not in {"-3", "INF"}):
            raise FilingError(f"unsupported financial-institution number format for {tag} {year}")
        sign = fact.get("sign")
        if sign not in (None, "-"):
            raise FilingError(f"unsupported sign for {tag} {year}")
        value_text = "".join(fact.itertext()).strip()
        if len(value_text) > 40 or not NUMBER_RE.fullmatch(value_text):
            raise FilingError(f"non-numeric fact for {tag} {year}")
        try:
            number = Decimal(value_text.replace(",", "")) * 1000
        except InvalidOperation as exc:
            raise FilingError(f"invalid fact for {tag} {year}") from exc
        if number != number.to_integral_value():
            raise FilingError(f"non-integral TWD fact for {tag} {year}")
        values[tag] = int(number) * (-1 if sign == "-" else 1)
        if tag in OUTFLOWS and values[tag] > 0:
            raise FilingError(f"cash outflow sign is ambiguous for {tag} {year}")
    if not allow_missing and set(values) != set(fields):
        raise FilingError(f"missing financial-institution facts for {year}: {','.join(sorted(set(fields) - set(values)))}")
    return values


def assemble_histories(facts_by_year: dict[int, dict[str, int]], *, expected_years: list[int]) -> dict:
    years = sorted(expected_years)
    if len(years) != len(set(years)) or set(years) != set(facts_by_year):
        raise FilingError("financial-institution year coverage is incomplete")
    result = {"schema": "financial_institution_consolidated.v1", "years": [str(y) for y in years],
              "raw_twd_by_year": {}}
    fields = _fact_fields(facts_by_year[years[0]]) if years else FIELDS
    if fields is BANK_FIELDS:
        result["schema"] = BANK_SCHEMA
        result["statement_taxonomy"] = "bank"
    for year in years:
        facts = facts_by_year[year]
        missing = set(fields) - set(facts)
        optional_missing = OPTIONAL_BANK_CASHFLOW_FACTS if fields is BANK_FIELDS else set()
        if missing - optional_missing or set(facts) - set(fields):
            raise FilingError(f"financial-institution facts are incomplete for {year}")
        row = {field: facts[tag] for tag, field in fields.items() if tag in facts}
        if missing:
            # Missing reported capex is unknown. Do not turn it into zero or
            # publish a fabricated free-cash-flow value.
            row["intangible_purchase"] = None
            row["free_cash_flow"] = None
        else:
            row["free_cash_flow"] = row["operating_cash_flow"] + row["ppe_purchase"] + row["intangible_purchase"]
        result["raw_twd_by_year"][str(year)] = row
    return result


def reconcile_comparatives(rows: dict[int, dict[str, int]], comparatives: dict[int, dict[str, int]]) -> tuple[dict, list]:
    resolved = {year: dict(values) for year, values in rows.items()}
    revisions = []
    for year, comparative in comparatives.items():
        original = resolved[year]
        fields = _fact_fields(original)
        if not set(comparative) <= set(fields):
            raise FilingError(f"financial-institution comparative taxonomy mismatch for {year}")
        conflicts = {tag: (original[tag], value) for tag, value in comparative.items()
                     if tag in original and original[tag] != value}
        bank_taxonomy = fields is BANK_FIELDS
        if conflicts and set(comparative) != set(fields) and not bank_taxonomy:
            raise FilingError(f"conflicting incomplete financial-institution comparative for {year}")
        for tag, value in comparative.items():
            if tag not in original:
                revisions.append({"year": year, "fact": tag, "original_twd": None, "revised_twd": value,
                                  "original_filing_year": year, "comparative_filing_year": year + 1,
                                  "kind": "missing_fact_fill"})
        for tag, (old, new) in conflicts.items():
            revisions.append({"year": year, "fact": tag, "original_twd": old, "revised_twd": new,
                              "original_filing_year": year, "comparative_filing_year": year + 1,
                              "kind": "restatement"})
        if set(comparative) == set(fields):
            resolved[year] = dict(comparative)
        else:
            for tag, value in comparative.items():
                if bank_taxonomy:
                    # This is an explicit same-issuer bank fact from a later
                    # official filing. Apply the restatement and retain both
                    # values in comparative_revisions above.
                    original[tag] = value
                else:
                    original.setdefault(tag, value)
    return resolved, revisions


def verified_bank_originals(statement, ticker):
    """Reconstruct the bank's facts and revisions from five complete bodies."""
    return _verified_institution_originals(statement, ticker, BANK_SCHEMA, "bank", BANK_FIELDS)


def verified_holding_originals(statement, ticker):
    """A v2 holding never falls back to legacy facts-only receipt validation."""
    if (not isinstance(statement, dict) or statement.get("currency") != "TWD"
            or statement.get("report_scope") != "consolidated"):
        return False
    return _verified_institution_originals(statement, ticker, HOLDING_SCHEMA, "financial_holding", FIELDS)


def _verified_institution_originals(statement, ticker, schema, taxonomy, fact_fields):
    from official_response_evidence import read_response
    if (not isinstance(statement, dict) or not isinstance(ticker, str)
            or not re.fullmatch(r"[0-9]{4}\.TW(?:O)?", ticker)
            or statement.get("schema") != schema or statement.get("ticker") != ticker
            or statement.get("statement_taxonomy") != taxonomy
            or not isinstance(statement.get("years"), list)
            or any(not isinstance(y, str) or not re.fullmatch(r"20[0-9]{2}", y) for y in statement["years"])
            or not isinstance(statement.get("documents"), list) or len(statement["documents"]) != 5):
        return False
    try:
        years = [int(y) for y in statement["years"]]
        if len(years) != 5 or years != list(range(years[0], years[0] + 5)):
            return False
        issuer = ticker.split(".")[0]
        rows, comparatives = {}, {}
        for document in statement["documents"]:
            if (not isinstance(document, dict) or type(document.get("year")) is not int
                    or not isinstance(document.get("source_record_archive"), dict)
                    or not isinstance(document.get("url"), str)):
                return False
            year = document["year"]
            if document.get("statement_taxonomy") != taxonomy or year not in years or year in rows:
                return False
            proof = document["source_record_archive"]
            url = document["url"]; parsed = urlsplit(url); query = parse_qs(parsed.query, keep_blank_values=True)
            expected = {"functionName": ["t164sb01"], "step": ["9"], "co_id": [issuer],
                        "year": [str(year)], "season": ["4"], "report_id": ["C"]}
            if (parsed.scheme != "https" or parsed.netloc != "mopsov.twse.com.tw"
                    or parsed.path != "/server-java/FileDownLoad" or parsed.fragment or query != expected
                    or proof.get("status") != "archived" or proof.get("source_url") != url
                    or proof.get("evidence_kind") != "decoded_http_response_body_bytes"
                    or type(proof.get("http_status")) is not int or proof["http_status"] != 200):
                return False
            epoch = proof.get("retrieved_at")
            period_closed = datetime(year + 1, 1, 1, tzinfo=ZoneInfo("Asia/Taipei")).timestamp()
            if type(epoch) not in (int, float) or not math.isfinite(epoch) or not period_closed <= epoch <= time.time():
                return False
            raw = read_response(proof)
            if (not 0 < len(raw) <= MAX_BYTES or type(proof.get("raw_response_bytes")) is not int or proof["raw_response_bytes"] != len(raw)
                    or proof.get("raw_response_sha256") != document.get("sha256")):
                return False
            rows[year] = parse_filing(raw, issuer, year, allow_missing=True)
            if _fact_fields(rows[year]) is not fact_fields:
                return False
            if year > years[0]:
                comparatives[year - 1] = parse_filing(raw, issuer, year - 1, allow_missing=True)
        if set(rows) != set(years):
            return False
        rows, revisions = reconcile_comparatives(rows, comparatives)
        rebuilt = assemble_histories(rows, expected_years=years)
        return (rebuilt["raw_twd_by_year"] == statement["raw_twd_by_year"]
                and revisions == statement["comparative_revisions"])
    except (KeyError,ValueError,TypeError,OverflowError,OSError,EOFError,zlib.error):
        return False


def fetch_financial_institution_histories(ticker: str, *, client: httpx.Client | None = None) -> dict:
    """Fetch sector filings, preserving consolidated versus insurer individual scope."""
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1" and client is None:
        raise FilingError("network is disabled for tests")
    match = re.fullmatch(r"(\d{4})\.TW(?:O)?", ticker)
    if not match:
        raise FilingError("financial-institution XBRL requires a Taiwan stock ticker")
    issuer = match.group(1)
    owns_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False)
    try:
        index = _fetch_index_response(client, {
            "step": "1", "firstin": "ture", "off": "1", "queryName": "co_id",
            "inpuType": "co_id", "TYPEK": "all", "co_id": issuer,
        }, request=_bounded_request)
        urls = _filing_urls(index, issuer)
        insurer_individual = len(urls) < 5
        if insurer_individual:
            urls = _filing_urls(index, issuer, report_id="A")
        if len(urls) < 5:
            raise FilingError("fewer than five consolidated or insurer individual annual filings")
        years = sorted(urls)[-5:]
        if years != list(range(years[0], years[0] + 5)):
            raise FilingError("financial-institution filing years are not contiguous")
        rows, comparatives, documents = {}, {}, []
        broker_taxonomy = None
        bank_taxonomy = None
        for year in years:
            raw = _fetch_filing_document(client, urls[year], request=_bounded_request)
            if insurer_individual and not insurer_taxonomy_present(raw):
                raise FilingError("individual annual filing is not an insurer statement")
            documents.append({"year": year, "url": urls[year], "sha256": sha256(raw).hexdigest(),
                              "report_scope": "individual" if insurer_individual else "consolidated"})
            if insurer_individual:
                scope_evidence = standalone_scope_evidence(raw, issuer, year)
                if scope_evidence:
                    documents[-1]["standalone_scope_evidence"] = scope_evidence
            observed_broker = broker_taxonomy_present(raw)
            if not insurer_individual:
                if broker_taxonomy is None:
                    broker_taxonomy = observed_broker
                elif broker_taxonomy != observed_broker:
                    raise FilingError("financial-institution filing taxonomy changes across years")
            parser = parse_insurer_filing if insurer_individual else (parse_broker_filing if broker_taxonomy else parse_filing)
            rows[year] = parser(raw, issuer, year, allow_missing=True)
            if not insurer_individual and not broker_taxonomy:
                is_bank = _fact_fields(rows[year]) is BANK_FIELDS
                if bank_taxonomy is not None and bank_taxonomy != is_bank:
                    raise FilingError("bank/financial-holding statement taxonomy changes across years")
                bank_taxonomy = is_bank
                from official_response_evidence import archive_response, read_response
                try:
                    proof = archive_response(raw, source_url=urls[year], retrieved_at=time.time(),
                        evidence_kind="decoded_http_response_body_bytes", http_status=200)
                    if proof.get("status") != "archived" or read_response(proof) != raw:
                        raise FilingError("financial-institution complete original could not be archived")
                except (OSError,ValueError,EOFError,zlib.error) as exc:
                    raise FilingError("financial-institution complete original archive is unreadable") from exc
                documents[-1].update(statement_taxonomy="bank" if is_bank else "financial_holding",
                                     source_record_archive=proof)
            if year > years[0]:
                comparatives[year - 1] = parser(raw, issuer, year - 1, allow_missing=True)
        reconciler = (reconcile_insurer_comparatives if insurer_individual else
                      reconcile_broker_comparatives if broker_taxonomy else reconcile_comparatives)
        assembler = (assemble_insurer_histories if insurer_individual else
                     assemble_broker_histories if broker_taxonomy else assemble_histories)
        rows, revisions = reconciler(rows, comparatives)
        result = assembler(rows, expected_years=years)
        standalone = insurer_individual and all(d.get("standalone_scope_evidence") for d in documents)
        scope = "standalone" if standalone else "individual" if insurer_individual else "consolidated"
        if standalone:
            result["schema"] = STANDALONE_SCHEMA
            for document in documents:
                document["report_scope"] = scope
        result.update(ticker=ticker, report_scope=scope,
                      documents=documents, source_url=INDEX_URL, comparative_revisions=revisions)
        if not insurer_individual and not broker_taxonomy and bank_taxonomy is False:
            result.update(schema=HOLDING_SCHEMA, statement_taxonomy="financial_holding", currency="TWD")
            if not verified_holding_originals(result, ticker):
                raise FilingError("financial-holding complete originals could not be verified")
        return result
    except httpx.HTTPError as exc:
        raise FilingTransportError(f"MOPS transport error: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            client.close()
