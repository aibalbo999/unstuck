"""Stable identities for a persisted parallel superstep, never draft acceptance."""
from __future__ import annotations

import hashlib
import json
import re

_NODE = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,95}')
_MAX_MEMBERS = 128


def stage_key(members):
    if len(members) == 1:
        return members[0]
    encoded = json.dumps(members, separators=(',', ':')).encode()
    return 'parallel_' + hashlib.sha256(encoded).hexdigest()[:32]


def valid_members(node, members):
    return (isinstance(members, (tuple, list)) and 0 < len(members) <= _MAX_MEMBERS
            and all(isinstance(n, str) and _NODE.fullmatch(n) for n in members)
            and list(members) == sorted(set(members)) and stage_key(members) == node)


def pending_members(checkpoint, snapshot):
    """Keep original root branch membership even when pending writes finish a sibling.

    snapshot.next can shrink as complete pending writes are applied by LangGraph.
    Those writes remain reusable by the graph, but do not complete this superstep.
    Dynamic Send/ambiguous fanout without root branch channels remains unknown.
    """
    pending = snapshot.next
    if (not isinstance(pending, (tuple, list)) or not 0 < len(pending) <= _MAX_MEMBERS
            or any(not isinstance(n, str) or not _NODE.fullmatch(n) for n in pending)
            or len(set(pending)) != len(pending)):
        return None
    branches = sorted(k.removeprefix('branch:to:') for k in checkpoint['channel_values']
                      if isinstance(k, str) and k.startswith('branch:to:'))
    if branches:
        if (len(branches) > _MAX_MEMBERS or any(not _NODE.fullmatch(n) for n in branches)
                or not set(pending).issubset(branches)):
            return None
        return tuple(branches)
    return tuple(pending) if len(pending) == 1 else None


def ledger_members(last):
    node = last.get('node')
    if 'members' in last:
        members = last['members']
    elif isinstance(node, str) and not node.startswith('parallel_'):
        members = (node,)  # Existing single-node v1 ledgers had no member field.
    else:
        return None
    return tuple(members) if valid_members(node, members) else None


def completion_token(completed, members):
    if not members or any(n not in completed for n in members):
        return None
    if len(members) == 1:
        return completed[members[0]]
    encoded = json.dumps([(n, completed[n]) for n in members], separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()
