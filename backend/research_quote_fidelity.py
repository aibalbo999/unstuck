"""Recover uniquely provable bold formatting from current, role-bound sources.

No approximate matching, omitted words, cross-leaf joins or prior candidates.
The restored value must still pass the unmodified verbatim evidence predicate.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re

from research_assumption_contract import reconciliation_sources

POLICY = 'research-quote-format:v1:paired-bold-only'
_BOLD = re.compile(r'(?<![A-Za-z0-9_\\*])\*\*(?=\S)([^*\n]*?\S)(?<!\\)\*\*(?![A-Za-z0-9_*])')


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _json_hash(value):
    return _hash(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _code_positions(source):
    protected = set()
    fence = None
    offset = 0
    for line in source.splitlines(keepends=True):
        marker = re.match(r' {0,3}(`{3,}|~{3,})(.*)', line)
        if fence:
            protected.update(range(offset, offset + len(line)))
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            protected.update(range(offset, offset + len(line)))
        elif '`' in line or line.startswith(('    ', '\t')):
            protected.update(range(offset, offset + len(line)))
        offset += len(line)
    return protected


def _source_view(source):
    protected = _code_positions(source)
    pairs = []
    for match in _BOLD.finditer(source):
        start, end = match.span()
        if start in protected:
            continue  # Code or an ambiguous mixed-markup line is not a bold witness.
        pairs.append((start, end))
    removed = {i for start, end in pairs for i in (start, start + 1, end - 2, end - 1)}
    offsets = [i for i in range(len(source)) if i not in removed]
    return ''.join(source[i] for i in offsets), offsets, pairs


def _unique_literal(quote, sources):
    # Exact quotes are authoritative already; never canonicalize their formatting.
    if not quote or any(quote.strip() in source for source in sources):
        return None
    if len(quote) > 4096 or quote != quote.strip() or '\n' in quote or '...' in quote or '…' in quote:
        return None
    matches = {}
    attempts = 0
    for source in dict.fromkeys(sources):
        if len(source) > 100_000:
            continue
        plain, offsets, pairs = _source_view(source)
        position = plain.find(quote)
        while position >= 0:
            attempts += 1
            if attempts > 64:
                return None  # Bound rejected partial matches as well as accepted witnesses.
            start, end = offsets[position], offsets[position + len(quote) - 1] + 1
            # Restore entire paired delimiters only when their full contents are
            # covered. A partial bold span cannot become an unbalanced quote.
            for opening, closing in pairs:
                if start <= opening + 2 and end >= closing - 2:
                    start, end = min(start, opening), max(end, closing)
            literal = source[start:end]
            partial_pair = any(start < closing and end > opening and not (start <= opening and end >= closing)
                               for opening, closing in pairs)
            if literal != quote and not partial_pair:
                witness = {'source_sha256': _hash(source), 'start': start, 'end': end}
                matches.setdefault(literal, []).append(witness)
            if len(matches) > 1 or sum(map(len, matches.values())) > 64:
                return None  # Distinct literal choices or excessive ambiguity fail closed.
            position = plain.find(quote, position + 1)
    return next(iter(matches.items())) if len(matches) == 1 else None


def restore_reconciliation_quotes(value, context, raw_text):
    """Return a copy plus a locally produced receipt; preserve every other claim."""
    result = copy.deepcopy(value)
    if not isinstance(result, dict) or not isinstance(result.get('checks'), list) or len(result['checks']) != 5:
        return result, None
    sources = reconciliation_sources(context)
    changes = []
    for row in result['checks']:
        if not isinstance(row, dict):
            continue
        for field, agent in (('valuation_quote', 4), ('growth_quote', 5)):
            quote = row.get(field)
            if not isinstance(quote, str):
                continue
            match = _unique_literal(quote, sources[str(agent)])
            if match is None:
                continue
            literal, witnesses = match
            row[field] = literal
            changes.append({'topic': row.get('topic'), 'field': field, 'source_agent': agent,
                'before_sha256': _hash(quote), 'after_sha256': _hash(literal), 'sources': witnesses})
    if not changes:
        return result, None
    return result, {'policy': POLICY, 'raw_response_sha256': _hash(raw_text),
        'before_reconciliation_sha256': _json_hash(value), 'after_reconciliation_sha256': _json_hash(result),
        'upstream_fingerprint': _json_hash(sources), 'changes': changes,
        'verification_scope': 'format_restoration_only_not_semantic_approval'}
