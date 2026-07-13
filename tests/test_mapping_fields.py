from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction

from mapping_fields import (
    safe_dict_list,
    safe_int,
    safe_mapping_dict,
    safe_mapping_items,
    safe_sequence_items,
    safe_text,
    safe_text_list,
)


def test_safe_mapping_dict_normalizes_dict_subclasses_to_plain_dict():
    class BrokenAccessorDict(dict):
        def items(self):
            raise RuntimeError("mapping items accessor unavailable")

        def keys(self):
            raise RuntimeError("mapping keys accessor unavailable")

        def __iter__(self):
            raise RuntimeError("mapping iterator unavailable")

    result = safe_mapping_dict(BrokenAccessorDict({"ticker": "NVDA", "priority_score": 900}))

    assert type(result) is dict
    assert result == {"ticker": "NVDA", "priority_score": 900}


def test_safe_mapping_dict_uses_mapping_items_when_mapping_keys_fail():
    class ItemsOnlyMapping(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            return self._data[key]

        def __iter__(self):
            raise RuntimeError("mapping iterator unavailable")

        def __len__(self):
            return len(self._data)

        def keys(self):
            raise RuntimeError("mapping keys unavailable")

        def items(self):
            return self._data.items()

    result = safe_mapping_dict(ItemsOnlyMapping({"ticker": "TSM", "priority_score": 880}))

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_uses_mapping_traversal_when_items_accessor_lookup_fails():
    class LookupItemsMapping(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            return self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

        def items(self):
            raise KeyError("mapping items lookup unavailable")

    result = safe_mapping_dict(LookupItemsMapping({"ticker": "TSM", "priority_score": 880}))

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_uses_mapping_traversal_when_items_iter_lookup_fails():
    class LookupBrokenItemsIterable:
        def __iter__(self):
            raise KeyError("mapping items iterable lookup unavailable")

    class LookupItemsIterableMapping(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            return self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

        def items(self):
            return LookupBrokenItemsIterable()

    result = safe_mapping_dict(LookupItemsIterableMapping({"ticker": "TSM", "priority_score": 880}))

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_skips_lookup_item_failures_during_mapping_traversal():
    class LookupItemMapping(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            if key == "broken":
                raise KeyError("mapping item lookup unavailable")
            return self._data[key]

        def __iter__(self):
            return iter(("broken", "ticker", "priority_score"))

        def __len__(self):
            return 3

    result = safe_mapping_dict(LookupItemMapping({"ticker": "TSM", "priority_score": 880}))

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_skips_lookup_key_hash_failures_during_mapping_traversal():
    class LookupBrokenKey:
        def __hash__(self):
            raise KeyError("mapping traversal key hash lookup unavailable")

    class LookupKeyHashTraversalMapping(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            if key in self._data:
                return self._data[key]
            raise KeyError(key)

        def __iter__(self):
            return iter((LookupBrokenKey(), "ticker", "priority_score"))

        def __len__(self):
            return 3

        def items(self):
            raise KeyError("mapping items lookup unavailable")

    result = safe_mapping_dict(LookupKeyHashTraversalMapping({"ticker": "TSM", "priority_score": 880}))

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_skips_lookup_item_unpack_failures():
    class LookupBrokenItemPair:
        def __iter__(self):
            raise KeyError("mapping item pair lookup unavailable")

    class LookupItemPairMapping(Mapping):
        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("mapping iterator unavailable")

        def __len__(self):
            return 3

        def items(self):
            return [LookupBrokenItemPair(), ("ticker", "TSM"), ("priority_score", 880)]

    result = safe_mapping_dict(LookupItemPairMapping())

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_skips_lookup_key_hash_failures():
    class LookupBrokenKey:
        def __hash__(self):
            raise KeyError("mapping key hash lookup unavailable")

    class LookupKeyHashMapping(Mapping):
        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("mapping iterator unavailable")

        def __len__(self):
            return 3

        def items(self):
            return [(LookupBrokenKey(), "BROKEN"), ("ticker", "TSM"), ("priority_score", 880)]

    result = safe_mapping_dict(LookupKeyHashMapping())

    assert type(result) is dict
    assert result == {"ticker": "TSM", "priority_score": 880}


def test_safe_mapping_dict_normalizes_empty_mapping_wrappers_to_plain_dict():
    class EmptyMapping(Mapping):
        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("empty mapping iterator unavailable")

        def __len__(self):
            return 0

        def keys(self):
            raise RuntimeError("empty mapping keys unavailable")

        def items(self):
            return []

    result = safe_mapping_dict(EmptyMapping())

    assert type(result) is dict
    assert result == {}


def test_safe_mapping_items_preserves_partial_dict_subclass_items_when_native_backing_is_empty():
    class PartialBrokenItemsIterator:
        def __init__(self, first_item):
            self._first_item = first_item
            self._step = 0

        def __iter__(self):
            return self

        def __next__(self):
            self._step += 1
            if self._step == 1:
                return self._first_item
            raise RuntimeError("mapping items stopped early")

    class PartialBrokenItemsDict(dict):
        def __init__(self, first_item):
            super().__init__()
            self._first_item = first_item

        def items(self):
            return PartialBrokenItemsIterator(self._first_item)

    result = safe_mapping_items(PartialBrokenItemsDict(("ticker", "NVDA")))

    assert result == [("ticker", "NVDA")]


def test_safe_mapping_items_skips_string_like_malformed_item_pairs():
    class StringItemMapping(Mapping):
        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("mapping iterator unavailable")

        def __len__(self):
            return 2

        def items(self):
            return ["ti", ("ticker", "NVDA")]

    result = safe_mapping_items(StringItemMapping())

    assert result == [("ticker", "NVDA")]


def test_safe_mapping_dict_skips_unhashable_mapping_item_keys():
    class UnhashableKeyMapping(Mapping):
        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("mapping iterator unavailable")

        def __len__(self):
            return 2

        def items(self):
            return [(["bad"], "BROKEN"), ("ticker", "NVDA")]

    result = safe_mapping_dict(UnhashableKeyMapping())

    assert result == {"ticker": "NVDA"}


def test_safe_int_treats_boolean_values_as_malformed_numeric_input():
    assert safe_int(True) == 0
    assert safe_int(False) == 0


def test_safe_int_treats_fractional_float_values_as_malformed_numeric_input():
    assert safe_int(1.5) == 0
    assert safe_int(-1.5) == 0
    assert safe_int(2.0) == 2


def test_safe_int_treats_fractional_exact_numeric_values_as_malformed_numeric_input():
    assert safe_int(Decimal("1.5")) == 0
    assert safe_int(Fraction(3, 2)) == 0
    assert safe_int(Decimal("2.0")) == 2
    assert safe_int(Fraction(4, 2)) == 2


def test_safe_int_uses_default_for_lookup_integer_conversion_failures():
    class LookupBrokenInt:
        def __int__(self):
            raise KeyError("integer lookup unavailable")

    assert safe_int(LookupBrokenInt()) == 0
    assert safe_int(LookupBrokenInt(), default=5) == 5


def test_safe_text_treats_boolean_values_as_malformed_text_input():
    assert safe_text(True) == ""
    assert safe_text(False) == ""


def test_safe_text_treats_binary_values_as_malformed_text_input():
    assert safe_text(b"ticker") == ""
    assert safe_text(bytearray(b"ticker")) == ""


def test_safe_text_treats_memoryview_values_as_malformed_text_input():
    assert safe_text(memoryview(b"ticker")) == ""


def test_safe_text_treats_lookup_string_conversion_failures_as_blank():
    class LookupBrokenText:
        def __str__(self):
            raise KeyError("text lookup unavailable")

    assert safe_text(LookupBrokenText()) == ""


def test_safe_text_list_uses_native_sequence_for_lookup_iterator_failures():
    class LookupBrokenTextIterator:
        def __iter__(self):
            return self

        def __next__(self):
            raise KeyError("text list lookup unavailable")

    class LookupBrokenTextList(list):
        def __iter__(self):
            return LookupBrokenTextIterator()

    assert safe_text_list(LookupBrokenTextList(["source_error:market_data"])) == ["source_error:market_data"]


def test_safe_dict_list_uses_native_sequence_for_lookup_iterator_failures():
    class LookupBrokenDictIterator:
        def __iter__(self):
            return self

        def __next__(self):
            raise KeyError("dict list lookup unavailable")

    class LookupBrokenDictList(list):
        def __iter__(self):
            return LookupBrokenDictIterator()

    assert safe_dict_list(LookupBrokenDictList([{"source": "market_data"}])) == [{"source": "market_data"}]


def test_safe_sequence_items_uses_native_sequence_for_lookup_iterator_failures():
    class LookupBrokenSequenceIterator:
        def __iter__(self):
            return self

        def __next__(self):
            raise KeyError("sequence lookup unavailable")

    class LookupBrokenSequenceList(list):
        def __iter__(self):
            return LookupBrokenSequenceIterator()

    assert safe_sequence_items(LookupBrokenSequenceList(["market_data"])) == ["market_data"]


def test_safe_sequence_items_uses_native_sequence_for_lookup_iterator_creation_failures():
    class LookupBrokenSequenceList(list):
        def __iter__(self):
            raise KeyError("sequence iterator lookup unavailable")

    assert safe_sequence_items(LookupBrokenSequenceList(["market_data"])) == ["market_data"]
