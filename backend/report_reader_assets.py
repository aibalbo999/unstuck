"""Reversible, presentation-only additions to saved HTML reports."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

START = "<!-- onstock-reader:start:v1 -->"
END = "<!-- onstock-reader:end:v1 -->"
TEMPLATES = Path(__file__).resolve().parent / "templates"


def reader_payload() -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.get_template("includes/report_reader.html.j2").render()


def remove_reader(html: str) -> str:
    if "<!-- onstock-reader:" not in html:
        return html
    if html.count(START) != 1 or html.count(END) != 1:
        raise ValueError("Unknown or incomplete reader asset block")
    start, end_start = html.index(START), html.index(END)
    if end_start < start:
        raise ValueError("Invalid reader asset block order")
    end = end_start + len(END)
    return html[:start] + html[end:]


def inject_reader(html: str) -> str:
    original = remove_reader(html)
    if not re.search(r'<main\b[^>]*class=["\'][^"\']*\bmain\b', original, re.I):
        raise ValueError("Unrecognized report HTML")
    closing = re.search(r"</body\s*>\s*</html\s*>\s*$", original, re.I)
    if closing is None:
        raise ValueError("Incomplete report HTML")
    return original[:closing.start()] + reader_payload() + original[closing.start():]
