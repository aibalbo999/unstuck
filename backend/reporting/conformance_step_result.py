"""Shared decision-tree result helpers for report conformance."""

from __future__ import annotations

from typing import Any


def step(step_id: str, status: str, message: str, details: Any = None) -> dict:
    result = {"id": step_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def issue_from_step(item: dict) -> dict:
    return {"id": item["id"], "message": item["message"], "details": dict.get(item, "details")}


def step_result(item: dict, *, issue_kind: str | None = None) -> dict:
    result = {"decision_tree": [item], "blocking_issues": [], "warnings": []}
    if issue_kind == "blocking":
        result["blocking_issues"].append(issue_from_step(item))
    elif issue_kind == "warning":
        result["warnings"].append(issue_from_step(item))
    return result


def merge_step_result(target: dict, source: dict) -> None:
    target["decision_tree"].extend(source["decision_tree"])
    target["blocking_issues"].extend(source["blocking_issues"])
    target["warnings"].extend(source["warnings"])
