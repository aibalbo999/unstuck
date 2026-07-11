from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MAX_BACKEND_MODULE_LINES = 350
FORBIDDEN_ROOT_SHIMS = {"agent_runner", "api_report_service", "financial_data", "market_data_fetchers", "rag_service", "report_gen"}
FORBIDDEN_MODULES = {
    "data_fetch.core_assembler",
    "data_fetch.core_builder",
    "data_fetch.orchestrator",
    "data_fetch.payload_assembler",
    "data_fetch.providers",
    "data_fetch.yfinance_payload_builder",
    "data_fetch.yfinance_legacy_fetch",
}
ALLOWED_SHIM_FILES = {
    BACKEND / "agent_runner.py",
    BACKEND / "api_report_service.py",
    BACKEND / "financial_data.py",
    BACKEND / "market_data_fetchers.py",
    BACKEND / "rag_service.py",
    BACKEND / "report_gen.py",
    BACKEND / "financial_data_orchestrator.py",
    BACKEND / "data_fetch" / "core_assembler.py",
    BACKEND / "data_fetch" / "core_builder.py",
    BACKEND / "data_fetch" / "orchestrator.py",
    BACKEND / "data_fetch" / "payload_assembler.py",
    BACKEND / "data_fetch" / "providers.py",
    BACKEND / "data_fetch" / "legacy_orchestrator.py",
    BACKEND / "data_fetch" / "yfinance_payload_builder.py",
    BACKEND / "data_fetch" / "yfinance_legacy_fetch.py",
}


def _module_for_import_from(path: Path, node: ast.ImportFrom, alias_name: str | None = None) -> str | None:
    if node.level <= 0:
        if node.module and alias_name:
            return f"{node.module}.{alias_name}"
        return node.module

    rel_parts = path.relative_to(BACKEND).with_suffix("").parts
    package_parts = list(rel_parts[:-1])
    if path.name == "__init__.py":
        package_parts = list(rel_parts[:-1])
    base_parts = package_parts[: max(0, len(package_parts) - node.level + 1)]
    module_parts = node.module.split(".") if node.module else []
    if alias_name:
        module_parts.append(alias_name)
    resolved = ".".join(base_parts + module_parts)
    return resolved or None


