"""Atomic, temporary model-congestion state; never provider quota entitlement."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import threading
import time


CONGESTION_LUA = r"""
local raw = redis.call('GET', KEYS[1])
local s = raw and cjson.decode(raw) or {generation=0, stage=0, active=false, until_at=0, probe_until=0, owner='', failures={}, hint_until=0}
local previous_generation, was_active = s.generation, s.active
local stamp = redis.call('TIME')
local now = tonumber(stamp[1]) + tonumber(stamp[2])/1000000
local action, key, owner = ARGV[1], ARGV[2], ARGV[3]
local generation, delay, lease, jitter = tonumber(ARGV[4]), tonumber(ARGV[5]), tonumber(ARGV[6]), tonumber(ARGV[7])
local admitted, probe = false, false
local function wait()
  if not s.active then return 0 end
  return math.max(0, s.until_at-now, s.probe_until-now)
end
local function reopen(seconds, increase)
  s.generation = s.generation + 1
  if increase then s.stage = math.min(s.stage+1, 4) end
  s.active = true
  s.until_at = now + seconds
  s.owner = ''
  s.probe_until = 0
  s.failures = {}
  s.hint_until = 0
end
local matched = generation == s.generation
local owned = matched and owner ~= '' and owner == s.owner and s.probe_until > now
if action == 'admit' then
  if not s.active then admitted = true
  elseif wait() <= 0 and owner ~= '' then
    s.owner = owner
    s.probe_until = now + lease
    admitted, probe = true, true
  end
elseif action == 'server_failure' and matched then
  -- An actual 503 is service availability, not quota evidence. Share it at
  -- the transport boundary instead of waiting for each route's retry budget.
  if not s.active or owned then
    reopen(math.max(math.min(60*2^s.stage,300)+jitter,delay), true)
  end
elseif action == 'failure' and matched then
  if s.active then
    if owned then reopen(math.max(math.min(60*2^s.stage,300)+jitter,delay), true) end
  elseif key ~= '' then
    local count = 0
    for k, at in pairs(s.failures) do
      if at <= now-60 then s.failures[k] = nil else count = count+1 end
    end
    if count == 0 then s.hint_until = 0 end
    if s.failures[key] == nil then count = count+1 end
    s.failures[key] = now
    s.hint_until = math.max(s.hint_until, now+delay)
    if count >= 2 then reopen(math.max(60+jitter,s.hint_until-now),true) end
  end
elseif action == 'success' and owned then
  s.generation = s.generation+1
  s.stage, s.until_at, s.probe_until, s.hint_until = 0, 0, 0, 0
  s.active, s.owner, s.failures = false, '', {}
elseif action == 'release' and owned then
  reopen(30, false)
end
local transition = 'unchanged'
if action == 'admit' then
  transition = probe and 'probe_admitted' or admitted and 'admitted' or 'blocked'
elseif s.generation ~= previous_generation then
  if action == 'success' then transition = 'recovered'
  elseif action == 'release' then transition = 'probe_released'
  else transition = was_active and 'reopened' or 'opened' end
elseif action == 'failure' and matched and not was_active and key ~= '' then
  transition = 'failure_observed'
