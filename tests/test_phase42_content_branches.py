"""Public boundary checks. Original private-data replay cases remain local."""
import copy
import json
import pytest
from market_context_manifest import build_source_blocks, market_assessment_workplan

@pytest.mark.parametrize('agent', [7, 16, 19])
def test_workplan_uses_only_actual_visible_refs_and_does_not_assign_impact(agent):
    data = {'global_market_context': {'items': [{'symbol': 'TEST', 'close': 10}]}, 'international_news_context': {'topics': [{'title': 'dated input'}]}}
    blocks = build_source_blocks(data, agent_num=agent)
    text = market_assessment_workplan(data, blocks)
    plan = json.loads(text.split('\n', 1)[1])
    for source, entry in plan.items():
        assert entry['visible_source_refs'] == [b['ref'] for b in blocks if b['source'] == source]
        assert 'impact' not in entry and 'reason' not in entry
    assert 'not_assessed' in text and '兩週' in text
    missing = json.loads(market_assessment_workplan({}, []).split('\n', 1)[1])
    assert all((v['available_count'] == 0 and v['visible_source_refs'] == [] for v in missing.values()))

@pytest.mark.parametrize('force', [False, True])
def test_forced_official_recovery_bypasses_cache_without_changing_dates_or_limits(monkeypatch, force):
    import official_institutional_source as official
    from datetime import datetime, timezone
    captured = []
    monkeypatch.setattr(official, 'expected_sessions', lambda *a, **k: ['2026-10-08'])

    def fetch(key, callback, **kwargs):
        captured.append((key, kwargs))
        return ({'rows': {'5314': {'foreign': -2508317, 'investment_trust': 0, 'dealer': -61862}}, 'raw_evidence': {'raw_response_sha256': 'new-version', 'retrieved_at': '2026-10-08T13:16:00Z'}}, {})
    monkeypatch.setattr('shared_provider_cache.shared_fetch', fetch)
    original = {'daily_category_observations': [{'date': '2026-10-08', 'category': 'foreign', 'net_buy_shares': 191683, 'source': 'saved', 'unit': 'shares'}]}
    before = copy.deepcopy(original)
    out, diagnostics = official.recover_institutional_observations('5314.TWO', original, now_epoch=datetime(2026, 10, 8, 13, 20, tzinfo=timezone.utc).timestamp(), limit=30, force_refresh=force)
    assert captured[0][1]['use_cache'] is (not force)
    assert captured[0][1]['freshness_seconds'] == 300
    assert diagnostics['latest_official_observation']['categories']['foreign'] == -2508317
    assert diagnostics['conflicts'][0]['selected'] == 'primary'
    assert original == before
