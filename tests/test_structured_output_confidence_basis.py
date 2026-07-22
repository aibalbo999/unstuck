import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from structured_output_confidence_basis import ConfidenceBasis  # noqa: E402


class StringifyingStructuredText:
    def __str__(self) -> str:
        return "bad-body-literal"


def test_confidence_basis_filters_non_string_items_and_pads_minimum_lists():
    output = ConfidenceBasis.model_validate({
        "evidence_items": ["估值接近基本情境", StringifyingStructuredText(), "FCF 維持正值"],
        "key_risks_acknowledged": ["毛利率下滑", StringifyingStructuredText()],
        "data_gaps": [StringifyingStructuredText(), "法說會逐字稿待補"],
    })

    assert output.evidence_items == ["估值接近基本情境", "FCF 維持正值", "待補具體佐證"]
    assert output.key_risks_acknowledged == ["毛利率下滑", "待補已納入風險"]
    assert output.data_gaps == ["法說會逐字稿待補"]


def test_confidence_basis_legacy_recommendation_types_import_remains_compatible():
    from structured_output_recommendation_types import ConfidenceBasis as legacy_import

    assert legacy_import is ConfidenceBasis
