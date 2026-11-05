"""Fresh private controllers do not depend on a test runner's sys.path/cache."""
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def guarded(tmp_path, source, *, project=ROOT):
    root = tmp_path.resolve()
    preamble = '''
import os, sys
from pathlib import Path
tests, project = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(tests))
from test_maintenance_rq_private_integration_child import install_boundary
install_boundary()
sys.path.remove(str(tests))
sys.path.insert(0, str(project / 'scripts'))
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', preamble + source,
        str(ROOT / 'tests'), str(project)], cwd=root,
        env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1',
             'STOCK_AGENT_PRIVATE_RQ_ROOT': str(root), 'STOCK_AGENT_PRIVATE_RQ_SOCKET': str(root / 'redis.sock')},
        capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr[-6000:]


def test_dispatch_imports_exact_harness_without_tests_or_backend_path(tmp_path):
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
bootstrap.load_control_bundle(bootstrap.control_digest())
import maintenance_canary_dispatch as dispatch
assert str(project / 'tests') not in sys.path
assert str(project / 'backend') not in sys.path
assert Path(dispatch.runner.__file__) == project / 'tests/quality_campaign_runner.py'
assert dispatch.CampaignBudget is sys.modules['quality_campaign_budget'].CampaignBudget
assert not any(name in sys.modules for name in ('config', 'api', 'analysis_jobs', 'dotenv'))
''')


def test_dispatch_never_executes_foreign_harness_on_sys_path(tmp_path):
    guarded(tmp_path, '''
shadow = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']) / 'shadow'
shadow.mkdir()
(shadow / 'quality_campaign_runner.py').write_text("raise AssertionError('Foreign harness executed')")
sys.path.insert(0, str(shadow))
import maintenance_entry as bootstrap
bootstrap.load_control_bundle(bootstrap.control_digest())
import maintenance_canary_dispatch as dispatch
assert Path(dispatch.runner.__file__) == project / 'tests/quality_campaign_runner.py'
''')


@pytest.mark.parametrize('case', ['real_preloaded', 'foreign_preloaded'])
def test_dispatch_requires_fresh_harness_not_preloaded_modules(tmp_path, case):
    setup = """
sys.path.insert(0, str(project / 'backend'))
sys.path.insert(0, str(tests)); import quality_campaign_runner
# Isolate the harness-preload rejection from the separate control-preload gate.
sys.modules.pop('canary_release_policy')
""" if case == 'real_preloaded' else '''
import types
sys.modules['quality_campaign_graph'] = types.ModuleType('quality_campaign_graph')
sys.path.insert(0, str(tests))
'''
    guarded(tmp_path, setup + '''
sys.path.insert(0, str(project / 'backend'))
try:
    import maintenance_entry as bootstrap
    bootstrap.load_control_bundle(bootstrap.control_digest())
except RuntimeError as error:
    assert 'Fresh' in str(error) and 'harness' in str(error), str(error)
else:
    raise AssertionError('Dispatcher accepted preloaded campaign code')
''')


def copy_controller(tmp_path):
    project = tmp_path / 'controller'
    scripts = ('maintenance_canary_dispatch', 'maintenance_canary_claim', 'maintenance_canary_settlement',
               'maintenance_canary_enrollment', 'maintenance_owned_process', 'maintenance_entry',
               'maintenance_legacy_inventory', 'maintenance_readiness', 'maintenance_control_sources')
    harness = ('runner', 'budget', 'wire', 'transport', 'watchdog', 'safety', 'graph')
    files = ['start_mac.command', 'backend/maintenance_state.py', 'backend/maintenance_guard.py',
             'backend/canary_release_policy.py']
    files += ['backend/storage/' + name + '.py' for name in ('__init__', 'capacity', 'capacity_delegation', 'capacity_companion', 'migrations', 'report_storage', '_local_file_operations', '_report_keys', 'memory_report_storage')]
    files += ['scripts/' + name + '.py' for name in scripts]
    files += ['tests/quality_campaign_' + name + '.py' for name in harness]
    for relative in files:
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    return project


