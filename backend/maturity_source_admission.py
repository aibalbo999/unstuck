"""Maturity needs a dated independent raw observation, not merely a clock cutoff."""
from report_source_admission import price_admission


def assess_maturity_source(bars, ticker, maturity_date):
    result={'eligible':False,'expected_date':maturity_date,'finality_guaranteed':False,'all_historical_bars_verified':False}
    if not bars or bars[-1].get('date')!=maturity_date:
        return {**result,'reason':'maturity_session_bar_missing'}
    latest=bars[-1];proof=latest.get('observation_provenance',{}).get('official_observation') or {}
    raw=price_admission({'as_of':maturity_date,'official_observation':proof},ticker)
    if not raw['eligible']:return {**result,'reason':raw['reason']}
    for field in ('open','high','low','close'):
        try:
            before,after=float(latest[field]),float(proof[field])
            import math
            if not math.isfinite(before) or not math.isfinite(after) or abs(before-after)>max(.0001,abs(after)*1e-7):
                return {**result,'reason':'maturity_provider_official_price_mismatch','field':field,'provider':before,'official':after}
        except (KeyError,TypeError,ValueError):return {**result,'reason':'maturity_price_fields_missing'}
    return {**result,'eligible':True,'reason':'maturity_session_prices_match_archived_official_response','raw_evidence':raw['raw_evidence']}
