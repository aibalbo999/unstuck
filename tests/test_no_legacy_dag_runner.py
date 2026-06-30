from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def test_production_pipeline_has_no_manual_dag_group_runner():
    source = (BACKEND / "pipeline_async.py").read_text(encoding="utf-8")

    assert "_run_agent_groups" not in source
    assert "asyncio.as_completed" not in source
    assert 'pipeline_def["groups"]' not in source
    assert "run_analysis_workflow" in source


def test_pipeline_runtime_has_single_async_entrypoint():
    assert not (BACKEND / "pipeline_sync.py").exists()
    assert not (BACKEND / "agent_runtime" / "pipeline_compat.py").exists()

    pipeline_source = (BACKEND / "pipeline.py").read_text(encoding="utf-8")
    legacy_source = (BACKEND / "agent_runtime" / "legacy_agent_runner.py").read_text(encoding="utf-8")

    assert "pipeline_sync" not in pipeline_source
    assert "run_analysis_pipeline =" not in pipeline_source
    assert "pipeline_compat" not in legacy_source


def test_final_audit_has_single_versionless_entrypoint():
    assert not (BACKEND / "final_audit_v3.py").exists()
    assert not (BACKEND / "final_audit_v4.py").exists()

    source = (BACKEND / "final_audit.py").read_text(encoding="utf-8")
    assert "final_audit_mode_contracts" in source
    assert "final_audit_v3" not in source
    assert "final_audit_v4" not in source
