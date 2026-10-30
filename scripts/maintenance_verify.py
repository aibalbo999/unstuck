"""Explicit, standalone maintenance listener. Never import the production API."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8080


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["--maintenance-verify"] or os.environ.get("LAN_ACCESS", "0") not in ("", "0", "false", "no"):
        print("Maintenance verification requires --maintenance-verify and loopback-only configuration.", file=sys.stderr)
        return 64

    # -I/-B are provided by the launcher. Direct invocation must also avoid
    # creating bytecode in the checkout; no .env or runtime settings are loaded.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "backend"))
    from api_routes.maintenance_verify import MaintenanceApplication

    try:
        # Own only this new socket. An existing listener or simultaneous start
        # fails here; there is no PID lookup, signal, Redis operation, or cleanup.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((HOST, PORT))
            import uvicorn

            config = uvicorn.Config(
                MaintenanceApplication(ROOT), host=HOST, port=PORT,
                workers=1, reload=False, loop="asyncio", http="h11", ws="none",
                interface="asgi3", lifespan="on", proxy_headers=False,
                access_log=False, log_config=None, log_level="warning",
                server_header=False, date_header=False, timeout_keep_alive=1,
                timeout_graceful_shutdown=2,
            )
            server = uvicorn.Server(config)
            print("Maintenance verification only: http://127.0.0.1:8080; production API, workers and Redis are not started.", flush=True)
            server.run(sockets=[listener])
            return 0 if server.started else 1
    except KeyboardInterrupt:
        return 130
    except OSError:
        print("Maintenance listener unavailable; existing services were not inspected or stopped.", file=sys.stderr)
        return 1
    except ImportError:
        print("Maintenance dependencies unavailable; nothing will be installed.", file=sys.stderr)
        return 69


if __name__ == "__main__":
    raise SystemExit(main())
