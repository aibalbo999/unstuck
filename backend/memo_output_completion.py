"""Raw evidence-memo completion, before tolerant defaults can fill missing fields."""
import hashlib
import json
from json_utils import _strip_code_fence
from llm_completion_provenance import completion_diagnostics, completion_is_incomplete
from pipeline_modes import PIPELINE_DEFINITIONS

_PLACEHOLDERS = {'資料不足', '資料時點未提供', 'N/A', 'null', ''}
_SPECIAL_COMPLETION_AGENTS = frozenset({3, 4, 7, 11, 14, 16, 19, 21, 22, 23, 24})
_PIPELINE_AGENTS = frozenset(agent for mode in PIPELINE_DEFINITIONS.values() for agent in mode['agents'])
PROVIDER_COMPLETION_AGENTS = _PIPELINE_AGENTS - _SPECIAL_COMPLETION_AGENTS
PROVIDER_COMPLETION_POLICY = 'provider-output-completion:v2-all-pipeline-roles'
_PROVIDER_COMPLETION_POLICIES = {PROVIDER_COMPLETION_POLICY, 'provider-output-completion:v1'}


def provider_output_incomplete(output):
    receipt = output.get('output_completion') if isinstance(output, dict) else None
    return (isinstance(receipt, dict) and receipt.get('contract_version') in _PROVIDER_COMPLETION_POLICIES
            and receipt.get('status') == 'incomplete')


def bind_incomplete_text(receipt, raw, rendered):
    """Bind a specialized receipt to exact parser/sanitizer transformations."""
    if receipt.get('status') == 'incomplete':
        from output_sanitizer import sanitize_model_output
        receipt['reparse_sha256'] = sorted({hashlib.sha256(text.encode()).hexdigest()
            for text in (raw, rendered, sanitize_model_output(raw), sanitize_model_output(rendered))})
    return receipt


def retain_known_provider_incomplete(agent, raw, context, diagnostics):
    observed = completion_diagnostics(diagnostics)
    if observed['finish_reasons'] or completion_is_incomplete(observed):
        return False
    outputs = context.get('structured_outputs') or {}
    prior = (outputs.get(agent, outputs.get(str(agent))) or {}).get('output_completion') or {}
    prior_observed = prior.get('diagnostics', prior)
    if prior.get('status') != 'incomplete' or not (
            completion_is_incomplete(prior_observed) or 'provider_output_incomplete' in prior.get('issues', [])):
        return False
    hashes = prior.get('reparse_sha256') or [prior.get('raw_sha256')]
    return hashlib.sha256(raw.encode()).hexdigest() in hashes


def bind_known_provider_incomplete(agent, raw, rendered, context, diagnostics):
    """Preserve observed truncation through reparse; unknown is never STOP."""
    if agent not in PROVIDER_COMPLETION_AGENTS:
        return False
    outputs = context.setdefault('structured_outputs', {})
    previous = outputs.get(agent, outputs.get(str(agent))) or {}
    prior = previous.get('output_completion') if provider_output_incomplete(previous) else None
    observed = completion_diagnostics(diagnostics)
    sha = lambda text: hashlib.sha256(text.encode()).hexdigest()
    receipt = None
    if completion_is_incomplete(observed):
        from output_sanitizer import sanitize_model_output
        receipt = {'contract_version': PROVIDER_COMPLETION_POLICY, 'status': 'incomplete',
            'agent': agent, 'raw_sha256': sha(raw),
            'text_sha256': sorted({sha(raw), sha(rendered), sha(sanitize_model_output(raw)),
                                   sha(sanitize_model_output(rendered))}),
            'finish_reasons': observed['finish_reasons'], 'diagnostics': observed,
            'issues': ['provider_output_incomplete'], 'basis': 'observed_provider_finish_only', 'recoverable': True}
    elif (prior and not observed['finish_reasons']
          and sha(raw) in prior.get('text_sha256', [])):
        receipt = prior
    if receipt:
        outputs.pop(str(agent), None)
        outputs[agent] = {'output_completion': receipt}
        return True
    if prior:
        outputs.pop(agent, None)
        outputs.pop(str(agent), None)
    return False


