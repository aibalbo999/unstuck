"""Request-local source-reference enums; ordinary evidence validation still applies."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import re

_CURRENT = ContextVar('market_source_schema', default=None)
_SOURCES = ('global_market_context', 'international_news_context')


@contextmanager
def bound_market_source_schema(agent, refs):
    value = None
    if type(agent) is int and agent in (7, 16, 19) and isinstance(refs, dict) and set(refs) == set(_SOURCES):
        valid = all(type(refs[source]) is list and len(refs[source]) <= 32
                    and all(type(ref) is str and re.fullmatch(r'mc:[0-9a-f]{32}', ref)
                            for ref in refs[source])
                    and len(set(refs[source])) == len(refs[source]) for source in _SOURCES)
        if valid and not (set(refs[_SOURCES[0]]) & set(refs[_SOURCES[1]])):
            value = (agent, deepcopy(refs))
    token = _CURRENT.set(value)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def apply_market_source_schema(schema, agent):
    current = _CURRENT.get()
    if current is None or current[0] != agent or not isinstance(schema, dict):
        return schema
    definitions = schema.get('$defs', {})
    market = definitions.get('MarketContextAssessment')
    base = definitions.get('MarketSourceAssessment')
    if not isinstance(market, dict) or not isinstance(base, dict):
        return schema
    result = deepcopy(schema)
    for source in _SOURCES:
        field = result['$defs']['MarketContextAssessment'].get('properties', {}).get(source)
        if not isinstance(field, dict):
            return schema
        alternatives = field.get('anyOf', [])
        original_ref = next((part for part in alternatives if isinstance(part, dict)
                             and part.get('$ref') == '#/$defs/MarketSourceAssessment'), None)
        if original_ref is None:
            return schema
        name = 'MarketSourceAssessment_' + source
        specialized = deepcopy(base)
        items = specialized.get('properties', {}).get('source_refs')
        if not isinstance(items, dict):
            return schema
        refs = current[1][source]
        if not refs:
            items['maxItems'] = 0
        if refs:
            items['items'] = {**items.get('items', {}), 'type': 'string', 'enum': list(refs)}
        result['$defs'][name] = specialized
        original_ref['$ref'] = '#/$defs/' + name
    return result
