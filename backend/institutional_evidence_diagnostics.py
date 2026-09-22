"""Lossless claim locations and source-scoped repair explanations."""
import re


def normalized_claim_text(text):
    original = str(text or '')
    offsets = [i for i, char in enumerate(original) if not re.match(r'[^\S\n]|[*`]', char)]
    return ''.join(original[i] for i in offsets), offsets


def claim_diagnostic(reason, original, offsets, match, prefix, population, window, eligible, candidates):
    start, end = offsets[match.start()], offsets[match.end() - 1] + 1
    def source(record):
        value = {key: record.get(key) for key in ('path', 'population', 'window', 'observed_at', 'unit', 'value', 'provider')}
        value['source_ref'] = record.get('path') or record.get('evidence_ref')
        return value
    return {'reason': reason, 'span': [start, end], 'claim': original[start:end],
            'context': prefix, 'population': population, 'window': window,
            'claimed_unit': (match['scale'] or '') + match['unit'],
            'same_scope_sources': [source(r) for r in candidates],
            # Alternatives are not evidence for this claim; never silently select by numeric equality.
            'available_population_sources': [source(r) for r in eligible if r['population'] == population]}
