"""Role projections for small-model evidence work; never truncate a source record."""

# Remove only known sections outside the role's written contract. Unknown/new
# sections, identity, units, freshness, audit records and quality warnings survive.
# Financial, valuation, adversarial and final roles deliberately have no projection.
_FINANCIAL_TOOLS = {'deterministic_financial_tool_results'}
_BALANCE = {'cash_flow', 'balance_sheet'}
_PEERS = {'peer_context'}
_HISTORY = {'history', 'growth', 'recent_monthly_revenue_text'}
ROLE_EXCLUDED_SECTIONS = {
    11: _FINANCIAL_TOOLS | _BALANCE | _PEERS | {'valuation_metrics', 'local_valuation_context', 'institutional_trading'},
    15: _FINANCIAL_TOOLS | _BALANCE | _PEERS | _HISTORY | {'ttm_financials'},
    17: _FINANCIAL_TOOLS | _BALANCE | _PEERS,
    20: _FINANCIAL_TOOLS | _PEERS | {'valuation_metrics', 'local_valuation_context', 'institutional_trading'},
    22: _FINANCIAL_TOOLS | _BALANCE | _PEERS | _HISTORY | {'ttm_financials', 'valuation_metrics', 'local_valuation_context'},
    23: _FINANCIAL_TOOLS | _BALANCE | _PEERS | _HISTORY | {'ttm_financials', 'valuation_metrics', 'local_valuation_context'},
}


def project_role_payload(payload: dict, agent_num: int | None) -> dict:
    excluded = ROLE_EXCLUDED_SECTIONS.get(agent_num)
    if not excluded:
        return payload
    result = {key: value for key, value in payload.items() if key not in excluded}
    # These roles do not select competitors. Keep the target identity lock and
    # industry classification, but leave the full exchange registry to peer work.
    company = dict(result.get('company', {}))
    identity = dict(company.get('identity', {}))
    omitted_fields = []
    if 'same_industry_peers' in identity:
        identity.pop('same_industry_peers')
        omitted_fields.append('company.identity.same_industry_peers')
    company['identity'] = identity
    result['company'] = company
    result['prompt_scope'] = {
        'agent_num': agent_num,
        'omitted_sections': sorted(set(payload) & excluded),
        'omitted_fields': omitted_fields,
        'rule': '只分析本角色任務；省略區塊屬其他角色範圍，不表示原始資料缺失。不得推測未提供的數值。來源日期、單位與品質警示仍須遵守。',
    }
    return result
