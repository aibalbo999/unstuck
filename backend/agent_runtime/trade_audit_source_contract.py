"""Validate audit rewrites through the existing bounded repair budget."""
from trade_source_contract import allowed_source_refs
from workflow_trade_evidence import trade_manifest_matches_input

_PREFIX = 'Agent 24 來源引用未通過：'


def audit_source_issues(context):
    output = (context.get('structured_outputs') or {}).get(24) or (context.get('structured_outputs') or {}).get('24') or {}
    assessment = output.get('source_assessment') or {}
    manifest = context.get('_trade_source_manifest') or {}
    if (context.get('pipeline_id') != 'v4' or assessment.get('status') != 'degraded'
            or (assessment.get('output_completion') or {}).get('status') == 'local_fallback'
            or not trade_manifest_matches_input(manifest, context.get('data', {}))
            or assessment.get('source_fingerprint') != manifest.get('fingerprint')
            or not any(allowed_source_refs(manifest.get('catalog', {})).values())):
        return []
    return [_PREFIX + '、'.join(str(x) for x in assessment.get('reason_codes', [])) +
            '。現況主張須引用本次目錄內同主體、期間、單位的來源；未來条件另以「等待…後再重新評估」表達，不能用空引用保留現況斷言。']


def mark_audit_source_attempt(agent_num, context, issues):
    if agent_num != 24 or not any(str(issue).startswith(_PREFIX) for issue in issues):
        return
    output = (context.get('structured_outputs') or {}).get(24) or (context.get('structured_outputs') or {}).get('24') or {}
    assessment = output.get('source_assessment')
    if isinstance(assessment, dict):
        assessment['repair_attempted'] = True