def assess_memo_completion(raw_text, diagnostics=None):
    observed = completion_diagnostics(diagnostics)
    try:
        payload = json.loads(_strip_code_fence(str(raw_text or '')))
    except (ValueError, TypeError):
        payload = None
    issues = []
    if completion_is_incomplete(observed):
        issues.append('provider_output_incomplete')
    if not isinstance(payload, dict):
        issues.append('incomplete_or_invalid_json')
    else:
        for key in ('as_of_date', 'confidence', 'evidence_items', 'analysis_markdown'):
            if key not in payload:
                issues.append('missing_' + key)
        if payload.get('confidence') not in {'high', 'medium', 'low', 'unassessed'}:
            issues.append('invalid_confidence')
        for key in ('as_of_date', 'analysis_markdown'):
            if not isinstance(payload.get(key), str) or payload[key].strip() in _PLACEHOLDERS:
                issues.append('unassessed_' + key)
        items = payload.get('evidence_items')
        if not isinstance(items, list) or not 1 <= len(items) <= 8:
            issues.append('invalid_evidence_items')
        else:
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    issues.append(f'evidence_{index}_invalid')
                    continue
                for key in ('finding', 'freshness_note', 'counterevidence'):
                    # Explicit limitations/counterevidence may be unavailable; omission
                    # still cannot be silently manufactured by normalizer defaults.
                    if not isinstance(item.get(key), str) or not item[key].strip():
                        issues.append(f'evidence_{index}_missing_{key}')
                refs = item.get('source_refs')
                if not isinstance(refs, list) or not 1 <= len(refs) <= 6 or any(not isinstance(x, str) or not x.strip() for x in refs):
                    issues.append(f'evidence_{index}_missing_source_refs')
    return {'contract_version': 'memo-output-completion:v1',
            'status': 'incomplete' if issues else 'complete',
            'basis': 'provider_finish_and_raw_required_content',
            'finish_reasons': observed['finish_reasons'],
            'provider_finish_observed': bool(observed['finish_reasons']),
            'raw_sha256': hashlib.sha256(str(raw_text or '').encode()).hexdigest(),
            'issues': list(dict.fromkeys(issues)), 'recoverable': bool(issues)}


def incomplete_memo_roles(payload):
    from industry_output_completion import POLICY as INDUSTRY_POLICY
    from assessment_output_completion import CONTRACT as ASSESSMENT_POLICY
    root = payload if isinstance(payload, dict) else {}
    rerun=root.get('rerun_context')
    context = {**(rerun if isinstance(rerun,dict) else {}), **root}
    outputs = context.get('structured_outputs') or {}
    outputs=outputs if isinstance(outputs,dict) else {}
    result = []
    for num in sorted(_PIPELINE_AGENTS):
        role = outputs.get(num, outputs.get(str(num))) or {}
        receipt = (context.get('analysis_output_completions') or {}).get(str(num)) or role.get('output_completion') or {}
        if num in {7, 24}:
            raw = context.get('_research_completion_receipt' if num == 7 else '_trade_completion_receipt') or {}
            observed = completion_diagnostics(raw.get('diagnostics'))
            if completion_is_incomplete(observed):
                receipt = {'contract_version': 'final-output-completion:v1', 'status': 'incomplete',
                           'finish_reasons': observed['finish_reasons'], 'issues': ['provider_output_incomplete'],
                           'raw_sha256': raw.get('raw_sha256'), 'recoverable': True}

        if receipt.get('contract_version') in ({'memo-output-completion:v1', 'final-output-completion:v1', INDUSTRY_POLICY, ASSESSMENT_POLICY} | _PROVIDER_COMPLETION_POLICIES) and receipt.get('status') == 'incomplete':
            result.append({'agent': num, 'receipt': receipt})
    return result


def incomplete_memo_notice(payload):
    roles = incomplete_memo_roles(payload)
    details = [f"Agent {role['agent']}（{'/'.join(role['receipt'].get('finish_reasons') or role['receipt'].get('issues') or ['必要內容缺漏'])}）" for role in roles]
    return ('分析未完整：' + '、'.join(details) + '。已保留原輸出；須有限次重新驗證，不能視為完整有效的新預測，不納入決策追蹤或績效觀察母體。') if roles else ''
