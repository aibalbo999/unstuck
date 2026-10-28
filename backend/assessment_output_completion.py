"""Check raw assessment completeness before tolerant legacy normalization."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal, get_args, get_origin

from json_utils import _strip_code_fence
from llm_completion_provenance import completion_diagnostics, completion_is_incomplete

CONTRACT = 'assessment-output-completion:v1'
AGENTS = frozenset({3, 4, 14, 21})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('nonfinite JSON value: ' + value)


def _required_fields(value, model, issues, prefix=''):
    if not isinstance(value, dict):
        issues.append('missing_or_invalid_' + prefix.rstrip('.'))
        return
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        keys = tuple(dict.fromkeys((field.alias or name, name)))
        present = [value[key] for key in keys if key in value]
        if not present:
            issues.append('missing_' + prefix + keys[0])
        elif len(present) > 1 and present[0] != present[1]:
            issues.append('ambiguous_' + prefix + keys[0])
        else:
            item = present[0]
            annotation = field.annotation
            invalid = ((annotation is str and (not isinstance(item, str) or not item.strip()))
                       or (annotation is bool and type(item) is not bool)
                       or (get_origin(annotation) is list and not isinstance(item, list))
                       or (get_origin(annotation) is Literal and item not in get_args(annotation)))
            if invalid:
                issues.append('invalid_' + prefix + keys[0])


def assess_completion(agent, raw_text, diagnostics=None, prior=None):
    from structured_output_models import get_structured_response_schema
    from structured_output_valuation_models import MoatScores, PriceTargets, ValuationSummary

    observed = completion_diagnostics(diagnostics)
    raw_sha = hashlib.sha256(str(raw_text or '').encode()).hexdigest()
    if (isinstance(prior, dict) and prior.get('contract_version') == CONTRACT
            and prior.get('raw_sha256') == raw_sha and prior.get('status') == 'incomplete'
            and not observed['finish_reasons'] and observed.get('stream_completed') is not False):
        return dict(prior)
    issues = ['provider_output_incomplete'] if completion_is_incomplete(observed) else []
    try:
        raw = json.loads(_strip_code_fence(str(raw_text or '')), object_pairs_hook=_unique_object,
                         parse_constant=_invalid_constant)
    except (ValueError, TypeError):
        raw = None
    if not isinstance(raw, dict):
        issues.append('incomplete_or_invalid_json')
    else:
        _required_fields(raw, get_structured_response_schema(agent), issues)
        if not isinstance(raw.get('analysis_markdown'), str) or not raw['analysis_markdown'].strip():
            issues.append('missing_or_empty_analysis_markdown')
        if agent == 3:
            scores = raw.get('moat_scores')
            _required_fields(scores, MoatScores, issues, 'moat_scores.')
            if isinstance(scores, dict):
                for name, field in MoatScores.model_fields.items():
                    value = scores.get(field.alias, scores.get(name))
                    if value is not None and (type(value) not in {int, float} or not math.isfinite(value) or not 1 <= value <= 10):
                        issues.append('invalid_moat_scores.' + field.alias)
            steps = raw.get('reasoning_steps')
            if not isinstance(steps, list) or len(steps) < 3 or not all(isinstance(s, str) and s.strip() for s in steps):
                issues.append('incomplete_reasoning_steps')
        elif agent in {4, 14}:
            targets = raw.get('price_targets')
            _required_fields(targets, PriceTargets, issues, 'price_targets.')
            _required_fields(raw.get('valuation_summary'), ValuationSummary, issues, 'valuation_summary.')
            if isinstance(targets, dict):
                for alias, name in (('熊市情境', 'bear_case'), ('基本情境', 'base_case'), ('牛市情境', 'bull_case')):
                    value = targets.get(alias, targets.get(name))
                    if value is not None and (type(value) not in {int, float} or not math.isfinite(value) or value <= 0):
                        issues.append('invalid_price_targets.' + alias)
        elif agent == 21 and not isinstance(raw.get('downside_risks'), list):
            issues.append('missing_or_invalid_downside_risks')
    return {'contract_version': CONTRACT, 'status': 'incomplete' if issues else 'complete',
            'raw_sha256': raw_sha, 'finish_reasons': observed['finish_reasons'],
            'provider_finish_observed': bool(observed['finish_reasons']),
            'basis': 'provider_finish_and_raw_required_content', 'issues': list(dict.fromkeys(issues))}


def incomplete_output(output):
    receipt = output.get('output_completion') if isinstance(output, dict) else None
    return isinstance(receipt, dict) and receipt.get('contract_version') == CONTRACT and receipt.get('status') == 'incomplete'
