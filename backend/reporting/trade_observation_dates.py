"""Expose market observation dates separately from report generation time."""

from datetime import date

from mapping_fields import safe_mapping_dict


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
        return parsed.isoformat() if value == parsed.isoformat() else None
    except ValueError:
        return None


def trade_observation_rows(data: dict) -> list[dict[str, str]]:
    daily = safe_mapping_dict(data.get("daily_market_data")) or {}
    institutional = safe_mapping_dict(data.get("institutional_trading")) or {}
    price_date = _date(daily.get("as_of"))
    raw_dates = institutional.get("observation_dates")
    dates = [d for value in raw_dates if (d := _date(value))] if isinstance(raw_dates, list) else []
    institutional_date = max(dates) if dates else None
    alignment = "日期相同；不代表所有股票、法人分類或交易日完整" if price_date and price_date == institutional_date else "日期未對齊或缺漏；不可視為當日行情與法人皆完整"
    from report_source_admission import institutional_admission,admission_reason_label
    admission=institutional_admission(institutional,price_date)
    alignment += "；" + ("最新法人與盤後原始官方證據相符（不保證最終版本）" if admission["eligible"] else "不可採用為已查驗候選：" + admission_reason_label(admission["reason"]))
    from market_price_reconciliation import observation_rows
    return [
        {"label": "行情觀測日", "value": f"{price_date or '未確認'}（data.daily_market_data.as_of；{daily.get('source') or '來源未確認'}）"},
        {"label": "歷史價格基準", "value": daily.get("price_adjustment_basis") or "未確認除權息／分割調整口徑；歷史支撐與現價比較待核，不代表原始成交價已驗證"},
        {"label": "價位用途", "value": "均線、支撐及目標是分析參考價；進場需等待條件並核對合法跳動單位，尚非可直接執行的限價委託。"},
        {"label": "法人觀測日", "value": f"{institutional_date or '未確認'}（data.institutional_trading.observation_dates；{institutional.get('source') or '來源未確認'}；單位：股）"},
        {"label": "盤後資料對齊", "value": alignment},
        *observation_rows(daily),
        {"label": "兩週候選判讀", "value": "未來兩週需核對催化事件日期與來源、進場條件、停損及失效條件；新聞發布日不是事件日。Neutral 或證據不足時可不選股；分數不是上漲機率，目標不是已驗證報酬。"},
    ]