end
local result = {generation=s.generation, wait=wait(), probe=probe, admitted=admitted, transition=transition}
-- Keep the generation tombstone beyond the longest admitted request; expired
-- state must not let an old generation-zero completion become current again.
local ttl = math.ceil(math.max(86400, s.until_at-now+86400, s.probe_until-now+86400, lease+86400)*1000)
redis.call('SET', KEYS[1], cjson.encode(s), 'PX', ttl)
return cjson.encode({result=result,state=s,now=now})
"""


def _state():
    return dict(generation=0, stage=0, active=False, until_at=0.0,
                probe_until=0.0, owner='', failures={}, hint_until=0.0)


def _wait(state, now):
    return max(0.0, state['until_at']-now, state['probe_until']-now) if state['active'] else 0.0


def _reopen(state, now, seconds, *, increase):
    state.update(generation=state['generation']+1,
                 stage=min(state['stage']+1, 4) if increase else state['stage'],
                 active=True, until_at=now+seconds, owner='', probe_until=0.0,
                 failures={}, hint_until=0.0)


def _local_operate(state, now, action, key, owner, generation, delay, lease, jitter):
    previous_generation, was_active = state['generation'], state['active']
    admitted = probe = False
    owned = (generation == state['generation'] and bool(owner) and owner == state['owner']
             and state['probe_until'] > now)
    if action == 'admit':
        if not state['active']:
            admitted = True
        elif _wait(state, now) <= 0 and owner:
            state.update(owner=owner, probe_until=now+lease)
            admitted = probe = True
    elif action == 'server_failure' and generation == state['generation']:
        if not state['active'] or owned:
            _reopen(state, now, max(min(60*2**state['stage'], 300)+jitter, delay), increase=True)
    elif action == 'failure' and generation == state['generation']:
        if state['active']:
            if owned:
                seconds = max(min(60*2**state['stage'], 300)+jitter, delay)
                _reopen(state, now, seconds, increase=True)
        elif key:
            failures = {k: at for k, at in state['failures'].items() if at > now-60}
            if not failures:
                state['hint_until'] = 0.0
            failures[key] = now
            state['failures'] = failures
            state['hint_until'] = max(state['hint_until'], now+delay)
            if len(failures) >= 2:
                _reopen(state, now, max(60+jitter, state['hint_until']-now), increase=True)
    elif action == 'success' and owned:
        generation = state['generation']+1
        state.clear()
        state.update(_state(), generation=generation)
    elif action == 'release' and owned:
        _reopen(state, now, 30, increase=False)
    transition = 'unchanged'
    if action == 'admit':
        transition = 'probe_admitted' if probe else 'admitted' if admitted else 'blocked'
    elif state['generation'] != previous_generation:
        transition = ('recovered' if action == 'success' else 'probe_released' if action == 'release'
                      else 'reopened' if was_active else 'opened')
    elif action == 'failure' and generation == previous_generation and not was_active and key:
        transition = 'failure_observed'
    return dict(generation=state['generation'], wait=_wait(state, now), probe=probe, admitted=admitted, transition=transition)


def _finite(value, *, minimum=0.0):
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError('Congestion timing must be finite and nonnegative')
    return result


class CongestionStore:
    """Share one instance in a process; Redis coordinates independent instances.

    Recovery admission requires a nonempty opaque ``owner``. Every completion
    must return its admission generation and owner. Model/key values should be
    canonical model identity and a key hash; raw credentials are never needed.
    A Redis outage conservatively quarantines each first-used model once, then
    uses local state. That fallback cannot promise cross-process single probes.
    """
    def __init__(self, redis_client=None, clock=time.time, jitter=None, *, shared_required=False):
        self._client = redis_client
        self._clock = clock
        self._jitter = jitter if jitter is not None else lambda: random.uniform(0, 10)
        self._shared_required = bool(shared_required or redis_client is not None)
        self._states = {}
        self._quarantined = set()
        self._lock = threading.RLock()

    def operate(self, model, action, key_hash='', owner='', generation=0, delay=0, lease=400):
        """Inspect or transition state; peek never claims/extends a probe/cooldown.

        Redis peek refreshes only garbage-collection TTL for the generation
        tombstone. First-use outage quarantine is a conservative exception to
        otherwise read-only availability inspection.
        """
        if action not in {'peek', 'admit', 'failure', 'server_failure', 'success', 'release'}:
            raise ValueError('Unknown congestion operation')
        delay, lease = _finite(delay), _finite(lease, minimum=0.001)
        jitter = min(_finite(self._jitter()), 30.0)
        generation = int(generation)
        identity = hashlib.sha256(str(model).encode()).hexdigest()
        with self._lock:
            now = float(self._clock())
            if self._client is not None:
                try:
                    encoded = self._client.eval(CONGESTION_LUA, 1,
                        'stock-agent:llm:congestion:'+identity, action, str(key_hash), str(owner),
                        generation, delay, lease, jitter)
                    payload = json.loads(encoded)
                    mirrored = copy.deepcopy(payload['state'])
                    offset = float(self._clock())-float(payload['now'])
                    for field in ('until_at', 'probe_until', 'hint_until'):
                        if mirrored[field]:
                            mirrored[field] += offset
                    mirrored['failures'] = {k: at+offset for k, at in (mirrored['failures'] or {}).items()}
                    self._states[identity] = mirrored
                    return payload['result']
                except Exception:
                    self._client = None
            state = self._states.setdefault(identity, _state())
            if self._shared_required and identity not in self._quarantined:
                self._quarantined.add(identity)
                provider_wait = delay if action in {'failure', 'server_failure'} and generation == state['generation'] else 0.0
                _reopen(state, now, max(60.0, _wait(state, now), provider_wait), increase=not state['active'])
            return _local_operate(state, now, action, str(key_hash), str(owner), generation, delay, lease, jitter)
