from concurrent.futures import ThreadPoolExecutor
import pytest
from evidence_claim_boundaries import _normalize_match_text, _MATCH_TEXT_CACHE, with_match_normalization_cache


def test_cache_is_report_local_and_preserves_text_semantics():
    @with_match_normalization_cache
    def run(text):
        cache = _MATCH_TEXT_CACHE.get()
        result = _normalize_match_text(text)
        assert _normalize_match_text(text) == result
        assert len(cache) == 1
        return result, cache
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ['Revenue: 2025 / 營收', 'Revenue: 2025 / 營收']))
    assert results[0][0] == results[1][0] == 'revenue2025營收'
    assert results[0][1] is not results[1][1]
    assert _MATCH_TEXT_CACHE.get() is None


def test_failed_report_does_not_leave_cache():
    @with_match_normalization_cache
    def fail():
        _normalize_match_text('2025 Revenue')
        raise ValueError('test failure')
    with pytest.raises(ValueError):
        fail()
    assert _MATCH_TEXT_CACHE.get() is None
