"""Typed annual histories from complete issuer-bound statement receipts."""
from __future__ import annotations

from datetime import date
import math
import re
from urllib.parse import parse_qs, urlsplit

from mapping_fields import safe_mapping_dict

from .market_sources.broker_xbrl import FIELDS, SCHEMA
from .market_sources.financial_institution_xbrl import (
    FIELDS as INSTITUTION_FIELDS, BANK_FIELDS, BANK_SCHEMA, HOLDING_SCHEMA,
    verified_bank_originals, verified_holding_originals,
)
from .market_sources.official_xbrl_financial import INDEX_URL
from .market_sources.mops_public_holding import SCHEMA as PUBLIC_HOLDING_SCHEMA, project_public_holding_statement
from .market_sources.tcfhc_annual_financial import SCHEMA as AUDITED_HOLDING_SCHEMA, project_annual_statement, NOTE as AUDITED_HOLDING_NOTE
from .market_sources.insurer_xbrl import (
    FIELDS as INSURER_FIELDS, STANDALONE_SCHEMA, standalone_evidence_valid,
)


COMMON_FIELDS = {
    "revenue_history": ("reported_revenue", "ifrs-full:Revenue", "證券商合併營業收入"),
    "net_income_history": ("net_income_attributable", "ifrs-full:ProfitLossAttributableToOwnersOfParent", "合併淨利歸屬母公司業主"),
    "total_assets_history": ("assets", "ifrs-full:Assets", "合併資產總額"),
    "total_equity_history": ("equity", "ifrs-full:EquityAttributableToOwnersOfParent", "合併權益歸屬母公司業主"),
    "fcf_history": ("free_cash_flow", "operating_cash_flow+ppe_purchase+intangible_purchase", "合併營業現金流加明列設備及無形資產支出"),
}
UNSUPPLIED_FIELDS = ("gross_profit_history", "operating_income_history")
INSTITUTION_SCHEMA = "financial_institution_consolidated.v1"
INSTITUTION_SCHEMAS = frozenset({INSTITUTION_SCHEMA, BANK_SCHEMA, HOLDING_SCHEMA, PUBLIC_HOLDING_SCHEMA, AUDITED_HOLDING_SCHEMA})
INSTITUTION_COMMON_FIELDS = {
    "net_revenue_history": ("net_revenue", "tifrs-bsci-fh:NetIncomeLoss", "金融業合併淨收益"),
    **{key: value for key, value in COMMON_FIELDS.items() if key != "revenue_history"},
}
INSURER_COMMON_FIELDS = {
    "revenue_history": ("insurance_operating_revenue", "tifrs-bsci-ins:OperatingRevenue", "保險業個別營業收入"),
    "net_income_history": ("profit_loss", "ifrs-full:ProfitLoss", "保險業個別本期損益"),
    "total_assets_history": ("assets", "ifrs-full:Assets", "保險業個別資產總額"),
    "total_equity_history": ("equity", "ifrs-full:Equity", "保險業個別權益總額"),
    "fcf_history": ("free_cash_flow", "operating_cash_flow+ppe_purchase+intangible_purchase", "個別營業現金流加明列設備及無形資產支出"),
}


def is_ordinary_individual_basis(data):
    """A declared individual scope cannot license group/market conversions."""
    if not isinstance(data,dict):return False
    statement=safe_mapping_dict(data.get('sector_specific_financials'))or{}
    basis=safe_mapping_dict(data.get('financial_history_basis'))or{}
    return statement.get('schema')=='ordinary_individual.v1'or basis.get('statement_schema')=='ordinary_individual.v1'


def project_ordinary_individual_histories(statement,ticker):
    from .market_sources.ordinary_individual_annual import project_individual_history
    result=project_individual_history(statement,ticker)
    if result is None:return None
    return {k:v for k,v in result.items()if k!='sector_specific_financials'}


def project_insurer_standalone_histories(statement, ticker: str) -> dict | None:
    return _project_histories(statement, ticker, schema=STANDALONE_SCHEMA,
        required_fields=INSURER_FIELDS, common_fields=INSURER_COMMON_FIELDS,
        unsupplied_fields=UNSUPPLIED_FIELDS, scope="standalone", report_id="A",
        note="五年原件均明示本公司無子公司，採保險業個別財報；營業收入與本期損益保留原科目，不代表合併集團、銀行淨收益或一般業毛利。現金流算式未驗證金融業股東現金流 DCF 口徑。")


def project_broker_histories(statement, ticker: str) -> dict | None:
    return _project_histories(statement, ticker, schema=SCHEMA, required_fields=FIELDS,
        common_fields=COMMON_FIELDS, unsupplied_fields=UNSUPPLIED_FIELDS,
        note="證券商明列合併科目；營業收入不同於銀行淨收益，毛利及營業利益維持未提供。")


