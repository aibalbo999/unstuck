"""Raw completion boundary for mode B/C final decisions, before defaults."""
import hashlib
import json
from json_utils import _strip_code_fence
from llm_completion_provenance import completion_diagnostics, completion_is_incomplete

CONTRACT = 'final-output-completion:v1'

def assess_final_completion(agent_num, raw_text, diagnostics=None, prior=None):
    observed = completion_diagnostics(diagnostics)
    raw_sha = hashlib.sha256(str(raw_text or '').encode()).hexdigest()
    if (isinstance(prior, dict) and prior.get('contract_version') == CONTRACT
            and prior.get('raw_sha256') == raw_sha and prior.get('status') == 'incomplete'
            and not observed['finish_reasons'] and observed.get('stream_completed') is not False):
        return dict(prior)
    issues = ['provider_output_incomplete'] if completion_is_incomplete(observed) else []
    try:
        raw = json.loads(_strip_code_fence(str(raw_text or '')))
    except (ValueError, TypeError):
        raw = None
    if not isinstance(raw, dict):
        issues.append('incomplete_or_invalid_json')
    else:
        required = {'recommendation': dict, 'confidence_basis': dict,
                    'scenario_triggers': list, 'analysis_markdown': str,
                    'position_plan' if agent_num == 16 else 'short_setup': dict}
        for key, kind in required.items():
            if not isinstance(raw.get(key), kind) or not raw[key] or (kind is str and not raw[key].strip()):
                issues.append('missing_or_empty_' + key)
    return {'contract_version': CONTRACT, 'status': 'incomplete' if issues else 'complete',
            'finish_reasons': observed['finish_reasons'],
            'provider_finish_observed': bool(observed['finish_reasons']),
            'basis': 'provider_finish_and_raw_required_content',
            'raw_sha256': raw_sha,
            'issues': issues, 'recoverable': bool(issues)}
