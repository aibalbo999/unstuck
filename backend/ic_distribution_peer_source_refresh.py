"""Source-only IC leads preserve original analysis, prices and quality gates."""
from fastapi import HTTPException
from data_fetch.market_sources.official_ic_distribution_peer_cohort import (
    TARGET, SHORT, LEGAL, verified_candidates,
)
from thermal_peer_source_refresh import _merge_segment_peer_source


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TARGET or not isinstance(data, dict) or data.get('ticker') != TARGET
            or str(data.get('company_name') or '').split('/')[0].strip() not in {SHORT, LEGAL}
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quoteType', 'quote_type'))
            or not isinstance(data.get('dynamic_peer_metrics'), list)):
        raise HTTPException(status_code=400, detail='此同業來源刷新須有一致的巨路股票身分及原指標清單')
    identity = data.get('company_identity')
    if isinstance(identity, dict):
        stock_id = identity.get('stock_id')
        if (identity.get('ticker') not in (None, '', TARGET)
                or stock_id not in (None, '') and (type(stock_id) not in (str, int) or str(stock_id) != '6192')
                or identity.get('official_name') not in (None, '', SHORT, LEGAL)):
            raise HTTPException(status_code=400, detail='原公司身分與巨路來源不一致')


def merge_source(old_data, old_audits, value, audits, ticker):
    return _merge_segment_peer_source(old_data, old_audits, value, audits, ticker,
        validate_context=validate_context, verify_candidates=verified_candidates)
