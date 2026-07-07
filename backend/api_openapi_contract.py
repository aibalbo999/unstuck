"""OpenAPI security annotations for mutation endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

MUTATION_METHODS = {"post", "delete", "put", "patch"}
MUTATION_SECURITY_SCHEME_NAME = "MutationToken"


def operation_requires_mutation_security(path: str, method: str) -> bool:
    return method.lower() in MUTATION_METHODS or path == "/api/maintenance/storage-summary"


def install_openapi_contract(app: FastAPI, *, mutation_header_name: str) -> None:
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        security_schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        security_schemes[MUTATION_SECURITY_SCHEME_NAME] = {
            "type": "apiKey",
            "in": "header",
            "name": mutation_header_name,
        }
        mutation_security = {MUTATION_SECURITY_SCHEME_NAME: []}
        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                if not isinstance(operation, dict):
                    continue
                if operation_requires_mutation_security(path, method):
                    security = operation.setdefault("security", [])
                    if mutation_security not in security:
                        security.append(mutation_security)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi
