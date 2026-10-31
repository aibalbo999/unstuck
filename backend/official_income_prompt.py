"""Expose replayed income facts separately from provider scalars and EPS guesses."""


def official_income_prompt_facts(data):
    from official_financial_projection import read_official_financial_projection
    from data_fetch.market_sources.tewc_income_reference import replay_income_reference
    selected = read_official_financial_projection(data)
    if selected is None:
        return None
    income = replay_income_reference({
        'schema': 'tewc-income-reference:v1', 'ticker': data.get('ticker'),
        'financial_reference': selected['reference'],
    }, data.get('ticker'))
    if income.get('status') != 'income_originals_verified':
        return None
    return {'monetary_amount_unit': 'TWD', 'ratio_unit': 'percent',
        **({'issuer_english_name': income['issuer_english_name']} if income.get('issuer_english_name') else {}),
        **{key: income[key] for key in (
        'status', 'ticker', 'issuer_name', 'report_scope', 'currency',
        'period_start', 'period_end', 'income_components', 'net_income_ttm_raw',
        'net_income_ttm_formula', 'fcf_conversion_ttm_pct', 'reported_basic_eps',
        'issued_capital', 'ttm_eps_verified', 'share_count_bridge_verified',
        'ttm_eps_unavailable_reason', 'source_documents', 'capture_boundary',
        'freshness_status', 'historical_pit_verified', 'native_acquisition',
        'five_year_history_verified')}}


def official_income_reference_text(facts, cashflow_facts=None):
    """Format already replayed facts, without rebinding any vendor amount.

    This is prompt presentation only; the ordinary evidence gate must still
    replay originals and verify each final statement's complete local scope.
    """
    from datetime import date
    from decimal import Decimal
    if (not isinstance(facts, dict) or facts.get('status') != 'income_originals_verified'
            or facts.get('currency') != 'TWD' or facts.get('report_scope') != 'individual'
            or facts.get('monetary_amount_unit') != 'TWD'
            or type(facts.get('net_income_ttm_raw')) is not int):
        return None
    name = facts.get('issuer_name')
    if not isinstance(name,str) or not 1 <= len(name) <= 120 or name != name.strip() or any(c in name for c in '\n\r\t'):
        return None
    try:
        start = date.fromisoformat(facts['period_start'])
        end = date.fromisoformat(facts['period_end'])
        if not start < end <= date.today():
            return None
        amount = format(Decimal(facts['net_income_ttm_raw']) / Decimal(100_000_000), 'f')
    except (KeyError,TypeError,ValueError):
        return None
    reference = {
        'statement': f"{name}官方個別財報 TWD TTM（{start.isoformat()} 至 {end.isoformat()}）淨利為 {amount} 億元。",
        'source_path': 'data.cash_flow.official_income_facts.source_documents[*].url',
        'usage': '若引用這個已重播官方金額，每次另起完整一句，保留公司、個別、TWD及起訖日期；不改寫成上述或同期間，不把此範圍延用給相鄰供應商金額。原件仍須由證據查核重新核對。',
        'limitations': '不認證原 quote 期間，不提供TTM EPS、五年歷史、目標價、目前新鮮度或歷史首次可得性。',
    }

    if (isinstance(cashflow_facts, dict)
            and cashflow_facts.get('report_scope') == 'individual'
            and cashflow_facts.get('currency') == 'TWD'
            and cashflow_facts.get('period_start') == facts['period_start']
            and cashflow_facts.get('period_end') == facts['period_end']):
        raw = ((cashflow_facts.get('cashflows') or {}).get('ttm') or {}).get('free_cash_flow')
        if type(raw) is int:
            fcf_amount = format(Decimal(raw) / Decimal(100_000_000), 'f')
            reference['free_cash_flow_statement'] = (
                f"{name}官方個別財報 TWD TTM（{start.isoformat()} 至 {end.isoformat()}）"
                f"自由現金流為 {fcf_amount} 億元。")
            reference['free_cash_flow_source_path'] = 'data.official_financial_projection.facts.cashflows.ttm.free_cash_flow'
    return reference
