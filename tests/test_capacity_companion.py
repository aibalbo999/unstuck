"""Real bounded local processes; no providers, application services or sockets."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from storage import capacity_delegation as delegation
from test_storage_capacity_delegation import held


def test_parent_sigkill_keeps_child_capacity_until_readonly_lifetime_closes(tmp_path):
    project=Path(__file__).resolve().parents[1]
    script=r"""
import os,sys,json,time,subprocess
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,'/Volumes/X10 Pro Mac/project-system-tools/work')
import shared_capacity as shared
from storage import capacity_delegation as delegation
from storage.capacity_companion import CapacityCompanion
root=Path(sys.argv[2]);output=root/'output';output.mkdir(mode=0o700)
registry=root/'capacity-reservations'
delegation.REGISTRY=registry
delegation._shared=lambda:SimpleNamespace(REGISTRY=registry,external=shared.external,estimate_peak=shared.estimate_peak,
    Reservation=lambda peak,reserve,reason,**kw:shared.Reservation(peak,0,reason,**kw,directory=registry,
        legacy_directories=[root/'legacy'],available_fn=lambda:1024**3))
companion=CapacityCompanion(output,'job','0'*64,{'components':{k:1024**2 for k in delegation.COMPONENTS},'maximum_files':100})
child_source=r'''
import os,sys,json,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from storage import capacity_delegation as delegation
from storage.capacity import reserve_write
row=json.loads(sys.argv[4]);root=Path(row['output'])
delegation.REGISTRY=Path(sys.argv[5])
delegation.install_readonly_capacity(int(sys.argv[2]),row,output=root,job_id='job',manifest_sha256='0'*64,lifetime_fd=int(sys.argv[3]))
(root/'child-ready').write_text('ready')
end=time.monotonic()+2
number=0
while time.monotonic()<end:
    with reserve_write(root/'progress',100,'bounded local progress'):
        number+=1;(root/'progress').write_text(str(number))
    time.sleep(.025)
(root/'finished').write_text(str(number))
'''
child=subprocess.Popen([sys.executable,'-I','-B','-c',child_source,sys.argv[1],str(companion.readonly_fd),str(companion.reader),
    json.dumps(companion.capability),str(registry)],close_fds=True,pass_fds=(companion.readonly_fd,companion.reader),
    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
companion.handoff_complete()
(root/'ready.json').write_text(json.dumps({'parent':os.getpid(),'child':child.pid,'companion':companion.process.pid,'claim':companion.lease.id}))
time.sleep(20)
"""
    parent=subprocess.Popen([sys.executable,'-I','-B','-c',script,str(project/'backend'),str(tmp_path)],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+8
        while not (tmp_path/'output'/'child-ready').exists() and time.monotonic()<deadline:
            if parent.poll() is not None:break
            time.sleep(.02)
        assert (tmp_path/'output'/'child-ready').exists()
        info=json.loads((tmp_path/'ready.json').read_text());assert info['parent']==parent.pid
        progress=tmp_path/'output'/'progress'
        before=int(progress.read_text()) if progress.exists() else 0
        parent.kill();parent.wait(timeout=3)  # Only our exact Popen child is signalled.
        lock=tmp_path/'capacity-reservations'/(info['claim']+'.lock')
        with lock.open('rb') as stream:
            try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:pass
            else:raise AssertionError('Capacity vanished while the true child was alive')
        deadline=time.monotonic()+6
        while not (tmp_path/'output'/'finished').exists() and time.monotonic()<deadline:time.sleep(.02)
        assert int((tmp_path/'output'/'finished').read_text())>before
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:os.kill(info['companion'],0)
            except ProcessLookupError:break
            time.sleep(.02)
        else:raise AssertionError('Readonly lifetime closure left an orphan companion')
        with lock.open('rb') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(stream,fcntl.LOCK_UN)
        # History is retained, while kernel ownership has ended.
        assert lock.with_suffix('.json').exists()
    finally:
        if parent.poll() is None:parent.kill()
        parent.communicate(timeout=3)


def test_keeper_early_exit_refuses_before_any_true_child(held, monkeypatch):
    from storage import capacity_companion as module
    from storage.capacity_delegation import REGISTRY
    original = subprocess.Popen
    launches = []
    def early_exit(argv, **kwargs):
        launches.append(argv)
        return original([sys.executable, '-I', '-B', '-c', 'pass'], **kwargs)
    monkeypatch.setattr(module.subprocess, 'Popen', early_exit)
    with pytest.raises(RuntimeError, match='[Cc]apacity companion'):
        module.CapacityCompanion(held[3], 'new-job', '0'*64,
            {'components':{k:1024**2 for k in delegation.COMPONENTS}, 'maximum_files':100})
    assert len(launches)==1
    assert len([p for p in REGISTRY.glob('*.lock') if p.name!='registry.lock'])==1  # only the fixture's original lease


def test_keeper_death_is_detected_before_handoff(held):
    from storage.capacity_companion import CapacityCompanion
    companion=CapacityCompanion(held[3], 'new-job', '0'*64,
        {'components':{k:1024**2 for k in delegation.COMPONENTS}, 'maximum_files':100})
    try:
        companion.process.terminate();companion.process.wait(timeout=3)
        with pytest.raises(RuntimeError,match='[Cc]apacity companion'):
            companion.ensure_ready()
        assert companion.lease.receipt()['state']=='active'
    finally:companion.finish(child_never_started=True)
