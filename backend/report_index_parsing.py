"""Filename and report-summary parsing helpers for the report index."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR
from recommendation_labels import normalize_recommendation_label
from reporting.mode_templates import decision_markdown_heading, get_report_template_profile


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def output_dir_key(output_dir: Optional[str] = None) -> str:
    return str(Path(output_dir or OUTPUT_DIR).expanduser().resolve())


def is_safe_report_filename(filename: str, suffix: Optional[str] = None) -> bool:
    if "/" in filename or "\\" in filename or filename != os.path.basename(filename):
        return False
    if suffix and not filename.endswith(suffix):
        return False
    return True


def clean_report_text(value: str, limit: int = 360) -> str:
    """Collapse report markdown/html text for compact API summaries."""
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def extract_section(markdown_text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown_text or "")
    return match.group("body").strip() if match else ""


def _safe_report_path_segment(value: str, *, fallback: str = "unknown") -> str:
    segment = _SAFE_SEGMENT_RE.sub("_", str(value or "").strip()).strip("._-")
    return segment or fallback


def _storage_path_candidates(output_dir: Optional[str], filename: str, basename: str) -> list[Path]:
    root = Path(output_dir_key(output_dir))
    candidates = [root / basename]
    parsed = parse_report_filename(filename)
    report_date = str(parsed.get("date") or "")
    month = report_date[:7] if re.match(r"^\d{4}-\d{2}", report_date) else "unknown-month"
    ticker = _safe_report_path_segment(str(parsed.get("ticker") or "unknown"), fallback="unknown-ticker")
    nested = root / month / ticker / basename
    if nested not in candidates:
        candidates.append(nested)
    return candidates


def _markdown_path_candidates(output_dir: Optional[str], filename: str) -> list[Path]:
    return _storage_path_candidates(output_dir, filename, filename[:-5] + ".md")


def _html_path_candidates(output_dir: Optional[str], filename: str) -> list[Path]:
    return _storage_path_candidates(output_dir, filename, filename)


def _format_report_datetime(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")


def _snapshot_generated_at(snapshot_path: str) -> str:
    if not snapshot_path:
        return ""
    try:
        with open(snapshot_path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(snapshot, dict):
        return ""
    return _format_report_datetime(snapshot.get("conclusion_generated_at") or snapshot.get("generated_at"))


def normalize_report_display_date(parsed_date: str, *, snapshot_path: str = "", timestamp: float = 0.0) -> str:
    text = str(parsed_date or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?$", text):
        return text
    from_snapshot = _snapshot_generated_at(snapshot_path)
    if from_snapshot:
        return from_snapshot
    if timestamp:
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(timestamp)))
        except (TypeError, ValueError, OSError):
            pass
    return text or "未知時間"


def parse_recommendation_summary(
    filename: str,
    output_dir: Optional[str] = None,
    markdown_text: Optional[str] = None,
) -> dict:
    """Extract the decision snapshot shown before opening a full report."""
    summary = {
        "recommendation": "N/A",
        "current_price": "N/A",
        "target_3m": "N/A",
        "target_6m": "N/A",
        "target_12m": "N/A",
        "confidence": "N/A",
        "summary": "",
    }
    if not is_safe_report_filename(filename, ".html"):
        return summary
    pipeline_id = parse_report_filename(filename).get("pipeline_id", "v1")
    mode_template = get_report_template_profile(pipeline_id)

    if markdown_text is None:
        for md_path in _markdown_path_candidates(output_dir, filename):
            if not md_path.exists():
                continue
            try:
                markdown_text = md_path.read_text(encoding="utf-8")
            except OSError:
                continue
            break
        if markdown_text is None:
            return summary

    one_page = extract_section(markdown_text, str(mode_template.get("summary_heading") or "一頁式摘要"))
    if not one_page and mode_template.get("summary_heading") != "一頁式摘要":
        one_page = extract_section(markdown_text, "一頁式摘要")
    if one_page:
        summary["summary"] = clean_report_text(one_page)

    metrics_section = extract_section(markdown_text, "📊 關鍵指標")
    price_match = re.search(
        r"^\s*-\s*\*\*股價:\*\*\s*(?P<value>.+?)\s*$",
        metrics_section,
        re.MULTILINE,
    )
    if price_match:
        summary["current_price"] = clean_report_text(price_match.group("value"), limit=80)

    decision_heading = decision_markdown_heading(mode_template).removeprefix("## ").strip()
    recommendation_section = extract_section(markdown_text, decision_heading)
    if not recommendation_section and decision_heading != "🎯 最終投資建議":
        recommendation_section = extract_section(markdown_text, "🎯 最終投資建議")
    field_map = {
        "綜合建議": "recommendation",
        "3個月目標": "target_3m",
        "6個月目標": "target_6m",
        "12個月目標": "target_12m",
        "信心指數": "confidence",
    }
    for raw_label, key in field_map.items():
        match = re.search(
            rf"^\s*-\s*\*\*{re.escape(raw_label)}:\*\*\s*(?P<value>.+?)\s*$",
            recommendation_section,
            re.MULTILINE,
        )
        if match:
            summary[key] = clean_report_text(match.group("value"), limit=80)

    if summary["recommendation"] == "N/A":
        match = re.search(r"\[投資建議\](?P<body>.*?)\[/投資建議\]", markdown_text, re.DOTALL)
        if match:
            body = match.group("body")
            fallback_map = {
                "建議": "recommendation",
                "3個月": "target_3m",
                "6個月": "target_6m",
                "12個月": "target_12m",
                "信心": "confidence",
            }
            for label, key in fallback_map.items():
                field = re.search(rf"^\s*.*{label}.*?[：:]\s*(?P<value>.+?)\s*$", body, re.MULTILINE)
                if field:
                    summary[key] = clean_report_text(field.group("value"), limit=80)

    if not summary["summary"]:
        title_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
        if title_match:
            summary["summary"] = clean_report_text(title_match.group(1))

    summary["recommendation"] = normalize_recommendation_label(summary.get("recommendation"))
    return summary


def parse_report_filename(filename: str) -> dict:
    parts = filename.replace(".html", "").split("_report_")
    if len(parts) == 2:
        raw_ticker = parts[0]
        pipeline_id = "v1"
        if raw_ticker.endswith(("_v1", "_v2", "_v3", "_v4")):
            pipeline_id = raw_ticker[-2:]
            raw_ticker = raw_ticker[:-3]
        ticker = raw_ticker.replace("_", ".")
        date_str = parts[1]
        try:
            dt = time.strptime(date_str, "%Y%m%d_%H%M%S")
            formatted_date = time.strftime("%Y-%m-%d %H:%M", dt)
        except ValueError:
            formatted_date = date_str
    else:
        ticker = filename
        formatted_date = "未知時間"
        pipeline_id = "v1"

    return {
        "ticker": ticker,
        "date": formatted_date,
        "pipeline_id": pipeline_id,
    }


def extract_company_name(filename: str, ticker: str, output_dir: str, html_content: Optional[str]) -> str:
    company_name = ticker
    if html_content is None:
        html_content = ""
        for html_path in _html_path_candidates(output_dir, filename):
            try:
                html_content = html_path.read_text(encoding="utf-8")
            except OSError:
                continue
            break
    match = re.search(r'<div class="sidebar-name">([^<]+)</div>', html_content or "")
    if match:
        company_name = match.group(1).strip()
    return company_name
