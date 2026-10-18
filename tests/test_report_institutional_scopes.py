"""Different declared transaction coverage must not be called a same-scope revision."""
from copy import deepcopy
from datetime import datetime, timezone
import json

from official_response_evidence import archive_response, read_response
from official_institutional_source import _url
from report_evidence_gap_details import institutional_detail
from test_report_evidence_gap_details import institutional_data

EXCLUDING = '本統計資訊含一般、零股、盤後定價，不含鉅額、拍賣、標購。'
INCLUDING = '本統計資訊含一般、零股、盤後定價、鉅額，不含拍賣、標購。'


def scoped_versions(old_note=EXCLUDING, new_note=INCLUDING):
    data = institutional_data()
    original = data['institutional_trading']['official_recovery']['reports'][0]
    payload = json.loads(read_response(original['raw_evidence']))
    payload['notes'] = [old_note]
    payload['data'][0][9] = '100'
    original['raw_evidence'] = archive_response(json.dumps(payload).encode(),
        source_url=_url('TWSE', original['date']), retrieved_at=datetime.now(timezone.utc).isoformat())
    newer = deepcopy(original)
    payload['notes'] = [new_note]
    payload['data'][0][8], payload['data'][0][10], payload['data'][0][18] = '1', '-99', '1155'
    newer['raw_evidence'] = archive_response(json.dumps(payload).encode(),
        source_url=_url('TWSE', original['date']), retrieved_at=datetime.now(timezone.utc).isoformat())
    return data, newer


def test_different_transaction_coverage_is_explained_without_selecting_a_winner():
    data, newer = scoped_versions()
    before = deepcopy(data)
    result = institutional_detail(data, [newer])
    conflict = result['conflicts'][0]
    assert conflict.get('kind') == 'transaction_scope_difference'
    assert conflict['official_values'] == [-100, -99]
    assert {v['includes_block_trades'] for v in conflict['observations']} == {False, True}
    assert result['status'] == 'partial' and result['matched_values'] == 2
    assert result['historical_pit_verified'] is False
    assert '不能認定差額全由鉅額交易造成' in conflict['reason']
    assert data == before


def test_same_scope_conflict_and_unknown_scope_are_not_mislabeled_as_coverage_difference():
    for old_note, new_note, expected in [(INCLUDING, INCLUDING, 'same_scope_value_conflict'),
                                          ('未宣告', INCLUDING, 'scope_unverified')]:
        data, newer = scoped_versions(old_note, new_note)
        result = institutional_detail(data, [newer])
        assert result['conflicts'][0].get('kind') == expected
        assert result['status'] == 'partial'


def test_conflicting_scope_notes_do_not_establish_block_trade_coverage():
    data, newer = scoped_versions()
    payload = json.loads(read_response(newer['raw_evidence']))
    payload['notes'] = [INCLUDING, EXCLUDING]
    newer['raw_evidence'] = archive_response(json.dumps(payload).encode(),
        source_url=_url('TWSE', newer['date']), retrieved_at=datetime.now(timezone.utc).isoformat())
    assert institutional_detail(data, [newer])['conflicts'][0]['kind'] == 'scope_unverified'
