import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _nested_review_path(output_dir: Path, filename: str) -> Path:
    from report_paths import report_storage_prefix_for_filename

    return output_dir / report_storage_prefix_for_filename(filename) / f"{filename[:-5]}.review.json"


def test_review_gate_reads_partitioned_sidecar_without_explicit_storage(tmp_path):
    from report_review_gate import get_review_status

    filename = "2308_TW_v4_report_20260703_220941.html"
    sidecar = _nested_review_path(tmp_path, filename)
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(
        json.dumps({"verdict": "approved", "review_summary": "nested review"}),
        encoding="utf-8",
    )

    status = get_review_status(filename, str(tmp_path))

    assert status["verdict"] == "approved"
    assert status["review_summary"] == "nested review"


def test_review_gate_writes_partitioned_sidecar_without_explicit_storage(tmp_path):
    from report_review_gate import write_ai_review_result

    filename = "2308_TW_v4_report_20260703_220941.html"

    write_ai_review_result(
        filename,
        str(tmp_path),
        verdict="caution",
        review_summary="needs follow-up",
        critical_issues=[],
        warnings=["check source freshness"],
        review_agents_used=["local test"],
    )

    assert _nested_review_path(tmp_path, filename).is_file()
    assert not (tmp_path / f"{filename[:-5]}.review.json").exists()


def test_review_gate_keeps_legacy_flat_sidecar_readable(tmp_path):
    from report_review_gate import get_review_status

    filename = "2308_TW_v4_report_20260703_220941.html"
    (tmp_path / f"{filename[:-5]}.review.json").write_text(
        json.dumps({"verdict": "caution", "review_summary": "legacy review"}),
        encoding="utf-8",
    )

    status = get_review_status(filename, str(tmp_path))

    assert status["verdict"] == "caution"
    assert status["review_summary"] == "legacy review"


def test_review_route_uses_injected_report_storage():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api_routes.review import ReviewRouteDeps, create_review_router
    from report_paths import report_storage_candidates_for_filename
    from storage.report_storage import InMemoryStorage

    filename = "2308_TW_v4_report_20260703_220941.html"
    storage = InMemoryStorage()
    app = FastAPI()
    app.include_router(
        create_review_router(
            ReviewRouteDeps(
                get_output_dir=lambda: "/missing-output-dir",
                require_mutation_authorized=lambda _request: None,
                get_report_storage=lambda: storage,
            )
        )
    )
    client = TestClient(app)

    response = client.post(
        f"/api/report/{filename}/review",
        json={"status": "approved", "review_summary": "stored review"},
    )

    review_key = report_storage_candidates_for_filename(filename, kind="review")[0]
    assert response.status_code == 200
    assert storage.get_report(review_key) is not None
    assert client.get(f"/api/report/{filename}/review").json()["verdict"] == "approved"
