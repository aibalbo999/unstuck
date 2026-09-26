"""Read-only, deterministic diagnostics for the candidate being rewritten."""
from __future__ import annotations

import json
import math

from final_audit_helpers import extract_first_price, recommendation_value
from forward_consistency_checker import recommendation_contract_guidance
from pipeline_modes import get_structured_agent_num
from recommendation_labels import normalize_recommendation_label
from structured_output_parser import parse_recommendation_from_text
from trade_execution_contract import evaluate_trade_execution


def _short_setup_diagnostic(output: dict, label: str) -> str:
    setup = output.get('short_setup') if isinstance(output, dict) else None
    if not isinstance(setup, dict):
        return '\nshort_setup 原始結構未提供，無法診斷價格；不得從其他欄位推補。\n'
    execution = evaluate_trade_execution(
        direction='Short', entry_zone=setup.get('entry_trigger'),
        target_price=setup.get('downside_target'), stop_loss=setup.get('cover_stop'),
        transaction_cost=setup.get('transaction_cost'),
    )
    lines = ['【short_setup 原值與既有價格解析；僅供研究欄位修復，不是交易指令】']
    for field, alias, parsed in (
        ('entry_trigger', 'entry_zone', 'entry_range'),
        ('downside_target', 'target_price', 'target_range'),
        ('cover_stop', 'stop_loss', 'stop_range'),
    ):
        raw = json.dumps(setup.get(field), ensure_ascii=False, default=str)
        lines.append(f'- short_setup.{field}（通用檢查欄位 {alias}）：'
                     f'原值：{raw[:1000]}；價格解析：{json.dumps(execution["details"][parsed])}。')
    if label == '放空':
        lines.extend(f'- 既有交易契約 {issue["id"]}：{issue["message"]}' for issue in execution['issues'])
        lines.append('SHORT 研究情境須以本次來源支持上述三個價格欄位；純事件條件或「均線附近」不能代替價格。'
                     '須符合完整區間的 target < entry < stop，不能只比較區間中點。')
    else:
        lines.append('非放空分類依既有觀望契約驗證；不要求補造進場或停損價。')
    lines.append('價格解析 null 表示既有解析器無法驗證，不是零；解析成功也不代表已有來源證明。'
                 '不得以現價、均線、目標價或其他欄位自動代填；缺少依據應明示不足，依證據重新審視分類與情境，'
                 '不可為通過檢查強迫選擇 AVOID，也不可發布實際交易指令。')
    return '\n' + '\n'.join(lines) + '\n'


def recommendation_repair_diagnostic(context: dict, data: dict, previous_text: str = '') -> str:
    """Describe rejected values; never select a replacement decision or target."""
    agent_num = get_structured_agent_num('recommendation', context)
    if agent_num not in (7, 16, 19):
        return ''
    outputs = context.get('structured_outputs') or {}
    output = outputs.get(agent_num, outputs.get(str(agent_num)))
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
    lines.append(recommendation_contract_guidance())
    summary = '【前次決策數值診斷；不是新的估值或交易指示】\n' + '\n'.join(lines) + '\n'
    if agent_num != get_structured_agent_num('short_setup', context):
        return (summary + '重寫完整正文與 JSON；若推薦或目標改變，依本次來源重新評估 '
                'market_context_assessment，不沿用前次結論；缺證據保留未評估。\n')
    return (summary
            + _short_setup_diagnostic(output, label) +
            '- 依證據重新判斷建議與估值；不可為通過門檻而調高目標價，也不可一律改為避免。\n'
            '- 持有不是所有「等待／觀察」的代稱；目標無法支持時，明確說明證據限制。\n'
            '- 輸出完整正文與 JSON；製造業風險應逐項討論產能、CapEx、折舊、良率、客戶議價，'
            '缺資料就說明未知及對結論的限制，不可捏造已驗證。\n'
            '- 若最終建議、目標或交易方案改變，必須依本次可見來源重新填寫 market_context_assessment；'
            '不要沿用前次結論的評估。有效 source_refs 必須來自本次提供的來源；不足就保留 not_assessed。\n'
            '- 不建立空方部位時，entry_trigger 與 cover_stop 都必須忠實表達無部位；'
            '有既有部位或條件交易時，保留其實際狀態及價格依據。\n')
