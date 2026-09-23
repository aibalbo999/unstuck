"""Server-owned committed-node receipts for conservative stage-local RQ backoff.

Never promote graph state or reset provider cooldowns. A failed node's pending
writes, timestamps and unvalidated candidates do not establish progress.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

_FIELD = 'availability_stage_progress'
_RECEIPT = '_committed_retry_progress'
_NODE = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,95}')
_HASH = re.compile(r'[0-9a-f]{64}')
_MAX_NODES = 128


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class _CommittedProgress:
    thread: str
    scope: str
    node: str
    checkpoint: str
    completed: tuple[tuple[str, str], ...]


async def attach_committed_retry_progress(error, saver, graph, config):
    """Read the durable root checkpoint only; failure to prove progress is benign."""
    # Exceptions may be reused by callers; a failed fresh read cannot reuse old proof.
    try:
        error.__dict__.pop(_RECEIPT, None)
    except Exception:
        return
    from agent_runtime.retry_policy import AgentRateLimitError, AgentTransientError
    if not isinstance(error, (AgentRateLimitError, AgentTransientError)):
        return
    try:
        saved = await saver.aget_tuple(config)
        if saved is None:
            return
        checkpoint = saved.checkpoint
        snapshot = await graph.aget_state(saved.config)
        thread = config['configurable']['thread_id']
        if not isinstance(thread, str) or not thread or len(thread) > 512:
            return
        saved_config = saved.config['configurable']
        if (saved_config.get('thread_id') != thread or saved_config.get('checkpoint_ns', '')
                or saved.metadata.get('source') != 'loop' or len(snapshot.next) != 1):
            return
        node = snapshot.next[0]
        if not isinstance(node, str) or not _NODE.fullmatch(node):
            return
        values = checkpoint['channel_values']
        data = values.get('raw_financial_data', {}).get('input')
        if not isinstance(data, dict) or not data:
            return
        scope = _hash({'thread': thread, 'input': data, 'pipeline': values.get('pipeline_id'),
                       'prompt_version': values.get('prompt_version'),
                       'prompt_fingerprint': values.get('prompt_fingerprint')})
        seen = checkpoint.get('versions_seen')
        if not isinstance(seen, dict) or len(seen) > _MAX_NODES:
            return
        completed = []
        for name, versions in seen.items():
            if not isinstance(name, str) or not _NODE.fullmatch(name):
                continue  # Internal __start__/__interrupt__ channels are not node completions.
            if not isinstance(versions, dict) or not versions:
                return
            completed.append((name, _hash(versions)))
        checkpoint_id = checkpoint.get('id')
        if not isinstance(checkpoint_id, str) or not checkpoint_id or len(checkpoint_id) > 128:
            return
        setattr(error, _RECEIPT, _CommittedProgress(thread, scope, node, checkpoint_id, tuple(completed)))
    except Exception:
        return  # Keep the original provider failure and legacy backoff, not a new failure.


def _valid_ledger(value, receipt, global_count):
    if (not isinstance(value, dict) or type(value.get('version')) is not int
            or value['version'] != 1 or value.get('scope') != receipt.scope):
        return False
    if type(value.get('global_count')) is not int or value['global_count'] != global_count - 1:
        return False
    counts, last = value.get('counts'), value.get('last')
    if not isinstance(counts, dict) or not 0 < len(counts) <= _MAX_NODES or not isinstance(last, dict):
        return False
    if any(not isinstance(n, str) or not _NODE.fullmatch(n) or type(c) is not int or not 0 < c <= global_count
           for n, c in counts.items()):
        return False
    # Every recorded availability failure belongs to exactly one retained stage.
    if sum(counts.values()) != global_count - 1 or 'completion_token' not in last:
        return False
    token = last['completion_token']
    node, checkpoint = last.get('node'), last.get('checkpoint')
    return (isinstance(node, str) and bool(_NODE.fullmatch(node)) and node in counts
            and isinstance(checkpoint, str) and 0 < len(checkpoint) <= 128
            and (token is None or isinstance(token, str) and bool(_HASH.fullmatch(token))))


def availability_stage_count(meta, error, job_id, global_count):
    """Malformed optional metadata must never replace a retryable provider failure."""
    try:
        return _stage_count(meta, error, job_id, global_count)
    except Exception:
        return global_count


def _stage_count(meta, error, job_id, global_count):
    receipt = getattr(error, _RECEIPT, None)
    if not _valid_receipt(receipt) or receipt.thread.split(':', 1)[0] != job_id:
        return global_count
    completed = dict(receipt.completed)
    old = meta.get(_FIELD)
    valid = _valid_ledger(old, receipt, global_count)
    counts = dict(old['counts']) if valid else {}
    count = global_count
    if valid:
        last = old['last']
        if receipt.node in counts:
            count = counts[receipt.node] + 1
        elif (receipt.checkpoint != last['checkpoint']
              and completed.get(last['node']) is not None
              and completed[last['node']] != last['completion_token']):
            count = 1  # The previously failing node actually committed before this new node.
    if len(counts) >= _MAX_NODES and receipt.node not in counts:
        return global_count
    counts[receipt.node] = count
    meta[_FIELD] = {'version': 1, 'scope': receipt.scope, 'global_count': global_count,
                    'counts': counts, 'last': {'node': receipt.node, 'checkpoint': receipt.checkpoint,
                                              'completion_token': completed.get(receipt.node)}}
    return count


def _valid_receipt(receipt):
    if not isinstance(receipt, _CommittedProgress):
        return False
    if (not isinstance(receipt.thread, str) or not 0 < len(receipt.thread) <= 512
            or not isinstance(receipt.scope, str) or not _HASH.fullmatch(receipt.scope)
            or not isinstance(receipt.node, str) or not _NODE.fullmatch(receipt.node)
            or not isinstance(receipt.checkpoint, str) or not 0 < len(receipt.checkpoint) <= 128
            or not isinstance(receipt.completed, tuple) or len(receipt.completed) > _MAX_NODES):
        return False
    names = set()
    for item in receipt.completed:
        if not isinstance(item, tuple) or len(item) != 2:
            return False
        name, token = item
        if (not isinstance(name, str) or not _NODE.fullmatch(name) or name in names
                or not isinstance(token, str) or not _HASH.fullmatch(token)):
            return False
        names.add(name)
    return True
