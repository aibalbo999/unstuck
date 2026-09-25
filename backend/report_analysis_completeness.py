"""Read-only analysis completeness; never changes publication or quality gates."""

from mapping_fields import safe_mapping_dict, safe_text
from final_audit_mode_contracts import v4_trade_setup_contract_issues
from trade_execution_contract import neutral_observation_is_explicit


_GATES = {'report_lint': ('status', 'passed'), 'final_audit': ('status', 'passed'),
          'evidence_exit_gate': ('verdict', 'approved'),
          'content_credibility': ('status', 'passed'), 'report_conformance': ('status', 'passed')}
_LABELS = {'complete': '分析完整', 'observation': '正常觀望',
           'degraded': '資料不足降級', 'quality_warning': '分析品質警告'}
_NOTES = {
    'complete': '分析欄位與來源契約已完成，仍須依原品質檢查與資料時點判讀。',
    'observation': '已明確選擇不交易並保留重新評估條件，屬正常觀望。',
    'degraded': '來源、輸出或資料不足而保守降級；不代表完整分析已完成。',
    'quality_warning': '分析仍有品質警告或完整度尚未確認，請查看原品質檢查與資料限制。',
}


def _v2_position_status(context, output):
    """Recheck the saved receipt; lack of capital is not a research failure."""
    from position_sizing_runtime import assess_position_plan

    plan = safe_mapping_dict(output.get('position_plan')) or {}
    parsed = safe_mapping_dict(context.get('parsed')) or {}
    receipt = safe_mapping_dict(output.get('position_sizing_assessment')) or {}
    evidence = safe_mapping_dict(plan.get('sizing_evidence')) or {}
    if (not plan or plan != parsed.get('position_plan')
            or receipt.get('contract_version') != 'position-sizing:v1'
            or receipt.get('issues') != []):
        return 'unconfirmed'
    checked = assess_position_plan(plan, context, output.get('recommendation'), output.get('analysis_markdown'))
    expected = checked.get('calculation') or {}
    if (checked.get('issues') or receipt.get('status') != checked.get('status')
            or receipt.get('calculation') != expected or evidence.get('status') != expected.get('status')):
        return 'unconfirmed'
    # The waiting runtime contract allows legacy additive fields to be absent.
    # Present model fields must still agree with the system's unknown inputs.
    if expected.get('status') == 'unassessed':
        if (plan.get('planning_context') != 'unassessed'
                or any(value is None and evidence.get(key) is not None for key, value in expected.items())
                or evidence.get('position_state', 'unknown') != 'unknown'
                or evidence.get('scenario_type', 'unassessed') != 'unassessed'):
            return 'unconfirmed'
    return checked.get('status') if checked.get('status') in {'calculated', 'unassessed'} else 'unconfirmed'


def _v2_explicit_gaps(context):
    """Explain recorded gaps, without inventing a positive source certification.

    A green gate is not an all-role source receipt. Even when no explicit gap is
    recorded, research completeness remains unconfirmed until that exists.
    """
    from moat_assessment import MOAT_FIELDS, moat_assessment
    from pipeline_modes import PIPELINE_DEFINITIONS

    outputs = safe_mapping_dict(context.get('structured_outputs')) or {}
    analyses = safe_mapping_dict(context.get('analyses')) or {}
    required = PIPELINE_DEFINITIONS['v2']['agents']
    roles = {num: safe_mapping_dict(outputs.get(num, outputs.get(str(num)))) or {} for num in required}
    missing = [num for num in required if not roles[num] or not safe_text(
        roles[num].get('analysis_markdown') or analyses.get(num, analyses.get(str(num)))).strip()]
    reasons, research_gaps = [], []
    if missing:
        reasons.append('required_role_output_unrecorded')
    for num in (11, 13, 15):
        if roles[num].get('confidence') == 'unassessed':
            reasons.append(f'agent_{num}_evidence_unassessed')
            research_gaps.append(f'Agent {num} 證據未評估')
    scores = safe_mapping_dict(roles[12].get('moat_scores')) or {}
    if set(MOAT_FIELDS) <= set(scores):
        unassessed = moat_assessment(scores)['unassessed_fields']
        if unassessed:
            reasons.append('agent_12_moat_unassessed')
            research_gaps.append('護城河未評估：' + '、'.join(unassessed))

    data = safe_mapping_dict(context.get('data')) or {}
    earnings = safe_mapping_dict(data.get('earnings_call')) or {}
    transcript = any(isinstance(earnings.get(key), str) and earnings[key].strip()
                     for key in ('transcript_excerpt', 'transcript', 'content'))
    transcript_unavailable = not transcript and (
        earnings.get('transcript_available') is False
        or safe_text(earnings.get('coverage_status')) in {'metadata_only', 'unavailable', 'missing'})
    if roles[20].get('guidance_tone') == '資料不足':
        reasons.append('agent_20_guidance_unassessed')
        research_gaps.append('管理層語氣未評估')
    if transcript_unavailable:
        reasons.append('earnings_call_transcript_unavailable')
        research_gaps.append('法說會逐字稿未取得')

    position_status = _v2_position_status(context, roles[16])
    reasons.append('position_sizing_unassessed' if position_status == 'unassessed'
                   else 'position_sizing_contract_unconfirmed' if position_status == 'unconfirmed'
                   else 'position_sizing_calculated')
    if not research_gaps:
        reasons.append('analysis_completeness_unconfirmed')
    detail = {
        'contract_version': 'v2-explicit-gaps:v1',
        'required_roles': list(required), 'missing_roles': missing,
        'research_status': 'incomplete' if research_gaps else 'unconfirmed',
        'research_gaps': research_gaps,
        'earnings_call_source_status': 'available' if transcript else 'unavailable' if transcript_unavailable else 'unknown',
        'position_sizing_status': position_status,
        'positive_completeness_certified': False,
    }
    summary = ('研究缺口：' + '；'.join(research_gaps) + '。' if research_gaps
               else '研究來源完整度尚未取得逐角色確認。')
    if missing:
        summary += '未保存完整角色輸出：' + '、'.join(str(num) for num in missing) + '。'
    if position_status == 'unassessed':
        summary += '執行狀態：部位比例未評估；等待與零部位僅表示本研究不新增部位，不代表實際持倉。'
    elif position_status == 'unconfirmed':
        summary += '執行狀態：部位計算收據缺漏或不一致，尚未確認。'
    else:
        summary += '部位比例已依可信輸入重算；此結果不替代研究來源完整度確認。'
    return detail, reasons, summary


