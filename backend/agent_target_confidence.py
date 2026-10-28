"""Apply the existing report target-price confidence policy before integration."""
from report_reproducibility import build_data_confidence_controls

TARGET_AGENTS = frozenset({4, 7, 14, 16, 19, 24})


def target_confidence_instruction(agent_num, data):
    if agent_num not in TARGET_AGENTS or not isinstance(data.get('data_trust'), dict):
        return ''
    controls = build_data_confidence_controls({}, data['data_trust'])
    rule = controls['conclusion_guardrails']['explicit_target_price']
    if rule['allowed']:
        return ''
    value_rule = ('price_targets 的熊市情境、基本情境、牛市情境三個必要鍵均填 null，'
                  '在既有三項 reasoning 與正文說明原因，不得填 0 或補造價格。'
                  if agent_num in {4, 14} else
                  '目標價欄位須明示資料不足及原因；不把前序情境值或資料來源中的價格當成本次目標。')
    return (f"【本次目標價限制】資料信心 {controls['data_confidence_score']}/100 低於 "
            f"{rule['min_data_confidence_score']}/100，不得給明確目標價。{value_rule}"
            '現價、歷史價格、支持與反證資料保留；不要為通過檢查改變研究分類或提高信心。')


def target_confidence_issues(agent_num, text, data, structured=None):
    if agent_num not in TARGET_AGENTS or not isinstance(data.get('data_trust'), dict):
        return []
    probe = {'structured_outputs': {agent_num: structured}} if structured else {}
    if not structured and agent_num in {4, 14}:
        from structured_output_parser import parse_price_targets_from_text
        probe = {'parsed': {'price_targets': parse_price_targets_from_text(text)}}
    controls = build_data_confidence_controls(probe, data['data_trust'])
    rule = controls['conclusion_guardrails']['explicit_target_price']
    if rule['allowed'] or not rule['detected_fields']:
        return []
    return [f"資料信心 {controls['data_confidence_score']}/100 低於 {rule['min_data_confidence_score']}/100，"
            f"明確目標價尚未獲准：{'、'.join(rule['detected_fields'])}。"
            + target_confidence_instruction(agent_num, data)]
