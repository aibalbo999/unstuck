from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_mode_catalog_projects_backend_and_frontend_contract():
    from pipeline_mode_catalog import build_pipeline_mode_catalog

    catalog = build_pipeline_mode_catalog()
    assert [item["id"] for item in catalog] == ["v1", "v2", "v3", "v4", "both"]
    assert catalog[0]["label"] == "模式 A：學術深度派"
    assert catalog[0]["shortLabel"] == "學術深度派"
    assert catalog[0]["agentCount"] == 10
    assert catalog[0]["optionLabel"].endswith("10 Agent")
    assert catalog[-1]["label"] == "連續模式：模式 A → 模式 B → 模式 C"
    assert catalog[-1]["agentCount"] == 23
    assert catalog[-1]["optionLabel"].endswith("23 模組")


def test_pipeline_mode_catalog_route_is_read_only_and_versioned():
    from api_routes.pipeline_modes import create_pipeline_modes_router

    app = FastAPI()
    app.include_router(create_pipeline_modes_router())
    response = TestClient(app).get("/api/pipeline-modes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "pipeline_modes.v1"
    assert [item["id"] for item in payload["modes"]] == ["v1", "v2", "v3", "v4", "both"]


def test_pipeline_mode_fallback_is_generated_and_in_sync_with_backend_catalog():
    generator = ROOT / "scripts" / "generate_pipeline_mode_fallback.py"
    fallback = ROOT / "backend" / "static" / "pipeline_mode_fallback.js"

    result = subprocess.run(
        [sys.executable, str(generator), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert fallback.exists()
    assert "StockAgentUiPipelineModeFallback" in fallback.read_text(encoding="utf-8")


def test_ci_gate_checks_generated_pipeline_mode_fallback():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "scripts/generate_pipeline_mode_fallback.py --check" in ci_gate
