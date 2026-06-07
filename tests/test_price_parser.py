import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from validators import _extract_price_numbers  # noqa: E402


def test_extract_price_numbers_accepts_twd_words():
    assert _extract_price_numbers("基本情境目標價 TWD 1,000") == [1000.0]
    assert _extract_price_numbers("12個月目標：新台幣 1000 元") == [1000.0]
    assert _extract_price_numbers("合理價約台幣1,250.5元") == [1250.5]
