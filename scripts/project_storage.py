"""External-drive environment for this Mac's project commands (no local fallback)."""
from __future__ import annotations

import os
from pathlib import Path
import sys

VOLUME = Path('/Volumes/X10 Pro Mac')
PROJECT = Path(__file__).resolve().parents[1]


def external_environment(project: Path = PROJECT, volume: Path = VOLUME) -> dict[str, str]:
    # Check before mkdir: an unmounted /Volumes path must never become a local copy.
    if not os.path.ismount(volume):
        raise RuntimeError(f'外接碟未掛載，停止寫入：{volume}')
    volume = volume.resolve(strict=True)
    project = project.resolve(strict=True)
    if not project.is_relative_to(volume) or project.stat().st_dev != volume.stat().st_dev:
        raise RuntimeError('專案不在指定外接碟，停止寫入')
    archive = volume / 'stock-agent-archives'
    paths = {
        'TMPDIR': project / 'backend/cache/tmp',
        'XDG_CACHE_HOME': project / 'backend/cache/tools',
        'PIP_CACHE_DIR': project / 'backend/cache/tools/pip',
        'MPLCONFIGDIR': project / 'backend/cache/tools/matplotlib',
        'STOCK_AGENT_ARCHIVE_DIR': archive,
    }
    for path in paths.values():
        if not path.resolve().is_relative_to(volume):
            raise RuntimeError(f'儲存路徑離開外接碟，停止寫入：{path}')
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.stat().st_dev != volume.stat().st_dev:
            raise RuntimeError(f'儲存路徑位於其他磁碟，停止寫入：{path}')
    result = {key: str(value) for key, value in paths.items()}
    json_cache = project / 'backend/cache/provider_json_cache.sqlite3'
    if not json_cache.resolve().is_relative_to(volume) or json_cache.is_dir():
        raise RuntimeError('來源 JSON 快取路徑不合格，停止寫入')
    result['JSON_CACHE_DB_PATH'] = str(json_cache)
    result.update(TEMP=result['TMPDIR'], TMP=result['TMPDIR'])
    return result


if __name__ == '__main__':
    try:
        for key, value in external_environment().items():
            print(key)
            print(value)
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
