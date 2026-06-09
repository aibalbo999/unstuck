from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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

    assert "--host 127.0.0.1" in launcher
    assert "--host 127.0.0.1" in readme
    assert "--host 0.0.0.0" not in launcher
    assert "--host 0.0.0.0" not in readme
