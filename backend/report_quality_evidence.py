"""Read-only quality evidence lookup shared by audit and report previews."""

from __future__ import annotations

import re
from typing import Any

from mapping_fields import safe_text
from report_artifact_text import decode_utf8_artifact_text
from report_history_storage import load_storage_item


QUALITY_METADATA_FIELDS = ("report_conformance", "evidence_exit_gate", "content_credibility")
ARTIFACT_QUALITY_MARKERS = {
    "report_conformance": (re.compile(r"(?im)^\s*-\s*\*\*Report conformance:\*\*\s*\S+"), re.compile(r"(?is)<[^>]*>\s*Report conformance[:：]\s*[^<\n]+")),
    "evidence_exit_gate": (re.compile(r"(?im)^\s*-\s*\*\*Evidence gate:\*\*\s*\S+"), re.compile(r"(?is)<[^>]*>\s*Evidence gate[:：]\s*[^<\n]+")),
    "content_credibility": (
        re.compile(r"(?im)^\s*-\s*\*\*Content credibility:\*\*\s*\S+"),
        re.compile(r"(?im)^\s*-\s*\*\*內容一致性:\*\*\s*\S+"),
        re.compile(r"(?is)<[^>]*>\s*Content credibility[:：]\s*[^<\n]+"),
        re.compile(r"(?is)<[^>]*>\s*內容一致性[:：]\s*[^<\n]+"),
    ),
}


def read_artifact_quality_summary(storage: Any, filename: Any, *, load_item=load_storage_item) -> dict[str, Any]:
    source = ""
    unreadable = False
    for kind in ("md", "html"):
        try:
            item = load_item(storage, safe_text(filename).strip(), kind=kind)
        except Exception:
            continue
        if item is None:
            continue
        source = "markdown" if kind == "md" else kind
        try:
            content = item.content
            text = decode_utf8_artifact_text(content)
        except Exception:
            unreadable = True
            continue
        if text is None:
            unreadable = True
            continue
        fields = [field for field in QUALITY_METADATA_FIELDS if any(pattern.search(text) for pattern in ARTIFACT_QUALITY_MARKERS[field])]
        if fields:
            return {"status": "present", "source": source, "fields": fields}
    status = "unavailable" if unreadable or not source else "not_found"
    return {"status": status, "source": source, "fields": []}
