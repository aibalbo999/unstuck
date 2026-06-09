import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture(autouse=True)
def isolate_provider_sla_db(monkeypatch, tmp_path):
    import provider_sla

    monkeypatch.setattr(provider_sla, "TASK_DB_PATH", str(tmp_path / "provider_sla.sqlite3"))


@pytest.fixture(autouse=True)
def isolate_runtime_task_db(monkeypatch, tmp_path):
    import job_observability
    import job_store
    import job_store_maintenance
    import storage_inventory

    task_db = str(tmp_path / "analysis_jobs.sqlite3")
    monkeypatch.setattr(job_store, "TASK_DB_PATH", task_db)
    monkeypatch.setattr(job_observability, "TASK_DB_PATH", task_db)
    monkeypatch.setattr(job_store_maintenance, "TASK_DB_PATH", task_db)
    monkeypatch.setattr(storage_inventory, "TASK_DB_PATH", task_db)
    job_store.reset_job_store_for_tests()
    yield
    job_store.reset_job_store_for_tests()


@pytest.fixture(autouse=True)
def isolate_runtime_cache_db(monkeypatch, tmp_path):
    import cache_store
    import report_index
    import report_index_maintenance
    import storage_inventory

    cache_db = str(tmp_path / "stock_agent_cache.sqlite3")
    monkeypatch.setattr(cache_store, "CACHE_DB_PATH", cache_db)
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", cache_db)
    monkeypatch.setattr(report_index_maintenance, "CACHE_DB_PATH", cache_db)
    monkeypatch.setattr(storage_inventory, "CACHE_DB_PATH", cache_db)
    cache_store.reset_cache_store_for_tests()
    yield
    cache_store.reset_cache_store_for_tests()


@pytest.fixture
def mutation_headers(monkeypatch):
    import api

    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "test-mutation-token")
    return {"X-Mutation-Token": "test-mutation-token"}
