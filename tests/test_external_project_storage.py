"""Storage policy failures must precede writes or launching a child command."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('external_project_storage', ROOT / 'scripts/project_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


def test_missing_volume_does_not_create_local_fallback(tmp_path, monkeypatch):
    volume = tmp_path / 'missing volume'
    monkeypatch.setattr(storage.os.path, 'ismount', lambda path: False)
    with pytest.raises(RuntimeError, match='未掛載'):
        storage.external_environment(tmp_path, volume)
    assert not volume.exists()


def test_local_checkout_is_rejected_before_creating_data(tmp_path, monkeypatch):
    volume = tmp_path / 'external'; volume.mkdir()
    project = tmp_path / 'local'; project.mkdir()
    monkeypatch.setattr(storage.os.path, 'ismount', lambda path: True)
    with pytest.raises(RuntimeError, match='專案不在'):
        storage.external_environment(project, volume)
    assert not (project / 'backend').exists()


def test_symlink_to_local_storage_is_rejected(tmp_path, monkeypatch):
    volume = tmp_path / 'external'; volume.mkdir()
    project = volume / 'project'; project.mkdir()
    (project / 'backend').mkdir()
    local = tmp_path / 'local'; local.mkdir()
    (project / 'backend/cache').symlink_to(local, target_is_directory=True)
    monkeypatch.setattr(storage.os.path, 'ismount', lambda path: True)
    with pytest.raises(RuntimeError, match='離開外接碟'):
        storage.external_environment(project, volume)
    assert list(local.iterdir()) == []


def test_all_command_paths_are_on_selected_volume(tmp_path, monkeypatch):
    volume = tmp_path / 'external drive'; volume.mkdir()
    project = volume / 'project'; project.mkdir()
    monkeypatch.setattr(storage.os.path, 'ismount', lambda path: True)
    settings = storage.external_environment(project, volume)
    assert settings['TMPDIR'] == settings['TEMP'] == settings['TMP']
    directories = [value for key, value in settings.items() if key != 'JSON_CACHE_DB_PATH']
    assert all(Path(value).is_relative_to(volume) and Path(value).is_dir() for value in directories)
    if 'JSON_CACHE_DB_PATH' in settings:
        cache = Path(settings['JSON_CACHE_DB_PATH'])
        assert cache.is_relative_to(volume) and cache.parent.is_dir() and not cache.exists()


@pytest.mark.skipif(os.uname().sysname != 'Darwin', reason='Mac deployment entrypoint')
def test_command_entry_overrides_local_temp_and_cleans_temporary_files():
    probe = (
        'import tempfile,pathlib,json; '
        'p=pathlib.Path(tempfile.gettempdir()); '
        'f=tempfile.NamedTemporaryFile(); '
        'print(json.dumps({"root":str(p),"file":f.name})); f.close()'
    )
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/project_exec.sh'), str(ROOT / '.venv/bin/python'), '-c', probe],
        env={**os.environ, 'TMPDIR': '/tmp', 'TEMP': '/tmp', 'TMP': '/tmp'},
        capture_output=True, text=True, check=True,
    )
    paths = json.loads(result.stdout)
    assert Path(paths['root']).resolve().is_relative_to(storage.VOLUME)
    assert not Path(paths['file']).exists()


def test_failed_storage_preflight_does_not_execute_command(tmp_path):
    project = tmp_path / 'copied project'; (project / 'scripts').mkdir(parents=True)
    for name in ('project_exec.sh', 'project_environment.sh', 'project_python.sh', 'project_storage.py'):
        target = project / 'scripts' / name
        target.write_bytes((ROOT / 'scripts' / name).read_bytes()); target.chmod(0o755)
    # The test sandbox itself now lives on the external drive. Simulate a
    # failed preflight without unmounting or touching the real service volume.
    (project / 'scripts/project_storage.py').write_text('raise SystemExit(73)\n')
    marker = tmp_path / 'unexpected-command'
    result = subprocess.run(
        ['bash', str(project / 'scripts/project_exec.sh'), 'touch', str(marker)],
        env={**os.environ, 'PYTHON_BIN': str(ROOT / '.venv/bin/python')}, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert not marker.exists()
