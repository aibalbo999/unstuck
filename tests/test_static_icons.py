import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402


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
