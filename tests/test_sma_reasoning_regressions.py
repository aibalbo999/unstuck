"""Public boundary checks. Original private-data replay cases remain local."""
import pytest
from technical_reasoning import histogram_data_from_snapshot

def test_hypothetical_is_not_current_assertion():
    from technical_reasoning import sma_reasoning_checks
    assert sma_reasoning_checks('若股價站上5日線，才重新評估。', {}) == []

def test_missing_original_evidence_does_not_use_new_snapshot():
    from technical_reasoning import sma_reasoning_checks
    snapshot = {'refreshed_without_analysis_rerun': True, 'data': {'technical_indicators': {'sma_5': 1}}}
    checks = sma_reasoning_checks('收盤價站上5日線。', histogram_data_from_snapshot(snapshot))
    assert checks and all((c['status'] == 'unverifiable' for c in checks))

def test_negated_above_is_not_a_positive_assertion():
    from technical_reasoning import sma_reasoning_checks
    assert sma_reasoning_checks('股價未高於5日線。', {}) == []

@pytest.mark.parametrize('text', ['目前均線值順序為 SMA5 > SMA20 > SMA10，未達 SMA5 > SMA10 > SMA20 之標準多頭排列結構。', '當前均線順序為 SMA20 > SMA5 > SMA10，不符合典型5/10/20日多頭排列。', '動能延續情境：收盤價需帶量站穩20日均線之上。'])
def test_negated_or_required_future_order_is_not_positive(text):
    from technical_reasoning import sma_reasoning_checks
    assert sma_reasoning_checks(text, {}) == []
