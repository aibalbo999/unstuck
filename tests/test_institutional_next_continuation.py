import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'docs/evidence/source-acquisition/20261015/source-runtime-reconciliation/institutional_continue_next.py'
def helper():
    s=importlib.util.spec_from_file_location('next_continuation_test',PATH)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_excludes_any_previous_current_batch_attempt(tmp_path,monkeypatch):
    m=helper();monkeypatch.setattr(m,'OLD',tmp_path/'old');monkeypatch.setattr(m,'PRIOR',tmp_path/'prior')
    p=m.PRIOR/'one/attempt.json';p.parent.mkdir(parents=True);p.write_text('{}')
    with pytest.raises(AssertionError,match='Prior request never repeated'):
        m.select_targets({'targets':[{'ticker':'one'}]},{'rows':[{'ticker':'one','state':'unchanged_genuine_gap'}]})

def test_dispatch_cutoff_stops_before_any_post(tmp_path,monkeypatch):
    m=helper();path=tmp_path/'attempt.json';attempt={'state':'one_post_prepared','POST_count':0}
    m.c.persist(path,attempt,create=True);posts=[]
    class Reply:
        def raise_for_status(self):pass
        def json(self):return {'mutation_header':'test','mutation_token':'not-a-real-token'}
    class Client:
        def get(self,*a,**k):return Reply()
        def post(self,*a,**k):posts.append(a);raise AssertionError('POST must not occur')
    monkeypatch.setattr(m.time,'time',lambda:m.LATEST_SAFE_DISPATCH)
    with pytest.raises(AssertionError,match='dispatch window closed'):
        m.bounded_send_once(Client(),{'filename':'x.html'},attempt,path,pre_dispatch=lambda:None)
    assert posts==[]
    saved=m.c.load(path)
    assert saved['state']=='pre_dispatch_failed_no_POST' and saved['POST_count']==0

def test_run_after_deadline_does_not_read_contract_or_create_attempt(monkeypatch):
    m=helper();monkeypatch.setattr(m.time,'time',lambda:m.LATEST_SAFE_DISPATCH+1)
    monkeypatch.setattr(m,'bind',lambda:pytest.fail('must stop before bind'))
    with pytest.raises(AssertionError,match='no attempt'):m.run('one')

def test_previous_batch_requires_all_ten_verified_receipts(monkeypatch):
    m=helper()
    def load(path):
        if path==m.PRIOR_CONTRACT:return {'targets':[{'ticker':str(i)}for i in range(10)]}
        return {'not_attempted':['9'],'completed':[str(i)for i in range(9)]}
    monkeypatch.setattr(m.c,'load',load);monkeypatch.setattr(m.c,'file_hash',lambda p:'test')
    monkeypatch.setattr(m.c,'completed_receipts',lambda *a:{str(i):{}for i in range(9)})
    with pytest.raises(AssertionError):m.runtime()
