"""Split report rendering helper."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import AGENT_MODELS

try:
    import markdown as markdown_lib
except Exception:  # pragma: no cover - dependency fallback for older local installs
    markdown_lib = None

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
JINJA_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)

AGENT_INSTITUTIONS = {
    1: "Goldman Sachs",
    2: "Morgan Stanley",
    3: "BlackRock",
    4: "JPMorgan",
    5: "Fidelity",
    6: "Financial Media",
    7: "Bridgewater",
    11: "Macro Hedge Fund",
    12: "Morningstar / BlackRock",
    13: "Muddy Waters / Morgan Stanley",
    14: "Goldman Sachs",
    15: "Point72",
    16: "Citadel",
}

def build_agent_model_labels() -> dict[int, str]:
    return {
        agent_num: f"{institution} · {AGENT_MODELS.get(agent_num, 'N/A')}"
        for agent_num, institution in AGENT_INSTITUTIONS.items()
    }


def render_report_template(template_name: str, values: dict) -> str:
    """Render a report template with precomputed report values."""
    return JINJA_ENV.get_template(template_name).render(**values)
