"""Execute one previously reserved frozen job, never initialize/reset a campaign.

This is an application-layer launcher, not billing/source certification or an
OS sandbox. A human-reviewed manifest and existing pinned ledger are required.
Stage acceptance and release remain separate; this module never passes stages,
closes batches, qualifies reports, or automatically adopts candidate addenda.
Imports are inert. Only the owned child entry reads the explicit credential file.
"""
import argparse
import asyncio
import copy
from contextlib import closing, contextmanager
import fcntl
import hashlib
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import re
import select
import signal
import sqlite3
import stat
import sys
import threading
import time

if __name__ == '__main__':
    # Do not undo -I by exposing every sibling file as an SDK/stdlib import.
    # Only the exact reviewed support modules are loadable from this directory.
    from importlib.util import spec_from_file_location
    class _HarnessImports:
        names = {'quality_campaign_budget', 'quality_campaign_wire', 'quality_campaign_transport',
                 'quality_campaign_watchdog', 'quality_campaign_safety', 'quality_campaign_graph'}
        def find_spec(self, fullname, path=None, target=None):
            if fullname == 'canary_release_policy':
                return spec_from_file_location(fullname, Path(__file__).resolve().parents[1] / 'backend' / 'canary_release_policy.py')
            if fullname in self.names:
                return spec_from_file_location(fullname, Path(__file__).resolve().with_name(fullname + '.py'))
            return None
    sys.meta_path.insert(0, _HarnessImports())

from quality_campaign_budget import BudgetDenied, CampaignBudget
from quality_campaign_watchdog import CleanupUnconfirmed, run_reserved_process
from quality_campaign_wire import ReplayAbort, unique_object
import canary_release_policy

REFERENCES = ('source', 'routes', 'environment', 'billing_review',
              'reservation_review', 'source_review', 'policies')
HARNESS = ('quality_campaign_budget.py', 'quality_campaign_wire.py',
           'quality_campaign_transport.py', 'quality_campaign_watchdog.py',
           'quality_campaign_safety.py', 'quality_campaign_graph.py', 'quality_campaign_runner.py')
EXTENSIONS = {'.py', '.json', '.yaml', '.yml', '.html', '.css', '.js', '.txt', '.md',
              '.j2', '.lock', '.svg', '.png', '.ico', '.woff', '.woff2'}
IGNORED = {'cache', 'output', '__pycache__', 'node_modules', '.venv'}
RUNTIME_PACKAGES = ('google-genai', 'httpx', 'httpcore', 'pydantic', 'pydantic-core',
                    'langgraph', 'langgraph-checkpoint', 'langgraph-checkpoint-sqlite',
                    'langchain-core', 'aiosqlite', 'jinja2', 'tenacity', 'redis')
