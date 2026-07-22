import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from structured_output_list_coercion import (  # noqa: E402
    coerce_confidence_basis,
    coerce_reasoning_steps,
    coerce_required_text_list,
    coerce_string_text_list,
)


def test_coerce_reasoning_steps_pads_sequence_inputs_to_minimum():
    assert coerce_reasoning_steps(["估值合理", 123], minimum=3) == [
        "估值合理",
        "待補推論步驟",
        "待補推論步驟",
    ]


def test_coerce_required_text_list_filters_non_string_items_and_pads():
    assert coerce_required_text_list(["FCF 維持正值", object()], 3, "待補具體佐證") == [
        "FCF 維持正值",
        "待補具體佐證",
        "待補具體佐證",
    ]


def test_coerce_string_text_list_skips_non_string_values():
    assert coerce_string_text_list(["月營收細項待補", True, 5]) == ["月營收細項待補"]


def test_coerce_confidence_basis_preserves_mapping_and_minimum_evidence_lists():
    basis = coerce_confidence_basis({
        "evidence_items": ["估值接近基本情境"],
        "key_risks_acknowledged": ["毛利率下滑", object()],
        "data_gaps": [object(), "法說會逐字稿待補"],
        "confidence_note": "中性偏保守",
    })

    assert basis["evidence_items"] == ["估值接近基本情境", "待補具體佐證", "待補具體佐證"]
    assert basis["key_risks_acknowledged"] == ["毛利率下滑", "待補已納入風險"]
    assert basis["data_gaps"] == ["法說會逐字稿待補"]
    assert basis["confidence_note"] == "中性偏保守"


def test_coerce_confidence_basis_returns_non_mapping_value_unchanged():
    value = ["not", "a", "mapping"]

    assert coerce_confidence_basis(value) is value
