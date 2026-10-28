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
