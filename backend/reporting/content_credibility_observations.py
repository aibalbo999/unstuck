"""Required, unsampled v4 market observations; no provider calls during rendering."""
from datetime import date, datetime
from math import isfinite
from zoneinfo import ZoneInfo
from two_week_market_eligibility import observation_readiness
from trade_catalyst_semantics import bullish_sma_alignment_issue
from .trade_price_grid import execution_evidence


def _day(value):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _number(value):
    try:
        number = float(value)
        return number if isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None


def evaluate_observation_credibility(context, snapshot, data, pipeline):
    result = {"blocking_issues": [], "warnings": [], "checks": []}
    if pipeline != "v4":
        return result
    def issue(key, message, *, warning=False, details=None):
        result["warnings" if warning else "blocking_issues"].append({"id": key, "message": message, **({'details': details} if details is not None else {})})
    daily = data.get("daily_market_data")
    daily = daily if isinstance(daily, dict) else {}
    from market_session_admission import assess_daily_session_integrity
    session_integrity = assess_daily_session_integrity(daily, ticker=data.get('ticker'))
    result['session_integrity'] = session_integrity
    if session_integrity['status'] == 'invalid':
        issue('v4_market_session_integrity_invalid', '技術序列含非交易日或不准入日期；同一輸入的數值與雜湊一致不能證明序列有效。', details=session_integrity)
    elif not session_integrity['eligible']:
        issue('v4_market_session_integrity_unverifiable', '技術序列缺少可核對的市場或交易日曆；不可標為已核實行情。', warning=True, details=session_integrity)
    observed = _day(daily.get("as_of"))
    bars = daily.get("bars")
    bars = bars if isinstance(bars, list) else []
    last = bars[-1] if bars and isinstance(bars[-1], dict) else {}
    if not observed or not str(daily.get("source") or "").strip() or not bars:
        issue("v4_market_observation_missing", "兩週觀察缺少可追溯日線來源、觀測日或價格；不可發布候選報告。")
    reference = None
    try:
        reference = datetime.fromisoformat(str(snapshot.get("generated_at") or context.get("generated_at"))).astimezone(ZoneInfo("Asia/Taipei")).date()
    except (TypeError, ValueError):
        reference = _day(daily.get("requested_as_of"))
    if observed and reference:
        age = (reference - observed).days
        if age < 0:
            issue("v4_market_observation_future", "行情觀測日晚於報告基準日。")
        elif age > 7:
            issue("v4_market_observation_stale", "行情超過七個日曆日未更新；需重新取數。此門檻不代表交易日完整。")
        elif age > 0:
            issue("v4_market_observation_lag", "行情不是報告基準日資料，須確認休市或資料延遲。", warning=True)
    if observed and _day(last.get("date")) != observed:
        issue("v4_market_bar_date_mismatch", "日線最後一筆日期與行情觀測日不一致。")
    price, close = _number(data.get("current_price")), _number(last.get("close"))
    if price is None or close is None:
        issue("v4_market_price_missing", "最新價或日線收盤價缺漏、無效。")
    elif abs(price / close - 1) > .01:
        issue("v4_market_price_basis_mismatch", "最新價與日線最後收盤差異超過1%；需確認盤中／盤後時點與調整基準，禁止直接混用。")
    if not daily.get("price_adjustment_basis"):
        issue("v4_price_adjustment_basis_unknown", "歷史價格除權息／分割調整基準未記錄，跨期比較待確認。", warning=True)
    from market_price_reconciliation import reconcile
    basis = reconcile(daily)
    if basis["price_status"] == "different":
        issue("v4_official_raw_price_mismatch", "同日Yahoo原始OHLC與官方行情不一致，禁止混用為進出場基準。")
    if basis["volume"]["status"] == "different":
        issue("v4_volume_scope_mismatch", "同日Yahoo與官方成交量不一致；同單位不能證明同口徑，禁止跨來源量比／法人占比混算。", warning=True)
    result["price_reconciliation"] = basis
    parsed = context.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    setup = parsed.get("trade_setup")
    setup = setup if isinstance(setup, dict) else {}
    technical = data.get("technical_indicators")
    technical = technical if isinstance(technical, dict) else {}
    for text in (str(setup.get(key) or "") for key in ("catalyst", "observed_signal", "core_catalyst")):
        alignment_issue = bullish_sma_alignment_issue(text, technical)
        if alignment_issue == "bullish_sma_alignment_contradiction":
            issue("v4_bullish_sma_alignment_contradiction", "宣稱5／10／20日均線多頭排列，但快照並非 SMA5 > SMA10 > SMA20。")
        elif alignment_issue == "bullish_sma_alignment_unverified":
            issue("v4_bullish_sma_alignment_unverified", "宣稱均線多頭排列卻缺少對應均線值。")
    if data.get("free_cash_flow_raw") is not None:
        from .content_credibility_fcf_scope import fcf_quality_scope
        fcf_scope = fcf_quality_scope(data)
        result['fcf_scope'] = fcf_scope
        if fcf_scope['selected_field']['period_status'] != 'verified':
            issue("v4_raw_fcf_period_unverified", "即期 free_cash_flow_raw 未附可核對的期間、報表口徑及完整CapEx組成；不得與年度FCF混為同一期事實。", warning=True, details=fcf_scope)
        elif fcf_scope['preserved_quote']['value'] is not None:
            issue('v4_preserved_quote_fcf_period_unverified', '目前選用的官方FCF已按原件與期別核對；另存的舊quote期間仍未核實，不可混用。', warning=True, details=fcf_scope)
    institution = data.get("institutional_trading")
    institution = institution if isinstance(institution, dict) else {}
    days = [_day(v) for v in institution.get("observation_dates", [])] if isinstance(institution.get("observation_dates"), list) else []
    days = [v for v in days if v]
    if days and reference and max(days) > reference:
        issue("v4_institutional_observation_future", "法人觀測日晚於報告基準日，不能當作已發生的籌碼證據。")
    if not days or not observed or max(days) != observed:
        issue("v4_institutional_observation_unaligned", "法人與行情觀測日未對齊或缺漏，不可稱當日籌碼確認。", warning=True)
    try:
        moment = datetime.fromisoformat(str(context.get("candidate_evaluation_at") or snapshot.get("generated_at") or context.get("generated_at")))
    except (TypeError, ValueError):
        moment = None
    readiness = observation_readiness(price_date=observed.isoformat() if observed else None,
                                     institutional_date=max(days).isoformat() if days else None, moment=moment,
                                     ticker=data.get("ticker") or snapshot.get("ticker") or daily.get("ticker"))
    if not readiness["latest_source_dates_aligned"]:
        issue("v4_latest_completed_session_unconfirmed", readiness["reason"], warning=True)
    readiness["price_reconciliation"] = basis
    readiness['session_integrity'] = session_integrity
    if result.get('fcf_scope'):
        readiness['fcf_scope'] = result['fcf_scope']
    readiness["execution_evidence"] = execution_evidence(data, setup)
    result["checks"] = [{"id": "v4_market_observations", "details": readiness, "status": "blocked" if result["blocking_issues"] else "warning" if result["warnings"] else "passed", "message": "行情來源、日期與價格採必查條件；非抽樣、非官方獨立驗價。"}]
    return result
