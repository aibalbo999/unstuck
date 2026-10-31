#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "$PROJECT_ROOT/scripts/project_environment.sh"
if [ "$#" -eq 0 ]; then
    echo 'Usage: scripts/project_exec.sh <command> [args...]' >&2
    exit 64
fi
exec "$@"