def project_financial_institution_histories(statement, ticker: str) -> dict | None:
    statement = safe_mapping_dict(statement)
    if statement is None:
        return None
    documents = statement.get("documents")
    if not isinstance(documents, list):
        return None
    schema = statement.get("schema")
    if schema == BANK_SCHEMA:
        if not verified_bank_originals(statement, ticker):
            return None
        common_fields = {**INSTITUTION_COMMON_FIELDS,
            "net_revenue_history": ("net_revenue", "tifrs-bsci-basi:NetIncome", "銀行業合併淨收益")}
    elif schema == HOLDING_SCHEMA:
        if not verified_holding_originals(statement, ticker):
            return None
        common_fields = INSTITUTION_COMMON_FIELDS
    elif schema in {PUBLIC_HOLDING_SCHEMA, AUDITED_HOLDING_SCHEMA}:
        verified = (project_annual_statement(statement, ticker) if schema == AUDITED_HOLDING_SCHEMA
                    else project_public_holding_statement(statement, ticker))
        if verified is None:
            return None
        return _history_projection(verified['raw_twd_by_year'], verified['years'], ticker,
            schema=schema, common_fields=INSTITUTION_COMMON_FIELDS,
            unsupplied_fields=("revenue_history", *UNSUPPLIED_FIELDS), scope="consolidated",
            note=(AUDITED_HOLDING_NOTE if schema == AUDITED_HOLDING_SCHEMA else
                  "金融業合併淨收益保留獨立 net_revenue_history；不代填一般產業營收、毛利或營業利益。原件現金流算式不證明可用於一般業 DCF 的正常化金融業股東現金流。"))
    elif schema == INSTITUTION_SCHEMA:
        if ("statement_taxonomy" in statement or any(isinstance(doc,dict)
                and ("statement_taxonomy" in doc or "source_record_archive" in doc)
                for doc in documents)):
            return None
        common_fields = INSTITUTION_COMMON_FIELDS
    else:
        return None
    note = "金融業合併淨收益保留獨立 net_revenue_history；不代填一般產業營收、毛利或營業利益。原件現金流算式不證明可用於一般業 DCF 的正常化金融業股東現金流。"
    if schema == BANK_SCHEMA and any(
            isinstance(row, dict) and row.get("intangible_purchase") is None
            for row in (statement.get("raw_twd_by_year") or {}).values()):
        note += "銀行原件未明列無形資產購置支出之年度，該年度 FCF 保持未知，不以零補值。"
    return _project_histories(statement, ticker, schema=schema,
        required_fields=BANK_FIELDS if schema == BANK_SCHEMA else INSTITUTION_FIELDS, common_fields=common_fields,
        unsupplied_fields=("revenue_history", *UNSUPPLIED_FIELDS),
        note=note)


