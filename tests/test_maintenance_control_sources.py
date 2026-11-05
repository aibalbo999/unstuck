"""Actual public entry and fresh controller imports, confined to private copies."""
import pytest
from test_maintenance_canary_dispatch_imports import copy_controller, guarded


def test_public_entry_uses_current_guard_source_not_valid_timestamp_bytecode(tmp_path):
    project = copy_controller(tmp_path)
    guarded(tmp_path, r'''
import json, py_compile, subprocess
path = project / 'backend/maintenance_guard.py'
source = path.read_bytes() + b'\ndef read_state(root): return {"phase": "old_source"}\n'
path.write_bytes(source)
py_compile.compile(str(path), doraise=True)
info = path.stat()
path.write_bytes(source.replace(b'old_source', b'new_source'))
os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']) / 'status-only'
root.mkdir()
result = subprocess.run([sys.executable, '-I', '-B', str(project / 'scripts/maintenance_entry.py'),
    '--maintenance-status'], env={'PATH': '/usr/bin:/bin', 'STOCK_AGENT_MAINTENANCE_DIR': str(root)},
    cwd=root, capture_output=True, text=True, timeout=10)
assert result.returncode == 0, result.stderr
assert json.loads(result.stdout)['phase'] == 'new_source', result.stdout
''', project=project)


def test_approved_bundle_loads_all_controls_without_application_or_credentials(tmp_path):
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
expected = bootstrap.control_digest()
bundle = bootstrap.load_control_bundle(expected)
proof = bundle.verify()
assert proof['control_sha256'] == expected
assert set(proof['loaded_control_files']) | set(proof['loaded_harness_files']) == set(bootstrap.CONTROL_FILES) - {
    'start_mac.command', 'scripts/maintenance_control_sources.py'}
assert proof['bootstrap_source_sha256']
assert proof['shell_execution_verified'] is proof['production_ready'] is False
assert bundle.module('maintenance_canary_dispatch') is sys.modules['maintenance_canary_dispatch']
assert not any(name in sys.modules for name in ('config', 'api', 'analysis_jobs', 'dotenv'))
assert str(project / 'tests') not in sys.path and str(project / 'backend') not in sys.path
''')


@pytest.mark.parametrize('name', ['maintenance_guard', 'maintenance_canary_claim', 'quality_campaign_graph', 'storage', 'storage.capacity', 'storage.capacity_delegation', 'storage.capacity_companion'])
def test_bundle_rejects_preloaded_controls_or_harness_before_compilation(tmp_path, name):
    guarded(tmp_path, '''
import maintenance_entry as bootstrap, types
name = ''' + repr(name) + '''
foreign = types.ModuleType(name)
sys.modules[name] = foreign
try:
    bootstrap.load_control_bundle(bootstrap.control_digest())
except RuntimeError as error:
    assert 'Fresh' in str(error), str(error)
else:
    raise AssertionError('Unverified preloaded code was adopted')
assert sys.modules[name] is foreign
assert 'maintenance_canary_dispatch' not in sys.modules
''')


def test_bundle_rejects_changed_source_before_executing_it(tmp_path):
    project = copy_controller(tmp_path)
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
expected = bootstrap.control_digest()
path = project / 'scripts/maintenance_canary_claim.py'
path.write_bytes(b"raise AssertionError('Unapproved code executed')\\n" + path.read_bytes())
try:
    bootstrap.load_control_bundle(expected)
except RuntimeError as error:
    assert 'digest' in str(error), str(error)
else:
    raise AssertionError('Changed controls admitted')
assert 'maintenance_canary_claim' not in sys.modules
''', project=project)


