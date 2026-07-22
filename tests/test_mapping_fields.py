import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


class BrokenNativeRows(list):
    def __iter__(self):
        raise RuntimeError("native row list iterator accessor unavailable")


class BrokenLookupNativeRows(list):
    def __iter__(self):
        raise KeyError("native row list iterator lookup unavailable")


class BrokenFirstNextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("row first item unavailable")


class BrokenFirstNextRows(list):
    def __iter__(self):
        return BrokenFirstNextIterator()


def test_mapping_sequence_items_preserve_native_list_items_when_custom_iterators_fail():
    from mapping_fields import safe_sequence_items as facade_safe_sequence_items
    from mapping_sequence_items import safe_sequence_items

    rows = [{"provider": "yfinance"}]

    for value in (
        BrokenNativeRows(rows),
        BrokenLookupNativeRows(rows),
        BrokenFirstNextRows(rows),
    ):
        assert safe_sequence_items(value) == rows
        assert facade_safe_sequence_items(value) == rows


def test_mapping_sequence_items_reject_non_list_or_tuple_values():
    from mapping_sequence_items import safe_sequence_items

    assert safe_sequence_items({"not": "a sequence"}) == []
    assert safe_sequence_items("text") == []
