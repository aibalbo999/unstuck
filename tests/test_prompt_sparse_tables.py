import copy
import json

from prompt_record_tables import pack_record_tables
from prompt_builder import format_data_for_prompt


def expand(value):
    if isinstance(value, list):
        return [expand(item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get('__record_table__') == 1:
        records = []
        for i, row in enumerate(value['rows']):
            missing = value.get('absent', {}).get(str(i), [])
            records.append({key: expand(row[j]) for j, key in enumerate(value['columns']) if j not in missing})
        return dict(zip(value['row_keys'], records)) if 'row_keys' in value else records
    return {key: expand(item) for key, item in value.items()}


def records():
    return [{'source_observation_timestamp': '2026-09-10T00:30:00+08:00',
             'source_observation_status': 'partial',
             **({'source_value_unknown': None} if i % 2 else {}),
             'source_value_zero': 0, 'source_value_false': False,
             'source_warning': '缺少資料，不可推測'} for i in range(15)]


def test_sparse_tables_save_space_without_conflating_absent_null_zero_false():
    original = records()
    before = copy.deepcopy(original)
    packed = pack_record_tables(original)
    assert packed.get('__record_table__') == 1
    assert expand(packed) == original == before
    assert list(expand(packed)[0]) == list(original[0])
    assert list(expand(packed)[1]) == list(original[1])
    assert 'source_value_unknown' not in expand(packed)[0]
    assert expand(packed)[1]['source_value_unknown'] is None
    assert expand(packed)[0]['source_value_false'] is False
    assert len(json.dumps(packed, ensure_ascii=False)) < len(json.dumps(original, ensure_ascii=False)) * 0.7


def test_sparse_tables_do_not_reorder_incompatible_records():
    original = records()
    original[-1] = dict(reversed(list(original[-1].items())))
    packed = pack_record_tables(original)
    assert isinstance(packed, list)
    assert [list(row) for row in expand(packed)] == [list(row) for row in original]


def test_identical_freshness_uses_local_reference_and_keeps_different_sources():
    freshness = {str(i): row for i, row in enumerate(records())}
    data = {'ticker': 'TEST', 'source_freshness': freshness, 'data_freshness': {'source_freshness': dict(reversed(list(copy.deepcopy(freshness).items()))) }}
    def get(dense):
        return json.loads(format_data_for_prompt(data, dense=dense).split('【財務資料 JSON】\n')[1].split('\n\n【使用規則】')[0])
    dense = get(True)
    assert dense['data_freshness']['source_freshness'] == {'$ref': '#/source_freshness'}
    decoded = expand(dense)
    decoded['data_freshness']['source_freshness'] = copy.deepcopy(decoded['source_freshness'])
    assert decoded == get(False)
    data['data_freshness']['source_freshness']['0']['source_value_zero'] = False
    assert '$ref' not in get(True)['data_freshness']['source_freshness']
