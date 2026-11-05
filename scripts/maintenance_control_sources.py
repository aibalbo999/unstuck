"""Compile one approved control snapshot in a fresh dedicated controller.

Loaded only from the exact buffer already checked by the source entry bootstrap.
This is application provenance, not a sandbox against hostile Python/native code.
No command, service, credential, queue, budget or release authority is granted.
The shell is captured for the digest but is not executed or certified here.
"""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading


FILES = {
    'storage': 'backend/storage/__init__.py',
    'storage.capacity': 'backend/storage/capacity.py',
    'storage.capacity_delegation': 'backend/storage/capacity_delegation.py',
    'storage.capacity_companion': 'backend/storage/capacity_companion.py',
    'storage.migrations': 'backend/storage/migrations.py',
    'storage.report_storage': 'backend/storage/report_storage.py',
    'storage._local_file_operations': 'backend/storage/_local_file_operations.py',
    'storage._report_keys': 'backend/storage/_report_keys.py',
    'storage.memory_report_storage': 'backend/storage/memory_report_storage.py',
    'canary_release_policy': 'backend/canary_release_policy.py',
    'maintenance_entry': 'scripts/maintenance_entry.py',
    'maintenance_state': 'backend/maintenance_state.py',
    'maintenance_guard': 'backend/maintenance_guard.py',
    'maintenance_readiness': 'scripts/maintenance_readiness.py',
    'maintenance_legacy_inventory': 'scripts/maintenance_legacy_inventory.py',
    'maintenance_owned_process': 'scripts/maintenance_owned_process.py',
    'maintenance_canary_claim': 'scripts/maintenance_canary_claim.py',
    'maintenance_canary_enrollment': 'scripts/maintenance_canary_enrollment.py',
    'maintenance_canary_settlement': 'scripts/maintenance_canary_settlement.py',
    'maintenance_canary_dispatch': 'scripts/maintenance_canary_dispatch.py',
}
BOOTSTRAP = 'scripts/maintenance_control_sources.py'
HARNESS = tuple('quality_campaign_' + name for name in ('runner', 'budget', 'wire', 'transport', 'watchdog', 'safety', 'graph'))
HARNESS_FILES = {name: 'tests/' + name + '.py' for name in HARNESS}


