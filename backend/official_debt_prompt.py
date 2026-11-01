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


def official_financial_amount_reference_prompt(data):
    """Present existing canonical income/FCF statements with debt, for Agent 2."""
    from official_income_prompt import official_income_prompt_facts, official_income_reference_text
    debt = official_debt_reference_prompt(data)
    income = official_income_prompt_facts(data)
    checked = read_official_financial_projection(data)
    reference = official_income_reference_text(income, checked['facts'] if checked else None)
    if not isinstance(reference, dict) or not isinstance(reference.get('statement'), str):
        return debt
    statements = []
    annual = income.get('annual_facts') or {}
    for period in (annual.get('periods') or {}).values():
        values = period.get('statements') if isinstance(period, dict) else None
        if isinstance(values, dict):
            for metric in ('營收', '淨利', '自由現金流'):
                if isinstance(values.get(metric), str):
                    statements.append(values[metric])
    statements.append(reference['statement'])
    if isinstance(reference.get('free_cash_flow_statement'), str):
        statements.append(reference['free_cash_flow_statement'])
    income_section = (
        '【官方損益與現金流完整引用句】\n'
        '以下均為已重播原件的提示輸入；不改寫模型輸出，也不證明歷史首次可得性。'
        '每個貨幣金額主張應獨立成句並保留完整公司、TWD、個別及起訖日期。'
        '比較年度與TTM時保留各自完整句；重疊期間說明另段，不改成省略口徑的金額串列。'
        '轉換率公式可以使用FCF／同口徑淨利的科目名稱與百分比；若重述金額，仍須完整引用下列句子。\n\n'
        + '\n\n'.join(dict.fromkeys(statements)))
    return '\n\n'.join(part for part in (income_section, debt) if part)
