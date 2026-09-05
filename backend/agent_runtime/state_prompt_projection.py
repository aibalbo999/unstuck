"""Scope and bound derived State context without cutting canonical evidence."""

import json

from config import BLIND_CONTEXT_AGENTS
from context_dependencies import upstream_agent_numbers


def restrict_state_reports(view: dict, state, agent_num: int, context: dict) -> dict:
    allowed = set() if agent_num in BLIND_CONTEXT_AGENTS else {
        str(number) for number in upstream_agent_numbers(agent_num, context)
    }
    reports = getattr(state, "agent_reports", {})
    reports = reports if isinstance(reports, dict) else {}
    excluded_flags = [
        flag.model_dump(mode="json")
        for agent_id, report in reports.items() if str(agent_id) not in allowed
        for flag in report.risk_flags
    ]
    if isinstance(view.get("agent_reports"), dict):
        view["agent_reports"] = {
            key: report for key, report in view["agent_reports"].items() if str(key) in allowed
        }
    if isinstance(view.get("risk_flags"), list):
        view["risk_flags"] = [
            flag for flag in view["risk_flags"] if isinstance(flag, dict)
            and all(str(source) in allowed for source in flag.get("source_agents", []))
            and flag not in excluded_flags
        ]
    return view


def _encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _bounded_fields(value: dict, max_chars: int) -> dict:
    """Keep whole leaves/list entries, testing the complete serialized candidate."""
    selected = {}

    def admit(target, key, item):
        target[key] = item
        if len(_encode(selected)) <= max_chars:
            return
        del target[key]
        if isinstance(item, dict):
            target[key] = {}
            for field, child in item.items():
                admit(target[key], field, child)
            if not target[key]:
                del target[key]
        elif isinstance(item, list):
            target[key] = []
            for child in item:
                target[key].append(child)
                if len(_encode(selected)) > max_chars:
                    target[key].pop()
            if not target[key]:
                del target[key]

    for key, item in value.items():
        admit(selected, key, item)
    return selected


def bound_state_analysis(view: dict, max_chars: int) -> dict:
    """Reports and their flags share a cap; financial/tool fields stay untouched."""
    reports = view.pop("agent_reports", {})
    flags = view.pop("risk_flags", [])
    reports = reports if isinstance(reports, dict) else {}
    flags = list(flags) if isinstance(flags, list) else []
    projected = {}
    for key, report in reports.items():
        if not isinstance(report, dict):
            continue
        if isinstance(report.get("risk_flags"), list):
            flags.extend(report["risk_flags"])
        # State holds the canonical structured projection. Avoid the duplicate
        # markdown already stored inside a structured response and in `prev`.
        structured = report.get("structured_output")
        if isinstance(structured, dict):
            structured = {field: item for field, item in structured.items()
                          if field != "analysis_markdown" or item != report.get("markdown")}
        projected[key] = {
            "structured_output": structured,
            **{field: item for field, item in report.items()
               if field not in {"risk_flags", "structured_output"}},
        }
    unique_flags = {_encode(flag): flag for flag in flags if isinstance(flag, dict)}
    derived = {"risk_flags": list(unique_flags.values()), "agent_reports": projected}
    if len(_encode(derived)) <= max_chars:
        view.update(derived)
        return view
    # Cap flags first so repeated risk narratives cannot crowd out report facts.
    flag_part = _bounded_fields({"risk_flags": derived["risk_flags"]}, max_chars // 3)
    selected = {"_analysis_context_omitted": True, **flag_part, "agent_reports": {}}
    remaining = max(0, max_chars - len(_encode(selected)))
    per_report = remaining // max(1, len(projected))
    for key, report in projected.items():
        part = _bounded_fields({key: report}, per_report)
        selected["agent_reports"].update(part)
    view.update(_bounded_fields(selected, max_chars))
    return view
