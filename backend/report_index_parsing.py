"""Filename and report-summary parsing helpers for the report index."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR


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


def normalize_recommendation_label(value: str) -> str:
    text = str(value or "").strip()
    if "強烈放空" in text:
        return "強烈放空"
    if "買進" in text:
        return "買進"
    if "買入" in text or text.lower() == "buy":
        return "買入"
    if "避免" in text or "賣出" in text or text.lower() in {"avoid", "sell"}:
        return "避免"
    if "持有" in text or text.lower() == "hold":
        return "持有"
    return text or "N/A"


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

    md_filename = filename[:-5] + ".md"
    if markdown_text is None:
        md_path = os.path.join(output_dir_key(output_dir), md_filename)
        if not os.path.exists(md_path):
            return summary
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()
        except OSError:
            return summary

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

    return summary


def parse_report_filename(filename: str) -> dict:
    parts = filename.replace(".html", "").split("_report_")
    if len(parts) == 2:
        raw_ticker = parts[0]
        pipeline_id = "v1"
        if raw_ticker.endswith("_v1") or raw_ticker.endswith("_v2") or raw_ticker.endswith("_v3"):
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
        html_path = os.path.join(output_dir, filename)
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except OSError:
            html_content = ""
    match = re.search(r'<div class="sidebar-name">([^<]+)</div>', html_content or "")
    if match:
        company_name = match.group(1).strip()
    return company_name
