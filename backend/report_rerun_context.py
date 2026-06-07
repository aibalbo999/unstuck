"""Snapshot and Markdown context helpers for partial report reruns."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from fastapi import HTTPException

from data_trust import data_snapshot_filename_for_report
from report_index import is_safe_report_filename


RERUN_SCOPE_LABELS = {
    "final_recommendation": "只重跑最終建議",
    "mode_b": "只重跑模式 B",
}


def normalize_rerun_scope(scope: str) -> str:
    value = str(scope or "final_recommendation").strip().lower().replace("-", "_")
    aliases = {
        "final": "final_recommendation",
        "recommendation": "final_recommendation",
        "final_agent": "final_recommendation",
        "modeb": "mode_b",
        "v2": "mode_b",
        "trading": "mode_b",
    }
    value = aliases.get(value, value)
    if value not in RERUN_SCOPE_LABELS:
        raise HTTPException(status_code=400, detail="scope must be final_recommendation or mode_b")
    return value


def read_report_snapshot(filename: str, output_dir: str) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    data_path = os.path.join(output_dir, data_snapshot_filename_for_report(filename))
    if not os.path.exists(data_path):
        raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法局部重跑")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"資料快照無法讀取：{exc}") from exc
    if not isinstance(snapshot.get("data"), dict):
        raise HTTPException(status_code=400, detail="資料快照缺少可重跑的 data payload")
    return snapshot


def read_report_markdown(filename: str, output_dir: str) -> str:
    md_path = os.path.join(output_dir, filename[:-5] + ".md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="找不到原始 Markdown，無法還原前序 Agent 段落")
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Markdown 無法讀取：{exc}") from exc


def parse_agent_sections_from_markdown(markdown_text: str) -> dict[int, str]:
    heading_re = re.compile(r"^##\s+\d+\.\s+.*?\(Agent\s+(\d+)\)\s*$", re.MULTILINE)
    matches = list(heading_re.finditer(markdown_text or ""))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        agent_num = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        body = markdown_text[start:end]
        body = re.split(r"\n---\n\n##\s+(?:來源審計|📚)", body, maxsplit=1)[0]
        body = re.sub(r"\n---\s*$", "", body.strip())
        if body:
            sections[agent_num] = body.strip()
    return sections


def coerce_agent_map(value: Any) -> dict[int, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[int, Any] = {}
    for key, item in value.items():
        try:
            agent_num = int(key)
        except (TypeError, ValueError):
            continue
        result[agent_num] = item
    return result


def rerun_context_from_snapshot(snapshot: dict) -> tuple[dict[int, str], dict[int, Any]]:
    rerun_context = snapshot.get("rerun_context") if isinstance(snapshot.get("rerun_context"), dict) else {}
    analyses = {
        agent_num: str(text)
        for agent_num, text in coerce_agent_map(rerun_context.get("analyses")).items()
        if str(text or "").strip()
    }
    structured_outputs = coerce_agent_map(rerun_context.get("structured_outputs"))
    return analyses, structured_outputs
