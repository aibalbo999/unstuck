"""Canonical research playbook registry."""

from __future__ import annotations

from typing import Any

from pipeline_modes import PIPELINE_DEFINITIONS


_PIPELINE_CATEGORIES = {
    "v1": "deep_research",
    "v2": "trading",
    "v3": "contrarian",
    "v4": "event_driven",
}


def list_playbooks() -> list[dict[str, Any]]:
    """Return every canonical research playbook."""
    playbooks = [_playbook_from_pipeline(pipeline_id, definition) for pipeline_id, definition in PIPELINE_DEFINITIONS.items()]
    playbooks.extend(_NON_PIPELINE_PLAYBOOKS)
    return [dict(item) for item in playbooks]


def get_playbook(playbook_id: str) -> dict[str, Any]:
    """Return a playbook by id or raise KeyError."""
    normalized = str(playbook_id or "").strip().lower()
    for playbook in list_playbooks():
        if playbook["id"] == normalized:
            return playbook
    raise KeyError(f"unknown research playbook: {playbook_id}")


def playbook_summary(playbook_id: str) -> dict[str, Any]:
    """Return a compact summary for UI, docs, and pipeline labels."""
    playbook = get_playbook(playbook_id)
    return {
        "id": playbook["id"],
        "label": playbook["label"],
        "category": playbook["category"],
        "pipeline_id": playbook["pipeline_id"],
        "output_contract": playbook["output_contract"],
        "gates": list(playbook["gates"]),
    }


def _playbook_from_pipeline(pipeline_id: str, definition: dict[str, Any]) -> dict[str, Any]:
    structured_kinds = sorted((definition.get("structured_agents") or {}).keys())
    gates = ["資料可信度", "Final audit", "Evidence exit gate"]
    if "recommendation" in structured_kinds:
        gates.append("投資論文")
    if "trade_setup" in structured_kinds:
        gates.append("交易計畫")
    return {
        "id": str(pipeline_id),
        "label": definition["label"],
        "short_label": definition["short_label"],
        "category": _PIPELINE_CATEGORIES.get(str(pipeline_id), "deep_research"),
        "pipeline_id": str(pipeline_id),
        "agent_sequence": list(definition["agents"]),
        "agent_groups": [list(group) for group in definition["groups"]],
        "structured_outputs": structured_kinds,
        "gates": gates,
        "output_contract": "HTML/Markdown report + data snapshot + review metadata",
        "source": "backend/pipeline_modes.py",
    }


_NON_PIPELINE_PLAYBOOKS: list[dict[str, Any]] = [
    {
        "id": "investment-checklist",
        "label": "巴菲特買入前 Checklist",
        "short_label": "買入前 Checklist",
        "category": "discipline",
        "pipeline_id": None,
        "agent_sequence": [],
        "agent_groups": [],
        "structured_outputs": ["checklist_result", "mirror_test"],
        "gates": ["能力圈", "好生意", "護城河", "管理層", "安全邊際", "鏡子測試", "快速否決"],
        "output_contract": "pass/gray/reject + 鏡子測試 + 快速否決理由",
        "source": "ai-berkshire skills/investment-checklist.md",
    },
    {
        "id": "thesis-tracker",
        "label": "投資論文追蹤",
        "short_label": "論文追蹤",
        "category": "discipline",
        "pipeline_id": None,
        "agent_sequence": [],
        "agent_groups": [],
        "structured_outputs": ["investment_thesis", "thesis_health"],
        "gates": ["核心假設", "紅線", "估值錨點", "健康度"],
        "output_contract": "核心假設 + 紅線 + 論文健康度 + 下次檢查條件",
        "source": "ai-berkshire skills/thesis-tracker.md",
    },
    {
        "id": "portfolio-review",
        "label": "組合管理與優化",
        "short_label": "組合檢查",
        "category": "portfolio",
        "pipeline_id": None,
        "agent_sequence": [],
        "agent_groups": [],
        "structured_outputs": ["portfolio_health"],
        "gates": ["集中度", "相關性", "風險貢獻", "再平衡"],
        "output_contract": "portfolio health + concentration risks + rebalance actions",
        "source": "ai-berkshire skills/portfolio-review.md",
    },
    {
        "id": "quality-screen",
        "label": "去劣篩選",
        "short_label": "Quality Funnel",
        "category": "screening",
        "pipeline_id": None,
        "agent_sequence": [],
        "agent_groups": [],
        "structured_outputs": ["quality_funnel"],
        "gates": ["ROE", "FCF", "利息保障", "毛利率", "OCF/NI", "淨利率", "股本稀釋"],
        "output_contract": "pass/gray/reject + triggered rules + exemption notes",
        "source": "ai-berkshire skills/quality-screen.md",
    },
]
