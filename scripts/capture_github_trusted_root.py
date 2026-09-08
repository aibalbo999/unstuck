#!/usr/bin/env python3
"""Capture a bounded GitHub/Sigstore trusted root for later offline verification."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


MAX_BYTES = 8_388_608


def capture(*, output: Path, runner=subprocess.run) -> dict:
    if not output.is_absolute() or output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("output must be a new absolute path in an existing directory")
    try:
        completed = runner(
            ["gh", "attestation", "trusted-root"],
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("trusted-root command could not be executed") from exc
    data = completed.stdout
    if completed.returncode != 0 or not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise RuntimeError("trusted-root command failed or returned invalid output")
    try:
        documents = [json.loads(line) for line in data.splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("trusted-root output is not valid JSON lines") from exc
    if not documents or any(not isinstance(document, dict) for document in documents):
        raise RuntimeError("trusted-root output is empty or malformed")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(output.parent.resolve() / output.name, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short trusted-root write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"bytes": len(data), "document_count": len(documents)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(capture(output=args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
