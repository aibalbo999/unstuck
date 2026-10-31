import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'docs/evidence/source-acquisition/20261015/source-runtime-reconciliation/institutional_continue_mature.py'

def helper():
    spec = importlib.util.spec_from_file_location('mature_continuation_test', PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

def inputs():
    original = {'ticker': 'one', 'filename': 'one.html', 'data_sha256': 'original',
                'expected_session': '2026-10-14', 'required_current_dates': ['2026-10-14'],
                'missing_current_pairs': [['2026-10-14', 'foreign']], 'current_admission': {'eligible': False}}
    current = {**original, 'expected_session': '2026-10-15', 'required_current_dates': ['2026-10-15'],
               'missing_current_pairs': [['2026-10-15', 'foreign']]}
    return {'targets': [original]}, {'rows': [{'ticker': 'one', 'state': 'unchanged_genuine_gap', 'target': current}]}

@pytest.mark.parametrize('root_name', ['PRIOR', 'SECOND'])
def test_never_repeats_prior_attempt_even_if_no_post(root_name, tmp_path, monkeypatch):
    m = helper()
    for name in ('OLD', 'PRIOR', 'SECOND'):
        monkeypatch.setattr(m, name, tmp_path / name)
    path = getattr(m, root_name) / 'one/attempt.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"POST_count":0}')
    with pytest.raises(AssertionError, match='Prior request never repeated'):
        m.select_targets(*inputs())

def test_only_maturity_fields_may_change(tmp_path, monkeypatch):
    m = helper()
    for name in ('OLD', 'PRIOR', 'SECOND'):
        monkeypatch.setattr(m, name, tmp_path / name)
    original, audit = inputs()
    assert m.select_targets(original, audit)[0]['data_sha256'] == 'original'
    audit['rows'][0]['target']['data_sha256'] = 'replacement'
    with pytest.raises(AssertionError):
        m.select_targets(original, audit)

def test_expired_window_contract_is_rejected(tmp_path, monkeypatch):
    m = helper()
    for name in ('OLD', 'PRIOR', 'SECOND'):
        monkeypatch.setattr(m, name, tmp_path / name)
    original, audit = inputs()
    audit['rows'][0]['target'] = original['targets'][0]
    with pytest.raises(AssertionError):
        m.select_targets(original, audit)

def test_deadline_prevents_post_after_preparation(tmp_path, monkeypatch):
    m = helper()
    path = tmp_path / 'attempt.json'
    attempt = {'state': 'one_post_prepared', 'POST_count': 0}
    m.c.persist(path, attempt, create=True)
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'mutation_header': 'test', 'mutation_token': 'test-only'}
    class Client:
        def get(self, *a, **k): return Reply()
        def post(self, *a, **k): pytest.fail('POST must not be sent')
    monkeypatch.setattr(m.time, 'time', lambda: m.LATEST_SAFE_DISPATCH)
    with pytest.raises(AssertionError, match='dispatch window closed'):
        m.bounded_send_once(Client(), {'filename': 'one.html'}, attempt, path, pre_dispatch=lambda: None)
    assert m.c.load(path)['state'] == 'pre_dispatch_failed_no_POST'
    assert m.c.load(path)['POST_count'] == 0
