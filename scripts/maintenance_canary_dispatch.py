"""Original-owner dispatch for one claimed, already-reserved normal canary.

Caller owns exclusive queue authority, qualified FrozenJob/ledger, and maintenance
phase approval. No source/billing review, budget initialization/refund,
stage promotion, descendant cleanup, formal endpoint or release is provided.
An attempt is never resumed. Retain this object/OwnedProcess until exit; closing
FDs or sending admission is not successful execution or permission to hand over.
"""
import copy
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import threading
import time

if globals().get('_CONTROL_BUNDLE') is None:
    raise RuntimeError('Fresh bound controls required; use maintenance_entry.load_control_bundle')

import canary_release_policy

# A dedicated fresh controller must not inherit arbitrary/stale test modules.
# Compile these exact source buffers (never timestamp pyc); do not expose the
# tests directory as an SDK/stdlib search path or read application credentials.
_ROOT = Path(__file__).resolve().parents[1]
_HARNESS = ('quality_campaign_runner', 'quality_campaign_budget', 'quality_campaign_wire',
            'quality_campaign_transport', 'quality_campaign_watchdog', 'quality_campaign_safety',
            'quality_campaign_graph')
if any(name in sys.modules for name in _HARNESS):
    raise RuntimeError('Fresh controller with unloaded campaign harness required')


