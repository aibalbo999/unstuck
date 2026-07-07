from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_runtime_paths_names_canonical_and_legacy_state_locations(tmp_path):
    from runtime_paths import RuntimePaths

    paths = RuntimePaths.from_values(
        output_dir=tmp_path / "output",
        cache_dir=tmp_path / "cache",
    )

    assert paths.output_dir == tmp_path / "output"
    assert paths.report_index_db == tmp_path / "cache" / "stock_agent_cache.sqlite3"
    assert paths.operational_db == tmp_path / "cache" / "operational.sqlite3"
    assert paths.task_db == paths.operational_db
    assert paths.legacy_decision_tracking_db == tmp_path / "cache" / "decision_tracking.sqlite3"

    summary = paths.as_dict()
    assert summary["decision_tracking_db"] == {
        "path": str(paths.task_db),
        "canonical": True,
        "owner": "decision_tracking_store",
    }
    assert summary["legacy_decision_tracking_db"] == {
        "path": str(paths.legacy_decision_tracking_db),
        "canonical": False,
        "owner": "legacy migration only",
    }


def test_current_runtime_paths_reads_grouped_settings():
    from runtime_paths import current_runtime_paths

    paths = current_runtime_paths()

    assert paths.output_dir.name == "output"
    assert paths.report_index_db.name == "stock_agent_cache.sqlite3"
    assert paths.operational_db.name == "operational.sqlite3"
    assert paths.task_db == paths.operational_db
