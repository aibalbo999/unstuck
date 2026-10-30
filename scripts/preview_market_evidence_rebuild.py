#!/usr/bin/env python3
"""Preview explicitly selected saved reports without network, writes or models."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--filename", action="append", required=True)
    parser.add_argument("--at", required=True, help="Timezone-aware evaluation timestamp")
    args = parser.parse_args(argv)
    def no_network(*_a, **_kw):
        raise OSError("Rebuild preview cannot contact services or providers")
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    from report_rebuild_preview import build_rebuild_preview, read_saved_bundle
    evaluated = datetime.fromisoformat(args.at)
    results = []
    for filename in dict.fromkeys(args.filename):
        snapshot, hashes = read_saved_bundle(args.output_dir, filename)
        preview = build_rebuild_preview(snapshot, filename=filename, artifact_hashes=hashes, evaluated_at=evaluated)
        _, after = read_saved_bundle(args.output_dir, filename)
        if hashes != after:
            raise RuntimeError("Artifacts changed during preview; result discarded")
        results.append(preview)
    print(json.dumps({"mode": "preview_only", "execution_enabled": False, "reports": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
