import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402


def test_simplified_commercial_assets_are_served_by_fastapi():
    client = TestClient(api.app)
    assets = (
        "/static/commercial/styles/tokens.css",
        "/static/commercial/styles/shell.css",
        "/static/commercial/styles/components.css",
        "/static/commercial/styles/responsive.css",
        "/static/commercial/styles/home_entry.css",
        "/static/commercial/shared/api.js",
        "/static/commercial/shared/async_state.js",
        "/static/commercial/shared/operator_policy.js",
        "/static/commercial/shared/shell.js",
        "/static/commercial/shared/source_status.js",
        "/static/commercial/pages/decision_page.js",
        "/static/commercial/pages/stock_page.js",
        "/static/commercial/pages/portfolio_page.js",
    )

    for asset in assets:
        response = client.get(asset)
        assert response.status_code == 200, asset
        assert response.text.strip(), asset
