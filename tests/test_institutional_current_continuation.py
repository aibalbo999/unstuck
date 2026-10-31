"""One-shot continuation must preserve old cohort identity and changed exclusions."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'docs/evidence/source-acquisition/20261015/source-runtime-reconciliation/institutional_continue_current.py'

def helper():
    spec = importlib.util.spec_from_file_location('current_continuation_test', PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_changed_and_prior_targets_excluded_without_reordering(tmp_path, monkeypatch):
    m = helper(); monkeypatch.setattr(m, 'OLD', tmp_path)
    original = {'targets': [{'ticker': x} for x in ('one', 'reconstructed', 'prior', 'two')]}
    audit = {'rows': [
        {'ticker': 'two', 'state': 'unchanged_genuine_gap'},
        {'ticker': 'prior', 'state': 'prior_attempt_excluded'},
        {'ticker': 'reconstructed', 'state': 'snapshot_changed_excluded'},
        {'ticker': 'one', 'state': 'unchanged_genuine_gap'}]}
    assert m.select_targets(original, audit) == [{'ticker': 'one'}, {'ticker': 'two'}]

def test_any_existing_attempt_is_never_replayed(tmp_path, monkeypatch):
    m = helper(); monkeypatch.setattr(m, 'OLD', tmp_path)
    p = tmp_path / 'formal/one/attempt.json'; p.parent.mkdir(parents=True)
    p.write_text('{"state":"unknown_outcome_do_not_resubmit"}')
    with pytest.raises(AssertionError, match='Prior request never repeated'):
        m.select_targets({'targets': [{'ticker': 'one'}]}, {'rows': [{'ticker': 'one', 'state': 'unchanged_genuine_gap'}]})

def test_runtime_rejects_an_unproven_state_before_identity_or_http(monkeypatch):
    m = helper()
    monkeypatch.setattr(m.c, 'load', lambda path: {'state': 'launcher_requested'})
    with pytest.raises(AssertionError):
        m.runtime()

def test_runtime_rejects_scope_drift_before_http(monkeypatch):
    m = helper()
    monkeypatch.setattr(m.c, 'load', lambda path: {'state': 'runtime_healthy_data_preserved_zero_call_gate_failed', 'source_files': {'x': 'old'}} if path.name == 'post-reload-readback-v2.json' else {'files': {'x': 'new'}})
    with pytest.raises(AssertionError):
        m.runtime()

def test_current_window_is_ticker_specific_and_rejects_boundary_change(monkeypatch):
    import institutional_source_refresh as refresh
    import official_institutional_source as official
    m = helper(); calls = []
    monkeypatch.setattr(refresh, 'institutional_refresh_session', lambda ticker: calls.append(ticker) or '2026-10-14')
    monkeypatch.setattr(official, 'expected_sessions', lambda ticker, now, count: ['2026-10-14'])
    m.check_window({'ticker': '1528.TW', 'required_current_dates': ['2026-10-14']})
    assert calls == ['1528.TW']
    with pytest.raises(AssertionError):
        m.check_window({'ticker': '1528.TW', 'required_current_dates': ['2026-10-15']})
