"""Offline checks for the one-off release and real-gap continuation safeguards."""
import importlib.util
from pathlib import Path
import sqlite3
import pytest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/evidence/source-acquisition/20261015/source-runtime-reconciliation'
def load(name):
 s=importlib.util.spec_from_file_location('test_source_guard_'+name,EVIDENCE/(name+'.py'))
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def test_target_checkpoint_pending_writes_are_bound_without_unrelated_scan(monkeypatch):
 m=load('reload_once')
 monkeypatch.setattr(m,'CHECKPOINT_ROWS',lambda db,target:['existing-checkpoint'])
 db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
 db.execute('create table writes(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,value blob)')
 db.executemany('insert into writes values(?,?,?,?,?,?,?,?)',[
  ('target','','cp','task',0,'x','msgpack',b'one'),('other','','cp','task',0,'x','msgpack',b'other')])
 first=m.checkpoint_state(db,{'thread_id':'target'})
 assert first['writes']['count']==1
 db.execute("update writes set value=? where thread_id='other'",(b'unrelated',))
 assert m.checkpoint_state(db,{'thread_id':'target'})==first
 db.execute("update writes set value=? where thread_id='target'",(b'changed',))
 assert m.checkpoint_state(db,{'thread_id':'target'})!=first


def test_static_startup_configuration_is_bound(monkeypatch):
 m=load('reload_once');monkeypatch.setattr(m,'inventory',lambda:{})
 for p in ('backend/model_routes.json','backend/prompts/runtime_rules.json','backend/requirements.txt','backend/static/index.html'):
  assert p in m.STATIC_INPUTS
  with pytest.raises(AssertionError,match=p):
   m.codecheck({'backend_inventory':{},'helper_dependencies':{},'static_inputs':{p:'not-the-current-hash'}})


def test_continuation_keeps_original_order_and_never_replays_prior_request(tmp_path,monkeypatch):
 m=load('institutional_continue');monkeypatch.setattr(m,'OLD',tmp_path)
 original={'targets':[{'ticker':'a'},{'ticker':'b'},{'ticker':'c'}]}
 audit={'rows':[{'ticker':'c','state':'unchanged_genuine_gap'},{'ticker':'a','state':'unchanged_genuine_gap'},{'ticker':'b','state':'snapshot_changed_excluded'}]}
 assert m.select_targets(original,audit,2)==[{'ticker':'a'},{'ticker':'c'}]
 p=tmp_path/'formal/a/attempt.json';p.parent.mkdir(parents=True);p.write_text('{}')
 with pytest.raises(AssertionError,match='Prior request never repeated'):m.select_targets(original,audit,2)
