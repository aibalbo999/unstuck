"""Campaign selection must not mistake diagnostic inputs for full research."""

import copy
import json
from pathlib import Path

import pytest

from quality_campaign_sources import inventory_sources, source_screen


def snapshot(mode='v1'):
    return {'pipeline': mode, 'ticker': '2330.TW', 'data': {
        'ticker': '2330.TW', 'fetch_date': '2026年09月11日',
        'sector': 'Technology', 'industry': 'Semiconductors', 'earnings_call': {}}}


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3'])
def test_missing_transcript_excludes_full_research_without_changing_source(mode):
    source = snapshot(mode)
    before = copy.deepcopy(source)
    result = source_screen(source)
    assert result['status'] == 'excluded_from_full_research'
    assert 'missing_earnings_call_transcript' in result['blockers']
    assert source == before


def test_v4_does_not_require_agent20_but_is_not_auto_qualified():
    result = source_screen(snapshot('v4'))
    assert result['status'] == 'needs_source_review'
    assert result['qualified_for_live'] is False
    assert 'missing_earnings_call_transcript' not in result['blockers']


def test_nonempty_transcript_is_only_a_candidate_not_proof():
    source = snapshot()
    source['data']['earnings_call']['transcript'] = 'Unverified local transcript candidate'
    result = source_screen(source)
    assert result['status'] == 'needs_source_review'
    assert result['qualified_for_live'] is False
    assert result['cutoff'] == '2026-09-11'


def test_etf_identity_cannot_supply_company_industry_diversity():
    source = snapshot('v4')
    source['ticker'] = source['data']['ticker'] = '0050.TW'
    source['data']['company_identity'] = {'industry_categories': ['ETF']}
    before = copy.deepcopy(source)
    result = source_screen(source)
    assert result['industry_quota_status'] == 'not_a_company_industry_sample'
    assert 'fund_identity_requires_separate_qualification' in result['source_flags']
    assert result['status'] == 'needs_source_review'  # Not proof all ETF v4 research fails.
    assert source == before


def test_ordinary_industry_label_remains_unverified_not_auto_qualified():
    result = source_screen(snapshot('v4'))
    assert result['industry_quota_status'] == 'unverified'


def test_corrupted_transcript_is_recorded_as_source_issue():
    source = snapshot()
    source['data']['earnings_call']['transcript'] = 'Results Mee\ufffdng with ques\ufffdons'
    result = source_screen(source)
    assert 'transcript_text_contains_replacement_character' in result['blockers']
    assert result['qualified_for_live'] is False


@pytest.mark.parametrize('cutoff', [None, '', 'N/A', '2026-02-30', '2026-09-11 extra'])
def test_cutoff_cannot_be_invented_from_generation_time(cutoff):
    source = snapshot('v4')
    source['data']['fetch_date'] = cutoff
    source['generated_at'] = '2026-09-14'
    assert 'invalid_source_cutoff' in source_screen(source)['blockers']


@pytest.mark.parametrize('mode', [None, '', 'both', 'unknown'])
def test_no_default_mode_in_cohort_identity(mode):
    assert 'invalid_pipeline_identity' in source_screen(snapshot(mode))['blockers']


def test_generated_context_cannot_supply_missing_source_transcript():
    source = snapshot()
    source['rerun_context'] = {'analyses': {'20': 'Invented transcript text'}}
    assert 'missing_earnings_call_transcript' in source_screen(source)['blockers']


def test_conflicting_company_identity_not_a_valid_pair():
    source = snapshot('v4')
    source['data']['ticker'] = '2882.TW'
    assert 'conflicting_ticker_identity' in source_screen(source)['blockers']


def test_inventory_counts_duplicate_snapshots_once_and_retains_malformed(tmp_path):
    import json
    for name in ('one', 'two'):
        (tmp_path / (name + '.data.json')).write_text(json.dumps(snapshot('v4')))
    (tmp_path / 'bad.data.json').write_text('{"data": {}, "data": {}}')
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    result = inventory_sources(tmp_path)
    assert result['artifact_files'] == 3
    assert result['unreadable_files'] == 1
    assert result['source_unchanged'] is True
    assert result['by_mode']['v4']['necessary_check_remaining_unique_pairs'] == 1
    assert result['by_mode']['v4']['qualified_for_live'] == 0
    assert result['by_mode']['v4']['impossible_with_this_same_mode_pool'] is True
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_inventory_does_not_follow_symlink(tmp_path):
    import json
    actual = tmp_path / 'source.json'
    actual.write_text(json.dumps(snapshot('v4')))
    (tmp_path / 'linked.data.json').symlink_to(actual)
    result = inventory_sources(tmp_path)
    assert result['rows'][0]['blockers'] == ['symlink_source_not_read']
    assert result['rows'][0]['qualified_for_live'] is False


def test_source_metadata_error_is_recorded_not_an_inventory_abort(tmp_path, monkeypatch):
    target = tmp_path / 'one.data.json'
    target.write_text(json.dumps(snapshot('v4')))
    original = Path.stat

    def unavailable(path, *args, **kwargs):
        if path == target and kwargs.get('follow_symlinks', True):
            raise FileNotFoundError('source disappeared before read')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', unavailable)
    result = inventory_sources(tmp_path)
    assert result['unreadable_files'] == 1
    assert result['rows'][0]['qualified_for_live'] is False


def test_symlink_swap_after_containment_check_never_reads_outside(tmp_path, monkeypatch):
    root = tmp_path / 'inventory'
    root.mkdir()
    target, outside = root / 'one.data.json', tmp_path / 'outside.json'
    target.write_text(json.dumps(snapshot('v4')))
    outside.write_text(json.dumps(snapshot('v4')))
    original_resolve, original_read = Path.resolve, Path.read_bytes
    swapped, outside_reads = [], []

    def swap(path, *args, **kwargs):
        result = original_resolve(path, *args, **kwargs)
        if path == target and not swapped:
            target.unlink()
            target.symlink_to(outside)
            swapped.append(True)
        return result

    def read(path):
        if path == target and original_resolve(path) == outside:
            outside_reads.append(True)
        return original_read(path)

    monkeypatch.setattr(Path, 'resolve', swap)
    monkeypatch.setattr(Path, 'read_bytes', read)
    result = inventory_sources(root)
    assert swapped and not outside_reads
    assert result['unreadable_files'] == 1
    assert result['rows'][0]['qualified_for_live'] is False


def test_named_pipe_is_rejected_without_waiting_for_writer(tmp_path):
    import os
    os.mkfifo(tmp_path / 'pipe.data.json')
    result = inventory_sources(tmp_path)
    assert result['unreadable_files'] == 1
