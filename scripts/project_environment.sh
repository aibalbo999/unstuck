#!/usr/bin/env bash
# Source this file; do not export project variables into global shell profiles.
stock_agent_environment() {
    local project_root interpreter settings key value
    project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
    interpreter="$("$project_root/scripts/project_python.sh")" || return 1
    settings="$("$interpreter" -B "$project_root/scripts/project_storage.py")" || return 1
    while IFS= read -r key && IFS= read -r value; do
        export "$key=$value"
    done <<< "$settings"
}
stock_agent_environment || return 1
unset -f stock_agent_environment
