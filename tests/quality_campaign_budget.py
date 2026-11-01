"""Append-only, cross-process admission ledger for ONE explicitly bound campaign.

This is not a network interceptor, billing verifier, process watchdog or live
runner. Callers must reserve before EVERY logical transport/physical HTTP and
prove cleanup before finish_batch. A crash leaves reservations/jobs/batches in
place. Cleanup can record overruns but cannot refund calls, jobs or missing
usage. This local ledger cannot protect against replacing/deleting its file or
using a different ledger; the integration owner must pin and protect its path.
"""
import copy
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

STAGES = ('S1', 'S2', 'S3', 'S4')
HASH_FIELDS = ('code_sha256', 'source_sha256', 'route_sha256')
DEFAULT_LIMITS = {
    'S1': {'jobs': 4, 'transport': 48, 'http': 48, 'tokens': 4_000_000, 'seconds': 40 * 60},
    'S2': {'jobs': 24, 'transport': 360, 'http': 360, 'tokens': 25_000_000, 'seconds': 240 * 60},
    'S3': {'jobs': 120, 'transport': 1920, 'http': 1920, 'tokens': 126_000_000, 'seconds': 1200 * 60},
    'S4': {'jobs': 4, 'transport': 72, 'http': 72, 'tokens': 5_000_000, 'seconds': 40 * 60},
    'campaign': {'jobs': 152, 'transport': 2400, 'http': 2400, 'tokens': 160_000_000,
                 'cost_microusd': 50_000_000, 'active_jobs': 2, 'live_seconds': 7 * 86400,
                 'job_seconds': 60 * 60},
}


class BudgetDenied(RuntimeError):
    """No permission to start more work; cleanup and true usage remain recordable."""


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise BudgetDenied('explicit sha256 evidence required')
    return value


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', value):
        raise BudgetDenied('invalid explicit identifier')
    return value


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise BudgetDenied('nonnegative integer accounting required')
    return value


def _limits(overrides):
    result = copy.deepcopy(DEFAULT_LIMITS)
    for section, fields in (overrides or {}).items():
        if section not in result or not isinstance(fields, dict):
            raise BudgetDenied('unknown limits')
        for key, value in fields.items():
            if key not in result[section] or _integer(value) > result[section][key]:
                raise BudgetDenied('limits may only be reduced')
            if key.endswith('seconds') and value == 0:
                raise BudgetDenied('deadline must be positive')
            result[section][key] = value
    return result


def manifest_identity(campaign_id, allowed_bindings):
    """Hash each immutable binding_id -> actual SHA column of the allowlist.

    A binding represents a permitted code/source/route combination. Both the
    initial mapping and its three column hashes are fixed for this ledger. One
    constrained S1 repair revision can append bindings, never replace this init
    manifest or reopen/reset any consumed budget or deadline.
    """
    _name(campaign_id)
    if not isinstance(allowed_bindings, dict) or not allowed_bindings:
        raise BudgetDenied('nonempty campaign manifest required')
    for name, values in allowed_bindings.items():
        _name(name)
        if not isinstance(values, dict) or set(values) != set(HASH_FIELDS):
            raise BudgetDenied('complete manifest actual hashes required')
        for value in values.values(): _hash(value)
    return {'campaign_id': campaign_id, **{field: hashlib.sha256(
        _json({name: row[field] for name, row in allowed_bindings.items()}).encode()).hexdigest()
        for field in HASH_FIELDS}}