def _project_histories(statement, ticker: str, *, schema, required_fields, common_fields,
                       unsupplied_fields, note, scope="consolidated", report_id="C") -> dict | None:
    """Only a complete issuer-bound five-year receipt with verified scope is eligible."""
    statement = safe_mapping_dict(statement)
    if (statement is None or not isinstance(ticker, str) or statement.get("schema") != schema
            or statement.get("ticker") != ticker or statement.get("report_scope") != scope
            or statement.get("source_url") != INDEX_URL
            or not isinstance(statement.get("comparative_revisions"), list)
            or not re.fullmatch(r"[0-9]{4}\.TW(?:O)?", ticker)):
        return None
    years = statement.get("years")
    rows = safe_mapping_dict(statement.get("raw_twd_by_year"))
    documents = statement.get("documents")
    if (not isinstance(years, list) or len(years) != 5
            or any(not isinstance(y, str) or not re.fullmatch(r"20[0-9]{2}", y) for y in years)
            or years != [str(y) for y in range(int(years[0]), int(years[0]) + 5)]
            or int(years[-1]) >= date.today().year
            or not isinstance(rows, dict) or set(rows) != set(years)
            or not isinstance(documents, list) or len(documents) != 5):
        return None
    document_years = set()
    for document in documents:
        document = safe_mapping_dict(document)
        if document is None or type(document.get("year")) is not int:
            return None
        year = str(document["year"])
        if year not in years or year in document_years or document.get("report_scope") != scope:
            return None
        url = document.get("url")
        if not isinstance(url, str):
            return None
        try:
            parsed = urlsplit(url)
        except ValueError:
            return None
        query = parse_qs(parsed.query)
        if (parsed.scheme != "https" or parsed.netloc != "mopsov.twse.com.tw"
                or parsed.path != "/server-java/FileDownLoad" or parsed.fragment
                or any(query.get(k) != [v] for k, v in {
                    "functionName": "t164sb01", "step": "9", "co_id": ticker.split(".")[0],
                    "season": "4", "report_id": report_id, "year": year}.items())
                or not isinstance(document.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", document["sha256"])):
            return None
        if scope == "standalone" and not standalone_evidence_valid(
                document.get("standalone_scope_evidence"), issuer=ticker.split(".")[0],
                year=document["year"], document_sha256=document["sha256"]):
            return None
        document_years.add(year)
    required = set(required_fields.values()) | {"free_cash_flow"}
    optional_unknown_fields = {"intangible_purchase", "free_cash_flow"} if schema == BANK_SCHEMA else set()
    for year in years:
        row = safe_mapping_dict(rows[year])
        if (row is None or set(row) != required
                or any(type(row[field]) is not int
                       and not (field in optional_unknown_fields and row[field] is None)
                       for field in required)
                or row["ppe_purchase"] > 0
                or (row["intangible_purchase"] is not None and row["intangible_purchase"] > 0)
                or (row["intangible_purchase"] is None and
                    (schema != BANK_SCHEMA or row["free_cash_flow"] is not None))
                or (row["intangible_purchase"] is not None and
                    row["free_cash_flow"] != row["operating_cash_flow"] + row["ppe_purchase"] + row["intangible_purchase"])):
            return None
        rows[year] = row
    return _history_projection(rows, years, ticker, schema=schema, common_fields=common_fields,
                               unsupplied_fields=unsupplied_fields, scope=scope, note=note)


def _history_projection(rows, years, ticker, *, schema, common_fields, unsupplied_fields, scope, note):
    """Format only rows already reconstructed and validated by their source contract."""
    try:
        values = {key: [None if rows[y][field] is None else rows[y][field] / 1e9 for y in years]
                  for key, (field, _fact, _label) in common_fields.items()}
    except OverflowError:
        return None
    if any(not math.isfinite(value) for history in values.values() for value in history if value is not None):
        return None
    result = {"years": list(years), **values,
              **{key: [None] * 5 for key in unsupplied_fields}}
    result["financial_history_basis"] = {
        "schema": "financial_history_basis.v1", "statement_schema": schema,
        "ticker": ticker, "report_scope": scope, "currency": "TWD", "unit": "billion_twd",
        "years": list(years),
        "source_path": "sector_specific_financials.raw_twd_by_year",
        "field_sources": {key: {"source_field": field, "fact": fact, "label": label}
                          for key, (field, fact, label) in common_fields.items()},
        "unsupplied_fields": list(unsupplied_fields),
        "note": note,
    }
    return result


def prompt_history_basis(data: dict) -> dict:
    """Expose scope only when preserved statement receipts match every array."""
    data = safe_mapping_dict(data)
    if data is None:
        return {}
    statement = safe_mapping_dict(data.get("sector_specific_financials")) or {}
    projector = (project_ordinary_individual_histories if statement.get("schema")=="ordinary_individual.v1"
                 else project_financial_institution_histories if statement.get("schema") in INSTITUTION_SCHEMAS
                 else project_insurer_standalone_histories if statement.get("schema") == STANDALONE_SCHEMA
                 else project_broker_histories)
    projected = projector(statement, data.get("ticker") or "")
    if projected is None or any(data.get(key) != value for key, value in projected.items()):
        return {}
    return projected["financial_history_basis"]


def financial_institution_history_metrics(data: dict) -> dict:
    """Same-period calculations keep the net-revenue input name and receipt."""
    basis = prompt_history_basis(data)
    if basis.get("statement_schema") not in INSTITUTION_SCHEMAS:
        return {}
    values, years = data["net_revenue_history"], data["years"]
    result = {}
    if values[0] > 0 and values[-1] > 0:
        cagr = ((values[-1] / values[0]) ** (1 / (len(years) - 1)) - 1) * 100
        if math.isfinite(cagr):
            result["net_revenue_cagr"] = {"growth_pct": round(cagr, 4), "years": list(years),
                "source_path": "data.net_revenue_history", "statement_schema": basis["statement_schema"],
                "formula": "(last net revenue / first net revenue)^(1 / fiscal year intervals) - 1"}
    if values[-2] > 0:
        growth = (values[-1] / values[-2] - 1) * 100
        if math.isfinite(growth):
            result["latest_annual_net_revenue_growth"] = {"growth_pct": round(growth, 4),
                "years": list(years[-2:]), "source_path": "data.net_revenue_history",
                "formula": "latest annual net revenue / prior annual net revenue - 1"}
    margins = [ni / value * 100 if value > 0 else None
               for ni, value in zip(data["net_income_history"], values)]
    margins = [round(v, 4) if v is not None and math.isfinite(v) else None for v in margins]
    result["net_income_to_net_revenue_pct_history"] = {
        "years": list(years), "values": margins,
        "source_paths": ["data.net_income_history", "data.net_revenue_history"],
        "formula": "parent-attributable annual net income / consolidated annual net revenue * 100"}
    return result
