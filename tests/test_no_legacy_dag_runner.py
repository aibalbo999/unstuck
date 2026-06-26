from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def test_production_pipeline_has_no_manual_dag_group_runner():
    source = (BACKEND / "pipeline_async.py").read_text(encoding="utf-8")

    assert "_run_agent_groups" not in source
    assert "asyncio.as_completed" not in source
    assert 'pipeline_def["groups"]' not in source
    assert "run_analysis_workflow" in source

