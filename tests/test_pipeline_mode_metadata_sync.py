from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"
FALLBACK_PATH = STATIC_DIR / "pipeline_mode_fallback.js"


def _frontend_pipeline_meta() -> dict[str, dict[str, str]]:
    script = """
global.window = {};
require(__UI_DATA_TRUST_PATH__);
require(__FALLBACK_PATH__);
require(__UI_HELPERS_PATH__);
process.stdout.write(JSON.stringify(window.StockAgentUi.PIPELINE_META));
""".replace("__UI_DATA_TRUST_PATH__", json.dumps(str(STATIC_DIR / "ui_data_trust.js"))).replace("__FALLBACK_PATH__", json.dumps(str(FALLBACK_PATH))).replace("__UI_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "ui_helpers.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_frontend_pipeline_catalog_loader_applies_api_payload_and_falls_back_on_error():
    script = """
global.window = {};
require(__UI_DATA_TRUST_PATH__);
require(__FALLBACK_PATH__);
require(__UI_HELPERS_PATH__);
require(__CATALOG_PATH__);
(async () => {
  const applied = await window.StockAgentUi.loadPipelineMeta(async () => ({
    ok: true,
    json: async () => ({ schema_version: 'pipeline_modes.v1', modes: [{ id: 'v1', label: 'Canonical mode A', optionLabel: 'Canonical · 10 Agent' }] })
  }));
  const rejected = await window.StockAgentUi.loadPipelineMeta(async () => ({ ok: false }));
  process.stdout.write(JSON.stringify({ applied, rejected, label: window.StockAgentUi.PIPELINE_META.v1.label }));
})();
""".replace("__UI_DATA_TRUST_PATH__", json.dumps(str(STATIC_DIR / "ui_data_trust.js"))).replace("__FALLBACK_PATH__", json.dumps(str(FALLBACK_PATH))).replace("__UI_HELPERS_PATH__", json.dumps(str(STATIC_DIR / "ui_helpers.js"))).replace("__CATALOG_PATH__", json.dumps(str(STATIC_DIR / "pipeline_mode_catalog.js")))
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload == {"applied": True, "rejected": False, "label": "Canonical mode A"}


def test_frontend_pipeline_metadata_matches_backend_runtime_contract():
    from pipeline_modes import get_pipeline_definition, get_pipeline_run_agent_total, get_pipeline_run_hint, get_pipeline_run_label

    frontend = _frontend_pipeline_meta()
    for pipeline_id in ("v1", "v2", "v3", "v4"):
        backend = get_pipeline_definition(pipeline_id)
        metadata = frontend[pipeline_id]
        assert metadata["label"] == backend["label"]
        assert metadata["shortLabel"] == backend["short_label"]
        assert metadata["hint"] == backend["hint_text"]
        assert metadata["optionLabel"].endswith(f"{len(backend['agents'])} Agent")

    both = frontend["both"]
    assert both["label"] == get_pipeline_run_label("both")
    assert both["hint"] == get_pipeline_run_hint("both")
    assert both["shortLabel"] == "A+B+C 連續"
    assert both["optionLabel"].endswith(f"{get_pipeline_run_agent_total('both')} 模組")


def test_pipeline_catalog_script_loads_after_ui_helpers_before_app():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert index_html.index("/static/ui_data_trust.js") < index_html.index("/static/pipeline_mode_fallback.js") < index_html.index("/static/ui_helpers.js") < index_html.index("/static/pipeline_mode_catalog.js") < index_html.index("/static/app.js")
