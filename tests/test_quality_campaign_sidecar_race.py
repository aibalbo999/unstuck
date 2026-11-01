"""Discriminate real DELETE-journal lifecycle from a private SQL guard denial."""
import json
import os
from pathlib import Path
import sqlite3
import threading

import pytest
import quality_campaign_safety as safety
from test_quality_campaign_safety import layout, fresh_guarded_child


@pytest.mark.parametrize('suffix', ['-journal', '-wal', '-shm'])
def test_unlinked_owned_private_sqlite_sidecar_is_observed_as_absent(tmp_path, monkeypatch, suffix):
    ledger, output = layout(tmp_path)
    target = Path(str(ledger.path) + suffix)
    observed = list(ledger.path.stat())
    observed[3] = 0  # macOS lstat during SQLite unlink, captured by real race below.
    lstat = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda path: os.stat_result(observed) if path == target else lstat(path))
    guarded = safety.sqlite_guard(output, sqlite3.connect, ledger_path=ledger.path)
    with guarded(':memory:') as connection:
        assert connection.execute('SELECT 1').fetchone() == (1,)


@pytest.mark.parametrize('kind', ['hardlink', 'public', 'foreign_owner', 'symlink', 'main', 'http'])
def test_unlinked_sidecar_handling_does_not_admit_other_unsafe_states(tmp_path, monkeypatch, kind):
    ledger, output = layout(tmp_path)
    target = ledger.path if kind == 'main' else ledger.path.with_suffix('.http.jsonl') if kind == 'http' else Path(str(ledger.path) + '-journal')
    observed = list(ledger.path.stat())
    observed[3] = 2 if kind == 'hardlink' else 0
    if kind == 'public': observed[0] = 0o100644
    if kind == 'foreign_owner': observed[4] += 1
    if kind == 'symlink': observed[0] = 0o120600
    lstat = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda path: os.stat_result(observed) if path == target else lstat(path))
    with pytest.raises((safety.ReplayAbort, sqlite3.DatabaseError)):
        guarded = safety.sqlite_guard(output, sqlite3.connect, ledger_path=ledger.path)
        guarded(':memory:')


def test_observing_unlinked_sidecar_does_not_authorize_writing_it(tmp_path, monkeypatch):
    ledger, output = layout(tmp_path)
    target = Path(str(ledger.path) + '-journal')
    observed = list(ledger.path.stat())
    observed[3] = 0
    lstat = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda path: os.stat_result(observed) if path == target else lstat(path))
    guard = safety.write_audit_guard(output, ledger_path=ledger.path)
    with pytest.raises(safety.ReplayAbort):
        guard('open', (str(target), None, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW))


def test_guarded_sql_remains_available_during_other_process_ledger_commits(tmp_path):
    ledger, output = layout(tmp_path)
    stopped, writer_errors, commits = threading.Event(), [], []
    def write():
        try:
            while not stopped.is_set():
                ledger.check()
                commits.append(True)
        except BaseException as error:
            writer_errors.append(type(error).__name__)
    thread = threading.Thread(target=write, name='private-sidecar-writer')
    thread.start()
    try:
        result = fresh_guarded_child(ledger, output, '''
import traceback
count, failures = 0, []
try:
    with sqlite3.connect(':memory:') as connection:
        for _ in range(5000):
            assert connection.execute('SELECT 1').fetchone() == (1,)
            count += 1
except BaseException:
    failures.append({'sql_error': traceback.format_exc()})
print(json.dumps({'reads': count, 'failures': failures}))
''')
    finally:
        stopped.set()
        thread.join(timeout=5)
    assert not thread.is_alive() and not writer_errors
    value = json.loads(result)
    assert commits and value['reads'] == 5000 and not value['failures'], json.dumps(value, indent=2)
