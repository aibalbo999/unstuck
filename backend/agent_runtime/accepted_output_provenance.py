"""Output-bound model identity for final-only reruns, separate from call history."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import copy

from model_execution_provenance import model_executions_from_events, normalized_model_executions
from pipeline_modes import get_structured_agent_num
from validators import sanitize_model_output, strip_generated_audit_sections
from workflow_telemetry_attribution import (
    current_node_invocation, node_telemetry_scope, result_fingerprint, safe_model_label,
)
from .attempt_telemetry import build_agent_node_receipt, reset_node_attempt_telemetry, _deterministic_count
from .routing import is_agent_execution_failure


RECEIPT_FIELD = '_accepted_output_provenance'
_capture = ContextVar('final_rerun_model_provenance', default=None)


@contextmanager
def final_rerun_provenance_scope(context: dict, agent_num: int):
    """Enable local capture only for this rerun; private state never reaches render."""
    if agent_num not in (7, 16, 19) or get_structured_agent_num('recommendation', context) != agent_num:
        yield
        return
    private = (RECEIPT_FIELD, '_node_attempt_telemetry')
    previous = {key: context[key] for key in private if key in context}
    context.pop(RECEIPT_FIELD, None)
    with node_telemetry_scope(f'agent_{agent_num}', agent_num):
        token = _capture.set(current_node_invocation())
        reset_node_attempt_telemetry(context, agent_num)
        try:
            yield
        finally:
            _capture.reset(token)
            for key in private:
                if key in previous:
                    context[key] = previous[key]
                else:
                    context.pop(key, None)


def _active(agent_num):
    capture = _capture.get()
    return (capture if isinstance(capture, dict) and capture.get('agent_num') == agent_num
            and capture == current_node_invocation() else None)


def _delta(context, agent_num, text):
    if not isinstance(text, str) or not text.strip() or is_agent_execution_failure(text):
        return None
    for field in ('analyses', 'structured_outputs'):
        values = context.get(field) or {}
        if not isinstance(values, dict) or (agent_num in values and str(agent_num) in values):
            return None  # Consumers disagree on precedence for ambiguous dual keys.
    outputs = context.get('structured_outputs') or {}
    return {'analyses': {agent_num: sanitize_model_output(text).strip()},
            'structured_outputs': {agent_num: outputs.get(agent_num, outputs.get(str(agent_num)))}}


def _execution_record(context, agent_num, receipt):
    """Observed routes are descriptive; only the sealed receipt chooses the model."""
    events = context.get('_runtime_events') or []
    rows = [{'payload': event} for event in events if isinstance(event, dict)] if isinstance(events, list) else []
    observed = model_executions_from_events(rows, context.get('pipeline_id')).get(agent_num, {})
    model = safe_model_label(receipt.get('model'))
    record = {'agent_num': agent_num, 'model_id': model, 'cache_hit': receipt.get('cache_hit') is True}
    for field in ('route_considered', 'provider_call_models', 'route_skipped', 'failed_models'):
        record[field] = [value for value in observed.get(field, []) if safe_model_label(value)]
    record['route_index'] = record['route_considered'].index(model) if model in record['route_considered'] else None
    record['fallback_used'] = observed.get('fallback_used') is True
    # Cache entries do not carry the original generation settings. Current route
    # settings cannot establish how a cached response was generated.
    if not record['cache_hit'] and observed.get('model_id') == model:
        for field in ('generation_policy_version', 'generation_config', 'effective_settings_sha256'):
            if field in observed:
                record[field] = copy.deepcopy(observed[field])
    return record


def seal_returned_output(context: dict, agent_num: int, text: str) -> None:
    """Seal after routed decoding and market projection, without a quality verdict."""
    if _active(agent_num) is None:
        return
    delta = _delta(context, agent_num, text)
    receipt = build_agent_node_receipt(context, agent_num, delta) if delta is not None else {}
    if not receipt.get('result_fingerprint'):
        context.pop(RECEIPT_FIELD, None)
        return
    receipt['deterministic_count'] = _deterministic_count(context, agent_num)
    receipt['execution'] = _execution_record(context, agent_num, receipt)
    context[RECEIPT_FIELD] = receipt


def _known_system_appendix(context, agent_num, delta, fingerprint):
    """Require the exact system-generated suffix, not merely its heading."""
    from final_audit_sections import append_final_audit_section
    from validators import append_quality_warnings

    original = delta['analyses'][agent_num]
    base = strip_generated_audit_sections(original).strip()
    candidate = {**delta, 'analyses': {agent_num: base}}
    if result_fingerprint(candidate, agent_num) != fingerprint:
        return False
    warned = append_quality_warnings(agent_num, base, context.get('data'))
    for text in dict.fromkeys((base, warned)):
        if sanitize_model_output(text).strip() == original:
            return True
        audit_context = {'pipeline_id': context.get('pipeline_id'), 'analyses': {agent_num: text},
                         'audit_repair_log': context.get('audit_repair_log', [])}
        append_final_audit_section(audit_context, context.get('final_audit') or {})
        if sanitize_model_output(audit_context['analyses'][agent_num]).strip() == original:
            return True
    return False


def attach_accepted_final_model(context: dict, agent_num: int) -> None:
    """Attach only a matching current result; do not borrow a source report model."""
    context['model_id'], context['model_executions'] = 'unknown', {}
    capture = _active(agent_num)
    receipt = context.get(RECEIPT_FIELD)
    if (capture is None or not isinstance(receipt, dict)
            or any(receipt.get(key) != value for key, value in capture.items())
            or receipt.get('deterministic_count') != _deterministic_count(context, agent_num)
            or not safe_model_label(receipt.get('model'))):
        return
    analyses = context.get('analyses') or {}
    text = analyses.get(agent_num, analyses.get(str(agent_num))) if isinstance(analyses, dict) else None
    delta = _delta(context, agent_num, text)
    if delta is None:
        return
    if result_fingerprint(delta, agent_num) != receipt.get('result_fingerprint'):
        # Model-authored tails remain part of the seal. Reconstruct subsequent
        # system notes from current validator/audit inputs before excluding them.
        if not _known_system_appendix(context, agent_num, delta, receipt.get('result_fingerprint')):
            return
    record = receipt.get('execution')
    if not isinstance(record, dict) or record.get('model_id') != receipt['model']:
        return
    rows = normalized_model_executions({'model_executions': {agent_num: record}})
    if rows:
        context['model_executions'] = {agent_num: rows[0]}
        context['model_id'] = receipt['model']
