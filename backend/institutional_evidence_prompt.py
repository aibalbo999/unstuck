"""Render only individually verified institutional observations with explicit scope."""
import json

from institutional_daily_evidence import DAILY_CATEGORY_PATH_PREFIX

from institutional_evidence import (
    _valid_record, institutional_evidence_records, institutional_evidence_issues,
    institutional_evidence_diagnostics,
)

_RULE = ('【法人逐項來源契約】每一筆 finding、counterevidence 與正文數值，先選下列唯一來源，'
         '逐項明寫主體、期間、觀測日期、數值、單位及 source ref；另起段不可省略期間。'
         '單日與5/10/20/30日、合計與分項不可互借；累計值不證明每日連續買超或連續派發。'
         '只能描述來源實際觀測期間；觀測天數不足時不得擴成完整期間，缺少逐日來源不得推論連續建倉或派發。'
         '未來條件與已發生事實分開；缺來源維持資料不足，不得猜測、補數字或刪除重要反證。')


def build_institutional_source_prompt(data):
    lines = [_RULE]
    source = data.get("institutional_trading", {})
    observation = source.get("latest_official_observation", {}) if isinstance(source, dict) else {}
    raw = observation.get("raw_evidence", {}) if isinstance(observation, dict) else {}
    if isinstance(raw, dict) and raw.get("raw_response_sha256") and raw.get("retrieved_at"):
        # Receipt belongs to this input version; it never certifies later versions.
        receipt = {key: raw.get(key) for key in (
            "source_url", "retrieved_at", "raw_response_sha256", "evidence_kind",
            "finality_guaranteed", "historical_point_in_time_verified")}
        receipt.update(observed_date=observation.get("date"),
                       acquisition_phase=observation.get("acquisition_phase"),
                       categories=observation.get("categories"), unit=observation.get("unit"))
        lines.append("官方單日版本收據（與彙總期間分開；hash只证明此取得版本，不證明後續不變）："
                     + json.dumps(receipt, ensure_ascii=False, allow_nan=False))

    records = institutional_evidence_records(data)
    daily_dates = [record.get('observed_at') for record in records
                   if isinstance(record.get('path'), str)
                   and record['path'].startswith(DAILY_CATEGORY_PATH_PREFIX)
                   and _valid_record(record)]
    latest_daily = (source.get('latest_date') if isinstance(source, dict) else None)
    if latest_daily is None:
        latest_daily = max(daily_dates) if daily_dates else None
    for index, record in enumerate(records):
        if not _valid_record(record):
            continue
        path = record.get('path')
        # The gate/catalog retains ten exact dates; the repeated role prompt
        # adds only the newest three subgroup facts to avoid a large token cost.
        if (isinstance(path, str) and path.startswith(DAILY_CATEGORY_PATH_PREFIX)
                and record['observed_at'] != latest_daily):
            continue
        if not isinstance(path, str) or not path:
            path = f'short_term_market_context.institutional_evidence.records[{index}]'
        population = {'total': '三大法人合計', 'foreign': '外資',
                      'investment_trust': '投信', 'dealer': '自營商'}[record['population']]
        window = record['window']
        period = (f"近{int(window['trading_days'])}個交易日" if window['kind'] == 'trailing_trading_days'
                  else f"{window['date']}單日")
        value = float(record['value'])
        unit = {'shares': '股', 'thousand_shares': '千股'}[record['unit']]
        direction = '淨賣超' if value < 0 else '淨買超'
        fact = f"截至{record['observed_at']}，{population}{period}{direction}{abs(value):.15g}{unit}。"
        if institutional_evidence_issues(fact, data, allowed_paths=[path]):
            continue
        lines.append(f"- {fact} source ref={path}；provider={record['provider']}")
    if len(lines) == 1:
        lines.append('沒有可逐項核驗的法人來源；不得補造主體、期間或數字。')
    return '\n'.join(lines)


def institutional_repair_diagnostic_prompt(text, data):
    diagnostics = institutional_evidence_diagnostics(text, data)
    if not diagnostics:
        return ''
    return ('\n【法人退件精確診斷：原文位置為字元區間】\n'
            'available_population_sources 僅為同主體可用資料，不是原主張已獲證明；'
            '不得按數字相似自動換主體或期間。修正後每句仍須通過完整 gate。\n'
            + json.dumps(diagnostics, ensure_ascii=False, allow_nan=False) + '\n'
            + build_institutional_source_prompt(data))