RUNTIME_ROOTS = {'google-genai': ('google/genai',),
                 'langgraph-checkpoint': ('langgraph/checkpoint', 'langgraph/cache/base',
                     'langgraph/cache/memory', 'langgraph/cache/redis', 'langgraph/store/base', 'langgraph/store/memory'),
                 'langgraph-checkpoint-sqlite': ('langgraph/checkpoint/sqlite', 'langgraph/cache/sqlite',
                     'langgraph/store/sqlite')}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def regular_bytes(value, *, limit=64 * 1024 * 1024):
    path = Path(value)
    if not path.is_absolute() or path.resolve() != path:
        raise ReplayAbort('Absolute nonsymlink frozen file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ReplayAbort('Bounded regular frozen file required')
        chunks, length = [], 0
        while chunk := os.read(fd, min(65536, limit + 1 - length)):
            chunks.append(chunk)
            length += len(chunk)
            if length > limit:
                raise ReplayAbort('Frozen file grew beyond read limit')
        return b''.join(chunks)
    finally:
        os.close(fd)


def read_json(raw):
    try:
        result = json.loads(raw, object_pairs_hook=unique_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(result, dict): raise ValueError()
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise ReplayAbort('Unambiguous finite JSON object required') from None


def code_inventory(dev):
    root = Path(dev)
    if not root.is_absolute() or root.resolve() != root or not (root / 'backend').is_dir():
        raise ReplayAbort('Explicit real backend checkout required')
    if (root / 'backend' / '.env').exists() or (root / 'backend' / '.env').is_symlink():
        raise ReplayAbort('Frozen checkout must not auto-load backend/.env')
    result = {}
    for path in sorted((root / 'backend').rglob('*')):
        relative = path.relative_to(root)
        if IGNORED.intersection(relative.parts): continue
        if path.is_symlink(): raise ReplayAbort('Frozen backend symlink forbidden')
        if path.is_file() and path.suffix in EXTENSIONS:
            result[str(relative)] = sha(regular_bytes(path))
    if not result: raise ReplayAbort('Empty backend inventory')
    return result


def harness_inventory():
    root = Path(__file__).resolve().parent
    return {name: sha(regular_bytes(root / name)) for name in HARNESS}


def runtime_inventory():
    """Read actual critical dependency bytes, not only a distribution version.

    This binds the installed SDK/transport/graph/renderer path used in this
    process. It is not a full transitive OS/library or dependency security audit.
    """
    executable = Path(sys.executable).resolve(strict=True)
    result = {'python': {'version': sys.version, 'executable': str(executable),
                         'sha256': sha(regular_bytes(executable))}, 'packages': {}}
    for name in RUNTIME_PACKAGES:
        distribution = metadata.distribution(name)
        install_root = Path(distribution.locate_file(''))
        if not install_root.is_absolute() or install_root.resolve() != install_root:
            raise ReplayAbort('Real runtime installation root required')
        roots = tuple(Path(value) for value in RUNTIME_ROOTS.get(name, (name.replace('-', '_'),)))
        files, code_files = {}, set()
        for relative in distribution.files or []:
            relative = Path(relative)
            if relative.suffix not in ('.py', '.so', '.dylib') and relative.name not in ('METADATA', 'RECORD'):
                continue
            if relative.is_absolute() or '..' in relative.parts:
                raise ReplayAbort('Runtime RECORD path escapes its distribution root')
            path = Path(distribution.locate_file(relative))
            if not path.is_relative_to(install_root) or path.resolve() != path:
                raise ReplayAbort('Runtime RECORD target escapes its distribution root')
            is_code = relative.suffix in ('.py', '.so', '.dylib') and any(relative.is_relative_to(root) for root in roots)
            if not is_code and not (len(relative.parts) == 2 and relative.parts[0].endswith('.dist-info')
                                    and relative.name in ('METADATA', 'RECORD')):
                raise ReplayAbort('Runtime RECORD targets a file outside the reviewed package')
            files[str(relative)] = {'path': str(path), 'sha256': sha(regular_bytes(path))}
            if is_code: code_files.add(str(relative))
        # RECORD is not an authority to omit newly added importable code. Scan
        # only these fixed package roots, never the entire site-packages tree.
        for relative_root in roots:
            root = install_root / relative_root
            if not root.is_dir() or root.resolve() != root:
                raise ReplayAbort('Reviewed runtime package root missing or linked')
            for path in sorted(root.rglob('*')):
                if path.is_symlink(): raise ReplayAbort('Linked runtime package entry forbidden')
                if path.is_file() and path.suffix in ('.py', '.so', '.dylib'):
                    relative = str(path.relative_to(install_root))
                    code_files.add(relative)
                    if relative not in files:
                        files[relative] = {'path': str(path), 'sha256': sha(regular_bytes(path))}
        if not code_files: raise ReplayAbort('Critical runtime dependency code inventory missing')
        result['packages'][name] = {'version': distribution.version, 'files': files}
    return result


class FrozenJob:
    def __init__(self, path, expected_sha):
        self.path, self.expected_sha = Path(path), expected_sha
        raw = regular_bytes(self.path)
        if sha(raw) != expected_sha: raise ReplayAbort('Frozen manifest digest mismatch')
        self._manifest = read_json(raw)

    @property
    def manifest(self):
        return copy.deepcopy(self._manifest)

    def _reference(self, field):
        ref = self._manifest[field]
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
            raise ReplayAbort('Explicit frozen file reference required')
        raw = regular_bytes(ref['path'])
        if sha(raw) != ref['sha256']:
            raise ReplayAbort('Frozen ' + field + ' digest mismatch')
        return raw

    def source_job(self):
        source = read_json(self._reference('source'))
        if (Path(self._manifest['source']['path']).name != 'database-job.json'
                or source.get('pipeline_id') != self._manifest['mode']
                or not isinstance(source.get('data_snapshot'), dict) or not source['data_snapshot']
                or source.get('purpose') == 'independent_candidate_input_addendum_not_executable_job'):
            raise ReplayAbort('Original same-mode frozen database job required')
        from datetime import datetime
        data = source['data_snapshot']
        try:
            cutoff = datetime.fromisoformat(data['analysis_input_cutoff'])
            if cutoff.utcoffset() is None: raise ValueError('timezone missing')
        except (KeyError, TypeError, ValueError):
            raise ReplayAbort('Frozen normal job requires its original aware input cutoff') from None
        if (not isinstance(data.get('ticker'), str) or not data['ticker']
                or data['ticker'] != data['ticker'].strip().upper()
                or not isinstance(data.get('fetch_date'), str) or not data['fetch_date'].strip()
                or not isinstance(data.get('data_trust'), dict)):
            raise ReplayAbort('Frozen normal job requires original ticker, date and trust')
        return source

    def verify(self):
        try:
            return self._verify()
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ReplayAbort('Frozen preflight failed: ' + type(error).__name__) from None

    def _verify(self):
        row = self._manifest
        if sha(regular_bytes(self.path)) != self.expected_sha:
            raise ReplayAbort('Frozen manifest changed')
        if (row.get('schema') != 'campaign.frozen_job.v1'
                or row.get('stage') not in ('S1', 'S2', 'S3', 'S4')
                or row.get('mode') not in ('v1', 'v2', 'v3', 'v4')
                or row.get('role') not in ('baseline', 'candidate')
                or row.get('purpose') not in ('diagnostic', 'qualification')):
            raise ReplayAbort('Invalid frozen job scope')
        if row['stage'] == 'S1' and (row['mode'] != 'v4' or row['role'] != 'candidate'):
            raise ReplayAbort('S1 admits only v4 candidate jobs')
        if row['stage'] != 'S2' and row['role'] != 'candidate':
            raise ReplayAbort('Baseline code only belongs to S2')
        if row['stage'] in ('S3', 'S4') and row['purpose'] != 'qualification':
            raise ReplayAbort('Diagnostic sources cannot enter S3 or S4')
        if code_inventory(Path(row['dev'])) != row['code_files'] or harness_inventory() != row['harness_files']:
            raise ReplayAbort('Frozen backend or harness inventory changed')
        if runtime_inventory() != row['runtime_files']:
            raise ReplayAbort('Frozen Python or critical SDK/runtime dependency changed')
        for field in REFERENCES: self._reference(field)
        self.source_job()
        billing = read_json(self._reference('billing_review'))
        basis = read_json(self._reference('reservation_review'))
        source = read_json(self._reference('source_review'))
        policies = read_json(self._reference('policies'))
        now = int(time.time() * 1000)
        if (billing.get('schema') != 'campaign.billing_review.v1' or billing.get('decision') != 'approved'
                or billing.get('status') not in ('verified_paid', 'verified_free')
                or not billing.get('key_slots')
                or type(billing.get('reviewed_at_ms')) is not int
                or type(billing.get('expires_at_ms')) is not int
                or not 0 < billing['reviewed_at_ms'] <= now < billing['expires_at_ms']):
            raise ReplayAbort('Current externally reviewed billing identity is required')
        if (basis.get('schema') != 'campaign.reservation_review.v1' or basis.get('decision') != 'approved'
                or not policies or set(policies) != set(basis.get('models', {}))
                or set(policies) != set(billing.get('reviewed_models', []))):
            raise ReplayAbort('Reviewed pricing and all model reservation ceilings required')
        for model, policy in policies.items():
            if (not re.fullmatch(r'(?:gemini|gemma)-[A-Za-z0-9_.-]+', model)
                    or policy != {**basis['models'][model], 'billing_status': billing['status'],
                        'billing_identity_sha256': row['billing_review']['sha256'],
                        'reservation_basis_sha256': row['reservation_review']['sha256']}):
                raise ReplayAbort('Model policy is not bound to the reviewed evidence bytes')
            for field in ('maximum_total_tokens', 'maximum_output_tokens', 'maximum_request_bytes'):
                if type(policy.get(field)) is not int or policy[field] <= 0:
                    raise ReplayAbort('Positive integer reservation ceilings required')
            rate = policy.get('maximum_microusd_per_million_tokens')
            if (type(rate) is not int or rate < 0 or (billing['status'] == 'verified_free') != (rate == 0)
                    or policy['maximum_output_tokens'] > policy['maximum_total_tokens']):
                raise ReplayAbort('Contradictory reviewed reservation ceiling')
        if (source.get('schema') != 'campaign.source_review.v1' or source.get('mode') != row['mode']
                or source.get('source_sha256') != row['source']['sha256']
                or source.get('decision') != ('qualified' if row['purpose'] == 'qualification' else 'diagnostic_only')):
            raise ReplayAbort('Source disposition has not been independently reviewed for this exact input')
        # Reviews are trusted external evidence, not inferred from HTTP success,
        # nonempty transcripts or hash presence. No real review is created here.
        # Candidate identity is shared across sources/modes/stages. Per-job
        # review and environment bytes remain fixed by the manifest digest and
        # are re-read above; they must not invent additional code versions.
        binding = {'code_files': row['code_files'], 'harness_files': row['harness_files'],
                   'runtime_files': row['runtime_files']}
        return {'code_sha256': sha(encoded(binding)), 'source_sha256': row['source']['sha256'],
                'route_sha256': row['routes']['sha256']}


def ledger_pin(ledger):
    info = ledger.path.lstat()
    if (ledger.path.resolve() != ledger.path or not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size < 512):
        raise ReplayAbort('Existing private campaign ledger required')
    return {'path': str(ledger.path), 'device': info.st_dev, 'inode': info.st_ino,
            'config': copy.deepcopy(ledger.config)}


def reopen_ledger(pin):
    try:
        path = Path(pin['path'])
        info = path.lstat()
        if (path.resolve() != path or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size < 512 or (info.st_dev, info.st_ino) != (pin['device'], pin['inode'])):
            raise ReplayAbort('Pinned campaign ledger is missing, replaced or truncated')
        # The constructor must never be used to initialize missing state here.
        # Read and match the real immutable init event before any constructor.
        with closing(sqlite3.connect(path)) as connection:
            first = connection.execute('SELECT kind,payload FROM campaign_events WHERE seq=1').fetchone()
        if not first or first[0] != 'init' or read_json(first[1]) != pin['config']:
            raise ReplayAbort('Pinned ledger init evidence mismatch')
        config = pin['config']
        ledger = CampaignBudget(path, config['identity'], limits=config['limits'],
            allowed_bindings=config['allowed_bindings'] if config['manifest_mode'] else None)
        if ledger_pin(ledger) != pin: raise ReplayAbort('Ledger identity changed while reopening')
        return ledger
    except (OSError, sqlite3.Error, BudgetDenied, KeyError, TypeError, ValueError) as error:
        raise ReplayAbort('Existing campaign ledger unavailable: ' + type(error).__name__) from None


def child_environment(plan, output):
    plan.verify()
    environment = {}
    for raw in plan._reference('environment').decode('utf-8').splitlines():
        line = raw.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key in environment: raise ReplayAbort('Duplicate explicit environment key')
            environment[key] = value
    if (environment.get('MODEL_ROUTES_FILE') != plan.manifest['routes']['path']
            or not environment.get('REDIS_URL')):
        raise ReplayAbort('Explicit unchanged routes and shared Redis required')
    for key in tuple(environment):
        if key.startswith(('PG', 'GIT_', 'PYTHON', 'DYLD_', 'LD_')) or key in {
            'DATABASE_URL', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy',
            'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION', 'GOOGLE_APPLICATION_CREDENTIALS',
            'HOME', 'CODEX_HOME', 'PATH'}:
            environment.pop(key)
    environment.update(PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', TZ='Asia/Taipei',
        CACHE_DIR=str(output / 'cache'), CACHE_DB_PATH=str(output / 'cache.sqlite3'),
        OPERATIONAL_DB_PATH=str(output / 'operational.sqlite3'), TASK_DB_PATH=str(output / 'operational.sqlite3'),
        LANGGRAPH_CHECKPOINT_PATH=str(output / 'checkpoint.sqlite3'), LANGGRAPH_CHECKPOINT_BACKEND='sqlite',
        LANGGRAPH_CHECKPOINT_POSTGRES_DSN='isolated-postgres-disabled', CACHE_BACKEND='memory',
        OUTPUT_DIR=str(output / 'reports'), REPORT_STORAGE_BACKEND='local',
        LLM_SEMANTIC_CACHE_ENABLED='false', AGENT_STEP_CACHE_ENABLED='false', RAG_ENABLED='false',
        GEMMA_EVIDENCE_BATCHING_ENABLED='false', GOOGLE_GENAI_USE_VERTEXAI='false', GIT_OPTIONAL_LOCKS='0',
        TMPDIR=str(output / 'tmp'), MPLCONFIGDIR=str(output / 'mpl'), XDG_CACHE_HOME=str(output / 'xdg'),
        PYTHONDONTWRITEBYTECODE='1')
    return environment


def exclusive_json(path, value):
    raw = encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    return sha(raw)


def check_reserved(plan, ledger, job_id):
    hashes = plan.verify()
    ledger.check()
    state = ledger.snapshot()
    job = state['jobs'].get(job_id)
    if (state['blocked'] or ledger.identity['campaign_id'] != plan.manifest['campaign_id']
            or not job or job['status'] != 'active' or job['actual_hashes'] != hashes
            or job['binding_id'] != plan.manifest['binding_id'] or job['stage'] != plan.manifest['stage']):
        raise ReplayAbort('Job does not match the active frozen reservation')
    return hashes


def check_claim(ledger, job_id, job):
    expected = {'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
                'deadline_ms': job['deadline_ms'], 'actual_hashes': job['actual_hashes']}
    path = ledger.path.parent / (ledger.path.name + '.' + job_id + '.watchdog-started.json')
    try: claim = read_json(regular_bytes(path))
    except OSError: raise ReplayAbort('Owned watchdog claim missing') from None
    if claim != expected:
        raise ReplayAbort('Owned watchdog claim does not match the original reservation')
    return claim


def consume_maintenance_admission(ticket_path, ticket, fd):
    """Consume one inherited pipe before opening any frozen credential source.

    The original parent sends only after its durable started observation. Files
    alone cannot choose this lane, and an old watchdog claim is never fallback.
    This capability is not a sandbox against a host owner forging a launch.
    """
    if type(fd) is not int or not 3 <= fd < 1048576:
        raise ReplayAbort('Inherited maintenance admission pipe required')
    info = os.fstat(fd)
    private_mode = stat.S_IMODE(info.st_mode) == 0o600 or (sys.platform == 'darwin'
        and stat.S_IMODE(info.st_mode) == 0o660 and info.st_dev == 0 and info.st_nlink == 0)
    if (not stat.S_ISFIFO(info.st_mode) or info.st_uid != os.geteuid()
            or not private_mode
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
        raise ReplayAbort('Private read-only maintenance pipe required')
    identity = {'device': info.st_dev, 'inode': info.st_ino}
    try:
        metadata = ticket.get('maintenance_admission')
        if (type(metadata) is not dict or set(metadata) != {'schema', 'intent_sha256', 'parent_pid',
                'pipe_identity', 'process_binding'} or metadata['schema'] != 'maintenance.owned-admission.v1'
                or type(metadata['parent_pid']) is not int or metadata['parent_pid'] != os.getppid()
                or metadata['pipe_identity'] != identity):
            raise ReplayAbort('Maintenance admission metadata mismatch')
        deadline, raw = time.monotonic() + 5, b''
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise ReplayAbort('Maintenance parent admission timed out')
            part = os.read(fd, 8193 - len(raw))
            if not part: break
            raw += part
            if len(raw) > 8192: raise ReplayAbort('Maintenance admission exceeded bound')
        authorization = read_json(raw)
        expected = {'schema': 'maintenance.owned-admission.v1', 'parent_pid': metadata['parent_pid'],
            'child_pid': os.getpid(), 'pipe_identity': identity,
            'ticket_sha256': sha(regular_bytes(ticket_path)), 'intent_sha256': metadata['intent_sha256'],
            'started_journal_sha256': authorization.get('started_journal_sha256')}
        if (authorization != expected or type(expected['started_journal_sha256']) is not str
                or re.fullmatch('[a-f0-9]{64}', expected['started_journal_sha256']) is None
                or os.getppid() != metadata['parent_pid']):
            raise ReplayAbort('Maintenance parent authorization mismatch')
        intent_raw = regular_bytes(Path(ticket['output']) / 'dispatch-intent.json', limit=8192)
        intent = read_json(intent_raw)
        if (sha(intent_raw) != metadata['intent_sha256'] or intent.get('schema') != 'maintenance.canary-launch.v1'
                or intent.get('parent_pid') != metadata['parent_pid']
                or intent.get('process_binding') != metadata['process_binding']
                or intent.get('job_id') != ticket['job_id'] or intent.get('output') != ticket['output']
                or intent.get('manifest_sha256') != ticket['manifest_sha256']
                or intent.get('ledger_pin_sha256') != sha(encoded(ticket['ledger_pin']))):
            raise ReplayAbort('Maintenance launch intent mismatch')
        if 'owned_session' in intent and (intent['owned_session'] is not True
                or os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid()):
            raise ReplayAbort('Original owned process group mismatch')
        digest = exclusive_json(Path(ticket['output']) / 'maintenance-admission.json', authorization)
        return intent, digest
    finally:
        os.close(fd)


def private_artifacts_match(output, outcome):
    """Read back only child-owned storage keys; never trust a success scalar."""
    try:
        artifacts = outcome.get('artifacts')
        if (outcome.get('frozen_verified') is not True or not isinstance(outcome.get('publication'), dict)
                or not isinstance(artifacts, dict) or set(artifacts) != {'html_key', 'md_key', 'data_key'}):
            return False
        root = output / 'reports'
        if not root.is_dir() or root.resolve() != root: return False
        for field, extension in (('html_key', '.html'), ('md_key', '.md'), ('data_key', '.json')):
            row = artifacts[field]
            if (not isinstance(row, dict) or set(row) != {'key', 'bytes', 'sha256'}
                    or type(row['key']) is not str or not row['key'].endswith(extension)
                    or type(row['bytes']) is not int or row['bytes'] <= 0):
                return False
            relative = Path(row['key'])
            if relative.is_absolute() or '..' in relative.parts or not relative.parts: return False
            path = root / relative
            if not path.is_relative_to(root): return False
            raw = regular_bytes(path)
            if len(raw) != row['bytes'] or sha(raw) != row['sha256']: return False
        return True
    except (ReplayAbort, OSError, KeyError, ValueError, TypeError):
        return False


_UNCONFIRMED_STORAGE_CLAIMS = []


class _PreparedJobStorage:
    def __init__(self, plan, ledger, job_id, reference, lease, fd, capability):
        self.plan, self.ledger, self.job_id = plan, ledger, job_id
        self.reference = copy.deepcopy(reference)
        self.lease, self.fd, self.capability = lease, fd, capability
        self.active = True


@contextmanager
def reserved_job_storage(plan, ledger, job_id, storage_budget):
    """Admit a fixed job before its campaign stage/batch/slot can be consumed."""
    canary_release_policy.require_canary_enabled()
    plan.verify()
    backend = str(Path(plan.manifest['dev']) / 'backend')
    sys.path.insert(0, backend)
    try:
        from storage.capacity_delegation import reviewed_budget, prepare_parent_claim
        from storage.capacity import StorageCapacityUnavailable
    finally:
        sys.path.remove(backend)
    review = reviewed_budget(storage_budget, manifest_sha256=plan.expected_sha,
                             job_id=job_id, source_bytes=len(encoded(plan.source_job())))
    output = ledger.path.parent / job_id
    try:
        lease, fd, capability = prepare_parent_claim(output, job_id, plan.expected_sha, review)
    except (OSError, RuntimeError, ValueError) as error:
        raise StorageCapacityUnavailable('Guarded job storage admission refused before reservation') from error
    prepared = _PreparedJobStorage(plan, ledger, job_id, storage_budget, lease, fd, capability)
    try:
        yield prepared
    finally:
        prepared.active = False
        os.close(fd)
        if (getattr(lease, '_guardian_started', False)
                and not getattr(lease, '_guardian_cleanup_confirmed', False)):
            _UNCONFIRMED_STORAGE_CLAIMS.append(lease)
        else:
            lease.__exit__(*sys.exc_info())


def execute_reserved_job(plan, ledger, job_id, *, storage_budget=None, _storage=None):
    """Run an already reserved job using exactly its admitted storage claim."""
    canary_release_policy.require_canary_enabled()
    check_reserved(plan, ledger, job_id)
    if _storage is None:
        with reserved_job_storage(plan, ledger, job_id, storage_budget) as prepared:
            return execute_reserved_job(plan, ledger, job_id, storage_budget=storage_budget, _storage=prepared)
    if (type(_storage) is not _PreparedJobStorage or not _storage.active
            or _storage.plan is not plan or _storage.ledger is not ledger or _storage.job_id != job_id
            or _storage.reference != storage_budget or _storage.lease.receipt()['state'] != 'active'):
        raise ReplayAbort('Original active storage binding required; no adoption or replay')
    _storage.lease.check()
    return _execute_reserved_job(plan, ledger, job_id, storage_budget,
        _storage.lease, _storage.fd, _storage.capability)


def _execute_reserved_job(plan, ledger, job_id, storage_budget, lease, readonly_fd, capability):
    """Owned cleanup plus exact outcome readback; no stage/quality promotion."""
    canary_release_policy.require_canary_enabled()
    check_reserved(plan, ledger, job_id)
    pin = ledger_pin(ledger)
    original_job = ledger.snapshot()['jobs'][job_id]
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', job_id) or job_id in ('.', '..'):
        raise ReplayAbort('Invalid job identifier')
    output = ledger.path.parent / job_id
    try: output.mkdir(mode=0o700)
    except OSError: raise ReplayAbort('New exclusive job output required; no resume') from None
    ticket = {'manifest_path': str(plan.path), 'manifest_sha256': plan.expected_sha,
              'ledger_pin': pin, 'job_id': job_id, 'output': str(output),
              'storage_budget': storage_budget, 'storage_capacity': capability}
    ticket_path = output / 'child-ticket.json'
    exclusive_json(ticket_path, ticket)
    result = run_reserved_process(ledger, job_id,
        [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--owned-job', str(ticket_path),
         '--storage-capacity-fd', str(readonly_fd)],
        env={'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONDONTWRITEBYTECODE': '1'},
        output_dir=output, capacity_lease=lease, capacity_read_fd=readonly_fd)
    if not result.get('cleanup_verified'):
        raise CleanupUnconfirmed('Owned cleanup has not been verified')
    reopen_ledger(pin)
    if ledger.snapshot()['jobs'].get(job_id) != original_job:
        raise ReplayAbort('Reserved job changed while child was running')
    check_claim(ledger, job_id, original_job)
    cleanup_path = output / ('watchdog-' + job_id + '.cleanup.json')
    try:
        cleanup_bytes = regular_bytes(cleanup_path)
        cleanup = read_json(cleanup_bytes)
    except OSError: raise ReplayAbort('Owned cleanup readback missing') from None
    if (str(cleanup_path) != result.get('cleanup_path') or sha(cleanup_bytes) != result.get('cleanup_evidence_sha256')
            or cleanup.get('job_id') != job_id or cleanup.get('ledger_binding_sha256') != ledger.binding
            or cleanup.get('deadline_ms') != original_job['deadline_ms']
            or cleanup.get('command_returncode') != result.get('returncode')
            or result.get('status') != ('exited' if cleanup.get('stop_reason') == 'exited' else 'stopped')
            or type(cleanup.get('pgid')) is not int or cleanup['pgid'] <= 0
            or cleanup.get('guardian_reaped') is not True or cleanup.get('process_group_absent') is not True):
        raise ReplayAbort('Owned cleanup receipt does not match this job')
    outcome_path = output / 'outcome.json'
    outcome = read_json(regular_bytes(outcome_path)) if outcome_path.exists() else None
    published = bool(result.get('returncode') == 0 and result.get('status') == 'exited'
        and isinstance(outcome, dict) and outcome.get('status') == 'published'
        and outcome.get('job_id') == job_id and outcome.get('mode') == plan.manifest['mode']
        and outcome.get('formal_publication') is False and outcome.get('qualified_for_campaign') is False
        and private_artifacts_match(output, outcome))
    if published: check_reserved(plan, ledger, job_id)
    # A successful private pipeline is not a qualified report. Even failures
    # consume their job and all unfinalized reservations after proved cleanup.
    ledger.finish_job(job_id, status='completed' if published else 'failed')
    receipt = {'job_id': job_id, 'status': 'private_pipeline_completed' if published else 'failed',
        'qualified_for_campaign': False, 'formal_publication': False,
        'manifest_sha256': plan.expected_sha, 'cleanup_sha256': sha(cleanup_bytes),
        'prompts_sha256': sha(regular_bytes(output / 'prompts.jsonl')) if (output / 'prompts.jsonl').exists() else None,
        'outcome_sha256': sha(regular_bytes(outcome_path)) if outcome else None}
    exclusive_json(output / 'parent-receipt.json', receipt)
    return receipt


async def owned_job(ticket_path, *, stop_requested=lambda: False, completion=None, admission_fd=None, storage_capacity_fd=None, storage_lifetime_fd=None):
    canary_release_policy.require_canary_enabled()
    ticket_path = Path(ticket_path)
    ticket = read_json(regular_bytes(ticket_path))
    output, job_id = Path(ticket['output']), ticket['job_id']
    if ticket_path != output / 'child-ticket.json' or output.resolve() != output:
        raise ReplayAbort('Owned child ticket path mismatch')
    if any(name in sys.modules for name in ('config', 'llm_transport', 'psycopg', 'psycopg2', 'asyncpg', 'pg8000')):
        raise ReplayAbort('Fresh isolated process required')
    if storage_capacity_fd is None or 'storage_capacity' not in ticket or 'storage_budget' not in ticket:
        raise ReplayAbort('Reviewed parent-held storage capacity required before child execution')
    admission = None
    if 'maintenance_admission' in ticket:
        admission, admission_sha = consume_maintenance_admission(ticket_path, ticket, admission_fd)
    elif admission_fd is not None:
        raise ReplayAbort('Maintenance pipe requires an explicit maintenance ticket')
    if stop_requested():
        raise asyncio.CancelledError()
    observe_process_scope = None
    if admission is not None and admission.get('owned_session') is True:
        from quality_campaign_safety import install_owned_process_boundary
        observe_process_scope = install_owned_process_boundary()
    started = {'job_id': job_id, 'process_pid': os.getpid(), 'ticket_sha256': sha(regular_bytes(ticket_path))}
    if admission is not None: started['maintenance_admission_sha256'] = admission_sha
    plan = FrozenJob(ticket['manifest_path'], ticket['manifest_sha256'])
    ledger = reopen_ledger(ticket['ledger_pin'])
    hashes = check_reserved(plan, ledger, job_id)
    if output != ledger.path.parent / job_id:
        raise ReplayAbort('Private child output is outside the reserved job')
    job = ledger.snapshot()['jobs'][job_id]
    if admission is None:
        check_claim(ledger, job_id, job)
    elif (admission.get('reservation') != {'job_id': job_id, 'ledger_binding_sha256': ledger.binding,
            'deadline_ms': job['deadline_ms'], 'actual_hashes': job['actual_hashes']}
            or type(admission.get('timeout_seconds')) is not int or admission['timeout_seconds'] <= 0
            or ledger.limits['campaign']['job_seconds'] > admission['timeout_seconds']):
        raise ReplayAbort('Maintenance launch does not match the original reservation')
    if stop_requested():
        raise asyncio.CancelledError()
    backend = str(Path(plan.manifest['dev']) / 'backend')
    sys.path.insert(0, backend)
    try:
        from storage.capacity_delegation import reviewed_budget, install_readonly_capacity
    finally:
        sys.path.remove(backend)
    review = reviewed_budget(ticket['storage_budget'], manifest_sha256=plan.expected_sha,
                             job_id=job_id, source_bytes=len(encoded(plan.source_job())))
    if sum(review['components'].values()) != ticket['storage_capacity']['limit_bytes']:
        raise ReplayAbort('Readonly capability differs from reviewed byte budget')
    install_readonly_capacity(storage_capacity_fd, ticket['storage_capacity'], output=output,
                              job_id=job_id, manifest_sha256=plan.expected_sha, lifetime_fd=storage_lifetime_fd)
    exclusive_json(output / 'child-started.json', started)
    environment = child_environment(plan, output)
    runtime_identity = None
    if observe_process_scope is not None:
        runtime_identity = admission.get('runtime_code_identity')
        if (type(runtime_identity) is not dict or set(runtime_identity) != {'commit', 'dirty', 'code_sha256'}
                or type(runtime_identity['commit']) is not str or re.fullmatch('[a-f0-9]{40}', runtime_identity['commit']) is None
                or runtime_identity['commit'] != admission.get('process_binding', {}).get('backend_revision')
                or type(runtime_identity['dirty']) is not bool or runtime_identity['code_sha256'] != hashes['code_sha256']):
            raise ReplayAbort('Original runtime code identity mismatch')
        environment.update(GIT_COMMIT=runtime_identity['commit'], GIT_DIRTY=str(runtime_identity['dirty']).lower())
    os.umask(0o077)
    sys.dont_write_bytecode = True
    os.environ.clear()
    os.environ.update(environment)
    (output / 'tmp').mkdir(mode=0o700)
    from quality_campaign_safety import sqlite_guard, write_audit_guard, install_socket_boundary, credential_values
    sqlite3.connect = sqlite_guard(output, sqlite3.connect, ledger_path=ledger.path)
    sys.addaudithook(write_audit_guard(output, code_root=Path(plan.manifest['dev']), ledger_path=ledger.path))
    class NoPostgres:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in ('psycopg', 'psycopg2', 'asyncpg', 'pg8000'):
                raise ImportError('PostgreSQL disabled in frozen campaign child')
            return None
    sys.meta_path.insert(0, NoPostgres())
    install_socket_boundary(environment['REDIS_URL'])
    sys.path.insert(0, str(Path(plan.manifest['dev']) / 'backend'))
    logging.disable(logging.CRITICAL)
    from quality_campaign_graph import run_normal_job
    from quality_campaign_transport import CampaignTransport
    import config
    secrets = credential_values(environment,
        [key for keys in config.LLM_API_KEYS_BY_PROVIDER.values() for key in keys])
    transport = CampaignTransport(ledger, job_id, read_json(plan._reference('policies')),
                                  actual_hashes=hashes, verify_frozen=plan.verify, secrets=secrets)
    outcome = await run_normal_job(dev=Path(plan.manifest['dev']), source_job=plan.source_job(),
        output=output, job_id=job_id, mode=plan.manifest['mode'], ledger=ledger,
        transport=transport, check_frozen=plan.verify, secrets=secrets, manifest_sha256=plan.expected_sha)
    outcome_bytes = regular_bytes(output / 'outcome.json')
    if read_json(outcome_bytes) != outcome:
        raise ReplayAbort('Owned normal outcome changed before cleanup receipt')
    observation = {
        'schema': 'campaign.child_cleanup.v1', 'job_id': job_id, 'process_pid': os.getpid(),
        'ticket_sha256': sha(regular_bytes(ticket_path)), 'manifest_sha256': plan.expected_sha,
        'outcome_sha256': sha(outcome_bytes),
        'sdk_cleanup_verified': outcome.get('sdk_cleanup_verified') is True,
        'pre_shutdown_pending_async_tasks': len([task for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()]),
        # This is an in-process observation, not OS descendant or RQ settlement.
        # A future formal controller must verify those independently before release.
        'descendant_settlement_verified': False, 'handover_verified': False}
    if admission is not None: observation['maintenance_admission_sha256'] = admission_sha
    if runtime_identity is not None: observation['runtime_code_identity'] = runtime_identity
    if completion is not None:
        completion.update(output=output, ticket_path=ticket_path, transport=transport, observation=observation,
                          observe_process_scope=observe_process_scope)
    # The async core cannot certify its own loop/executor shutdown. Only the
    # CLI owner below writes a final cleanup receipt after Runner.close returns.
    return 0 if outcome.get('status') == 'published' and not stop_requested() else 2


@contextmanager
def _owned_asyncgen_tracking(loop):
    """Keep this thread's generators owned across FinMind/nest_asyncio imports.

    nest_asyncio.run_until_complete does not install the loop's asyncgen hooks.
    It can be applied before work or during a normal application import. Cover
    execution AND shutdown, including generators created by task finalizers;
    neither undo its global patches nor collect generators from another loop.
    """
    previous = sys.get_asyncgen_hooks()
    installed = (loop._asyncgen_firstiter_hook, loop._asyncgen_finalizer_hook)
    sys.set_asyncgen_hooks(*installed)
    try:
        yield
    finally:
        if sys.get_asyncgen_hooks() != installed:
            raise ReplayAbort('Owned async-generator hook ownership changed')
        sys.set_asyncgen_hooks(*previous)


def _run_owned_loop(loop_runner, work):
    with _owned_asyncgen_tracking(loop_runner.get_loop()):
        return loop_runner.run(work)


def _close_owned_loop(loop_runner):
    """Deny new HTTP while pending-task/async-generator finalizers are drained.

    The normal campaign hooks have unwound. Reuse their physical HTTPX seam as
    a terminal veto, not a new attempt/reservation; even cached SDK function
    references cannot send around it. This remains an application boundary,
    not a native networking sandbox or permission for arbitrary finalizers.
    """
    from quality_campaign_wire import instrument_http
    class Stopped:
        denied = 0
        def before_http(self, request):
            self.denied += 1
            raise ReplayAbort('New HTTP is forbidden during owned loop shutdown')
    observer = Stopped()
    restore = instrument_http(observer)
    loop = loop_runner.get_loop()
    previous_handler = loop.get_exception_handler()
    error_types, error_count = [], 0
    def record_error(error_type):
        nonlocal error_count
        error_count += 1
        if len(error_types) < 32:
            error_types.append(error_type[:80])
    def shutdown_error(loop, context):
        error = context.get('exception')
        record_error(type(error).__name__ if error is not None else 'LoopShutdownError')
        if previous_handler is not None:
            try:
                previous_handler(loop, context)
            except BaseException as handler_error:
                record_error(type(handler_error).__name__)
        # No default exception/body/task repr on inherited terminal output.
        # Runner.close gathers task/async-generator errors without raising them;
        # the safe count/types below must still veto a successful cleanup receipt.
    loop.set_exception_handler(shutdown_error)
    api = sys.modules.get('google.genai._api_client')
    previous = api.BaseApiClient._use_aiohttp if api else None
    def httpx_only(self): return False
    if api: api.BaseApiClient._use_aiohttp = httpx_only
    try:
        with _owned_asyncgen_tracking(loop):
            loop_runner.close()
    finally:
        if loop.get_exception_handler() is shutdown_error:
            loop.set_exception_handler(previous_handler)
        else:
            record_error('ShutdownExceptionHandlerChanged')
        changed = api is not None and api.BaseApiClient._use_aiohttp is not httpx_only
        if api is not None and not changed:
            api.BaseApiClient._use_aiohttp = previous
        restore()
        if changed:
            raise ReplayAbort('SDK shutdown hook ownership changed')
    # shutdown_asyncgens drains one snapshot. A finalizer may register another
    # generator after that snapshot; never report it clean or drain recursively
    # without a bound. Already-closed retained generators are not live resources.
    pending_generators = sum(generator.ag_frame is not None for generator in loop._asyncgens)
    return {'http_denials': observer.denied, 'async_error_types': error_types, 'async_error_count': error_count,
            'pending_async_generators': pending_generators}


def run_owned_job(ticket_path, *, admission_fd=None, storage_capacity_fd=None, storage_lifetime_fd=None):
    """CLI-owned loop: the first TERM cancels work; repeats do not cancel again.

    Keep the handler through Runner.close (including executor shutdown). Do not
    adopt another loop/task or claim a signal was delivered merely from a file.
    A non-cooperative child may stay alive; the maintenance owner must retain its
    gate, not escalate. The private campaign watchdog's policy is unchanged.
    """
    canary_release_policy.require_canary_enabled()
    loop_runner = asyncio.Runner()
    loop = loop_runner.get_loop()
    requested, task, installed = False, None, False
    completion = {}
    def stopping(signum, frame):
        nonlocal requested
        if requested:
            return
        requested = True
        # Schedule onto the owned loop and wake its selector. Synchronous work
        # cannot be forcibly unwound; the next cooperative await receives it.
        if task is not None and not task.done() and not task.cancelling():
            loop.call_soon_threadsafe(task.cancel)
    async def execute():
        nonlocal task
        task = asyncio.current_task()
        if requested:
            raise asyncio.CancelledError()
        options = {'admission_fd': admission_fd} if admission_fd is not None else {}
        if storage_capacity_fd is not None:
            options['storage_capacity_fd'] = storage_capacity_fd
        if storage_lifetime_fd is not None:
            options['storage_lifetime_fd'] = storage_lifetime_fd
        return await owned_job(ticket_path, stop_requested=lambda: requested, completion=completion, **options)
    try:
        previous = signal.signal(signal.SIGTERM, stopping)
        installed = True
        try:
            code = _run_owned_loop(loop_runner, execute())
        finally:
            shutdown = _close_owned_loop(loop_runner)
        if not completion:
            raise ReplayAbort('Owned job ended without application cleanup observations')
        observation = completion['observation']
        output = completion['output']
        if (sha(regular_bytes(completion['ticket_path'])) != observation['ticket_sha256']
                or sha(regular_bytes(output / 'outcome.json')) != observation['outcome_sha256']):
            raise ReplayAbort('Owned job evidence changed during event loop shutdown')
        sdk = sys.modules.get('llm_transport')
        sdk_empty = False
        if sdk is not None:
            with sdk._client_lock:
                sdk_empty = not sdk._client_cache
        pending = len([task for task in asyncio.all_tasks(loop) if not task.done()])
        threads = len([thread for thread in threading.enumerate()
                       if thread is not threading.current_thread() and thread.is_alive()])
        restored = completion['transport']._restore is None
        verified = (observation['sdk_cleanup_verified'] and sdk_empty and restored and not pending and not threads
                    and not shutdown['http_denials'] and not shutdown['async_error_count']
                    and not shutdown['pending_async_generators'])
        scope_reader = completion.get('observe_process_scope')
        if scope_reader is not None:
            scope = {**scope_reader(), 'pid': os.getpid(), 'pgid': os.getpgrp(), 'sid': os.getsid(0)}
            verified = verified and scope == {'policy': 'deny-python-process-creation-v1', 'denied': 0,
                                             'pid': os.getpid(), 'pgid': os.getpid(), 'sid': os.getpid()}
            observation['owned_process_scope'] = scope
        exclusive_json(output / 'child-cleanup.json', {**observation,
            'stop_requested': requested, 'event_loop_closed': loop.is_closed(),
            'sdk_cache_empty_after_shutdown': sdk_empty, 'transport_restored': restored,
            'shutdown_http_denials': shutdown['http_denials'],
            'shutdown_async_error_types': shutdown['async_error_types'],
            'shutdown_async_error_count': shutdown['async_error_count'],
            'pending_async_generators': shutdown['pending_async_generators'],
            'pending_async_tasks': pending, 'background_threads': threads,
            'application_cleanup_verified': bool(verified and loop.is_closed())})
        return 0 if code == 0 and verified and loop.is_closed() and not requested else 2
    finally:
        if installed:
            signal.signal(signal.SIGTERM, previous)
        else:
            loop_runner.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owned-job', required=True)
    parser.add_argument('--owned-admission-fd', type=int)
    parser.add_argument('--storage-capacity-fd', type=int)
    parser.add_argument('--storage-lifetime-fd', type=int)
    args = parser.parse_args()
    try:
        code = run_owned_job(args.owned_job, admission_fd=args.owned_admission_fd, storage_capacity_fd=args.storage_capacity_fd, storage_lifetime_fd=args.storage_lifetime_fd)
    except BaseException as error:
        # No exception/body/env repr on inherited terminal output.
        print(json.dumps({'status': 'child_failed', 'error_type': type(error).__name__}), flush=True)
        code = 2
    raise SystemExit(code)
