"""Complete statement templates from replayed official individual debt facts.

Input scaffolding only: never edits a model result, source observation or report.
"""
from datetime import date

from official_financial_projection import read_official_financial_projection

LABELS = {
    "shortterm_borrowings": "短期借款",
    "current_portion_longterm_borrowings": "一年內到期之長期借款",
    "longterm_borrowings": "長期借款",
    "current_lease_liabilities": "流動租賃負債",
    "noncurrent_lease_liabilities": "非流動租賃負債",
}


def official_debt_reference_prompt(data):
    checked = read_official_financial_projection(data)
    if not checked:
        return ""
    try:
        facts = checked["facts"]
        issuer = facts["issuer_name"]
        if (facts["currency"] != "TWD" or facts["report_scope"] != "individual"
                or not isinstance(issuer, str) or not issuer.strip()
                or any(ord(char) < 32 for char in issuer)):
            return ""
        asof = date.fromisoformat(facts["balance"]["as_of"]).isoformat()
        amounts = facts["debt_components"]
        if any(type(amounts[field]) is not int or amounts[field] < 0 for field in LABELS):
            return ""
        statements = [
            f"{issuer}官方個別財報 TWD 截至{asof} {label}為 {amounts[field]:,} TWD。"
            for field, label in LABELS.items()
        ]
    except (KeyError, TypeError, ValueError):
        return ""
    return ("【官方同日債務原件事實句】\n"
            "以下由原件重播產生。若採用金額主張，逐句保留公司、TWD、個別口徑與同日日期，"
            "每句獨立成段；比率與結論指回科目及日期，避免重述省略口徑的金額。"
            "來源為 balance_sheet.debt_to_equity_basis.debt_components；不是完整合併財報或歷史首次可得性證明。\n\n"
            + "\n\n".join(statements))
