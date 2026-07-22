import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agent_runtime.deterministic_fallback_audit import (  # noqa: E402
    clear_agent_blocking_issues,
    record_deterministic_fallback,
)


def test_clear_agent_blocking_issues_removes_agent_number_and_name_prefixes():
    context = {
        "blocking_issues": [
            "Agent 4 目標股價: 缺少 JSON",
            "Agent 4: 解析失敗",
            "投資銀行估值分析: 估值紅線",
            "Agent 7 最終投資決策: 仍需修復",
        ]
    }

    clear_agent_blocking_issues(context, 4)

    assert context["blocking_issues"] == ["Agent 7 最終投資決策: 仍需修復"]


def test_clear_agent_blocking_issues_drops_empty_list():
    context = {"blocking_issues": ["Agent 4 目標股價: 缺少 JSON"]}

    clear_agent_blocking_issues(context, 4)

    assert "blocking_issues" not in context


def test_record_deterministic_fallback_caps_issues_and_filters_metadata():
    context = {}
    issues = [f"issue-{idx}" for idx in range(7)]

    record_deterministic_fallback(
        context,
        4,
        "已套用 deterministic 三情境估值 fallback",
        "repair_429_failure",
        issues=issues,
        raw_failure="x" * 260,
        metadata={"kept": "yes", "dropped": None},
    )

    entry = context["deterministic_fallbacks"][0]
    assert entry["type"] == "deterministic_fallback"
    assert entry["agent_num"] == 4
    assert entry["issues"] == issues[:5]
    assert entry["raw_failure"] == "x" * 240
    assert entry["metadata"] == {"kept": "yes"}
    assert entry["created_at"]
