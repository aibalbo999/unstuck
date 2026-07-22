import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_api_app_setup_installs_cors_static_and_metrics_route(tmp_path):
    from api_app_setup import install_cors_static_and_metrics

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "sample.txt").write_text("asset-ok", encoding="utf-8")
    warnings = []
    metrics_calls = []

    async def fake_metrics(summary_provider, *, task_queue):
        metrics_calls.append((summary_provider(3), task_queue))
        return "metric_line 1\n"

    app = FastAPI()
    install_cors_static_and_metrics(
        app,
        allowed_origins=["*"],
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type"],
        static_dir=str(static_dir),
        build_metrics=fake_metrics,
        get_provider_sla_summary=lambda limit=100: [{"limit": limit}],
        get_task_queue=lambda: {"queue": "test"},
        emit_warning=warnings.append,
    )

    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")
    assert cors.kwargs["allow_credentials"] is False
    assert cors.kwargs["allow_methods"] == ["GET", "OPTIONS"]
    assert warnings == ["警告：ALLOWED_ORIGINS 含萬用字元 *，已停用 credentials 支援。"]

    client = TestClient(app)
    metrics = client.get("/metrics")
    static_asset = client.get("/static/sample.txt")

    assert metrics.status_code == 200
    assert metrics.text == "metric_line 1\n"
    assert metrics.headers["content-type"].startswith("text/plain")
    assert metrics_calls == [([{"limit": 3}], {"queue": "test"})]
    assert static_asset.text == "asset-ok"
