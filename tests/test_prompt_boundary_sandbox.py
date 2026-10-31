"""External test sandboxes must not weaken production/cache path guards."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sandbox_runner', ROOT / 'tests/run_prompt_boundary_tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_external_sandbox_is_outside_production_namespace(tmp_path, monkeypatch):
    volume = tmp_path / 'external'; volume.mkdir()
    archive = volume / 'stock-agent-archives'; archive.mkdir()
    monkeypatch.setattr(runner.os.path, 'ismount', lambda p: p == volume)
    path = runner.external_test_sandbox_base(archive, volume)
    assert path == archive / 'test-sandboxes'
    assert path.is_dir() and path.stat().st_dev == volume.stat().st_dev
    assert not {'backend', 'cache', 'output', '.git', 'artifacts', 'reports'}.intersection(path.parts)


def test_missing_mount_fails_before_creating_sandbox(tmp_path, monkeypatch):
    volume = tmp_path / 'external'; volume.mkdir()
    archive = volume / 'stock-agent-archives'; archive.mkdir()
    monkeypatch.setattr(runner.os.path, 'ismount', lambda p: False)
    with pytest.raises(RuntimeError):
        runner.external_test_sandbox_base(archive, volume)
    assert not (archive / 'test-sandboxes').exists()


def test_archive_outside_volume_fails_before_writes(tmp_path, monkeypatch):
    volume = tmp_path / 'external'; volume.mkdir()
    archive = tmp_path / 'other'; archive.mkdir()
    monkeypatch.setattr(runner.os.path, 'ismount', lambda p: True)
    with pytest.raises(RuntimeError):
        runner.external_test_sandbox_base(archive, volume)
    assert not (archive / 'test-sandboxes').exists()


def test_sandbox_symlink_escape_is_rejected(tmp_path, monkeypatch):
    volume = tmp_path / 'external'; volume.mkdir()
    archive = volume / 'stock-agent-archives'; archive.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    (archive / 'test-sandboxes').symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(runner.os.path, 'ismount', lambda p: True)
    with pytest.raises(RuntimeError):
        runner.external_test_sandbox_base(archive, volume)
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(sys.platform != 'darwin', reason='Mac external test sandbox')
def test_child_process_inherits_archive_sandbox_not_production_cache():
    expected = Path(tempfile.gettempdir()).resolve()
    assert expected == Path('/Volumes/X10 Pro Mac/stock-agent-archives/test-sandboxes')
    assert all(Path(os.environ[key]).resolve() == expected for key in ('TMPDIR', 'TMP', 'TEMP'))
    child = subprocess.run([sys.executable, '-B', '-c',
        'import tempfile,json; print(json.dumps(tempfile.gettempdir()))'],
        capture_output=True, text=True, check=True)
    assert Path(json.loads(child.stdout)).resolve() == expected
    assert not expected.is_relative_to(ROOT / 'backend/cache')
