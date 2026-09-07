from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def module():
    spec = importlib.util.spec_from_file_location(
        "capture_runtime_release_baseline",
        ROOT / "scripts/capture_runtime_release_baseline.py",
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def test_capture_is_secret_safe_and_collects_read_only_summaries(module, monkeypatch):
    pages = iter([
        _Response({"reports": [{
            "filename": "AAA_v1.html", "ticker": "AAA.TW", "pipeline_id": "v1", "timestamp": 20,
            "html_hash": "html", "markdown_hash": "markdown", "data_snapshot_hash": "snapshot",
            "decision_freshness": {"status": "needs_rerun", "requires_rerun": True},
        }], "pagination": {"total": 1, "has_next": False}}),
    ])

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if url.endswith("/api/reports"):
                return next(pages)
            payloads = {
                "/healthz": {"status": "ok"},
                "/readyz": {"status": "ready"},
                "/api/runtime-identity": {"schema_version": "stock-agent.runtime-identity.v1", "commit": "a" * 40, "dirty": False, "path": "/secret"},
                "/api/observability/active-jobs": {"active_count": 0, "jobs": [{"error": "do not copy"}]},
                "/api/decision-tracking": {"enabled_count": 1, "items": [{"ticker": "AAA"}]},
            }
            return _Response(payloads[url.removeprefix("http://fixture")])

    session = Session()
    monkeypatch.setattr(module.requests, "Session", lambda: session)
    monkeypatch.setattr(module, "_git_baseline", lambda: {"head": "b" * 40, "dirty": False, "status_available": True})
    monkeypatch.setattr(module, "_process_baseline", lambda: [{"pid": 7, "command": "uvicorn api:app", "cwd": str(ROOT / "backend")}])
    monkeypatch.setattr(module, "_database_baseline", lambda: [{"path": "cache.sqlite3", "present": True, "sha256": "c" * 64}])

    payload = module.capture("http://fixture", timeout=3)
    assert payload["schema_version"] == "stock-agent.runtime-release-baseline.v1"
    assert payload["git"]["head"] == "b" * 40
    assert payload["reports"]["total"] == 1
    assert payload["reports"]["requires_rerun_count"] == 1
    assert payload["endpoints"]["/api/runtime-identity"]["commit"] == "a" * 40
    assert payload["endpoints"]["/api/observability/active-jobs"] == {"status_code": 200, "active_count": 0}
    assert payload["endpoints"]["/api/decision-tracking"] == {"status_code": 200, "enabled_count": 1}
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "do not copy" not in serialized
    assert "/secret" not in serialized
    assert all("headers" not in kwargs for _, kwargs in session.calls)


def test_capture_records_request_failures_without_secret_text(module, monkeypatch):
    class Session:
        def get(self, url, **kwargs):
            if url.endswith("/api/reports"):
                raise requests.Timeout("token=super-secret")
            raise requests.ConnectionError("Authorization: bearer super-secret")

    monkeypatch.setattr(module.requests, "Session", Session)
    monkeypatch.setattr(module, "_git_baseline", lambda: {"head": None, "dirty": None, "status_available": False})
    monkeypatch.setattr(module, "_process_baseline", lambda: [])
    monkeypatch.setattr(module, "_database_baseline", lambda: [])
    payload = module.capture("http://fixture", timeout=1)
    assert payload["endpoints"]["/healthz"] == {"status_code": None, "error": "ConnectionError"}
    assert payload["reports"] == {"error": "Timeout"}
    assert "super-secret" not in json.dumps(payload)


def test_write_exclusive_rejects_overwrite_and_symlink(module, tmp_path):
    path = tmp_path / "baseline.json"
    module.write_exclusive(path, {"ok": True})
    with pytest.raises(ValueError):
        module.write_exclusive(path, {"ok": False})
    target = tmp_path / "target.json"
    target.write_text("existing")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        module.write_exclusive(link, {"ok": False})


def test_file_baseline_refuses_symlink_target(module, tmp_path):
    target = tmp_path / "db.sqlite3"
    target.write_bytes(b"data")
    link = tmp_path / "db-link.sqlite3"
    link.symlink_to(target)
    result = module._file_baseline(link)
    assert result == {"path": str(link), "present": True, "is_symlink": True}
