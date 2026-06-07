import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture(autouse=True)
def isolate_provider_sla_db(monkeypatch, tmp_path):
    import provider_sla

    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider_sla.sqlite3"))
