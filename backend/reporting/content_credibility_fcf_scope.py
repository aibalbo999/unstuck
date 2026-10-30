"""Field-specific FCF lineage; annual amounts never qualify an undated quote."""
from math import isfinite


def _number(value):
    try:
        return value if type(value) in (int, float) and isfinite(value) else None
    except OverflowError:
        return None


def fcf_quality_scope(data):
    from financial_fact_binding import financial_basis
    fact = financial_basis(data)['facts']['free_cash_flow_raw']
    selected = {key: fact.get(key) for key in (
        'source_path', 'selected_input_path', 'period_status', 'period_start', 'period_end',
        'currency', 'amount_twd', 'report_scope', 'definition', 'source_url', 'acquired_at')}
    selected['unit'] = 'TWD' if fact.get('amount_twd') is not None else None
    selected['source_replay_status'] = ('official_originals_and_selection_replayed'
                                        if fact.get('period_status') == 'verified' else 'not_established')
    preserved = data.get('original_quote_financials')
    preserved = preserved if isinstance(preserved, dict) else {}
    quote = preserved.get('values') if isinstance(preserved.get('values'), dict) else {}
    history_basis = data.get('financial_history_basis')
    history_basis = history_basis if isinstance(history_basis, dict) else {}
    annual = {
        'source_path': 'data.fcf_history', 'period_labels_path': 'data.years',
        'basis_path': 'data.financial_history_basis',
        'statement_schema': history_basis.get('statement_schema'),
        'status': 'separate_series_not_replayed_in_this_check' if data.get('fcf_history') else 'unavailable',
        'raw_scalar_period_verified': False,
        'reason': '年度原件須按年度查核器核對；即使年度已核實，也不替即期欄位補造期別。',
    }
    return {
        'schema': 'fcf_quality_scope.v1', 'selected_field': selected, 'annual_series': annual,
        'preserved_quote': {
            'source_path': 'data.original_quote_financials.values.free_cash_flow_raw',
            'value': _number(quote.get('free_cash_flow_raw')),
            'period_status': 'unverified', 'raw_scalar_period_verified': False,
        },
        'historical_point_in_time_verified': False,
    }
