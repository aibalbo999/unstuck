#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m compileall backend
python3 -m pytest -q -m "not live"
