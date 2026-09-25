"""Trusted position inputs and runtime receipts, never model-authored capital."""
import json

from position_sizing import build_position_sizing_context, calculate_position_sizing


def trusted_sizing_context(context):
    # Only the request/workflow channel may supply this context. In particular,
    # never read sizing inputs from structured_outputs or provider stock data.
    supplied = context.get('position_sizing_context')
    if not isinstance(supplied, dict) or supplied.get('status') != 'available':
        return build_position_sizing_context()
    rebuilt = build_position_sizing_context(supplied.get('inputs'),
        source_ref=supplied.get('source_ref'), quote_currency=supplied.get('quote_currency'))
    if supplied.get('context_sha256') != rebuilt.get('context_sha256'):
        return build_position_sizing_context()
    return rebuilt


def sizing_prompt(context):
    supplied = trusted_sizing_context(context)
    return ('【部位比例輸入契約】\n' + json.dumps(supplied, ensure_ascii=False, allow_nan=False) +
            '\n只有以上明確且 available 的資金／風險／持倉情境可支持數字比例。'
            'unavailable 時 position_plan 必須等待、0%、planning_context=unassessed，'
            'sizing_evidence={"status":"unassessed","reason":"缺少資金或風險預算來源"}，說明等待資金基準、風險預算或重新評估條件；'
            '這是本研究不建立新部位，不代表使用者實際持倉為零。'
            'recommendation 仍依研究證據獨立判斷，不為此強迫改成避免。'
            '不得把模型自行設定的預算或比例當作外部輸入，也不得假稱已執行計算。')


def assess_position_plan(raw_plan, context, recommendation, analysis_markdown=''):
    from final_audit_mode_contracts import v2_position_plan_contract_issues
    supplied = trusted_sizing_context(context)
    issues = (v2_position_plan_contract_issues(raw_plan, sizing_context=supplied, recommendation=recommendation)
              if isinstance(raw_plan.get('action'), str) else ['position action 必須為允許的字串，不能使用物件或陣列。'])
    if raw_plan.get('action') == '等待':
        from position_sizing_narrative import waiting_plan_has_immediate_order
        if waiting_plan_has_immediate_order(analysis_markdown):
            issues.append('等待計畫與正文的立即交易指令矛盾，必須同步修正，不能只把比例改為零。')
    calculation = calculate_position_sizing(raw_plan, supplied, recommendation=recommendation)
    return {'contract_version': 'position-sizing:v1', 'issues': issues,
            'status': 'blocked' if issues else calculation['status'], 'calculation': calculation}
