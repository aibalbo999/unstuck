from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_state_modules_use_runtime_paths_for_defaults():
    expected_modules = [
        BACKEND / "decision_tracking_store.py",
        BACKEND / "watchlist_store.py",
        BACKEND / "job_store.py",
        BACKEND / "provider_sla.py",
        BACKEND / "report_index.py",
    ]

    for path in expected_modules:
        assert "current_runtime_paths" in _source(path), path


def test_api_routes_do_not_own_sqlite_or_report_path_guessing():
    forbidden = ("sqlite3", "report_storage_candidates_for_filename", "Path(output_dir) /")
    offenders = []
    for path in (BACKEND / "api_routes").glob("*.py"):
        source = _source(path)
        for pattern in forbidden:
            if pattern in source:
                offenders.append(f"{path.name}: {pattern}")

    assert offenders == []


def test_agent_and_operator_guides_point_to_runtime_truth_map():
    architecture = _source(ROOT / "docs" / "architecture.md")
    operator_guide = _source(ROOT / "docs" / "operator-guide.md")
    agents = _source(ROOT / "AGENTS.md")

    assert "system-architecture-map.md" in architecture
    assert "scripts/doctor_runtime.py" in operator_guide
    assert "docs/system-architecture-map.md" in agents
    assert "scripts/doctor_runtime.py" in agents
