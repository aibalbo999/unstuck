def test_financial_tool_utils_read_latest_numeric_from_iterator_safe_sequence():
    from financial_tool_utils import latest_numeric, safe_sequence

    assert safe_sequence(None) == []
    assert safe_sequence(iter([1, "2", object()]))[0:2] == [1, "2"]
    assert latest_numeric(["N/A", "3.5", None]) == 3.5

    class BrokenIterator:
        def __iter__(self):
            return self

        def __next__(self):
            raise RuntimeError("stop reading")

    assert safe_sequence(BrokenIterator()) == []