class CampaignBudget:
    def __init__(self, path, identity, *, limits=None, clock=None, allowed_bindings=None):
        self.path = Path(path)
        if (not self.path.is_absolute() or self.path.parent.resolve() != self.path.parent
                or not self.path.parent.is_dir()):
            raise BudgetDenied('absolute, existing, nonsymlink parent required')
        if set(identity) != {'campaign_id', 'code_sha256', 'source_sha256', 'route_sha256'}:
            raise BudgetDenied('complete campaign identity required')
        self.identity = {'campaign_id': _name(identity['campaign_id']),
                         **{key: _hash(identity[key]) for key in HASH_FIELDS}}
        self.manifest_mode = allowed_bindings is not None
        if self.manifest_mode and manifest_identity(self.identity['campaign_id'], allowed_bindings) != self.identity:
            raise BudgetDenied('campaign manifest hash drift')
        self.bindings = copy.deepcopy(allowed_bindings) if self.manifest_mode else {'default': {key: self.identity[key] for key in HASH_FIELDS}}
        self.limits, self.clock = _limits(limits), clock or time.time
        self.binding = hashlib.sha256(_json(self.identity).encode()).hexdigest()
        self.config = {'identity': self.identity, 'limits': self.limits, 'binding_sha256': self.binding,
                       'allowed_bindings': self.bindings, 'manifest_mode': self.manifest_mode}
        self._replay_cache = None
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            mode = os.fstat(fd).st_mode
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600:
                raise BudgetDenied('ledger must be a private regular 0600 file')
        finally:
            os.close(fd)
        with closing(self._connect()) as connection:
            connection.execute('BEGIN IMMEDIATE')
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if tables - {'campaign_events'}:
                raise BudgetDenied('not a campaign-only database')
            if not tables:
                connection.execute('CREATE TABLE campaign_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, at_ms INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)')
                connection.execute("CREATE TRIGGER campaign_events_no_update BEFORE UPDATE ON campaign_events BEGIN SELECT RAISE(ABORT, 'append-only'); END")
                connection.execute("CREATE TRIGGER campaign_events_no_delete BEFORE DELETE ON campaign_events BEGIN SELECT RAISE(ABORT, 'append-only'); END")
                connection.execute('INSERT INTO campaign_events(at_ms,kind,payload) VALUES (?,?,?)',
                    (self._now(), 'init', _json(self.config)))
            checkpoint = {}
            self._load(connection, checkpoint=checkpoint)  # A new instance verifies the entire real ledger.
            connection.commit()
            self._replay_cache = checkpoint

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute('PRAGMA synchronous=FULL')
        return connection

    def _now(self):
        value = self.clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise BudgetDenied('invalid wall clock')
        return int(value * 1000)

    def _load(self, connection, *, checkpoint=None):
        """Replay the committed tail, still consulting SQLite on EVERY read.

        Callers hold a read/write transaction for a consistent prefix and adopt
        checkpoint only after commit. The append-only triggers protect verified
        history; init and the prior cursor row are also checked on every access.
        Like the ledger itself, this is not a defense against its filesystem owner
        removing SQL guards or replacing/deleting the database.
        """
        # Capture before establishing the read snapshot, never a newer prefix
        # published by another caller after that snapshot was established.
        cached = self._replay_cache
        first_row = connection.execute('SELECT seq,at_ms,kind,payload FROM campaign_events ORDER BY seq LIMIT 1').fetchone()
        if not first_row or first_row[2] != 'init':
            raise BudgetDenied('missing campaign initialization')
        first = json.loads(first_row[3])
        if first != self.config:
            raise BudgetDenied('campaign identity or limits drift')
        if cached is not None:
            anchor = connection.execute('SELECT seq,at_ms,kind,payload FROM campaign_events WHERE seq=?',
                (cached['last'][0],)).fetchone()
            if first_row != cached['first'] or anchor != cached['last']:
                raise BudgetDenied('verified ledger history drift')
            state, last = copy.deepcopy(cached['state']), cached['last']
        else:
            state = {'stage': None, 'stages': {}, 'batches': {}, 'jobs': {}, 'attempts': {}, 'reviews': {},
                     'live_deadline_ms': None, 'blocked': None, 'last_ms': first_row[1],
                     'effective_bindings': copy.deepcopy(self.bindings), 'candidate_revision': None}
            last = first_row
        rows = list(connection.execute('SELECT seq,at_ms,kind,payload FROM campaign_events WHERE seq>? ORDER BY seq', (last[0],)))
        for seq, at, kind, encoded in rows:
            item = json.loads(encoded)
            if item.get('binding_sha256') != self.binding or at < state['last_ms']:
                raise BudgetDenied('event identity or clock drift')
            state['last_ms'] = at
            if kind == 'stage_start':
                state['stage'] = item['stage']
                state['stages'][item['stage']] = 'open'
            elif kind == 'stage_pass': state['stages'][item['stage']] = 'passed'
            elif kind == 'batch_start':
                state['batches'][item['batch_id']] = {**item, 'started_ms': at, 'ended_ms': None}
                if state['live_deadline_ms'] is None: state['live_deadline_ms'] = item['live_deadline_ms']
            elif kind == 'batch_finish': state['batches'][item['batch_id']]['ended_ms'] = at
            elif kind == 'job_reserve': state['jobs'][item['job_id']] = {**item, 'status': 'active'}
            elif kind == 'job_finish':
                state['jobs'][item['job_id']]['status'] = item['status']
                if 'settlement_evidence_sha256' in item:
                    state['jobs'][item['job_id']]['settlement_evidence_sha256'] = item['settlement_evidence_sha256']
            elif kind == 'review_bind': state['reviews'][item['job_id']] = item['review_ref_sha256']
            elif kind == 'attempt_reserve':
                state['attempts'][item['attempt_id']] = {**item, 'actual_tokens': None, 'actual_cost_microusd': None,
                    'final_tokens': False, 'final_cost_microusd': False}
            elif kind == 'attempt_usage':
                attempt = state['attempts'][item['attempt_id']]
                for key in ('actual_tokens', 'actual_cost_microusd', 'cached_input_tokens'):
                    if item.get(key) is not None: attempt[key] = item[key]
                for key in ('tokens', 'cost_microusd'):
                    if item['usage_final'] and item.get('actual_' + key) is not None:
                        attempt['final_' + key] = True
            elif kind == 's1_candidate_revision':
                additions = self._candidate_revision_bindings(state, item['revisions'],
                    item['failed_job_id'], item['repair_evidence_sha256'], item.get('reviewed_quality_failure_sha256'))
                state['effective_bindings'].update(additions)
                state['candidate_revision'] = item
            elif kind == 'blocked': state['blocked'] = item['reason']
            elif kind != 'check': raise BudgetDenied('unknown ledger event')
        if checkpoint is not None:
            checkpoint.update({'first': first_row, 'last': rows[-1] if rows else last,
                               'state': copy.deepcopy(state)})
        return state

    def _append(self, connection, state, now, kind, payload):
        item = {'stage': state['stage'], **payload, 'binding_sha256': self.binding}
        connection.execute('INSERT INTO campaign_events(at_ms,kind,payload) VALUES (?,?,?)', (now, kind, _json(item)))

    def _block(self, connection, state, now, reason):
        if state['blocked'] is None:
            self._append(connection, state, max(now, state['last_ms']), 'blocked', {'reason': reason, 'observed_at_ms': now})
            state['blocked'] = reason

    def _guard(self, connection, state, now, cleanup):
        if now < state['last_ms']:
            self._block(connection, state, now, 'clock rollback')
            now = state['last_ms']
        deadlines = [state['live_deadline_ms']] + [row['deadline_ms'] for row in state['batches'].values() if row['ended_ms'] is None]
        deadlines += [row['deadline_ms'] for row in state['jobs'].values() if row['status'] == 'active']
        if any(deadline is not None and now >= deadline for deadline in deadlines):
            self._block(connection, state, now, 'deadline exceeded')
        if state['blocked'] and not cleanup:
            raise BudgetDenied(state['blocked'])
        return now

    def _mutate(self, action, *, cleanup=False):
        connection = self._connect()
        checkpoint = {}
        try:
            connection.execute('BEGIN IMMEDIATE')
            state = self._load(connection, checkpoint=checkpoint)
            now = self._guard(connection, state, self._now(), cleanup)
            # Even a capacity/identity denial has observed this wall clock.
            # Commit its watermark without consuming an unadmitted reservation.
            self._append(connection, state, now, 'check', {})
            result = action(connection, state, now)
            connection.commit()
            self._replay_cache = checkpoint
            return result
        except BudgetDenied:
            connection.commit()  # Durable overrun/rollback stop events must survive denial.
            if checkpoint: self._replay_cache = checkpoint
            raise
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _spent(self, state, stage=None):
        jobs = [row for row in state['jobs'].values() if stage is None or row['stage'] == stage]
        attempts = [row for row in state['attempts'].values() if stage is None or row['stage'] == stage]
        def charged(row, reserved, actual):
            observed = row.get(actual)
            return observed if row['final_' + reserved] and observed is not None else max(row[reserved], observed or 0)
        return {'jobs': len(jobs), 'transport': sum(row['transport'] for row in attempts),
                'http': sum(row['http'] for row in attempts),
                'tokens': sum(charged(row, 'tokens', 'actual_tokens') for row in attempts),
                'cost_microusd': sum(charged(row, 'cost_microusd', 'actual_cost_microusd') for row in attempts)}

    def _capacity(self, state, stage, addition):
        for scope in (stage, 'campaign'):
            spent = self._spent(state, None if scope == 'campaign' else scope)
            for key, value in addition.items():
                if key in self.limits[scope] and spent[key] + value > self.limits[scope][key]:
                    raise BudgetDenied(f'{scope} {key} budget exhausted')

    def start_stage(self, stage):
        def action(connection, state, now):
            if stage not in STAGES or stage in state['stages']:
                raise BudgetDenied('invalid or already started stage')
            index = STAGES.index(stage)
            if index and state['stages'].get(STAGES[index - 1]) != 'passed':
                raise BudgetDenied('previous stage has not passed')
            self._append(connection, state, now, 'stage_start', {'stage': stage})
        return self._mutate(action)

    def start_batch(self, batch_id, stage):
        _name(batch_id)
        def action(connection, state, now):
            if state['stage'] != stage or state['stages'].get(stage) != 'open':
                raise BudgetDenied('stage is not open')
            if batch_id in state['batches'] or any(row['ended_ms'] is None for row in state['batches'].values()):
                raise BudgetDenied('batch already exists or cleanup is pending')
            used = sum(row['ended_ms'] - row['started_ms'] for row in state['batches'].values() if row['stage'] == stage)
            remaining = self.limits[stage]['seconds'] * 1000 - used
            if remaining <= 0: raise BudgetDenied('stage wallclock budget exhausted')
            live = state['live_deadline_ms'] or now + self.limits['campaign']['live_seconds'] * 1000
            self._append(connection, state, now, 'batch_start', {'batch_id': batch_id, 'stage': stage,
                'deadline_ms': min(live, now + remaining), 'live_deadline_ms': live})
        return self._mutate(action)

    def reserve_job(self, job_id, batch_id, *, binding_id='default', actual_hashes=None):
        _name(job_id)
        _name(binding_id)
        def action(connection, state, now):
            expected = state['effective_bindings'].get(binding_id)
            implicit_initial = not self.manifest_mode and binding_id in self.bindings
            actual = expected if actual_hashes is None and implicit_initial else actual_hashes
            if expected is None or actual != expected:
                raise BudgetDenied('job actual hashes do not match campaign manifest')
            batch = state['batches'].get(batch_id)
            if not batch or batch['ended_ms'] is not None or job_id in state['jobs']:
                raise BudgetDenied('invalid batch or duplicate job')
            if sum(row['status'] == 'active' for row in state['jobs'].values()) >= self.limits['campaign']['active_jobs']:
                raise BudgetDenied('active jobs limit')
            self._capacity(state, batch['stage'], {'jobs': 1})
            self._append(connection, state, now, 'job_reserve', {'job_id': job_id, 'batch_id': batch_id,
                'stage': batch['stage'], 'binding_id': binding_id, 'actual_hashes': copy.deepcopy(actual),
                'deadline_ms': min(batch['deadline_ms'], now + self.limits['campaign']['job_seconds'] * 1000)})
        return self._mutate(action)

    def _candidate_revision_bindings(self, state, revisions, failed_job_id, repair_evidence_sha256,
                                     reviewed_quality_failure_sha256=None):
        _name(failed_job_id), _hash(repair_evidence_sha256)
        if state['blocked']:
            raise BudgetDenied(state['blocked'])
        if state['stage'] != 'S1' or state['stages'].get('S1') != 'open':
            raise BudgetDenied('candidate revision requires open S1')
        if state['candidate_revision'] is not None:
            raise BudgetDenied('candidate revision already registered')
        if any(row['status'] == 'active' for row in state['jobs'].values()):
            raise BudgetDenied('candidate revision requires no active jobs')
        if any(row['ended_ms'] is None for row in state['batches'].values()):
            raise BudgetDenied('candidate revision requires completed batch cleanup')
        failed = state['jobs'].get(failed_job_id)
        reviewed_failure = (reviewed_quality_failure_sha256 is not None
            and state['reviews'].get(failed_job_id) == _hash(reviewed_quality_failure_sha256))
        if not failed or failed['stage'] != 'S1' or not (failed['status'] == 'failed'
                or failed['status'] == 'completed' and reviewed_failure):
            raise BudgetDenied('candidate revision requires a terminal failed S1 job')
        if not isinstance(revisions, dict) or not revisions:
            raise BudgetDenied('nonempty candidate revision bindings required')
        additions, new_codes = {}, set()
        old_codes = {row['code_sha256'] for row in state['effective_bindings'].values()}
        for binding_id, row in revisions.items():
            _name(binding_id)
            if binding_id in state['effective_bindings']:
                raise BudgetDenied('candidate revision cannot overwrite binding IDs')
            if not isinstance(row, dict) or set(row) != {'parent_binding_id', *HASH_FIELDS}:
                raise BudgetDenied('complete candidate revision and parent hashes required')
            parent = state['effective_bindings'].get(_name(row['parent_binding_id']))
            if not parent or parent['code_sha256'] != failed['actual_hashes']['code_sha256']:
                raise BudgetDenied('parent code must match the failed S1 job')
            actual = {field: _hash(row[field]) for field in HASH_FIELDS}
            if any(actual[field] != parent[field] for field in ('source_sha256', 'route_sha256')):
                raise BudgetDenied('candidate revision cannot change parent source or route')
            if actual['code_sha256'] in old_codes:
                raise BudgetDenied('candidate revision requires a new code hash')
            new_codes.add(actual['code_sha256'])
            additions[binding_id] = actual
        if len(new_codes) != 1:
            raise BudgetDenied('candidate revision must use one new code hash')
        return additions

    def register_s1_candidate_revision(self, *, revisions, failed_job_id, repair_evidence_sha256,
                                        reviewed_quality_failure_sha256=None):
        """Append at most one repaired code version, preserving original manifest.

        revisions maps new IDs to parent_binding_id plus the three actual SHA
        fields. Parents must share the failed S1 job's code; each source/route
        must be unchanged. A completed private pipeline may fail quality only
        with its already-bound external review supplied; the controller checks
        that it is a genuine reviewed failure, not a successful report retry.
        Evidence verification remains the caller's duty.
        """
        revisions = copy.deepcopy(revisions)
        def action(connection, state, now):
            self._candidate_revision_bindings(state, revisions, failed_job_id, repair_evidence_sha256,
                                              reviewed_quality_failure_sha256)
            self._append(connection, state, now, 's1_candidate_revision', {
                'revisions': revisions, 'failed_job_id': failed_job_id,
                'repair_evidence_sha256': repair_evidence_sha256,
                'reviewed_quality_failure_sha256': reviewed_quality_failure_sha256})
        return self._mutate(action)

    def reserve_attempt(self, attempt_id, job_id, *, tokens, cost_microusd, billing_status,
                        billing_identity_sha256, reservation_basis_sha256, transport=1, http=1, actual_hashes=None):
        """One reservation can cover one transport AND its physical HTTP once.

        The two counters are independent; tokens/cost are charged only once per
        HTTP event. A transport-only event (http=0) requires zero tokens/cost but
        still verified billing identity and basis. A physical HTTP event requires
        positive tokens and paid cost reservation. Each SDK retry/tool continuation needs its own new attempt_id and
        conservative reservation. Preflight/cancelled reservations do not refund
        those hard counters, so they are not proof of delivered HTTP requests.
        """
        _name(attempt_id)
        _integer(tokens), _integer(cost_microusd), _integer(transport), _integer(http)
        _hash(billing_identity_sha256), _hash(reservation_basis_sha256)
        if billing_status not in ('verified_paid', 'verified_free') or not transport + http:
            raise BudgetDenied('verified billing and explicit attempt reservation required')
        if http == 0 and (tokens or cost_microusd):
            raise BudgetDenied('transport-only reservation cannot include provider usage')
        if http and (not tokens or (billing_status == 'verified_paid' and not cost_microusd)):
            raise BudgetDenied('HTTP requires conservative token and paid cost reservation')
        if billing_status == 'verified_free' and cost_microusd:
            raise BudgetDenied('billing reservation contradicts verified identity')
        def action(connection, state, now):
            job = state['jobs'].get(job_id)
            if not job or job['status'] != 'active' or attempt_id in state['attempts']:
                raise BudgetDenied('inactive job or duplicate attempt')
            implicit_initial = not self.manifest_mode and job['binding_id'] in self.bindings
            actual = job['actual_hashes'] if actual_hashes is None and implicit_initial else actual_hashes
            if actual != job['actual_hashes']:
                raise BudgetDenied('attempt actual hashes do not match reserved job')
            addition = {'tokens': tokens, 'cost_microusd': cost_microusd, 'transport': transport, 'http': http}
            self._capacity(state, job['stage'], addition)
            self._append(connection, state, now, 'attempt_reserve', {'attempt_id': attempt_id, 'job_id': job_id,
                'stage': job['stage'], 'binding_id': job['binding_id'], 'actual_hashes': copy.deepcopy(actual),
                **addition, 'billing_status': billing_status,
                'billing_identity_sha256': billing_identity_sha256, 'reservation_basis_sha256': reservation_basis_sha256})
        return self._mutate(action)

    def settle_attempt(self, attempt_id, *, actual_tokens=None, actual_cost_microusd=None,
                       cached_input_tokens=None, usage_evidence_sha256=None, usage_final=False):
        """Actual total already includes cached input: that diagnostic is NEVER added.

        Partial/missing usage retains max(reserved, observed). Only explicitly
        provided final quantities may reconcile their reservations downward. A
        final cost does not promote an earlier partial token count to final. The
        caller must verify finality; an evidence hash alone is not that proof.
        Observations are cumulative and never regress; final values are immutable.
        Any actual value above its conservative reservation stops further work.
        """
        values = {'actual_tokens': actual_tokens, 'actual_cost_microusd': actual_cost_microusd,
                  'cached_input_tokens': cached_input_tokens}
        if type(usage_final) is not bool: raise BudgetDenied('usage finality must be explicit boolean')
        for value in values.values():
            if value is not None: _integer(value)
        if usage_final or any(value is not None for value in values.values()): _hash(usage_evidence_sha256)
        def action(connection, state, now):
            attempt = state['attempts'].get(attempt_id)
            if not attempt: raise BudgetDenied('unknown attempt')
            def frozen(key):
                return attempt['final_cost_microusd' if key == 'actual_cost_microusd' else 'final_tokens']
            if any(value is not None and attempt.get(key) is not None and
                   (value != attempt[key] if frozen(key) else value < attempt[key]) for key, value in values.items()):
                raise BudgetDenied('observed usage is immutable')
            self._append(connection, state, now, 'attempt_usage', {'attempt_id': attempt_id, 'stage': attempt['stage'],
                **values, 'usage_final': usage_final, 'usage_evidence_sha256': usage_evidence_sha256})
            if (actual_tokens is not None and actual_tokens > attempt['tokens']
                    or actual_cost_microusd is not None and actual_cost_microusd > attempt['cost_microusd']):
                self._block(connection, state, now, 'actual usage exceeded conservative reservation')
        return self._mutate(action, cleanup=True)

    def finish_job(self, job_id, *, status, expected_job=None, settlement_evidence_sha256=None):
        """Abandonment is explicit; it closes a crash-held slot, never refunds."""
        if status not in ('completed', 'failed', 'cancelled', 'abandoned'):
            raise BudgetDenied('explicit terminal job status required')
        if (expected_job is None) != (settlement_evidence_sha256 is None):
            raise BudgetDenied('original reservation and settlement evidence required together')
        if expected_job is not None:
            if type(expected_job) is not dict or expected_job.get('job_id') != job_id or expected_job.get('status') != 'active':
                raise BudgetDenied('original active reservation required')
            _hash(settlement_evidence_sha256)
            expected_job = copy.deepcopy(expected_job)
        def action(connection, state, now):
            job = state['jobs'].get(job_id)
            if not job or job['status'] != 'active': raise BudgetDenied('job is not active')
            if expected_job is not None and job != expected_job:
                raise BudgetDenied('original reservation changed before settlement')
            evidence = {} if expected_job is None else {'settlement_evidence_sha256': settlement_evidence_sha256}
            self._append(connection, state, now, 'job_finish', {'job_id': job_id, 'stage': job['stage'], 'status': status, **evidence})
        return self._mutate(action, cleanup=True)

    def finish_batch(self, batch_id, *, cleanup_evidence_sha256):
        _hash(cleanup_evidence_sha256)
        def action(connection, state, now):
            batch = state['batches'].get(batch_id)
            if not batch or batch['ended_ms'] is not None: raise BudgetDenied('batch is not active')
            if any(row['batch_id'] == batch_id and row['status'] == 'active' for row in state['jobs'].values()):
                raise BudgetDenied('active jobs still require explicit cleanup')
            self._append(connection, state, now, 'batch_finish', {'batch_id': batch_id, 'stage': batch['stage'],
                'elapsed_ms': now - batch['started_ms'], 'cleanup_evidence_sha256': cleanup_evidence_sha256})
        return self._mutate(action, cleanup=True)

    def pass_stage(self, stage, *, acceptance_evidence_sha256):
        """The caller supplies independently verified acceptance, not this ledger."""
        _hash(acceptance_evidence_sha256)
        def action(connection, state, now):
            if state['stage'] != stage or state['stages'].get(stage) != 'open': raise BudgetDenied('stage is not open')
            if not any(row['stage'] == stage for row in state['jobs'].values()): raise BudgetDenied('stage has no jobs')
            if any(row['ended_ms'] is None for row in state['batches'].values()): raise BudgetDenied('batch cleanup is pending')
            self._append(connection, state, now, 'stage_pass', {'stage': stage, 'acceptance_evidence_sha256': acceptance_evidence_sha256})
        return self._mutate(action)

    def check(self):
        """Cooperative watchdog seam; does not terminate external processes."""
        return self._mutate(lambda connection, state, now: None)

    def stop(self, reason, *, evidence_sha256):
        """Persist a coordinator content/safety stop; retain cleanup and usage.

        A verified review/receipt is the coordinator's responsibility. Only a
        short stable reason code is stored, never report text or credentials.
        Existing stop causes are immutable; this cannot restart any campaign.
        """
        _name(reason), _hash(evidence_sha256)
        def action(connection, state, now):
            if state['blocked'] is None:
                self._append(connection, state, now, 'blocked', {'reason': reason,
                    'observed_at_ms': now, 'evidence_sha256': evidence_sha256})
        return self._mutate(action, cleanup=True)

    def bind_review(self, job_id, *, review_ref_sha256):
        """Bind one terminal job's exact external review reference, never replace.

        This stores identity only. The coordinator verifies content and durable
        reference bytes before binding; missing crash receipts do not auto-reset.
        """
        _name(job_id), _hash(review_ref_sha256)
        def action(connection, state, now):
            job = state['jobs'].get(job_id)
            if not job or job['status'] == 'active' or job_id in state['reviews']:
                raise BudgetDenied('review requires terminal unreviewed job')
            self._append(connection, state, now, 'review_bind', {'job_id': job_id,
                'stage': job['stage'], 'review_ref_sha256': review_ref_sha256})
        return self._mutate(action, cleanup=True)

    def snapshot(self):
        with closing(self._connect()) as connection:
            connection.execute('BEGIN')
            checkpoint = {}
            state = self._load(connection, checkpoint=checkpoint)
            connection.commit()
            self._replay_cache = checkpoint
        return {**state, 'spent': self._spent(state),
                'stage_spent': {stage: self._spent(state, stage) for stage in STAGES}}

    def events(self):
        with closing(self._connect()) as connection:
            connection.execute('BEGIN')
            checkpoint = {}
            self._load(connection, checkpoint=checkpoint)
            result = [{'seq': seq, 'at_ms': at, 'kind': kind, 'payload': json.loads(payload)}
                    for seq, at, kind, payload in connection.execute('SELECT seq,at_ms,kind,payload FROM campaign_events ORDER BY seq')]
            connection.commit()
            self._replay_cache = checkpoint
            return result
