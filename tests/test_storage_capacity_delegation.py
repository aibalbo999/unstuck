"""Private synthetic capabilities; no real reviews, providers or runtime DBs."""
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from storage.capacity import StorageCapacityUnavailable
from storage import capacity_delegation as delegation


@pytest.fixture
def held(tmp_path, monkeypatch):
    sys.path.insert(0, '/Volumes/X10 Pro Mac/project-system-tools/work')
    import shared_capacity as core
    registry = tmp_path / 'capacity-reservations'
    original = core.Reservation
    # Exercise the real lock/ledger implementation in an isolated registry.
    # No default/shared registry or native FDM mirror is mutated by this fixture.
    monkeypatch.setattr(core, 'volume_guard', lambda: None)
    engine = SimpleNamespace(REGISTRY=registry, external=core.external, estimate_peak=core.estimate_peak,
        Reservation=lambda peak,reserve,reason,**kw: original(peak,0,reason,**kw,
            directory=registry,legacy_directories=[tmp_path/'legacy-claims'],available_fn=lambda:1024**3))
    monkeypatch.setattr(delegation, '_shared', lambda: engine)
    monkeypatch.setattr(delegation, 'REGISTRY', registry)
    output = tmp_path / 'private';output.mkdir(mode=0o700)
    lease, fd, row = delegation.prepare_parent_claim(output,'job','0'*64,
        {'components':{key:1024**2 for key in delegation.COMPONENTS},'maximum_files':100})
    try:
        yield lease,fd,row,output
    finally:
        os.close(fd)
        if lease.receipt()['state']=='active':lease.__exit__(None,None,None)


def capability(held, **override):
    lease,fd,row,output=held
    return delegation.ReadonlyCapacity(fd,{**row,**override},output=output,job_id='job',manifest_sha256='0'*64)


def test_readonly_capability_rejects_wrong_identity_writable_fd_and_lost_lease(held):
    lease,fd,row,output=held
    cap=capability(held)
    with pytest.raises(StorageCapacityUnavailable):capability(held,job_id='wrong')
    with pytest.raises(StorageCapacityUnavailable):capability(held,limit_bytes=1)
    with pytest.raises(StorageCapacityUnavailable):
        delegation.ReadonlyCapacity(lease.claim_fds()[0],row,output=output,job_id='job',manifest_sha256='0'*64)
    lease.__exit__(None,None,None)
    with pytest.raises((StorageCapacityUnavailable,OSError)):cap.check()


def test_fixed_pool_rejects_unknown_outside_and_oversize_without_writes(held):
    cap=capability(held);root=held[3]
    for path,size in ((root/'..'/'escape',1),(root/'new',None),(root/'new',10*1024**2)):
        with pytest.raises(StorageCapacityUnavailable):
            with cap.reserve(path,size):raise AssertionError('unadmitted writer ran')
    assert list(root.iterdir())==[] and cap.active=={}


def test_parallel_tasks_count_separately_and_cancel_releases_pool(held):
    cap=capability(held);root=held[3]
    async def run():
        begun=asyncio.Event()
        async def hold():
            with cap.reserve(root/'first',3*1024**2):
                begun.set();await asyncio.Event().wait()
        first=asyncio.create_task(hold());await begun.wait()
        with pytest.raises(StorageCapacityUnavailable):
            with cap.reserve(root/'second',3*1024**2):pass
        first.cancel()
        with pytest.raises(asyncio.CancelledError):await first
        with cap.reserve(root/'second',3*1024**2):pass
    asyncio.run(run())
    assert cap.active=={}


def test_existing_output_growth_is_included_before_next_write(held):
    cap=capability(held);root=held[3]
    (root/'existing').write_bytes(b'x'*(4*1024**2))
    with pytest.raises(StorageCapacityUnavailable):
        with cap.reserve(root/'new',2*1024**2):pass
    assert not (root/'new').exists()