def assess_report_analysis_completeness(payload) -> dict:
    root = safe_mapping_dict(payload) or {}
    context = {**(safe_mapping_dict(root.get('rerun_context')) or {}), **root}
    pipeline = safe_text(context.get('pipeline_id') or context.get('pipeline')).strip()
    statuses, warning = {}, False
    for name, (field, passed) in _GATES.items():
        gate = safe_mapping_dict(context.get(name)) or {}
        value = safe_text(gate.get(field)).strip().lower()
        statuses[name] = value
        warning |= bool(value and value != passed) or any(bool(gate.get(k)) for k in ('warnings', 'blocking_issues', 'critical'))
    integrity = safe_mapping_dict(context.get('snapshot_integrity')) or {}
    freshness = safe_mapping_dict(context.get('decision_freshness')) or {}
    warning |= integrity.get('valid') is False or integrity.get('status') in {'invalid', 'failed', 'blocked'}
    warning |= freshness.get('status') == 'needs_rerun' or context.get('decision_validity_status') == 'needs_rerun'
    recorded = all(statuses[name] for name in _GATES)
    outputs = safe_mapping_dict(context.get('structured_outputs')) or {}
    setup = safe_mapping_dict(outputs.get(24, outputs.get('24'))) or {}
    if not setup:
        setup = safe_mapping_dict((safe_mapping_dict(context.get('parsed')) or {}).get('trade_setup')) or {}
    assessment = safe_mapping_dict(setup.get('source_assessment')) or {}
    source_status = safe_text(assessment.get('status')).strip()
    reason_codes = [x for x in assessment.get('reason_codes', []) if isinstance(x, str)][:12] if isinstance(assessment.get('reason_codes'), list) else []
    status, basis = 'quality_warning', 'unconfirmed'
    mode_assessment, mode_summary = None, ''
    catalyst = safe_text(setup.get('core_catalyst')).strip()
    if pipeline == 'v4':
        completion = safe_mapping_dict(assessment.get('output_completion')) or {}
        if completion.get('status') == 'incomplete':
            status, basis = 'degraded', 'output_completion'
            reason_codes.append('output_incomplete')
        elif source_status == 'degraded':
            status, basis = 'degraded', 'source_assessment'
        elif catalyst.startswith(('來源不足，原方向不可執行', '資料不足，原方向不可執行')):
            status, basis = 'degraded', 'legacy_system_prefix'
            reason_codes.append('legacy_source_or_execution_degradation')
        elif source_status == 'observation' and neutral_observation_is_explicit(setup):
            status, basis = 'observation', 'source_assessment'
        elif source_status == 'source_bound' and setup.get('trade_direction') in {'Long', 'Short'} and not v4_trade_setup_contract_issues(setup):
            status, basis = 'complete', 'source_assessment'
        else:
            reason_codes.append('analysis_completeness_unconfirmed')
    elif pipeline == 'v2':
        mode_assessment, reason_codes, mode_summary = _v2_explicit_gaps(context)
        basis = 'v2_role_source_contract'
        # A transcript's availability is not an all-source certification.
        source_status = 'degraded' if mode_assessment['earnings_call_source_status'] == 'unavailable' else 'unknown'
        if mode_assessment['research_status'] == 'incomplete':
            status = 'degraded'
    else:
        reason_codes.append('analysis_completeness_unconfirmed')
    if status in {'complete', 'observation'} and (warning or not recorded):
        reason_codes.append('quality_warning' if warning else 'quality_not_recorded')
        status = 'quality_warning'
    label = _LABELS[status]
    if status == 'quality_warning' and not warning:
        label = '分析完整度未確認'
    return {'schema_version': 1, 'status': status, 'label': label, 'summary': mode_summary or _NOTES[status],
            'basis': basis, 'reason_codes': list(dict.fromkeys(reason_codes)),
            'quality_warning': bool(warning), 'quality_recorded': bool(recorded),
            'source_status': source_status or 'unknown', 'quality_statuses': statuses,
            **({'mode_assessment': mode_assessment} if mode_assessment is not None else {})}
