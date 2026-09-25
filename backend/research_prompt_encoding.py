"""Lossless Mode-A representations; source selection and admission stay intact."""
from __future__ import annotations

import json

from llm_input_capacity import estimate_input_tokens
from prompt_record_tables import unpack_record_tables

POLICY = 'research-prompt:v2:lossless-tables-contained-sources'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _financial_payload(section):
    header = '【財務資料 JSON】\n'
    if not section.startswith(header):
        raise ValueError('unknown financial section')
    value, end = json.JSONDecoder(object_pairs_hook=_unique_object).raw_decode(section[len(header):])
    if not isinstance(value, dict) or not section[len(header) + end:].startswith('\n\n【使用規則】\n'):
        raise ValueError('ambiguous financial section')
    return value


def choose_financial_encoding(original: str, candidate: str) -> str:
    """Adopt the existing decoder only after exact typed round-trip and saving.

    Literal source table markers, duplicate keys and malformed encodings retain
    the original. Existing freshness references have one allowlisted address.
    """
    try:
        expected = _financial_payload(original)
        restored = unpack_record_tables(_financial_payload(candidate), strict=True)
        if not isinstance(restored, dict):
            return original
        freshness = restored.get('data_freshness')
        if isinstance(freshness, dict) and freshness.get('source_freshness') == {'$ref': '#/source_freshness'}:
            freshness['source_freshness'] = restored['source_freshness']
        if _canonical(restored) != _canonical(expected):
            return original
        if estimate_input_tokens(candidate) + 64 < estimate_input_tokens(original):
            return candidate
    except (KeyError, TypeError, ValueError, RecursionError):
        pass
    return original


def compact_previous_json(previous: str) -> str:
    """Re-encode only already-selected JSON, retaining all surrounding prose.

    Budget allocation and whole-field selection happen before this function.
    No new fields are admitted using space gained by removing JSON whitespace.
    """
    prefix, remaining = '', previous
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_unique_object)
        for header in ('【提煉 Agent 結構化摘要】\n', '【已解析結構化輸出】\n'):
            # Only system blocks at the leading boundary are eligible. A source
            # may quote these exact headers; never search within source prose.
            if not remaining.startswith(header):
                continue
            start = len(header)
            if remaining[start:start + 1] != '{':
                if header.startswith('【提煉 Agent') and '\n\n' in remaining:
                    notice, remaining = remaining.split('\n\n', 1)
                    prefix += notice + '\n\n'
                    continue
                return previous
            value, size = decoder.raw_decode(remaining[start:])
            tail = remaining[start + size:]
            if tail and not tail.startswith('\n\n'):
                return previous
            prefix += header + _encode(value)
            if tail:
                prefix += '\n\n'
                remaining = tail[2:]
            else:
                remaining = ''
        result = prefix + remaining
        return result if estimate_input_tokens(result) < estimate_input_tokens(previous) else previous
    except (TypeError, ValueError, RecursionError):
        return previous
