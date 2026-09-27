"""Conservative reported business comparisons; never numeric peer eligibility."""
from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
import time

from config import FINANCIAL_DATA_CACHE_SECONDS
from news_record_utils import canonical_link, clean_text, parse_news_datetime
from source_content_selection import company_aliases

POLICY = 'reported-peer-comparison-v1'
_TICKER = re.compile(r'^(\d{4,6})\.(TW|TWO)$')
_PAIR = re.compile(r'([\u3400-\u9fffA-Za-z][\u3400-\u9fffA-Za-z*\-]{1,30})\s*[（(]\s*(\d{4,6})\s*[)）]')
_SCOPE = re.compile(r'([A-Za-z0-9\u3400-\u9fff /\-]{1,24}(?:佈局|布局|技術|業務|產品|研發|製程|方案|策略))')
_EXCLUDED = re.compile(r'否認|否认|不再|並不|并不|不會|不会|沒有|没有|不是|並非|并非|非競爭|非同業|不屬於|不构成|不構成|不把|客戶|客人|供應商|供應鏈|供貨|合作夥伴|合作伙伴|股價|漲停|跌停|買超|賣超|外資|漲跌|大漲|大跌|股息|概念股|名錄|名單|盤點|一次看|全指南')


def peer_selection_diagnostics(ticker: str) -> dict:
    """Mark this attempt even if an outer provider circuit prevents its callback."""
    if re.fullmatch(r'\d{4,6}(?:\.(?:TW|TWO))?', str(ticker).strip().upper()):
        return {'selection_policy': POLICY}
    return {}


def is_reported_peer_record(record, ticker: str) -> bool:
    """Retain only the new evidence shape; retained records still use stale rules."""
    if not isinstance(record, dict):
        return False
    issuer, counterpart = record.get('issuer'), record.get('counterparty')
    stamp = parse_news_datetime(record.get('published_at'))
    if not isinstance(issuer, dict) or not isinstance(counterpart, dict):
        return False
    match = _TICKER.fullmatch(str(counterpart.get('ticker') or ''))
    stamps = [counterpart.get(key) for key in ('market_data_fetched_at_epoch', 'cache_generated_at_epoch')]
    if (not match or counterpart.get('stock_id') != match[1]
            or counterpart.get('exchange') != ('TAI' if match[2] == 'TW' else 'TWO')
            or not clean_text(counterpart.get('official_name'))
            or any(isinstance(t, bool) or not isinstance(t, (int, float))
                   or not math.isfinite(t) or not 0 <= t <= time.time() for t in stamps)
            or stamps[1] < stamps[0]):
        return False
    return bool(
        record.get('selection_policy') == POLICY
        and record.get('relationship_kind') == 'reported_business_peer_comparison'
        and record.get('relationship_basis') == 'headline_or_snippet'
        and record.get('numeric_comparability_verified') is False
        and isinstance(issuer, dict) and issuer.get('ticker') == ticker
        and isinstance(counterpart, dict) and _TICKER.fullmatch(str(counterpart.get('ticker') or ''))
        and counterpart.get('ticker') != ticker
        and counterpart.get('identity_basis') == 'existing_cached_self_identity'
        and counterpart.get('instrument_type') == 'EQUITY'
        and stamp is not None and stamp <= datetime.fromtimestamp(time.time(), timezone.utc)
        and canonical_link(record.get('link')) and clean_text(record.get('source'))
        and clean_text(record.get('reported_scope'))
        and isinstance(record.get('evidence_span'), str) and record['evidence_span'].strip()
        and record['evidence_span'] in clean_text(record.get('title'))
    )


def _identity_names(data: dict) -> list[str]:
    return company_aliases({**data, 'company_name': ''})


def verified_issuer(data: dict) -> dict | None:
    ticker = str(data.get('ticker') or '').strip().upper()
    match = _TICKER.fullmatch(ticker)
    identity = data.get('company_identity')
    if not match or not isinstance(identity, dict):
        return None
    name = clean_text(identity.get('official_name')).strip().strip('*')
    names = _identity_names(data)
    payload_names = [clean_text(part).strip().strip('*').casefold()
                     for part in str(data.get('company_name') or '').split(' / ')]
    if (identity.get('ticker') != ticker or str(identity.get('stock_id') or '') != match[1]
            or identity.get('instrument_type') != 'EQUITY'
            or data.get('quote_type') != 'EQUITY'
            or data.get('exchange') != ('TAI' if match[2] == 'TW' else 'TWO')
            or len(name) < 2 or name.casefold() not in names
            or any(part not in names for part in payload_names if part)):
        return None
    return {'ticker': ticker, 'stock_id': match[1], 'official_name': name}


def _fresh_identity(value, ticker: str, now: float) -> dict | None:
    if not isinstance(value, dict) or value.get('ticker') != ticker:
        return None
    issuer = verified_issuer(value)
    if not issuer or value.get('quote_type') != 'EQUITY':
        return None
    if value.get('exchange') != ('TAI' if ticker.endswith('.TW') else 'TWO'):
        return None
    stamps = {}
    for key in ('market_data_fetched_at_epoch', 'cache_generated_at_epoch'):
        raw = value.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            return None
        if not 0 <= now - raw <= FINANCIAL_DATA_CACHE_SECONDS:
            return None
        stamps[key] = raw
    if stamps['cache_generated_at_epoch'] < stamps['market_data_fetched_at_epoch']:
        return None
    identity = value['company_identity']
    return {**issuer, **stamps, 'exchange': value['exchange'], 'instrument_type': 'EQUITY',
            'identity_basis': 'existing_cached_self_identity',
            'identity_source': identity.get('instrument_type_source'),
            'allowed_names': _identity_names(value)}


