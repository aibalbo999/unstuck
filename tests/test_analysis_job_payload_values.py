import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_analysis_job_payload_value_helpers_coerce_bool_int_and_timestamp_fields():
    from analysis_job_payload_values import (
        _iso_timestamp,
        _safe_bool_field,
        _safe_bool_flag,
        _safe_int,
        _safe_optional_int,
    )

    assert _safe_bool_flag(" yes ") is True
    assert _safe_bool_flag("off", default=True) is False
    assert _safe_bool_flag(memoryview(b"true"), default=True) is True
    assert _safe_bool_flag({"truthy": True}) is False
    assert _safe_bool_field(Decimal("1")) is True
    assert _safe_bool_field(Fraction(0, 1)) is False
    assert _safe_bool_field(2) is False

    assert _safe_int(Fraction(3, 1)) == 3
    assert _safe_int(Fraction(3, 2)) == 0
    assert _safe_int(Decimal("4")) == 4
    assert _safe_int(Decimal("4.5")) == 0
    assert _safe_int(-1) == 0
    assert _safe_optional_int("7") == 7
    assert _safe_optional_int("7.0") == 7
    assert _safe_optional_int("7.5") is None
    assert _safe_optional_int(memoryview(b"7")) is None

    assert _iso_timestamp(0) == "1970-01-01T00:00:00Z"
    assert _iso_timestamp(Decimal("1")) == "1970-01-01T00:00:01Z"
    assert _iso_timestamp(memoryview(b"0")) is None


def test_analysis_job_payload_value_helpers_reject_arbitrary_numeric_objects():
    from analysis_job_payload_values import _iso_timestamp, _safe_optional_int

    class NumericLike:
        def __float__(self):
            return 1.0

        def __int__(self):
            return 1

    assert _safe_optional_int(NumericLike()) is None
    assert _iso_timestamp(NumericLike()) is None
