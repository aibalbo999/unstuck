from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FORBIDDEN_ROOT_SHIMS = {"agent_runner", "api_report_service", "financial_data", "market_data_fetchers", "rag_service", "report_gen"}
FORBIDDEN_MODULES = {
    "data_fetch.core_assembler",
    "data_fetch.core_builder",
    "data_fetch.orchestrator",
    "data_fetch.payload_assembler",
    "data_fetch.yfinance_payload_builder",
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
    BACKEND / "data_fetch" / "legacy_orchestrator.py",
    BACKEND / "data_fetch" / "yfinance_payload_builder.py",
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


def test_pipeline_runtime_does_not_print_directly():
    paths = [
        BACKEND / "pipeline.py",
        BACKEND / "agent_runtime" / "quality_gates.py",
    ]

    offenders = [
        str(path.relative_to(ROOT))
        for path in paths
        if "print(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
