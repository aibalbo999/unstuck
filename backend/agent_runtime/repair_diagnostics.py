"""Read-only, deterministic diagnostics for the candidate being rewritten."""
from __future__ import annotations

import math

from final_audit_helpers import extract_first_price, recommendation_value
from forward_consistency_checker import RECOMMENDATION_RETURN_GATES
from recommendation_labels import normalize_recommendation_label
from structured_output_parser import parse_recommendation_from_text


def recommendation_repair_diagnostic(context: dict, data: dict, previous_text: str = '') -> str:
    """Describe rejected values; never select a replacement decision or target."""
    outputs = context.get('structured_outputs') or {}
    output = outputs.get(19, outputs.get('19'))
    recommendation = output.get('recommendation') if isinstance(output, dict) else None
    if not isinstance(recommendation, dict):
        recommendation = parse_recommendation_from_text(previous_text)
    label = normalize_recommendation_label(recommendation_value(recommendation, '建議'))
    current = data.get('current_price')
    valid_current = (isinstance(current, (int, float)) and not isinstance(current, bool)
                     and math.isfinite(current) and current > 0)
    lines = [f'前次建議：{label or "未提供"}；現價：{current if valid_current else "無可驗證現價"}。']
    for horizon in ('3個月', '6個月', '12個月'):
        raw = recommendation_value(recommendation, horizon)
        price = extract_first_price(raw)
        if price is not None and math.isfinite(price) and price > 0:
            implied = f'；隱含報酬 {(price / current - 1) * 100:.1f}%' if valid_current else ''
            lines.append(f'{horizon} 原值：{str(raw)[:200]}；稽核採用價：{price:g}{implied}。')
    for name, gate in RECOMMENDATION_RETURN_GATES.items():
        bounds = []
        if 'min_expected_return_pct' in gate:
            bounds.append(f"至少 {gate['min_expected_return_pct']:g}%")
        if 'max_expected_return_pct' in gate:
            bounds.append(f"至多 {gate['max_expected_return_pct']:g}%")
        lines.append(f'{name} 的 12 個月報酬門檻：' + '、'.join(bounds) + '。')
    return ('【前次決策數值診斷；不是新的估值或交易指示】\n' + '\n'.join(lines) + '\n'
            '- 依證據重新判斷建議與估值；不可為通過門檻而調高目標價，也不可一律改為避免。\n'
            '- 持有不是所有「等待／觀察」的代稱；目標無法支持時，明確說明證據限制。\n'
            '- 輸出完整正文與 JSON；製造業風險應逐項討論產能、CapEx、折舊、良率、客戶議價，'
            '缺資料就說明未知及對結論的限制，不可捏造已驗證。\n'
            '- 若最終建議、目標或交易方案改變，必須依本次可見來源重新填寫 market_context_assessment；'
            '不要沿用前次結論的評估。有效 source_refs 必須來自本次提供的來源；不足就保留 not_assessed。\n'
            '- 不建立空方部位時，entry_trigger 與 cover_stop 都必須忠實表達無部位；'
            '有既有部位或條件交易時，保留其實際狀態及價格依據。\n')