def test_review_budget_requires_exact_pinned_complete_estimate(tmp_path):
    with pytest.raises(StorageCapacityUnavailable):
        delegation.reviewed_budget(None,manifest_sha256='0'*64,job_id='job',source_bytes=1)
    row={'schema':'stock.storage-budget-review.v1','decision':'reviewed','manifest_sha256':'0'*64,
         'job_id':'job','components':{key:100 for key in delegation.COMPONENTS},'maximum_files':20,
         'basis':{key:'offline synthetic estimate, not real review' for key in delegation.COMPONENTS}}
    path=tmp_path/'review.json';path.write_text(json.dumps(row))
    ref={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    assert delegation.reviewed_budget(ref,manifest_sha256='0'*64,job_id='job',source_bytes=100)==row
    with pytest.raises(StorageCapacityUnavailable):
        delegation.reviewed_budget(ref,manifest_sha256='0'*64,job_id='job',source_bytes=101)
    path.write_text('{}')
    with pytest.raises(StorageCapacityUnavailable):
        delegation.reviewed_budget(ref,manifest_sha256='0'*64,job_id='job',source_bytes=1)


def test_new_campaign_missing_review_refuses_before_output_or_launch(tmp_path,monkeypatch):
    from test_quality_campaign_runner import reserved
    import quality_campaign_runner as runner
    plan,manifest,ledger=reserved(tmp_path)
    monkeypatch.setattr(runner.canary_release_policy,'require_canary_enabled',lambda:None)
    launched=[]
    monkeypatch.setattr(runner,'run_reserved_process',lambda *a,**kw:launched.append(True))
    with pytest.raises(StorageCapacityUnavailable):runner.execute_reserved_job(plan,ledger,'job')
    assert launched==[] and not (ledger.path.parent/'job').exists()


def test_maintenance_missing_budget_keeps_owner_and_output_unstarted(tmp_path):
    from test_maintenance_canary_dispatch_imports import guarded
    guarded(tmp_path, """
import maintenance_entry as bootstrap
bootstrap.load_control_bundle(bootstrap.control_digest())
import maintenance_canary_dispatch as module
module.canary_release_policy.require_canary_enabled=lambda:None
obj=object.__new__(module.ClaimedCanaryDispatch)
launched=[]
obj._start=lambda:launched.append(True)
try:
    obj.start()
except module.runner.ReplayAbort as error:
    assert 'Reviewed storage budget' in str(error)
else:
    raise AssertionError('Unknown storage budget admitted')
assert launched==[]
""")


@pytest.mark.parametrize('case',['write','outside','oversize','binding'])
def test_real_guarded_child_receives_only_readonly_capacity_and_guardian_reaps(held,tmp_path,case):
    from test_quality_campaign_budget import active
    from quality_campaign_watchdog import run_reserved_process
    lease,fd,row,output=held
    ledger=active(tmp_path)
    source = r"""
import os,sys,json,fcntl
from pathlib import Path
readonly_fd=int(sys.argv[3]);claims=json.loads(sys.argv[6])
assert fcntl.fcntl(readonly_fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY
for original in claims:
    try:os.fstat(original)
    except OSError:pass
    else:raise AssertionError('Writable parent lease leaked into real child')
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
from storage import capacity_delegation as delegation
from storage.capacity import reserve_write,StorageCapacityUnavailable
from quality_campaign_safety import write_audit_guard
row=json.loads(sys.argv[4]);root=Path(row['output']);case=sys.argv[8]
delegation.REGISTRY=Path(sys.argv[5])
if case=='binding':row['job_id']='other-job'
try:
    delegation.install_readonly_capacity(readonly_fd,row,output=root,job_id='job',manifest_sha256='0'*64)
except StorageCapacityUnavailable:
    assert case=='binding'
    raise SystemExit(0)
assert case!='binding'
sys.addaudithook(write_audit_guard(root,ledger_path=Path(sys.argv[7])))
target=root/'artifact.txt' if case!='outside' else root.parent/'escape'
amount=10*1024**2 if case=='oversize' else 100
try:
    with reserve_write(target,amount,'private synthetic guarded write'):
        target.write_bytes(b'unknown remains unknown')
except StorageCapacityUnavailable:
    assert case in ('outside','oversize')
else:
    assert case=='write'
"""
    project=Path(__file__).resolve().parents[1]
    result=run_reserved_process(ledger,'job',[sys.executable,'-I','-B','-c',source,
        str(project/'backend'),str(project/'tests'),str(fd),json.dumps(row),str(delegation.REGISTRY),
        json.dumps(list(lease.claim_fds())),str(ledger.path),case],env={'PATH':'/usr/bin:/bin'},
        output_dir=output,capacity_lease=lease,capacity_read_fd=fd,term_grace=.05)
    assert result['returncode']==0 and result['cleanup_verified']
    assert lease._guardian_started and lease._guardian_cleanup_confirmed
    assert lease.receipt()['state']=='active'  # Parent owns release after cleanup.
    assert (output/'artifact.txt').exists()==(case=='write')
    assert not (tmp_path/'escape').exists()


def test_uncertain_guardian_cleanup_keeps_parent_claim(held,tmp_path,monkeypatch):
    from test_quality_campaign_runner import reserved,storage_review
    import quality_campaign_runner as runner
    plan,_,ledger=reserved(tmp_path)
    monkeypatch.setattr(runner.canary_release_policy,'require_canary_enabled',lambda:None)
    lease,fd,row,output=held
    # Replace only parent claim preparation; the already-held real isolated
    # kernel lease remains evidence when the owned cleanup result is unknown.
    monkeypatch.setattr(delegation,'prepare_parent_claim',lambda *a,**k:(lease,os.dup(fd),row))
    def uncertain(*a,**kw):
        kw['capacity_lease']._guardian_started=True
        kw['capacity_lease']._guardian_cleanup_confirmed=False
        raise runner.CleanupUnconfirmed('synthetic unknown descendant cleanup')
    monkeypatch.setattr(runner,'run_reserved_process',uncertain)
    with pytest.raises(runner.CleanupUnconfirmed):
        runner.execute_reserved_job(plan,ledger,'job',storage_budget=storage_review(plan,ledger))
    assert lease in runner._UNCONFIRMED_STORAGE_CLAIMS
    assert lease.receipt()['state']=='active'
    assert (delegation.REGISTRY/(lease.id+'.json')).exists()
    runner._UNCONFIRMED_STORAGE_CLAIMS.remove(lease)  # No process was spawned by this injected case.



def test_tiny_file_sequence_consumes_allocated_pool_and_keeps_existing_bytes(held):
    root=held[3]/'tiny';root.mkdir()
    lease,fd,row=delegation.prepare_parent_claim(root,'tiny','0'*64,
        {'components':{key:32768 for key in delegation.COMPONENTS},'maximum_files':100})
    cap=delegation.ReadonlyCapacity(fd,row,output=root,job_id='tiny',manifest_sha256='0'*64)
    written=[]
    try:
        for number in range(50):
            try:
                with cap.reserve(root/str(number),1):(root/str(number)).write_bytes(b'x')
            except StorageCapacityUnavailable:
                break
            written.append(str(number))
        else:raise AssertionError('Tiny files rolled indefinitely through the fixed byte pool')
        assert 0<len(written)<50
        assert {p.name:p.read_bytes() for p in root.iterdir()}=={name:b'x' for name in written}
        assert cap.used_bytes()>sum(p.stat().st_size for p in root.iterdir())
    finally:
        os.close(fd);lease.__exit__(None,None,None)


def test_guarded_exact_pool_does_not_count_own_materialized_bytes_twice(held):
    from storage.capacity import reserve_write,account_materialized
    root=held[3]/'exact-pool';root.mkdir();prior=root/'prior';prior.write_bytes(b'old')
    # root+one existing file as measured by ReadonlyCapacity.used_bytes, and
    # exactly one outer known write estimate, with no spare room for double count.
    limit=4096+8192+((20000+65536)*6+4)//5
    components={key:1 for key in delegation.COMPONENTS};components['artifacts']=limit-4
    lease,fd,row=delegation.prepare_parent_claim(root,'exact','0'*64,
        {'components':components,'maximum_files':10})
    cap=delegation.ReadonlyCapacity(fd,row,output=root,job_id='exact',manifest_sha256='0'*64)
    token=delegation._DELEGATED.set(cap)
    try:
        with reserve_write(root,20000,'exact parent budget'):
            with reserve_write(prior,12000,'first materialization'),account_materialized((prior,)):
                prior.write_bytes(b'x'*12000)
            extra=root/'second'
            with reserve_write(extra,1000,'second materialization'),account_materialized((extra,)):
                extra.write_bytes(b'y'*1000)
            with reserve_write(prior,3,'original-byte rollback'),account_materialized((prior,)):
                prior.write_bytes(b'old')
        assert prior.read_bytes()==b'old' and extra.read_bytes()==b'y'*1000
        assert cap.active=={}
    finally:
        delegation._DELEGATED.reset(token);os.close(fd);lease.__exit__(None,None,None)
