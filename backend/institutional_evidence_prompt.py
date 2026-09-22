"""Render only individually verified institutional observations with explicit scope."""
import json

from institutional_evidence import (
    _valid_record, institutional_evidence_records, institutional_evidence_issues,
    institutional_evidence_diagnostics,
)

_RULE = ('【法人逐項來源契約】每一筆 finding、counterevidence 與正文數值，先選下列唯一來源，'
         '逐項明寫主體、期間、觀測日期、數值、單位及 source ref；另起段不可省略期間。'
         '單日與5/30日、合計與分項不可互借；累計值不證明每日連續買超。'
         '未來條件與已發生事實分開；缺來源維持資料不足，不得猜測、補數字或刪除重要反證。')


def build_institutional_source_prompt(data):
    lines = [_RULE]
    for index, record in enumerate(institutional_evidence_records(data)):
        if not _valid_record(record):
            continue
        path = record.get('path')
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
