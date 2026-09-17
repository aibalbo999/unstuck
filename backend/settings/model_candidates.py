"""Pure, fail-closed role opt-ins for unvalidated fallback candidates."""

from __future__ import annotations

import json
from collections.abc import Mapping

from agent_catalog import AGENT_NAMES


CRITICAL_REPORT_AGENT_NUMBERS = frozenset({4, 7, 14, 16, 19, 24})


def _role_flags(routes: dict, environ: Mapping[str, str], env_name: str, section: str, allowed_agents) -> dict[int, bool]:
    # An explicit empty/malformed environment override disables the profile map.
    # Only literal JSON true enables a known role, never truthy strings/numbers.
    if env_name in environ:
        try:
            raw = json.loads(environ[env_name])
        except (TypeError, ValueError):
            return {}
    else:
        raw = routes.get(section, {})
    if not isinstance(raw, dict):
        return {}
    return {agent: True for agent in allowed_agents if raw.get(str(agent), raw.get(agent)) is True}


def load_lite_candidate_flags(routes: dict, environ: Mapping[str, str]) -> tuple[dict[int, bool], dict[int, bool]]:
    """Keep analysis and audit-rewrite canaries independent and off by default."""
    analysis = _role_flags(
        routes, environ, "CRITICAL_LITE_FALLBACK_AGENTS_JSON",
        "critical_lite_fallback_agents", CRITICAL_REPORT_AGENT_NUMBERS,
    )
    audit = _role_flags(
        routes, environ, "AUDIT_REWRITE_LITE_FALLBACK_AGENTS_JSON",
        "audit_rewrite_lite_fallback_agents", AGENT_NAMES,
    )
    return analysis, audit
