#!/usr/bin/env python3
"""Fail fast when the required Playwright browser runtime is unavailable."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
BROWSER_MANIFEST = ROOT / "scripts" / "visual_browser_runtime.json"


def _error_payload(message: str, error: Exception | None = None) -> dict:
    payload = {
        "status": "blocked",
        "browser": "chromium",
        "message": message,
        "remediation": "scripts/setup_visual_regression.sh",
    }
    if error is not None:
        payload["error"] = str(error).splitlines()[0][:240]
    return payload


def _browser_identity(playwright_api, expected: dict) -> dict:
    import playwright as playwright_package

    package_version = version("playwright")
    if package_version != expected["playwright"]:
        raise RuntimeError(
            f"Playwright package {package_version} 與 manifest {expected['playwright']} 不一致。"
        )

    catalog_path = Path(playwright_package.__file__).resolve().parent / "driver" / "package" / "browsers.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    chromium = next(
        browser for browser in catalog["browsers"] if browser["name"] == expected["browser"]
    )
    if chromium["revision"] != expected["revision"]:
        raise RuntimeError(
            f"Playwright Chromium revision {chromium['revision']} 與 manifest {expected['revision']} 不一致。"
        )
    if chromium["browserVersion"] != expected["browser_version"]:
        raise RuntimeError(
            f"Playwright Chromium version {chromium['browserVersion']} 與 manifest {expected['browser_version']} 不一致。"
        )

    executable = Path(playwright_api.chromium.executable_path).resolve()
    install_dir_name = f"chromium-{expected['revision']}"
    install_dir = next((parent for parent in executable.parents if parent.name == install_dir_name), None)
    if install_dir is None or not (install_dir / "INSTALLATION_COMPLETE").is_file():
        raise RuntimeError(
            f"Chromium revision {expected['revision']} 未在 Playwright cache 完整安裝。"
        )
    return {
        "browser_revision": expected["revision"],
        "browser_version": expected["browser_version"],
        "browser_path": str(executable),
    }


def check_visual_runtime() -> dict:
    started = perf_counter()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on runner environment
        return _error_payload("Python Playwright 套件不可用。", exc)

    try:
        expected = json.loads(BROWSER_MANIFEST.read_text(encoding="utf-8"))
        with sync_playwright() as playwright:
            identity = _browser_identity(playwright, expected)
            browser = playwright.chromium.launch(headless=True)
            actual_version = browser.version
            browser.close()
            if actual_version != expected["browser_version"]:
                raise RuntimeError(
                    f"啟動後 Chromium version {actual_version} 與 manifest {expected['browser_version']} 不一致。"
                )
    except Exception as exc:  # pragma: no cover - depends on runner browser cache
        return _error_payload("Chromium 無法啟動，視覺回歸尚未具備執行環境。", exc)

    return {
        "status": "passed",
        "browser": "chromium",
        "message": "Playwright Chromium 可啟動。",
        "duration_ms": round((perf_counter() - started) * 1000, 1),
        **identity,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    payload = check_visual_runtime()
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload["message"])
        if payload["status"] != "passed":
            print(f"請先執行：{payload['remediation']}", file=sys.stderr)
            if payload.get("error"):
                print(f"Runtime error: {payload['error']}", file=sys.stderr)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