def test_production_code_does_not_import_root_legacy_shims():
    offenders = []
    for path in BACKEND.rglob("*.py"):
        if path in ALLOWED_SHIM_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".", 1)[0]
                    if root_name in FORBIDDEN_ROOT_SHIMS:
                        offenders.append(f"{path.relative_to(ROOT)} imports {alias.name}")
                    if alias.name in FORBIDDEN_MODULES:
                        offenders.append(f"{path.relative_to(ROOT)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and (node.module or node.level):
                module_name = _module_for_import_from(path, node)
                root_name = (module_name or node.module).split(".", 1)[0]
                if root_name in FORBIDDEN_ROOT_SHIMS:
                    offenders.append(f"{path.relative_to(ROOT)} imports from {module_name or node.module}")
                if module_name in FORBIDDEN_MODULES:
                    offenders.append(f"{path.relative_to(ROOT)} imports from {module_name}")
                for alias in node.names:
                    alias_module = _module_for_import_from(path, node, alias.name)
                    if alias_module in FORBIDDEN_MODULES:
                        offenders.append(f"{path.relative_to(ROOT)} imports from {alias_module}")

    assert offenders == []


def test_yfinance_payload_builder_is_facade_sized():
    path = BACKEND / "data_fetch" / "yfinance_payload_builder.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count < 150


def test_market_data_fetchers_is_facade_sized():
    path = BACKEND / "market_data_fetchers.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count < 150


def test_rag_service_is_facade_sized():
    path = BACKEND / "rag_service.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count < 120


def test_api_report_service_is_facade_sized():
    path = BACKEND / "api_report_service.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count < 120


def test_data_trust_facade_is_sized():
    path = BACKEND / "data_trust.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count < 120


def test_validation_and_provider_facades_are_sized():
    limits = {
        BACKEND / "config.py": 40,
        BACKEND / "settings" / "app_config.py": 80,
        BACKEND / "daily_decision_queue.py": 340,
        BACKEND / "daily_decision_route_warnings.py": 80,
        BACKEND / "data_fetch" / "yfinance_core_fetch.py": 300,
        BACKEND / "validators.py": 90,
        BACKEND / "structured_outputs.py": 90,
        BACKEND / "data_fetch" / "providers.py": 80,
        BACKEND / "data_fetch" / "yfinance_legacy_fetch.py": 60,
        BACKEND / "report_index.py": 260,
    }

    for path, limit in limits.items():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count < limit, str(path.relative_to(ROOT))


def test_free_notification_identity_helpers_are_split_from_plan():
    plan = BACKEND / "free_notification_plan.py"
    identity = BACKEND / "free_notification_identity.py"
    plan_text = plan.read_text(encoding="utf-8")

    assert identity.exists()
    assert "from free_notification_identity import" in plan_text
    assert len(plan_text.splitlines()) < 300
    assert len(identity.read_text(encoding="utf-8").splitlines()) < 120


def test_provider_sla_payload_helpers_are_split_from_observability_service():
    service = BACKEND / "api_observability_service.py"
    provider_payload = BACKEND / "provider_sla_observability.py"
    service_text = service.read_text(encoding="utf-8")

    assert provider_payload.exists()
    assert "from provider_sla_observability import" in service_text
    assert len(service_text.splitlines()) < 280
    assert len(provider_payload.read_text(encoding="utf-8").splitlines()) < 170


def test_backend_python_modules_stay_split_below_threshold():
    offenders = []
    for path in BACKEND.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count >= MAX_BACKEND_MODULE_LINES:
            offenders.append(f"{path.relative_to(ROOT)} has {line_count} lines; limit is {MAX_BACKEND_MODULE_LINES}")

    assert offenders == []


def test_agent_runtime_prompt_safety_helpers_are_split_from_prompting():
    prompting = BACKEND / "agent_runtime" / "prompting.py"
    prompt_safety = BACKEND / "agent_runtime" / "prompt_safety.py"
    prompting_text = prompting.read_text(encoding="utf-8")

    assert prompt_safety.exists()
    assert "from .prompt_safety import" in prompting_text
    assert "def _safe_prompt_text(" not in prompting_text
    assert "def _safe_prompt_json_list(" not in prompting_text
    assert len(prompting_text.splitlines()) < 320
    assert len(prompt_safety.read_text(encoding="utf-8").splitlines()) < 120


def test_frontend_bootstrap_is_split_into_focused_modules():
    limits = {
        ROOT / "backend" / "static" / "app.js": 300,
        ROOT / "backend" / "static" / "history_workspace.js": 260,
    }

    for path, limit in limits.items():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count < limit, str(path.relative_to(ROOT))


def test_report_chart_entrypoint_is_include_only():
    entry = BACKEND / "templates" / "includes" / "report_charts.html.j2"
    text = entry.read_text(encoding="utf-8")

    assert len(text.splitlines()) < 20
    assert "const CHART_DATA" not in text
    assert text.count("{% include") == 5


def test_provider_service_imports_registry_not_compat_facade():
    for path in [
        BACKEND / "data_fetch" / "service.py",
        BACKEND / "data_fetch" / "workflow.py",
    ]:
        text = path.read_text(encoding="utf-8")
        assert ".providers import" not in text
        assert ".provider_registry import ProviderRegistry" in text


def test_config_settings_are_split_into_grouped_modules():
    expected = [
        "app_config.py",
        "env.py",
        "models.py",
        "providers.py",
        "security.py",
        "storage.py",
        "runtime_limits.py",
    ]
    for filename in expected:
        assert (BACKEND / "settings" / filename).exists()

    config_text = (BACKEND / "config.py").read_text(encoding="utf-8")
    app_config_text = (BACKEND / "settings" / "app_config.py").read_text(encoding="utf-8")
    assert "import *" not in config_text
    assert "import *" not in app_config_text
    assert "__all__" in config_text
    assert "__all__" in app_config_text
    assert len((BACKEND / "settings" / "models.py").read_text(encoding="utf-8").splitlines()) < 300


def test_runtime_and_job_helpers_are_split_into_focused_modules():
    expected = [
        "runtime_event_core.py",
        "runtime_event_emitters.py",
        "runtime_event_logs.py",
        "analysis_job_progress.py",
        "analysis_job_reports.py",
        "context_digest_payload.py",
        "data_freshness_market.py",
        "data_freshness_policy.py",
        "data_trust_sla_policy.py",
        "external_data_fmp.py",
        "external_data_parsers.py",
        "market_calendar_store.py",
        "provider_sla_maintenance.py",
        "snapshot_maintenance.py",
        "storage_inventory.py",
    ]
    for filename in expected:
        assert (BACKEND / filename).exists()


def test_report_index_is_split_into_focused_modules():
    expected = [
        "report_index.py",
        "report_index_metadata.py",
        "report_index_migrations.py",
        "report_index_rows.py",
        "report_repository.py",
    ]
    for filename in expected:
        assert (BACKEND / filename).exists()

    index_text = (BACKEND / "report_index.py").read_text(encoding="utf-8")
    assert "run_report_index_migrations" in index_text
    assert "row_to_report" in index_text
    assert "build_report_metadata" in index_text


def test_provider_resilience_module_is_wired_to_source_audit():
    assert (BACKEND / "provider_resilience.py").exists()
    source_text = (BACKEND / "source_audit.py").read_text(encoding="utf-8")

    assert "call_provider_with_resilience" in source_text
    assert "ProviderCircuitOpenError" in source_text


def test_report_template_entrypoint_is_sized():
    path = BACKEND / "templates" / "report.html.j2"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count < 80


def test_pipeline_runtime_does_not_print_directly():
    paths = [
        BACKEND / "pipeline.py",
        BACKEND / "agent_runtime" / "quality_gates.py",
        BACKEND / "runtime_events.py",
    ]

    offenders = [
        str(path.relative_to(ROOT))
        for path in paths
        if "print(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_api_routes_do_not_bypass_storage_or_operational_boundaries():
    offenders = []
    forbidden_text = (
        "sqlite3",
        "backend/output",
        "decision_tracking.sqlite3",
        "stock_agent_cache.sqlite3",
        "operational.sqlite3",
        ".data.json",
    )
    allowed_storage_helpers = {
        "existing_storage_key",
        "load_storage_item",
        "report_storage_candidates_for_filename",
    }
    for path in (BACKEND / "api_routes").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for token in forbidden_text:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {token}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "open":
                    offenders.append(f"{path.relative_to(ROOT)} calls open() directly")
                if isinstance(func, ast.Name) and func.id == "Path":
                    literal_args = [
                        arg.value
                        for arg in node.args
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    ]
                    if any(value in {"output", "backend/output"} for value in literal_args):
                        offenders.append(f"{path.relative_to(ROOT)} builds report output Path directly")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sqlite3":
                        offenders.append(f"{path.relative_to(ROOT)} imports sqlite3")
            if isinstance(node, ast.ImportFrom) and node.module == "sqlite3":
                offenders.append(f"{path.relative_to(ROOT)} imports from sqlite3")
            if isinstance(node, ast.ImportFrom) and node.module in {"report_history_storage", "report_artifacts"}:
                imported = {alias.name for alias in node.names}
                unexpected = imported - allowed_storage_helpers
                if unexpected:
                    offenders.append(f"{path.relative_to(ROOT)} imports unexpected storage helpers {sorted(unexpected)}")

    assert offenders == []