def test_dispatch_compiles_source_not_same_timestamp_stale_bytecode(tmp_path):
    project = copy_controller(tmp_path)
    guarded(tmp_path, r'''
import py_compile
path = project / 'tests/quality_campaign_runner.py'
source = path.read_bytes() + b'\nLOADER_SOURCE_PROBE = 0\n'
path.write_bytes(source)
py_compile.compile(str(path), doraise=True)
info = path.stat()
path.write_bytes(source.replace(b'LOADER_SOURCE_PROBE = 0', b'LOADER_SOURCE_PROBE = 1'))
os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
import maintenance_entry as bootstrap
bootstrap.load_control_bundle(bootstrap.control_digest())
import maintenance_canary_dispatch as dispatch
assert dispatch.runner.LOADER_SOURCE_PROBE == 1, 'Stale timestamp bytecode was loaded'
''', project=project)


@pytest.mark.parametrize('case', ['source', 'module', 'capacity_module'])
def test_dispatch_preflight_rejects_loaded_source_or_module_drift(tmp_path, case):
    project = copy_controller(tmp_path)
    mutation = r'''
path = project / 'tests/quality_campaign_runner.py'
path.write_bytes(path.read_bytes() + b'\n# Changed after controller load\n')
''' if case == 'source' else '''
import types
sys.modules['quality_campaign_budget'] = types.ModuleType('quality_campaign_budget')
'''
    if case == 'capacity_module':
        mutation = '''
import types
foreign = types.ModuleType('storage.capacity_delegation')
def unverified_budget(*args, **kwargs):
    (root / 'unverified-capacity-called').touch()
    return {}
foreign.reviewed_budget = unverified_budget
sys.modules['storage.capacity_delegation'] = foreign
'''
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
bundle = bootstrap.load_control_bundle(bootstrap.control_digest())
bundle.module('canary_release_policy').require_canary_enabled = lambda: None
import maintenance_canary_dispatch as dispatch
sys.path.insert(0, str(tests))
from test_quality_campaign_owned_normal import reserved_normal_fixture
from maintenance_canary_claim import prepare_analysis_job, _analysis_enrollment
from maintenance_entry import control_digest
from redis import Redis
root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']) / 'campaign'
root.mkdir(mode=0o700)
plan, ledger = reserved_normal_fixture(root, 'v4')
from test_quality_campaign_runner import storage_review
storage_budget=storage_review(plan,ledger)
bound = {'campaign_id': 'fixture', 'job_id': 'job', 'ticker': '2330.TW',
         'pipeline_id': 'v4', 'manifest_sha256': plan.expected_sha, 'timeout_seconds': 45}
# Primitive enrolled-shape fixture; no socket call and no claim/launch proof.
job = prepare_analysis_job(Redis(), queue_name='import-only', binding=bound)
job.enqueued_at, job._status = job.created_at, 'queued'
raw = {k.encode(): v if type(v) is bytes else str(v).encode() for k, v in job.to_dict().items()}
values = {'queue_name': 'import-only', 'registered_hashes': {job.id: raw}, 'remaining': [job.id],
          'analysis_bindings': {job.id: bound}}
pins, order, bindings, digest = _analysis_enrollment(**values)
claimed = {'outcome': 'claimed', 'analysis_semantics_verified': True, 'job_id': job.id,
    'raw_snapshot': raw, 'enrollment_sha256': digest, 'analysis_invocation': {
        'function': 'analysis_jobs.run_stock_analysis_job', 'args': ['job', '2330.TW', 'v4'],
        'kwargs': {'force_refresh': False}, **bound}}
owner = dispatch.ClaimedCanaryDispatch(plan, ledger, **values, claimed=claimed,
    process_binding={'operation_id': 'import-only', 'control_sha256': control_digest(), 'backend_revision': 'b' * 40})
''' + mutation + '''
try:
    owner.start(storage_budget=storage_budget)
except dispatch.runner.ReplayAbort as error:
    assert 'controller' in str(error) and 'drift' in str(error), str(error)
else:
    raise AssertionError('Changed loaded harness was admitted')
assert not (root / 'unverified-capacity-called').exists(), 'Unbound capacity callable executed before controller verification'
assert owner.process_owner is None and not (root / 'job').exists()
assert ledger.snapshot()['jobs']['job']['status'] == 'active'
''', project=project)