@pytest.mark.parametrize('option', ['separate', 'equals', 'abbreviated'])
@pytest.mark.parametrize('relative', ['backend/maintenance_guard.py', 'tests/quality_campaign_runner.py'])
def test_public_entry_rejects_unapproved_plan_before_any_control_exec(tmp_path, option, relative):
    project = copy_controller(tmp_path)
    guarded(tmp_path, '''
import maintenance_entry as bootstrap, json, subprocess
expected = bootstrap.control_digest()
root = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT'])
plan = root / 'plan.json'
plan.write_text(json.dumps({'control_sha256': expected}))
marker = root / 'unapproved-executed'
path = project / ''' + repr(relative) + '''
path.write_text(path.read_text() + '\\nfrom pathlib import Path\\nPath(' + repr(str(marker)) + ').touch()\\n')
kind = ''' + repr(option) + '''
args = ['--maintenance-arm', str(plan)] if kind == 'separate' else [
    ('--maintenance-ar=' if kind == 'abbreviated' else '--maintenance-arm=') + str(plan)]
result = subprocess.run([sys.executable, '-I', '-B', str(project / 'scripts/maintenance_entry.py'), *args],
    env={'PATH': '/usr/bin:/bin', 'STOCK_AGENT_MAINTENANCE_DIR': str(root / 'state')},
    cwd=root, capture_output=True, text=True, timeout=10)
assert result.returncode == 75, (result.stdout, result.stderr)
assert not marker.exists(), 'Unapproved controls executed before plan validation'
assert not (root / 'state').exists()
''', project=project)


def test_harness_changed_after_capture_is_never_executed(tmp_path):
    project = copy_controller(tmp_path)
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
expected = bootstrap.control_digest()
capture = bootstrap._control_sources
marker = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']) / 'late-harness-executed'
path = project / 'tests/quality_campaign_runner.py'
def capture_then_change():
    sources = capture()
    path.write_text(path.read_text() + '\\nfrom pathlib import Path\\nPath(' + repr(str(marker)) + ').touch()\\n')
    return sources
bootstrap._control_sources = capture_then_change
try:
    bootstrap.load_control_bundle(expected)
except BaseException as error:
    assert 'drift' in str(error), str(error)
else:
    raise AssertionError('Changed harness after snapshot was accepted')
assert not marker.exists(), 'Later harness bytes executed instead of captured snapshot'
''', project=project)


@pytest.mark.parametrize('case', ['source', 'module', 'spec', 'finder', 'harness_module', 'harness_spec', 'capacity_source', 'capacity_module', 'capacity_loaded_sha'])
def test_bound_controls_detect_drift_before_next_action(tmp_path, case):
    project = copy_controller(tmp_path)
    mutation = {
        'capacity_source': "path = project / 'backend/storage/capacity_companion.py'; path.write_bytes(path.read_bytes() + b'\\n# changed\\n')",
        'capacity_module': "import types; sys.modules['storage.capacity_delegation'] = types.ModuleType('storage.capacity_delegation')",
        'capacity_loaded_sha': "sys.modules['storage.capacity']._control_source_sha256 = '0'*64",
        'source': "path = project / 'scripts/maintenance_canary_claim.py'; path.write_bytes(path.read_bytes() + b'\\n# changed\\n')",
        'module': "import types; sys.modules['maintenance_canary_claim'] = types.ModuleType('maintenance_canary_claim')",
        'spec': "sys.modules['maintenance_canary_claim'].__spec__ = None",
        'finder': "sys.meta_path.remove(bundle)",
        'harness_module': "import types; sys.modules['quality_campaign_wire'] = types.ModuleType('quality_campaign_wire')",
        'harness_spec': "sys.modules['quality_campaign_wire'].__spec__ = None",
    }[case]
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
bundle = bootstrap.load_control_bundle(bootstrap.control_digest())
''' + mutation + '''
try:
    bundle.verify()
except RuntimeError as error:
    assert 'drift' in str(error), str(error)
else:
    raise AssertionError('Loaded control drift accepted')
''', project=project)


@pytest.mark.parametrize('relative,name', [
    ('scripts/maintenance_canary_claim.py', 'maintenance_canary_claim'),
    ('tests/quality_campaign_runner.py', 'quality_campaign_runner'),
])
@pytest.mark.parametrize('action', ['reload', 'reimport'])
def test_bound_controls_reject_reload_before_changed_source_executes(tmp_path, relative, name, action):
    project = copy_controller(tmp_path)
    guarded(tmp_path, '''
import maintenance_entry as bootstrap, importlib
bundle = bootstrap.load_control_bundle(bootstrap.control_digest())
marker = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']) / 'reload-executed'
path = project / ''' + repr(relative) + '''
path.write_text(path.read_text() + '\\nfrom pathlib import Path\\nPath(' + repr(str(marker)) + ').touch()\\n')
sys.path.insert(0, str(path.parent))
name, action = ''' + repr(name) + ', ' + repr(action) + '''
try:
    if action == 'reload':
        importlib.reload(sys.modules[name])
    else:
        sys.modules.pop(name)
        importlib.import_module(name)
except RuntimeError as error:
    assert action in str(error), str(error)
else:
    raise AssertionError('Reload was allowed to execute changed source')
assert not marker.exists(), 'Changed control source executed before rejection'
''', project=project)


