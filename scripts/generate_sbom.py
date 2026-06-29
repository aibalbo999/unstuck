#!/usr/bin/env python3
"""Generate a minimal CycloneDX SBOM from the backend lockfile."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = ROOT / "backend" / "requirements.lock"
DEFAULT_OUTPUT = ROOT / "backend" / "cache" / "sbom.cdx.json"


def _package_url(name: str, version: str) -> str:
    normalized = name.lower().replace("_", "-")
    return f"pkg:pypi/{normalized}@{version}"


def parse_locked_components(path: Path) -> list[dict[str, str]]:
    components = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "==" not in stripped:
            continue
        name, version = [part.strip() for part in stripped.split("==", 1)]
        components.append({
            "type": "library",
            "name": name,
            "version": version,
            "purl": _package_url(name, version),
        })
    return components


def build_sbom(requirements: Path) -> dict:
    components = parse_locked_components(requirements)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [
                {
                    "type": "application",
                    "name": "stock-agent-generate-sbom",
                    "version": "1",
                }
            ],
        },
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a CycloneDX SBOM from requirements.lock")
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.requirements.exists():
        parser.error(f"requirements file does not exist: {args.requirements}")
    sbom = build_sbom(args.requirements)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sbom, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SBOM written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
