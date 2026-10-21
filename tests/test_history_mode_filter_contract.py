"""History filters must select the same mode-specific decision the card shows."""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def report(tmp_path, mode, date, *, rating="持有", parsed=None, trust="fresh"):
    import report_index
    name = f"2330_TW_{mode}_report_{date}_090000.html"
    (tmp_path / name).write_text("<html></html>")
    (tmp_path / name.replace('.html', '.md')).write_text(
        f"# 2330 台積電\n\n## 🎯 最終投資建議\n- **綜合建議:** {rating}\n")
    (tmp_path / name.replace('.html', '.data.json')).write_text(json.dumps({
        'pipeline': mode, 'data': {'ticker': '2330.TW'},
        'rerun_context': {'parsed': parsed or {}},
    }))
    report_index.upsert_report_metadata(name, output_dir=str(tmp_path), data_trust={'status': trust})
    return name


@pytest.fixture
def history(tmp_path, monkeypatch):
    import report_index
    monkeypatch.setattr(report_index, 'CACHE_DB_PATH', str(tmp_path / 'index.sqlite3'))
    def query(**kwargs):
        return report_index.query_report_metadata(
            page=1, limit=100, output_dir=str(tmp_path), sync_metadata=False,
            row_mapper=lambda row: {'filename': row['filename']}, **kwargs)
    return query


@pytest.mark.parametrize('filter_values', [
    {'recommendation': '放空'}, {'data_trust': 'stale'}, {'q': '放空'},
])
def test_hidden_versions_never_resurrect_an_old_matching_report(tmp_path, history, filter_values):
    old = report(tmp_path, 'v1', '20261001', rating='放空', trust='stale')
    report(tmp_path, 'v1', '20261021', rating='持有')
    selected, total = history(include_versions=False, **filter_values)
    assert total == 0 and selected == []
    selected, total = history(include_versions=True, **filter_values)
    assert total == 1 and selected[0]['filename'] == old


@pytest.mark.parametrize('direction', ['Long', 'Short', 'Neutral'])
def test_mode_d_filter_reads_trade_direction_not_missing_long_term_rating(tmp_path, history, direction):
    name = report(tmp_path, 'v4', '20261021', rating='N/A',
                  parsed={'trade_setup': {'trade_direction': direction}})
    selected, total = history(pipeline='v4', recommendation='v4:' + direction)
    assert total == 1 and selected[0]['filename'] == name
    wrong = 'Short' if direction != 'Short' else 'Long'
    assert history(pipeline='v4', recommendation='v4:' + wrong)[1] == 0


def test_mode_b_wait_is_independent_of_research_hold_rating(tmp_path, history):
    name = report(tmp_path, 'v2', '20261021',
                  parsed={'position_plan': {'action': '等待'}})
    assert history(pipeline='v2', recommendation='v2:等待')[0] == [{'filename': name}]
    assert history(pipeline='v2', recommendation='v2:續抱')[1] == 0


def test_watch_and_hold_remain_distinct_in_display_filters(tmp_path, history):
    report(tmp_path, 'v1', '20261021', rating='觀望',
           parsed={'recommendation': {'建議': '觀望'}})
    assert history(pipeline='v1', recommendation='v1:觀望')[1] == 1
    assert history(pipeline='v1', recommendation='v1:持有')[1] == 0


def test_unknown_direction_is_not_promoted_to_neutral(tmp_path, history):
    report(tmp_path, 'v4', '20261021', rating='N/A')
    assert history(pipeline='v4', recommendation='v4:unknown')[1] == 1
    assert history(pipeline='v4', recommendation='v4:Neutral')[1] == 0


@pytest.mark.parametrize('mode', ['v1', 'v3'])
@pytest.mark.parametrize('rating', ['買入', '持有', '觀望', '避免', '放空'])
def test_rating_categories_keep_mode_and_visible_judgment(tmp_path, history, mode, rating):
    name = report(tmp_path, mode, '20261021', rating=rating,
                  parsed={'recommendation': {'建議': rating}})
    assert history(pipeline=mode, recommendation=f'{mode}:{rating}')[0] == [{'filename': name}]
    other = '持有' if rating != '持有' else '觀望'
    assert history(pipeline=mode, recommendation=f'{mode}:{other}')[1] == 0
    other_mode = 'v3' if mode == 'v1' else 'v1'
    assert history(pipeline=mode, recommendation=f'{other_mode}:{rating}')[1] == 0


@pytest.mark.parametrize('action', ['進場', '續抱', '減碼', '等待'])
def test_position_actions_use_their_own_contract(tmp_path, history, action):
    name = report(tmp_path, 'v2', '20261021',
                  parsed={'position_plan': {'action': action}})
    assert history(pipeline='v2', recommendation='v2:' + action)[0] == [{'filename': name}]


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_missing_decision_is_selectable_without_inventing_one(tmp_path, history, mode):
    report(tmp_path, mode, '20261021', rating='N/A')
    assert history(pipeline=mode, recommendation=f'{mode}:unknown')[1] == 1


def test_missing_position_action_is_visible_as_unknown_not_research_rating(tmp_path, history):
    import report_index
    name = report(tmp_path, 'v2', '20261021', rating='持有')
    reports, _ = report_index.query_report_metadata(page=1, limit=10, output_dir=str(tmp_path),
                                                   sync_metadata=False)
    assert reports[0]['preview']['kind'] == 'position_plan'
    assert reports[0]['history_decision']['key'] == 'v2:unknown'
    assert history(pipeline='v2', recommendation='v2:等待')[1] == 0


def test_frontend_changes_mode_options_and_clears_incompatible_selection():
    script = r'''
global.window = { sessionStorage: { getItem: () => null, setItem: () => {} } };
const root = process.argv[1];
for (const file of ['pipeline_mode_fallback.js', 'ui_data_trust.js', 'ui_helpers.js', 'history_decision_filters.js', 'history_filters.js']) require(root + '/backend/static/' + file);
const element = value => ({value, innerHTML:'', events:{}, addEventListener(name,fn){this.events[name]=fn}});
const pipelineEl=element('v4'), recommendationEl=element('all');
const filters=window.StockAgentHistoryFilters.create({pipelineEl,recommendationEl});
filters.bind({onFilter(){}});
filters.setValues({pipelineFilter:'v4',recommendationFilter:'v4:Neutral'});
const before=filters.values(); const directionOptions=recommendationEl.innerHTML;
pipelineEl.value='v2'; pipelineEl.events.change();
const after=filters.values(); const actionOptions=recommendationEl.innerHTML;
filters.setValues({recommendationFilter:'v2:等待'});
process.stdout.write(JSON.stringify({before,after,final:filters.values(),directionOptions,actionOptions}));
'''
    result = subprocess.run(['node', '-e', script, str(ROOT)], check=True, capture_output=True, text=True)
    actual = json.loads(result.stdout)
    assert actual['before']['recommendationFilter'] == 'v4:Neutral'
    assert actual['after']['recommendationFilter'] == 'all'
    assert actual['final']['recommendationFilter'] == 'v2:等待'
    assert 'v4:Long' in actual['directionOptions']
    assert 'v2:等待' in actual['actionOptions'] and 'v4:Long' not in actual['actionOptions']
