#!/usr/bin/env python3
"""Fail fast when the required Playwright browser runtime is unavailable."""

from __future__ import annotations

import argparse
import json
import sys
from time import perf_counter


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


def check_visual_runtime() -> dict:
    started = perf_counter()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on runner environment
        return _error_payload("Python Playwright 套件不可用。", exc)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on runner browser cache
        return _error_payload("Chromium 無法啟動，視覺回歸尚未具備執行環境。", exc)

    return {
        "status": "passed",
        "browser": "chromium",
        "message": "Playwright Chromium 可啟動。",
        "duration_ms": round((perf_counter() - started) * 1000, 1),
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
