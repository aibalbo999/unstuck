"""Closed ASGI maintenance surface; stdlib only, no production API dependencies."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

MODE = "maintenance_verification"
IDENTITY_FILES = (
    "start_mac.command", "scripts/maintenance_verify.py",
    "backend/api_routes/maintenance_verify.py",
    "backend/institutional_report_identity.py", "backend/institutional_report_sources.py",
    "backend/institutional_report_status.py", "backend/reporting/reading_notice_values.py",
    "backend/legacy_evidence_revisions.py", "backend/trade_backtest_store.py",
    "backend/market_evidence_policy.py", "backend/report_source_admission.py",
)
ALLOWED_PATHS = frozenset({"/healthz", "/readyz", "/api/runtime-identity"})


def capture_identity(root: Path) -> dict:
    """Hash only a fixed source allowlist once; never read DBs, .env or reports."""
    root = root.resolve()
    files = {}
    for name in IDENTITY_FILES:
        path = root / name
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                files[name] = {"status": "unsafe_path"}
            else:
                files[name] = {"status": "recorded", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        except OSError as exc:
            files[name] = {"status": "unavailable", "error_kind": type(exc).__name__}
    return {
        "schema_version": "stock-agent.maintenance-identity.v1",
        "mode": MODE, "production_runtime_loaded": False,
        "identity_basis": "source_files_at_maintenance_startup",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


class MaintenanceApplication:
    def __init__(self, root: Path):
        self.root = root
        self.identity: dict = {}
        self.started = False
        self.closed = False

    async def __call__(self, scope, receive, send):
        kind = scope.get("type")
        if kind == "lifespan":
            await self._lifespan(receive, send)
            return
        if kind == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if kind != "http":
            return
        path = scope.get("path")
        allowed = (
            self.started and not self.closed
            and scope.get("method") == "GET"
            and isinstance(path, str) and path in ALLOWED_PATHS
            and scope.get("raw_path") == path.encode("ascii")
            and scope.get("query_string", b"") == b""
            and scope.get("root_path", "") == ""
        )
        status, payload = 503, {"status": "unavailable", "mode": MODE, "production_ready": False}
        if allowed:
            if path == "/api/runtime-identity":
                status, payload = 200, self.identity
            elif path == "/healthz":
                status, payload = 200, {"status": "ok", "mode": MODE, "production_ready": False}
            else:
                ready = all(row.get("status") == "recorded" for row in self.identity.get("files", {}).values())
                status, payload = (200 if ready else 503), {
                    "status": "ready" if ready else "not_ready", "mode": MODE,
                    "scope": "maintenance_listener_and_source_identity_only",
                    "production_ready": False, "operational_checks_performed": False,
                }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")), (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": body})

    async def _lifespan(self, receive, send):
        while True:
            event = await receive()
            if event.get("type") == "lifespan.startup":
                if self.started or self.closed:
                    self.started, self.closed = False, True
                    await send({"type": "lifespan.startup.failed", "message": "Maintenance lifecycle cannot be restarted."})
                    return
                try:
                    self.identity = capture_identity(self.root)
                except Exception:
                    self.closed = True
                    await send({"type": "lifespan.startup.failed", "message": "Maintenance identity unavailable."})
                    return
                self.started = True
                await send({"type": "lifespan.startup.complete"})
            elif event.get("type") == "lifespan.shutdown":
                self.started, self.closed = False, True
                await send({"type": "lifespan.shutdown.complete"})
                return
            else:
                self.started, self.closed = False, True
                await send({"type": "lifespan.startup.failed", "message": "Unsupported maintenance lifecycle event."})
                return