class ControlSources:
    def __init__(self, root, sources, expected, bootstrap):
        self._root, self._sources, self._digest = Path(root), dict(sources), expected
        self._pid, self._modules, self._complete = os.getpid(), {}, False
        self._started, self._failed = False, False
        if (self._root.resolve() != self._root
                or set(sources) != {*FILES.values(), *HARNESS_FILES.values(), BOOTSTRAP, 'start_mac.command'}
                or any(type(value) is not bytes for value in sources.values())):
            raise RuntimeError('Exact control source snapshot required')
        hashes = {name: hashlib.sha256(source).hexdigest() for name, source in sources.items()}
        digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if digest != expected:
            raise RuntimeError('Control snapshot digest mismatch')
        for name in (*FILES, *HARNESS):
            if name in sys.modules and not (name == 'maintenance_entry' and sys.modules[name] is bootstrap):
                raise RuntimeError('Fresh controller required; preloaded controls or harness rejected')
        if (threading.current_thread() is not threading.main_thread() or threading.active_count() != 1
                or any(name in sys.modules for name in ('config', 'api', 'analysis_jobs', 'dotenv'))):
            raise RuntimeError('Fresh single-thread controller without application startup required')
        self._bootstrap_sha = hashes[BOOTSTRAP]

    def find_spec(self, fullname, path=None, target=None):
        if fullname in HARNESS and (target is not None or self._complete or self._failed):
            raise RuntimeError('Campaign harness reload or reimport drift rejected')
        if fullname in FILES:
            if target is not None:
                raise RuntimeError('Control reload drift rejected')
            if self._failed or fullname in self._modules:
                raise RuntimeError('Never resume or reimport a control bundle')
            package = [str(self._root / 'backend/storage')] if fullname == 'storage' else None
            return importlib.util.spec_from_file_location(fullname, self._root / FILES[fullname],
                                                         loader=self, submodule_search_locations=package)
        return None

    def create_module(self, spec):
        return None

    def harness_sources(self):
        if self._failed or os.getpid() != self._pid:
            raise RuntimeError('Original control source snapshot required')
        return {name: self._sources[path] for name, path in HARNESS_FILES.items()}

    def exec_module(self, module):
        name = module.__name__
        if name in self._modules:
            raise RuntimeError('Never re-execute a control module')
        module._control_source_sha256 = hashlib.sha256(self._sources[FILES[name]]).hexdigest()
        module._CONTROL_BUNDLE = self
        self._modules[name] = module
        exec(compile(self._sources[FILES[name]], module.__file__, 'exec'), module.__dict__)

    def load(self):
        if self._started:
            raise RuntimeError('Never reload or resume a control bundle')
        self._started = True
        # Only the source bootstrap may occupy this name. It has not loaded a
        # guard or started any operation. Keep unrelated modules untouched.
        previous = sys.modules.pop('maintenance_entry', None)
        sys.meta_path.insert(0, self)
        try:
            for name in FILES:
                importlib.import_module(name)
            self._complete = True
            self.verify()
        except BaseException:
            # Never retry/adopt a partial bundle; keep it visibly poisoned.
            self._failed, self._complete = True, False
            if 'maintenance_entry' not in self._modules and previous is not None:
                sys.modules['maintenance_entry'] = previous
            raise
        # Keep the exact-name finder for this dedicated controller's lifetime:
        # reload must be refused before PathFinder can execute changed code.
        # Failed loads keep the poisoned finder, never a resumable partial set.
        return self

    def verify(self):
        if os.getpid() != self._pid or self._failed or not self._complete or set(self._modules) != set(FILES):
            raise RuntimeError('Original complete control bundle required')
        if not sys.meta_path or sys.meta_path[0] is not self:
            raise RuntimeError('Loaded control finder drift')
        for name, module in self._modules.items():
            spec = getattr(module, '__spec__', None)
            if (sys.modules.get(name) is not module or getattr(module, '__loader__', None) is not self
                    or getattr(spec, 'loader', None) is not self or getattr(spec, 'origin', None) != str(self._root / FILES[name])
                    or getattr(module, '__file__', None) != str(self._root / FILES[name])
                    or getattr(module, '_CONTROL_BUNDLE', None) is not self
                    or getattr(module, '_control_source_sha256', None) != hashlib.sha256(self._sources[FILES[name]]).hexdigest()):
                raise RuntimeError('Loaded control module identity drift')
        dispatch = self._modules['maintenance_canary_dispatch']
        for name, path in HARNESS_FILES.items():
            module = dispatch._LOADED.get(name)
            spec = getattr(module, '__spec__', None)
            if (module is None or sys.modules.get(name) is not module
                    or getattr(module, '__loader__', None) is not dispatch._finder
                    or getattr(spec, 'loader', None) is not dispatch._finder
                    or getattr(spec, 'origin', None) != str(self._root / path)
                    or getattr(module, '__file__', None) != str(self._root / path)):
                raise RuntimeError('Loaded campaign harness identity drift')
        entry = self._modules['maintenance_entry']
        try:
            if set(entry.CONTROL_FILES) != set(self._sources) or entry._control_sources() != self._sources:
                raise RuntimeError('Captured control source drift')
        except (OSError, ValueError) as error:
            raise RuntimeError('Captured control source drift') from error
        return {'control_sha256': self._digest, 'loaded_control_files': sorted(FILES.values()),
                'loaded_harness_files': sorted(HARNESS_FILES.values()),
                'bootstrap_source_sha256': self._bootstrap_sha, 'shell_execution_verified': False,
                'production_ready': False}

    def module(self, name):
        self.verify()
        return self._modules[name]


def load_controls(root, sources, expected, bootstrap):
    return ControlSources(root, sources, expected, bootstrap).load()
