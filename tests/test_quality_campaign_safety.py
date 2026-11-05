"""Private files and fresh local processes only; never providers or runtime."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

import quality_campaign_safety as safety
from test_quality_campaign_budget import active, IDENTITY, RESERVATION


def layout(tmp_path):
    ledger = active(tmp_path)
    output = tmp_path / 'one-job'
    output.mkdir(mode=0o700)
    return ledger, output


def test_sqlite_guard_reopens_shared_ledger_but_rejects_siblings_and_uris(tmp_path):
    ledger, output = layout(tmp_path)
    guarded = safety.sqlite_guard(output, sqlite3.connect, ledger_path=ledger.path)
    with guarded(ledger.path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM campaign_events').fetchone()[0] > 0
    with guarded(output / 'cache.sqlite3') as connection:
        connection.execute('CREATE TABLE local (value INTEGER)')
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute('ATTACH DATABASE ? AS escaped', (str(tmp_path / 'other.sqlite3'),))
    for database in [tmp_path / 'sibling.sqlite3', 'file:' + str(ledger.path), output / '..' / 'outside.db']:
        with pytest.raises(safety.ReplayAbort):
            guarded(database)


def test_write_guard_pins_existing_ledger_and_never_allows_mainfile_reset(tmp_path):
    ledger, output = layout(tmp_path)
    guard = safety.write_audit_guard(output, ledger_path=ledger.path)
    guard('open', (str(ledger.path), None, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW))
    guard('open', (str(output / 'report.json'), 'w', os.O_WRONLY | os.O_CREAT | os.O_TRUNC))
    denied = [
        ('open', (str(ledger.path), 'w', os.O_WRONLY | os.O_TRUNC)),
        ('open', (str(tmp_path / 'sibling.json'), 'a', os.O_WRONLY | os.O_APPEND)),
        ('os.remove', (str(ledger.path), -1)),
        ('os.rename', (str(ledger.path), str(output / 'stolen'), -1, -1)),
        ('os.rename', (str(output / 'replacement'), str(ledger.path), -1, -1)),
        ('os.truncate', (str(ledger.path), 0)),
    ]
    for event, args in denied:
        with pytest.raises(safety.ReplayAbort):
            guard(event, args)
    ledger.path.rename(tmp_path / 'original.sqlite3')
    ledger.path.write_bytes(b'replaced')
    ledger.path.chmod(0o600)
    with pytest.raises(safety.ReplayAbort):
        guard('open', (str(ledger.path), None, os.O_RDWR))


def test_evidence_redaction_keeps_counters_and_private_exclusive_append_files(tmp_path):
    _, output = layout(tmp_path)
    fake_key = 'AIza' + 'X' * 30
    secrets = safety.credential_values({'MAX_OUTPUT_TOKENS': '6144',
        'REDIS_URL': 'redis://user:secret%21@redis.invalid:6379/0'}, [fake_key])
    assert '6144' not in secrets and 'secret!' in secrets
    evidence = safety.Evidence(output, secrets)
    evidence.save('safe.json', {2: {'input_tokens': 3, 'token': 'sensitive',
        'text': fake_key + ' secret!'}, 'llm_token_usage': {1: {'output_tokens': 2}}})
    evidence.append('rows.jsonl', {'row': 1})
    evidence.append('rows.jsonl', {'row': 2})
    assert json.loads((output / 'safe.json').read_text()) == {'2': {
        'input_tokens': 3, 'token': '[redacted]', 'text': '[redacted] [redacted]'},
        'llm_token_usage': {'1': {'output_tokens': 2}}}
    assert (output / 'safe.json').stat().st_mode & 0o777 == 0o600
    assert len((output / 'rows.jsonl').read_text().splitlines()) == 2
    with pytest.raises(FileExistsError): evidence.save('safe.json', {})
    with pytest.raises(safety.ReplayAbort): evidence.save('../escape', {})
    limited = safety.Evidence(output, maximum_bytes=160)
    with pytest.raises(safety.ReplayAbort): limited.save('too-large.json', {'text': 'x' * 160})
    limited.save('outcome.json', {'status': 'retained'})


def test_strict_quota_checks_before_and_after_no_local_fallback():
    class Limiter:
        _client = object()
        calls = 0
        def reserve(self):
            self.calls += 1
            self._client = None
            return 'local fallback'
    limiter = Limiter()
    wrapper = safety.StrictSharedQuota(limiter)
    with pytest.raises(safety.ReplayAbort): wrapper.reserve()
    with pytest.raises(safety.ReplayAbort): wrapper.reserve()
    assert limiter.calls == 1
    from quality_campaign_wire import ReplayAbort
    assert safety.ReplayAbort is ReplayAbort and not issubclass(ReplayAbort, Exception)


def test_missing_shared_limiter_is_a_hard_abort_not_retryable_attribute_error():
    with pytest.raises(safety.ReplayAbort): safety.StrictSharedQuota(None).reserve()


def test_socket_boundary_only_resolves_and_connects_google_and_supplied_redis(monkeypatch):
    import socket
    resolved, connected = [], []
    def resolve(host, port, **options):
        resolved.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '',
                 ('192.0.2.1' if port == 443 else '192.0.2.2', port))]
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    monkeypatch.setattr(socket.socket, 'connect', lambda sock, address: connected.append(address))
    monkeypatch.setattr(socket.socket, 'connect_ex', lambda sock, address: connected.append(address) or 0)
    safety.install_socket_boundary('rediss://user:dummy@redis.invalid:6380/0')
    assert resolved == [('generativelanguage.googleapis.com', 443), ('redis.invalid', 6380)]
    with socket.socket() as sock:
        sock.connect(('192.0.2.1', 443))
        assert sock.connect_ex(('192.0.2.2', 6380)) == 0
        for address in [('market.invalid', 443), ('192.0.2.1', 80), '/tmp/unknown.socket']:
            with pytest.raises(safety.ReplayAbort): sock.connect(address)
            with pytest.raises(safety.ReplayAbort): sock.connect_ex(address)
    assert len(connected) == 2


def fresh_guarded_child(ledger, output, source, *, identity=IDENTITY):
    setup = '''import os, sys, socket, sqlite3, json, stat
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import quality_campaign_safety as safety
from quality_campaign_budget import CampaignBudget
from quality_campaign_transport import _Journal
output, ledger_path = Path(sys.argv[2]), Path(sys.argv[3])
identity = json.loads(sys.argv[4])
def no_network(*args, **kwargs): raise AssertionError('test child cannot use network')
socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = no_network
backend=Path(sys.argv[1]).parent / 'backend'
sys.path.insert(0,str(backend))
from storage.capacity_delegation import install_readonly_capacity
install_readonly_capacity(int(sys.argv[5]), json.loads(sys.argv[6]), output=output,
                          job_id='guard-fixture', manifest_sha256='0'*64)
sys.path.remove(str(backend))
sqlite3.connect = safety.sqlite_guard(output, sqlite3.connect, ledger_path=ledger_path)
sys.addaudithook(safety.write_audit_guard(output, ledger_path=ledger_path))
backend=Path(sys.argv[1]).parent / 'backend'
sys.path.insert(0,str(backend))
import canary_release_policy
sys.path.remove(str(backend))
'''
    from storage.capacity_delegation import prepare_parent_claim, COMPONENTS
    # Synthetic offline scope only; this is not a real budget/source review.
    lease, fd, capability = prepare_parent_claim(output, 'guard-fixture', '0'*64,
        {'components': {key: 2*1024*1024 for key in COMPONENTS}, 'maximum_files': 200})
    try:
        result = subprocess.run([sys.executable, '-I', '-B', '-c', setup + source,
            str(Path(__file__).parent), str(output), str(ledger.path), json.dumps(identity), str(fd), json.dumps(capability)],
            env={'PATH': '/usr/bin:/bin'}, cwd=output, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, pass_fds=(fd,))
    finally:
        os.close(fd)
        lease.__exit__(*sys.exc_info())
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_create_only_publication_completes_under_real_write_guard(tmp_path):
    ledger, output = layout(tmp_path)
    result = fresh_guarded_child(ledger, output, '''
sys.path.insert(0, str(Path(sys.argv[1]).parent / 'backend'))
from storage.create_only_reports import create_only_bundle, publication_is_pending
from storage.report_storage import LocalFileStorage
root = output / 'reports'
root.mkdir(mode=0o700)
storage = LocalFileStorage(root)
arguments = dict(output_dir=str(root), filename='fixture.html',
    candidates=['fixture.html'], contents=[('fixture.html', b'private fixture', 'text/html')])
with create_only_bundle(storage, **arguments) as write:
    write()
    assert publication_is_pending(root, 'fixture.html')
    with sqlite3.connect(output / 'index.sqlite3') as connection:
        connection.execute('CREATE TABLE reports (filename TEXT PRIMARY KEY)')
        connection.execute('INSERT INTO reports VALUES (?)', ('fixture.html',))
assert not publication_is_pending(root, 'fixture.html')
assert storage.get_report('fixture.html').content == b'private fixture'
before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
try:
    with create_only_bundle(storage, **arguments): raise AssertionError('duplicate admitted')
except FileExistsError: pass
assert before == {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
assert all(p.stat().st_nlink == 1 for p in root.rglob('*') if p.is_file())
print('guarded create-only publication and collision verified')
''')
    assert 'collision verified' in result


def test_fresh_audit_allows_real_budget_reopen_settlement_and_journal_fdopen(tmp_path):
    ledger, output = layout(tmp_path)
    ledger.reserve_attempt('unknown', 'job', **RESERVATION)
    result = fresh_guarded_child(ledger, output, '''
ledger = CampaignBudget(ledger_path, identity)
seen_journal = []
original_append = ledger._append
def append(*args, **kwargs):
    original_append(*args, **kwargs)
    info = Path(str(ledger_path) + '-journal').stat()
    seen_journal.append(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600)
ledger._append = append
ledger.check()
ledger.settle_attempt('unknown', actual_tokens=3, usage_evidence_sha256='f' * 64)
assert seen_journal and all(seen_journal)
_Journal(SimpleNamespace(ledger=ledger)).record({'type': 'private-local-test'})
safety.Evidence(output).save('evidence.json', {'status': 'retained'})
fd = os.open(output / 'fdopen.json', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'w') as stream: stream.write('{}')
assert ledger.snapshot()['spent']['tokens'] == 6
print('private guards ok')
''')
    assert result.strip() == 'private guards ok'
    assert ledger.snapshot()['attempts']['unknown']['actual_tokens'] == 3
    assert ledger.snapshot()['spent']['tokens'] == RESERVATION['tokens']


@pytest.mark.parametrize('operation', [
    "open(ledger_path, 'r+b')",
    "os.open(ledger_path.with_suffix('.http.jsonl'), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)",
    "os.open(Path(str(ledger_path) + '-journal'), os.O_CREAT | os.O_RDWR, 0o600)",
])
def test_external_writable_open_requires_nofollow_and_exact_ledger_reopen(tmp_path, operation):
    ledger, output = layout(tmp_path)
    fresh_guarded_child(ledger, output, '''
try:
    result = ''' + operation + '''
except safety.ReplayAbort:
    pass
else:
    if isinstance(result, int): os.close(result)
    else: result.close()
    raise AssertionError('unsafe external writable open accepted')
''')


@pytest.mark.parametrize('operation', [
    "open(ledger_path, 'wb')", "os.unlink(ledger_path)",
    "os.rename(ledger_path, output / 'stolen')",
    "os.replace(output / 'replacement', ledger_path)",
    "os.truncate(ledger_path, 0)", "os.ftruncate(ledger_fd, 0)",
    "os.chmod(ledger_path, 0o644)",
    "open(output.parent / 'other-job' / 'report.json', 'w')",
    "open(output / '..' / 'escape.json', 'w')",
    "os.open('escape.json', os.O_CREAT | os.O_WRONLY, 0o600, dir_fd=outside_fd)",
    "os.symlink(ledger_path, output / 'link')",
    "os.link(ledger_path, output / 'hardlink')",
    "os.chmod(output, 0o755)",
    "__import__('subprocess').run([sys.executable, '-c', 'pass'])",
    "os.system('true')",
])
def test_fresh_audit_rejects_resets_cross_job_paths_links_and_subprocesses(tmp_path, operation):
    ledger, output = layout(tmp_path)
    (output / 'replacement').write_text('replacement')
    (tmp_path / 'other-job').mkdir(mode=0o700)
    inode, before = ledger.path.stat().st_ino, ledger.path.read_bytes()
    fresh_guarded_child(ledger, output, '''
ledger_fd = os.open(ledger_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
outside_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
try:
    ''' + operation + '''
except safety.ReplayAbort:
    pass
else:
    raise AssertionError('unsafe operation was accepted')
finally:
    os.close(ledger_fd)
    os.close(outside_fd)
''')
    assert ledger.path.stat().st_ino == inode and ledger.path.read_bytes() == before
    assert not (tmp_path / 'escape.json').exists()
    assert not (tmp_path / 'other-job' / 'report.json').exists()


def test_fresh_audit_creates_http_journal_privately_and_forbids_reset(tmp_path):
    ledger, output = layout(tmp_path)
    fresh_guarded_child(ledger, output, '''
path = ledger_path.with_suffix('.http.jsonl')
fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o666)
with os.fdopen(fd, 'ab') as stream: stream.write(b'{"receipt":1}\\n')
assert stat.S_IMODE(path.stat().st_mode) == 0o600
for operation in [lambda: path.open('w'), lambda: path.unlink(),
                  lambda: path.rename(output / 'removed'), lambda: os.truncate(path, 0)]:
    try: operation()
    except safety.ReplayAbort: pass
    else: raise AssertionError('HTTP journal reset accepted')
assert json.loads(path.read_text()) == {'receipt': 1}
''')


def test_fresh_audit_allows_only_precise_private_sqlite_wal_and_shm(tmp_path):
    ledger, output = layout(tmp_path)
    fresh_guarded_child(ledger, output, '''
connection = sqlite3.connect(ledger_path)
try:
    assert connection.execute('PRAGMA journal_mode=WAL').fetchone() == ('wal',)
    connection.execute('BEGIN')
    connection.execute('SELECT COUNT(*) FROM campaign_events').fetchone()
    ledger = CampaignBudget(ledger_path, identity)
    ledger.check()
    for suffix in ('-wal', '-shm'):
        info = Path(str(ledger_path) + suffix).stat()
        assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
    try:
        os.open(Path(str(ledger_path) + '-wal-other'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except safety.ReplayAbort:
        pass
    else:
        raise AssertionError('imprecise sidecar accepted')
finally:
    connection.close()
''')


@pytest.mark.parametrize('invalid', ['output_mode', 'ledger_mode', 'missing_ledger', 'ledger_symlink', 'ledger_hardlink'])
def test_guard_install_requires_private_existing_unlinked_layout(tmp_path, invalid):
    ledger, output = layout(tmp_path)
    path = ledger.path
    if invalid == 'output_mode': output.chmod(0o755)
    elif invalid == 'ledger_mode': path.chmod(0o644)
    elif invalid == 'missing_ledger': path.unlink()
    elif invalid == 'ledger_symlink':
        path = tmp_path / 'linked.sqlite3'
        path.symlink_to(ledger.path)
    else:
        os.link(path, tmp_path / 'linked.sqlite3')
    for factory in [lambda: safety.sqlite_guard(output, sqlite3.connect, ledger_path=path),
                    lambda: safety.write_audit_guard(output, ledger_path=path)]:
        with pytest.raises(safety.ReplayAbort): factory()


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'sidecar_symlink', 'sidecar_hardlink'])
def test_existing_link_escape_is_rejected_before_writing(tmp_path, kind):
    ledger, output = layout(tmp_path)
    target = tmp_path / 'unchanged'
    target.write_text('original')
    target.chmod(0o600)
    path = Path(str(ledger.path) + '-wal') if kind.startswith('sidecar') else output / 'linked'
    if kind.endswith('symlink'): path.symlink_to(target)
    else: os.link(target, path)
    guard = safety.write_audit_guard(output, ledger_path=ledger.path)
    with pytest.raises(safety.ReplayAbort):
        guard('open', (str(path), 'w', os.O_CREAT | os.O_WRONLY | os.O_TRUNC))
    assert target.read_text() == 'original'


def test_guarded_sqlite_preserves_append_only_schema_and_rechecks_pinned_identity(tmp_path):
    ledger, output = layout(tmp_path)
    connect = safety.sqlite_guard(output, sqlite3.connect, ledger_path=ledger.path)
    connection = connect(ledger.path)
    try:
        for sql in ['DROP TRIGGER campaign_events_no_delete', 'DROP TABLE campaign_events',
                    'DELETE FROM campaign_events', 'PRAGMA writable_schema=ON', 'VACUUM']:
            with pytest.raises(sqlite3.DatabaseError): connection.execute(sql)
        assert connection.execute('SELECT COUNT(*) FROM campaign_events').fetchone()[0] > 0
        ledger.path.rename(tmp_path / 'old.sqlite3')
        ledger.path.write_bytes(b'new inode')
        ledger.path.chmod(0o600)
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute('SELECT COUNT(*) FROM campaign_events')
    finally:
        connection.close()


def test_sqlite_native_temporary_storage_cannot_escape_job_directory(tmp_path):
    ledger, output = layout(tmp_path)
    connect = safety.sqlite_guard(output, sqlite3.connect, ledger_path=ledger.path)
    connection = connect(output / 'local.sqlite3')
    try:
        assert connection.execute('PRAGMA temp_store').fetchone() == (2,)
        for sql in ['PRAGMA temp_store=FILE', "PRAGMA temp_store_directory='/private/tmp'",
                    "VACUUM INTO '" + str(tmp_path / 'escape.sqlite3') + "'"]:
            with pytest.raises(sqlite3.DatabaseError): connection.execute(sql)
    finally:
        connection.close()
    assert not (tmp_path / 'escape.sqlite3').exists()


def test_import_is_inert_and_exact_readonly_git_shape_is_only_subprocess_exception(tmp_path, monkeypatch):
    import importlib.util
    import socket
    ledger, output = layout(tmp_path)
    guard = safety.write_audit_guard(output, code_root=Path(__file__).parent.parent, ledger_path=ledger.path)
    code = str(Path(__file__).parent.parent)
    guard('subprocess.Popen', ('git', ['git', '-C', code, 'rev-parse', 'HEAD'], None, None))
    guard('subprocess.Popen', ('git', ['git', '-C', code, 'status', '--porcelain=v1', '--untracked-files=normal'], None, None))
    for executable, argv in [('sh', ['git', '-C', code, 'rev-parse', 'HEAD']),
                             ('git', ['git', '-C', code, 'push'])]:
        with pytest.raises(safety.ReplayAbort): guard('subprocess.Popen', (executable, argv, None, None))
    def unexpected(*args, **kwargs): raise AssertionError('import must remain inert')
    monkeypatch.setattr(os, 'open', unexpected)
    monkeypatch.setattr(sqlite3, 'connect', unexpected)
    monkeypatch.setattr(socket, 'getaddrinfo', unexpected)
    monkeypatch.setattr(subprocess, 'Popen', unexpected)
    monkeypatch.setattr(sys, 'addaudithook', unexpected)
    spec = importlib.util.spec_from_file_location('inert_campaign_safety', safety.__file__)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