def test_inventory_action_reuses_the_same_bound_control_modules(tmp_path):
    guarded(tmp_path, '''
import maintenance_entry as bootstrap
bundle = bootstrap.load_control_bundle(bootstrap.control_digest())
entry = bundle.module('maintenance_entry')
inventory = bundle.module('maintenance_legacy_inventory')
seen = []
def read_inventory(manifest):
    seen.append(bundle.verify()['control_sha256'])
    return {'private_probe': True}
inventory.read_legacy_inventory = read_inventory
assert entry._legacy_inventory({'control_sha256': bootstrap.control_digest()}) == {'private_probe': True}
assert seen == [bootstrap.control_digest()]
assert bundle.module('maintenance_legacy_inventory') is inventory
''')


def test_dispatch_requires_bundle_even_when_source_is_imported_directly(tmp_path):
    guarded(tmp_path, '''
try:
    import maintenance_canary_dispatch
except RuntimeError as error:
    assert 'Fresh bound controls' in str(error), str(error)
else:
    raise AssertionError('Unbound dispatch import accepted')
assert 'quality_campaign_runner' not in sys.modules
''')


def test_all_controls_ignore_timestamp_cache_and_foreign_search_path(tmp_path):
    project = copy_controller(tmp_path)
    guarded(tmp_path, r'''
import maintenance_entry as bootstrap, py_compile
names = {}
for relative in bootstrap.CONTROL_FILES:
    if not relative.endswith('.py'): continue
    path = project / relative
    source = path.read_bytes() + b'\nLOADER_SOURCE_PROBE = 0\n'
    path.write_bytes(source)
    py_compile.compile(str(path), doraise=True)
    info = path.stat()
    path.write_bytes(source.replace(b'LOADER_SOURCE_PROBE = 0', b'LOADER_SOURCE_PROBE = 1'))
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    name = ('storage' if path.stem=='__init__' else 'storage.'+path.stem) if relative.startswith('backend/storage/') else path.stem
    names[name] = relative
shadow = Path(os.environ['STOCK_AGENT_PRIVATE_RQ_ROOT']) / 'shadow'
shadow.mkdir()
for name in names:
    (shadow / (name + '.py')).write_text("raise AssertionError('Foreign control executed')")
sys.path.insert(0, str(shadow))
bundle = bootstrap.load_control_bundle(bootstrap.control_digest())
for name in names.keys() - {'maintenance_control_sources'}:
    module = sys.modules[name] if name.startswith('quality_campaign_') else bundle.module(name)
    assert module.LOADER_SOURCE_PROBE == 1, name
''', project=project)


def test_failed_control_load_cannot_resume_or_execute_pending_controls(tmp_path):
    project = copy_controller(tmp_path)
    guarded(tmp_path, '''
import maintenance_entry as bootstrap, importlib
path = project / 'scripts/maintenance_canary_claim.py'
path.write_text("raise RuntimeError('Private partial load failure')\\n" + path.read_text())
try:
    bootstrap.load_control_bundle(bootstrap.control_digest())
except RuntimeError as error:
    assert 'Private partial load failure' in str(error), str(error)
else:
    raise AssertionError('Failed snapshot was accepted')
partial = sys.modules['maintenance_entry']._CONTROL_BUNDLE
for action in (partial.verify, partial.load, lambda: importlib.import_module('maintenance_canary_enrollment'),
               lambda: bootstrap.load_control_bundle(bootstrap.control_digest())):
    try:
        action()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Poisoned controller continued loading or was certified')
assert 'maintenance_canary_enrollment' not in sys.modules
assert sys.meta_path[0] is partial
''', project=project)
