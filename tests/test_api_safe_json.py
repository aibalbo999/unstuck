import json
import math

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_api_safe_json_response_replaces_non_finite_numbers_with_null():
    from api_safe_json import SafeJSONResponse

    app = FastAPI(default_response_class=SafeJSONResponse)

    @app.get("/nan-payload")
    def nan_payload():
        return {
            "price": math.nan,
            "range": [math.inf, -math.inf, 42.0],
            "nested": {"score": math.nan},
        }

    response = TestClient(app).get("/nan-payload")

    assert response.status_code == 200
    assert response.json() == {
        "price": None,
        "range": [None, None, 42.0],
        "nested": {"score": None},
    }
    json.dumps(response.json(), allow_nan=False)


def test_main_api_uses_safe_json_response_by_default():
    import api
    from api_safe_json import SafeJSONResponse

    app = api.create_app()

    assert app.router.default_response_class is SafeJSONResponse
