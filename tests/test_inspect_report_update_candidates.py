from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def module():
    spec = importlib.util.spec_from_file_location("inspect_candidates", ROOT / "scripts/inspect_report_update_candidates.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_collect_requires_complete_paginated_inventory(module, monkeypatch):
    pages = iter([
        {"reports": [{"filename": "A.html", "ticker": "A", "pipeline_id": "v1", "html_hash": "h", "decision_freshness": {"status": "needs_rerun", "requires_rerun": True}}], "pagination": {"total": 2, "has_next": True}},
        {"reports": [{"filename": "B.html", "ticker": "B", "pipeline_id": "v4", "html_hash": "i", "decision_freshness": {"status": "current", "requires_rerun": False}}], "pagination": {"total": 2, "has_next": False}},
    ])

    class Session:
        def get(self, *args, **kwargs):
            return _Response(next(pages))

    monkeypatch.setattr(module.requests, "Session", Session)
    payload = module.collect("http://fixture")
    assert payload["total"] == payload["returned"] == 2
    assert payload["status_counts"] == {"current": 1, "needs_rerun": 1}
    assert [item["filename"] for item in payload["candidates"]] == ["A.html"]


def test_write_exclusive_rejects_overwrite(module, tmp_path):
    path = tmp_path / "inventory.json"
    module.write_exclusive(path, {"x": 1})
    with pytest.raises(ValueError):
        module.write_exclusive(path, {"x": 2})
