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
    else:
        reason_codes.append('analysis_completeness_unconfirmed')
    if status in {'complete', 'observation'} and (warning or not recorded):
        reason_codes.append('quality_warning' if warning else 'quality_not_recorded')
        status = 'quality_warning'
    label = _LABELS[status]
    if status == 'quality_warning' and not warning:
        label = '分析完整度未確認'
    return {'schema_version': 1, 'status': status, 'label': label, 'summary': _NOTES[status],
            'basis': basis, 'reason_codes': list(dict.fromkeys(reason_codes)),
            'quality_warning': bool(warning), 'quality_recorded': bool(recorded),
            'source_status': source_status or 'unknown', 'quality_statuses': statuses}
