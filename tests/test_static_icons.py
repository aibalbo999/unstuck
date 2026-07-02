import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import api_routes.static_files as static_files  # noqa: E402


def test_root_shell_serves_index_without_streaming_file_response(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>Stock Agent</title>", encoding="utf-8")

    def fail_file_response(*_args, **_kwargs):
        raise AssertionError("root shell should not stream index.html with FileResponse")

    monkeypatch.setattr(static_files, "FileResponse", fail_file_response)
    app = FastAPI()
    app.include_router(static_files.create_static_router(lambda: str(tmp_path)))

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Stock Agent" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_browser_icon_paths_are_served():
    client = TestClient(api.app)

    expected_types = {
        "/favicon.ico": "image/x-icon",
        "/apple-touch-icon.png": "image/png",
        "/apple-touch-icon-precomposed.png": "image/png",
        "/static/site-icon.svg": "image/svg+xml",
    }

    for path, content_type in expected_types.items():
        response = client.get(path)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(content_type)
        assert response.content
