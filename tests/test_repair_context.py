import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_repair_attempt_context_installs_retry_state_and_preserves_existing_overrides():
    from agent_runtime.repair_context import capture_repair_context, install_repair_attempt_context

    context = {
        "_audit_retry_instruction": "previous retry",
        "_model_sequence_override": {3: ["existing-model"]},
        "structured_outputs": {7: {"old": "json"}, "7": {"legacy": "json"}, 3: {"keep": "json"}},
    }

    previous = capture_repair_context(context)
    install_repair_attempt_context(
        context,
        7,
        reflection_instruction="前次退件反思摘要：請改寫估值。",
        retry_instruction="請修復 Agent 7 的品質紅線。",
        model_sequence=["audit-model-a", "audit-model-b"],
    )

    assert previous == {
        "_audit_retry_instruction": "previous retry",
        "_audit_reflection_instruction": None,
        "_model_sequence_override": {3: ["existing-model"]},
    }
    assert context["_audit_reflection_instruction"] == "前次退件反思摘要：請改寫估值。"
    assert context["_audit_retry_instruction"] == "請修復 Agent 7 的品質紅線。"
    assert context["_model_sequence_override"] == {3: ["existing-model"], 7: ["audit-model-a", "audit-model-b"]}
    assert context["structured_outputs"] == {"7": {"legacy": "json"}, 3: {"keep": "json"}}


def test_repair_attempt_context_restore_removes_new_keys_and_restores_previous_values():
    from agent_runtime.repair_context import capture_repair_context, install_repair_attempt_context, restore_repair_context

    context = {"structured_outputs": {7: {"old": "json"}}}
    previous = capture_repair_context(context)
    install_repair_attempt_context(
        context,
        7,
        reflection_instruction="reflection",
        retry_instruction="retry",
        model_sequence=["audit-model"],
    )

    restore_repair_context(context, previous)

    assert "_audit_retry_instruction" not in context
    assert "_audit_reflection_instruction" not in context
    assert "_model_sequence_override" not in context
    assert context["structured_outputs"] == {}