def _source(name):
    path = _ROOT / 'tests' / (name + '.py')
    if path.resolve() != path: raise RuntimeError('Nonsymlink campaign harness required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 2 * 1024 * 1024:
            raise RuntimeError('Bounded regular campaign harness required')
        chunks, size = [], 0
        while part := os.read(fd, 2 * 1024 * 1024 + 1 - size):
            chunks.append(part)
            size += len(part)
            if size > 2 * 1024 * 1024: raise RuntimeError('Campaign harness grew beyond bound')
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
            value.st_gid, value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        # Reading may update atime; it is not a code mutation.
        if (identity(os.fstat(fd)) != identity(info)
                or identity(path.stat(follow_symlinks=False)) != identity(info) or size != info.st_size):
            raise RuntimeError('Campaign harness changed during load')
        return b''.join(chunks)
    finally:
        os.close(fd)


_SOURCES = _CONTROL_BUNDLE.harness_sources()
if set(_SOURCES) != set(_HARNESS):
    raise RuntimeError('Exact captured campaign harness required')


class _HarnessSources:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _SOURCES:
            return importlib.util.spec_from_file_location(fullname, _ROOT / 'tests' / (fullname + '.py'), loader=self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(_SOURCES[module.__name__], module.__file__, 'exec'), module.__dict__)


_finder = _HarnessSources()
sys.meta_path.insert(0, _finder)
try:
    for _name in _HARNESS:
        importlib.import_module(_name)
    import quality_campaign_runner as runner
    from quality_campaign_budget import CampaignBudget
finally:
    sys.meta_path.remove(_finder)
_LOADED = {name: sys.modules.get(name) for name in _HARNESS}


def _verify_harness():
    try:
        source_drift = any(_source(name) != source for name, source in _SOURCES.items())
    except (OSError, RuntimeError):
        raise runner.ReplayAbort('Loaded campaign harness source drift') from None
    if (set(runner.HARNESS) != {name + '.py' for name in _HARNESS}
            or any(sys.modules.get(name) is not module for name, module in _LOADED.items())
            or source_drift):
        raise runner.ReplayAbort('Loaded campaign harness identity or source drift')


_verify_harness()
from maintenance_entry import control_digest  # Loads only state/guard, no app startup.
from maintenance_canary_claim import checked_analysis_claim
from maintenance_canary_settlement import settle_claimed_analysis, _read, _completion
from maintenance_owned_process import OwnedProcess, OwnedProcessSupervisor, _binding, admission_pipe_identity


class ClaimedCanaryDispatch:
    def __init__(self, plan, ledger, *, queue_name, registered_hashes, remaining,
                 analysis_bindings, claimed, process_binding):
        canary_release_policy.require_canary_enabled()
        if type(plan) is not runner.FrozenJob or type(ledger) is not CampaignBudget:
            raise runner.ReplayAbort('Original frozen job and campaign ledger required')
        pins, order, bindings, digest = checked_analysis_claim(queue_name=queue_name,
            registered_hashes=registered_hashes, remaining=remaining, analysis_bindings=analysis_bindings, claimed=claimed)
        self._values = {'queue_name': queue_name, 'registered_hashes': pins,
                        'remaining': order, 'analysis_bindings': bindings}
        self._binding = bindings[order[0]]
        bound = self._binding
        self._claimed = {'outcome': 'claimed', 'analysis_semantics_verified': True, 'job_id': order[0],
            'raw_snapshot': dict(pins[order[0]]), 'enrollment_sha256': digest,
            'analysis_invocation': {'function': 'analysis_jobs.run_stock_analysis_job',
                'args': [bound['job_id'], bound['ticker'], bound['pipeline_id']],
                'kwargs': {'force_refresh': False}, **bound}}
        self._process_binding = _binding(process_binding)
        self._plan, self._ledger = plan, ledger
        self._job_id = self._binding['job_id']
        self._output = ledger.path.parent / self._job_id
        self._owner_pid = os.getpid()
        self._lock = threading.Lock()
        self._attempted = self._settlement_attempted = False
        self._owner = None
        self._supervisor = self._deadline = None
        self._authorization = self._original_job = self._pin = None
        self._preflight()

    @property
    def process_owner(self):
        return self._owner

    @contextmanager
    def _operation(self):
        if os.getpid() != self._owner_pid or not self._lock.acquire(blocking=False):
            raise runner.ReplayAbort('Original non-reentrant dispatcher required')
        try:
            yield
        finally:
            self._lock.release()

    def _verify_controls(self):
        try:
            proof = _CONTROL_BUNDLE.verify()
        except RuntimeError as error:
            raise runner.ReplayAbort('Loaded controller source or module drift') from error
        if proof['control_sha256'] != self._process_binding['control_sha256']:
            raise runner.ReplayAbort('Approved loaded controller digest mismatch')

    def _preflight(self, *, cleanup_only=False):
        self._verify_controls()
        _verify_harness()
        if os.getpid() != self._owner_pid or control_digest() != self._process_binding['control_sha256']:
            raise runner.ReplayAbort('Original controller and pinned control implementation required')
        if cleanup_only:
            # Expiry/blocked state must not authorize new work, but may close
            # this exact exited job. No ledger check/write or provider call.
            hashes = self._plan.verify()
            if (runner.ledger_pin(self._ledger) != self._pin
                    or self._ledger.snapshot()['jobs'].get(self._job_id) != self._original_job):
                raise runner.ReplayAbort('Original cleanup reservation changed')
        else:
            hashes = runner.check_reserved(self._plan, self._ledger, self._job_id)
        row, bound = self._plan.manifest, self._binding
        if self._ledger.limits['campaign']['job_seconds'] > bound['timeout_seconds']:
            raise runner.ReplayAbort('Campaign reservation exceeds registered RQ timeout')
        if (row['campaign_id'] != bound['campaign_id'] or row['mode'] != bound['pipeline_id']
                or self._plan.expected_sha != bound['manifest_sha256']
                or self._plan.source_job()['data_snapshot']['ticker'] != bound['ticker']):
            raise runner.ReplayAbort('Claim does not match the reserved frozen normal job')
        return hashes

    def start(self):
        canary_release_policy.require_canary_enabled()
        with self._operation():
            return self._start()

    def _runtime_code_identity(self, code_sha256):
        # Capture truthful Git provenance outside the no-spawn child. Never
        # trust an inherited GIT_COMMIT/GIT_DIRTY or let global fsmonitor run.
        root = self._plan.manifest['dev']
        environment = {'PATH': '/opt/homebrew/bin:/usr/bin:/bin', 'LANG': 'C',
            'GIT_OPTIONAL_LOCKS': '0', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
        def read(*args):
            result = subprocess.run(['git', '-C', root, '-c', 'core.fsmonitor=false', *args],
                env=environment, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=5, check=False)
            if result.returncode != 0 or len(result.stdout) > 1024 * 1024:
                raise runner.ReplayAbort('Original runtime Git identity unavailable')
            return result.stdout
        commit = read('rev-parse', 'HEAD').decode('ascii').strip()
        if commit != self._process_binding['backend_revision']:
            raise runner.ReplayAbort('Runtime Git revision differs from original process binding')
        return {'commit': commit, 'dirty': bool(read('status', '--porcelain=v1', '--untracked-files=normal')),
                'code_sha256': code_sha256}

    def _start(self):
        canary_release_policy.require_canary_enabled()
        if self._attempted: raise runner.ReplayAbort('Never relaunch a canary dispatch attempt')
        self._attempted = True
        hashes = self._preflight()
        self._pin = runner.ledger_pin(self._ledger)
        self._original_job = copy.deepcopy(self._ledger.snapshot()['jobs'][self._job_id])
        code_identity = self._runtime_code_identity(hashes['code_sha256'])
        # Sample monotonic first: time spent reading wall time cannot extend
        # the already-reserved deadline. Do not grant a new job-sized window.
        sampled_monotonic = time.monotonic()
        remaining_seconds = self._original_job['deadline_ms'] / 1000 - time.time()
        if not 0 < remaining_seconds <= self._ledger.limits['campaign']['job_seconds']:
            raise runner.ReplayAbort('Original reservation deadline unavailable')
        self._deadline = sampled_monotonic + remaining_seconds
        # Exclusive name retains an ambiguous/failed attempt; never remove it.
        self._output.mkdir(mode=0o700)
        namespace = self._output / 'process-owner'
        namespace.mkdir(mode=0o700)
        self._owner = OwnedProcess(namespace, self._process_binding)
        reader, writer = os.pipe()
        try:
            pipe_identity = admission_pipe_identity(reader)
            intent = {'schema': 'maintenance.canary-launch.v1', 'job_id': self._job_id,
                'output': str(self._output), 'manifest_sha256': self._plan.expected_sha,
                'parent_pid': self._owner_pid, 'process_binding': self._process_binding,
                'ledger_pin_sha256': runner.sha(runner.encoded(self._pin)),
                'queue_name': self._values['queue_name'], 'task_id': self._values['remaining'][0],
                'enrollment_sha256': self._claimed['enrollment_sha256'],
                'timeout_seconds': self._binding['timeout_seconds'],
                'owned_session': True, 'deadline_monotonic': self._deadline,
                'runtime_code_identity': code_identity,
                'reservation': {'job_id': self._job_id, 'ledger_binding_sha256': self._ledger.binding,
                    'deadline_ms': self._original_job['deadline_ms'], 'actual_hashes': self._original_job['actual_hashes']}}
            intent_sha = runner.exclusive_json(self._output / 'dispatch-intent.json', intent)
            ticket = {'manifest_path': str(self._plan.path), 'manifest_sha256': self._plan.expected_sha,
                'ledger_pin': self._pin, 'job_id': self._job_id, 'output': str(self._output),
                'maintenance_admission': {'schema': 'maintenance.owned-admission.v1',
                    'intent_sha256': intent_sha, 'parent_pid': self._owner_pid,
                    'pipe_identity': pipe_identity, 'process_binding': self._process_binding}}
            ticket_path = self._output / 'child-ticket.json'
            ticket_sha = runner.exclusive_json(ticket_path, ticket)
            self._preflight()
            if self._ledger.snapshot()['jobs'][self._job_id] != self._original_job:
                raise runner.ReplayAbort('Reservation changed before owned launch')
            self._owner.start([sys.executable, '-I', '-B', str(Path(runner.__file__).resolve()),
                '--owned-job', str(ticket_path), '--owned-admission-fd', str(reader)],
                env={'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONDONTWRITEBYTECODE': '1'},
                cwd=self._output, admission_fd=reader, owned_session=True)
            self._supervisor = OwnedProcessSupervisor(self._owner, deadline_monotonic=self._deadline)
            os.close(reader)
            reader = None
            state = self._supervisor.snapshot()
            if (state['phase'] != 'running' or state['binding'] != self._process_binding
                    or state['owner_pid'] != self._owner_pid or state['admission_pipe_identity'] != pipe_identity):
                raise runner.ReplayAbort('Original owned launch is unconfirmed')
            self._ledger.check()
            self._verify_controls()
            _verify_harness()
            if (self._ledger.snapshot()['jobs'][self._job_id] != self._original_job
                    or runner.ledger_pin(self._ledger) != self._pin
                    or control_digest() != self._process_binding['control_sha256']
                    or runner.sha(_read(ticket_path)) != ticket_sha
                    or runner.sha(_read(self._output / 'dispatch-intent.json')) != intent_sha):
                raise runner.ReplayAbort('Launch evidence changed before child admission')
            self._admission_active()
            authorization = {'schema': 'maintenance.owned-admission.v1', 'parent_pid': self._owner_pid,
                'child_pid': state['pid'], 'pipe_identity': pipe_identity, 'ticket_sha256': ticket_sha,
                'intent_sha256': intent_sha, 'started_journal_sha256': state['started_journal_sha256']}
            raw = runner.encoded(authorization)
            if len(raw) > 8192: raise runner.ReplayAbort('Admission message exceeded bound')
            os.set_blocking(writer, False)
            deadline, remaining = time.monotonic() + 2, memoryview(raw)
            while remaining:
                self._admission_active()
                left = deadline - time.monotonic()
                if left <= 0 or not select.select([], [writer], [], left)[1]:
                    raise runner.ReplayAbort('Child admission delivery timed out')
                written = os.write(writer, remaining)
                if not written: raise runner.ReplayAbort('Child admission delivery incomplete')
                remaining = remaining[written:]
            self._authorization = raw
            return {**state, 'admission_sent': True, 'application_cleanup_verified': False}
        finally:
            if reader is not None: os.close(reader)
            os.close(writer)  # EOF is required; failure is never old-claim fallback.

    def wait_for_exit(self, seconds):
        if self._owner is None: raise runner.ReplayAbort('No original process to observe')
        return (self._supervisor or self._owner).wait_for_exit(seconds)

    def request_stop(self):
        if self._owner is None: raise runner.ReplayAbort('No original process to stop')
        return (self._supervisor or self._owner).request_stop()

    def _admission_active(self):
        state = self._supervisor.snapshot()
        if (state['stop_reason'] is not None or state['supervision_complete']
                or time.monotonic() >= self._deadline):
            self._supervisor.request_stop()
            raise runner.ReplayAbort('Original supervision stopped before child admission')

    def settle(self, connection):
        with self._operation():
            return self._settle(connection)

    def _settle(self, connection):
        if self._settlement_attempted: raise runner.ReplayAbort('Never replay canary settlement')
        self._settlement_attempted = True
        self._preflight(cleanup_only=True)
        if self._supervisor is None:
            raise runner.ReplayAbort('Original process supervision required')
        supervised = self._supervisor.wait_for_exit(0)
        if (not supervised['supervision_complete'] or not supervised['process_group_absence_verified']
                or supervised['stop_reason'] is not None and not supervised['stop_requested']):
            raise runner.ReplayAbort('Original process supervision or group exit unconfirmed')
        if (self._authorization is None or self._owner is None
                or _read(self._output / 'maintenance-admission.json') != self._authorization
                or runner.ledger_pin(self._ledger) != self._pin
                or self._ledger.snapshot()['jobs'][self._job_id] != self._original_job):
            raise runner.ReplayAbort('Original child admission or reservation readback missing')
        admission = runner.read_json(self._authorization)
        if (runner.sha(_read(self._output / 'child-ticket.json')) != admission['ticket_sha256']
                or runner.sha(_read(self._output / 'dispatch-intent.json')) != admission['intent_sha256']):
            raise runner.ReplayAbort('Original admission ticket or intent changed')
        proof = _completion(self._owner, self._process_binding, self._output, self._binding)
        intent = {'schema': 'maintenance.canary-settlement-attempt.v1', 'job_id': self._job_id,
            'manifest_sha256': self._plan.expected_sha, 'process_binding': self._process_binding,
            'ledger_pin_sha256': runner.sha(runner.encoded(self._pin)), 'original_job': self._original_job,
            'completion_sha256': runner.sha(runner.encoded(proof)),
            'stop_reason': supervised['stop_reason'], 'deadline_monotonic': self._deadline}
        intent_sha = runner.exclusive_json(self._output / 'settlement-attempt.json', intent)
        result = settle_claimed_analysis(connection, **self._values, claimed=self._claimed,
            process=self._owner, process_binding=self._process_binding, output_dir=self._output)
        result = {**result, 'budget_job_settled': False}
        if result.get('outcome') != 'settled': return result
        # Only an ACK observed by this original caller can enter the next step.
        # This is a sequenced saga, not a Redis/SQLite atomic transaction. A
        # lost reply/file write leaves unknown state, never retry/refund/adopt.
        try:
            self._preflight(cleanup_only=True)
            if _completion(self._owner, self._process_binding, self._output, self._binding) != proof:
                raise runner.ReplayAbort('Completion changed after RQ acknowledgement')
            if runner.sha(_read(self._output / 'settlement-attempt.json')) != intent_sha:
                raise runner.ReplayAbort('Settlement attempt changed')
            before = self._ledger.snapshot()
            attempts = {key: row for key, row in before['attempts'].items() if row['job_id'] == self._job_id}
            status = ('cancelled' if supervised['stop_reason'] == 'cancelled' else
                      'completed' if result['terminal_status'] == 'finished' else 'failed')
            ack = {'schema': 'maintenance.canary-rq-ack.v1', 'attempt_sha256': intent_sha,
                   'rq_result': result, 'budget_status': status}
            ack_path = self._output / 'rq-settlement-ack.json'
            ack_sha = runner.exclusive_json(ack_path, ack)
            if (runner.sha(_read(ack_path)) != ack_sha
                    or _completion(self._owner, self._process_binding, self._output, self._binding) != proof):
                raise runner.ReplayAbort('RQ acknowledgement or cleanup changed before budget settlement')
            self._ledger.finish_job(self._job_id, status=status, expected_job=self._original_job,
                                    settlement_evidence_sha256=ack_sha)
            after = self._ledger.snapshot()
            expected_job = {**self._original_job, 'status': status, 'settlement_evidence_sha256': ack_sha}
            if (runner.ledger_pin(self._ledger) != self._pin or after['jobs'].get(self._job_id) != expected_job
                    or {key: row for key, row in after['attempts'].items() if row['job_id'] == self._job_id} != attempts
                    or runner.sha(_read(ack_path)) != ack_sha
                    or _completion(self._owner, self._process_binding, self._output, self._binding) != proof):
                raise runner.ReplayAbort('Budget settlement readback unconfirmed')
            receipt = {**result, 'budget_job_settled': True, 'budget_status': status,
                       'budget_evidence_sha256': ack_sha, 'stop_required': result['stop_required'] or bool(after['blocked'])}
            receipt_path = self._output / 'budget-job-settled.json'
            receipt_sha = runner.exclusive_json(receipt_path, receipt)
            if runner.sha(_read(receipt_path)) != receipt_sha:
                raise runner.ReplayAbort('Budget settlement receipt changed')
            return receipt
        except BaseException as error:
            return {**result, 'outcome': 'uncertain', 'stop_required': True,
                    'cancellation_requested': not isinstance(error, Exception),
                    'reason': 'budget_settlement_unconfirmed'}