class PeerRelationshipSelector:
    def __init__(self, data: dict, *, deadline: float):
        self.data, self.deadline = data, deadline
        self.issuer = verified_issuer(data)
        self.records, self.archive, self.raw_records = [], [], []
        self._identities, self._seen = {}, set()

    async def _counterparty(self, code: str) -> tuple[dict | None, str]:
        if code in self._identities:
            return self._identities[code]
        from cache_store import get_cache_json
        values = []
        for suffix in ('TW', 'TWO'):
            # Deliver pending cancellation before dispatching a local lookup.
            await asyncio.sleep(0)
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                return None, 'identity_deadline_exhausted'
            try:
                async with asyncio.timeout(remaining):
                    value = await asyncio.to_thread(get_cache_json, f'financial_data:{code}.{suffix}')
            except TimeoutError:
                return None, 'identity_deadline_exhausted'
            except Exception:
                return None, 'identity_cache_unavailable'
            if time.monotonic() >= self.deadline:
                return None, 'identity_deadline_exhausted'
            if value is not None:
                values.append((f'{code}.{suffix}', value))
        # Any two populated market keys are ambiguous, even if one is malformed.
        if len(values) != 1:
            answer = (None, 'counterparty_market_conflict' if values else 'counterparty_identity_missing')
        else:
            ticker, value = values[0]
            identity = _fresh_identity(value, ticker, time.time())
            answer = (identity, '' if identity else 'counterparty_identity_unverified')
        self._identities[code] = answer
        return answer

    def reject(self, record: dict, reason: str):
        self.archive.append({'reason': reason, 'record': deepcopy(record)})

    async def consider(self, record: dict, *, quality_selected: bool = True):
        self.raw_records.append(deepcopy(record))
        if not quality_selected:
            self.reject(record, 'search_quality_not_selected')
            return
        await asyncio.sleep(0)
        if time.monotonic() >= self.deadline:
            self.reject(record, 'search_deadline_exhausted')
            return
        title = clean_text(record.get('title'))
        stamp = parse_news_datetime(record.get('published_at'))
        link = canonical_link(record.get('link'))
        if (stamp is None or stamp > datetime.fromtimestamp(time.time(), timezone.utc)
                or not link or not clean_text(record.get('source'))):
            self.reject(record, 'publication_or_source_unverified')
            return
        key = (link, title.casefold())
        if key in self._seen:
            self.reject(record, 'duplicate')
            return
        self._seen.add(key)
        # Only explicit two-company business comparison headlines are supported.
        # Other text remains archived, not inferred into a competitor relation.
        if _EXCLUDED.search(title):
            self.reject(record, 'negated_or_nonpeer_context')
            return
        pairs = list(_PAIR.finditer(title))
        if (len(pairs) != 2 or not self.issuer
                or len({p[2] for p in pairs}) != 2
                or self.issuer['stock_id'] not in {p[2] for p in pairs}):
            self.reject(record, 'explicit_company_pair_missing')
            return
        bridge = title[pairs[0].end():pairs[1].start()] + pairs[1][1]
        connected = re.fullmatch(r'\s*(與|和|及|、|vs\.?)\s*(.+)', bridge, re.I)
        tail = title[pairs[1].end():]
        scope = _SCOPE.search(tail)
        if (not connected
                or not scope or not re.search(r'比較|對比', tail)):
            self.reject(record, 'explicit_business_comparison_missing')
            return
        names = [pairs[0][1], connected[2].strip()]
        target_index = next(i for i, p in enumerate(pairs) if p[2] == self.issuer['stock_id'])
        other_index = 1 - target_index
        other = pairs[other_index]
        if names[target_index].strip('*').casefold() not in _identity_names(self.data):
            self.reject(record, 'issuer_name_code_conflict')
            return
        identity, reason = await self._counterparty(other[2])
        if identity is None or names[other_index].strip('*').casefold() not in identity['allowed_names']:
            self.reject(record, reason or 'counterparty_name_code_conflict')
            return
        counterpart = {k: v for k, v in identity.items() if k != 'allowed_names'}
        self.records.append({**deepcopy(record), 'link': link,
            'relationship_kind': 'reported_business_peer_comparison',
            'relationship_basis': 'headline_or_snippet', 'selection_policy': POLICY,
            'evidence_span': title[pairs[0].start():], 'reported_scope': scope[1].strip(),
            'issuer': self.issuer, 'counterparty': counterpart,
            'source_record_archive': [{'reason': 'accepted_peer_original', 'record': deepcopy(record)}],
            'numeric_comparability_verified': False, 'content_coverage': 'headline_or_snippet'})

    def audit(self) -> dict:
        reasons = Counter(item['reason'] for item in self.archive)
        return {'selection_policy': POLICY, 'raw_count': len(self.raw_records),
                'usable_count': len(self.records), 'rejected_count': len(self.archive),
                'rejected_reason_counts': dict(reasons), 'source_record_archive': deepcopy(self.archive),
                'quality_status': 'reported_peer_evidence' if self.records else 'no_verified_peer_relationship',
                'identity_status': 'verified_issuer_context' if self.issuer else 'issuer_identity_unverified',
                'search_budget_exhausted': time.monotonic() >= self.deadline}
