import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import report_history_service as service
from report_paths import report_storage_key_for_filename,report_storage_candidates_for_filename

NAME='2069_TW_v4_report_job_e68cb50bf643.html'
NOW=2_000_000_000
DAY=86400

def bundle(tmp_path,ages,*,mixed=False):
 keys={}
 for kind,age in ages.items():
  candidates=report_storage_candidates_for_filename(NAME,kind=kind)
  key=candidates[-1]if mixed and kind=='html'else candidates[0]
  p=tmp_path/key;p.parent.mkdir(parents=True,exist_ok=True)
  p.write_bytes((kind+' original source timestamps unchanged').encode())
  os.utime(p,(NOW-age*DAY,NOW-age*DAY));keys[kind]=key
 return keys

@pytest.mark.parametrize('ages',[
 {'html':40,'md':40,'data':1},
 {'html':1,'md':40,'data':40},
 {'html':40,'md':40,'data':40,'review':1},
 {'html':40,'data':30},
])
def test_recent_member_preserves_entire_bundle_and_index(tmp_path,monkeypatch,ages):
 monkeypatch.setattr(service.time,'time',lambda:NOW);keys=bundle(tmp_path,ages)
 before={k:(tmp_path/k).read_bytes()for k in keys.values()};deleted=[]
 repo=SimpleNamespace(delete=lambda *args:deleted.append(args))
 assert service.cleanup_expired_reports(str(tmp_path),retention_days=30,repository=repo)==[]
 assert deleted==[]
 assert before=={k:(tmp_path/k).read_bytes()for k in keys.values()}

def test_wholly_expired_bundle_is_removed_together(tmp_path,monkeypatch):
 monkeypatch.setattr(service.time,'time',lambda:NOW);keys=bundle(tmp_path,{'html':40,'md':40,'data':40,'review':31},mixed=True)
 deleted=[];repo=SimpleNamespace(delete=lambda *args:deleted.append(args));cache={'2069.TW':NAME}
 actual=service.cleanup_expired_reports(str(tmp_path),cache,30,repository=repo)
 assert set(actual)==set(keys.values())
 assert deleted==[(NAME,str(tmp_path))]and cache=={}
 assert all(not(tmp_path/k).exists()for k in keys.values())

def test_mixed_legacy_html_and_partitioned_review_are_not_orphans(tmp_path):
 keys=bundle(tmp_path,{'html':40,'review':1,'data':1,'md':40},mixed=True)
 assert service.cleanup_orphan_markdown_reports(str(tmp_path))==[]
 assert all((tmp_path/k).exists()for k in keys.values())
