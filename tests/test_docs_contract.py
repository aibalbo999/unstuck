import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_operator_docs_and_demo_script_are_discoverable():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for relative in [
        "docs/architecture.md",
        "docs/operator-guide.md",
        "docs/api.md",
        "scripts/demo_report.sh",
    ]:
        assert (ROOT / relative).exists(), relative
        assert relative in readme


def test_architecture_doc_names_runtime_boundaries():
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

    assert "AnalysisPipelineRunner" in architecture
    assert "StockDataService" in architecture
    assert "decision_freshness" in architecture
    assert "mutation token" in architecture


def test_default_server_binding_is_localhost_only():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    launcher = (ROOT / "start_mac.command").read_text(encoding="utf-8")

    assert 'SERVER_HOST="127.0.0.1"' in launcher
    assert 'LAN_ACCESS="${LAN_ACCESS:-0}"' in launcher
    assert '--host "$SERVER_HOST"' in launcher
    assert "--host 127.0.0.1" in readme
    assert "LAN_ACCESS=1" in readme
    assert "--host 0.0.0.0" not in readme


def test_openapi_contract_covers_runtime_surface_and_mutation_security():
    import api

    schema = api.app.openapi()
    paths = schema["paths"]
    expected = {
        "/healthz": {"get"},
        "/readyz": {"get"},
        "/api/client-config": {"get"},
        "/api/analysis-jobs": {"post"},
        "/api/analysis-jobs/{job_id}": {"get"},
        "/api/analysis-jobs/{job_id}/events": {"get"},
        "/api/analysis-jobs/{job_id}/cancel": {"post"},
        "/api/report/{filename}/refresh/data": {"post"},
        "/api/report/{filename}/rerun": {"post"},
        "/api/reports": {"get"},
        "/api/reports/{filename}": {"delete"},
        "/api/watchlist": {"get", "post"},
        "/api/watchlist/symbols": {"get"},
        "/api/watchlist/import": {"post"},
        "/api/watchlist/daily-dashboard": {"get"},
        "/api/watchlist/portfolio/risk": {"post"},
        "/api/watchlist/run": {"post"},
        "/api/watchlist/{ticker}": {"delete"},
        "/api/maintenance/storage-summary": {"get"},
        "/api/maintenance/sqlite-maintenance": {"post"},
        "/api/observability/dashboard": {"get"},
        "/api/ops/dashboard": {"get"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods <= set(paths[path])

    analysis_job_schema = schema["components"]["schemas"]["AnalysisJobCreateRequest"]
    assert {"ticker", "pipeline_id", "force", "resume"} <= set(analysis_job_schema["properties"])

    operation_ids = [
        operation["operationId"]
        for operations in paths.values()
        for method, operation in operations.items()
        if method in {"get", "post", "delete", "put", "patch"}
    ]
    assert len(operation_ids) == len(set(operation_ids))

    security_scheme = schema["components"]["securitySchemes"]["MutationToken"]
    assert security_scheme == {"type": "apiKey", "in": "header", "name": "X-Mutation-Token"}
    for path, operations in paths.items():
        for method, operation in operations.items():
            if method in {"post", "delete", "put", "patch"} or path == "/api/maintenance/storage-summary":
                assert {"MutationToken": []} in operation.get("security", []), f"{method.upper()} {path}"
