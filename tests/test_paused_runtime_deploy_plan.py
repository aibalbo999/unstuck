import hashlib,importlib.util,json
from pathlib import Path
import pytest
from deployment_rq_pause import PauseError


def fixture(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('paused_runtime_plan',Path(__file__).resolve().parents[1]/'scripts/paused_runtime_deploy.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    root=tmp_path/'stock-agent';root.mkdir();case=tmp_path/'stock-agent-archives'/'case';case.mkdir(parents=True)
    entry=case/'entry.py';entry.write_text('# reviewed')
    p={'schema':'stock-agent.paused-deployment.v1','case':str(case),'expected_commit':'a'*40,'entrypoint':'entry.py','reviewed_scripts':{'entry.py':hashlib.sha256(entry.read_bytes()).hexdigest()},'queue_names':['stock-analysis'],'result_file':'result.json'}
    monkeypatch.setattr(m,'ROOT',root)
    monkeypatch.setattr(m.subprocess,'check_output',lambda args,**kw:b''if'diff'in args else'a'*40+'\n')
    return m,case,p


def test_default_plan_validation_has_no_redis_or_process_actions(tmp_path,monkeypatch):
    m,case,p=fixture(tmp_path,monkeypatch);path=case/'plan.json';path.write_text(json.dumps(p));assert m.validate(path)[0]==p

@pytest.mark.parametrize('case_name',['entry_drift','commit','unreviewed','escaped_result','dirty'])
def test_invalid_release_plan_fails_before_pause(tmp_path,monkeypatch,case_name):
    m,case,p=fixture(tmp_path,monkeypatch)
    if case_name=='entry_drift':(case/'entry.py').write_text('changed')
    if case_name=='commit':p['expected_commit']='b'*40
    if case_name=='unreviewed':p['entrypoint']='other.py'
    if case_name=='escaped_result':p['result_file']='../outside.json'
    if case_name=='dirty':monkeypatch.setattr(m.subprocess,'check_output',lambda args,**kw:b'changed'if'diff'in args else'a'*40+'\n')
    path=case/'plan.json';path.write_text(json.dumps(p))
    with pytest.raises(PauseError):m.validate(path)


def test_pause_intent_is_create_only_and_recovery_keeps_previous_bytes(tmp_path,monkeypatch):
    m,case,p=fixture(tmp_path,monkeypatch);path=case/'intent.json'
    m.write(path,{'owner':'first'});old=path.read_bytes()
    with pytest.raises(FileExistsError):m.write(path,{'owner':'other'})
    assert path.read_bytes()==old and path.stat().st_mode&0o777==0o600
    m.refresh(path,{'owner':'recovered'})
    assert json.loads(path.read_text())['owner']=='recovered'
    assert [x.read_bytes()for x in case.glob('intent.json.previous-*.json')]==[old]


def test_missing_worker_is_accepted_only_for_explicit_known_shutdown_recovery(tmp_path,monkeypatch):
    from rq import Worker
    m,case,p=fixture(tmp_path,monkeypatch);monkeypatch.setattr(Worker,'all',lambda **kw:[])
    with pytest.raises(PauseError):m.workers(object(),['stock-analysis'],drained=True)
    assert m.workers(object(),['stock-analysis'],drained=True,allow_absent=True)==[]


def test_revision_advance_requires_reviewed_ancestor_and_no_started_deployment(tmp_path,monkeypatch):
    from types import SimpleNamespace
    m,case,p=fixture(tmp_path,monkeypatch);previous={'commit':'b'*40}
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0))
    with pytest.raises(PauseError):m.validate_recovery_revision(previous,p,case)
    p['supersedes_commit']=previous['commit'];m.validate_recovery_revision(previous,p,case)
    (case/'before-state.json').write_text('{}')
    with pytest.raises(PauseError):m.validate_recovery_revision(previous,p,case)
