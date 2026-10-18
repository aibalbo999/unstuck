"""Native official risk notices retain clause words without accepting active HTML."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json

import pytest

NOW = datetime(2026, 10, 14, 0, 48, tzinfo=ZoneInfo('Asia/Taipei'))
FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'
CASES = [('6504', '九'), ('2468', '十'), ('6531', '十二'), ('2340', '十三')]


@pytest.mark.parametrize('stock,clause', CASES)
def test_native_full_issuer_original_retains_risk_clauses(stock, clause):
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices, verified_notice_record
    from official_response_evidence import read_response
    raw = (FIXTURES / f'twse_{stock}_trading_notices_markup_20261014.json').read_bytes()
    expected = json.loads(raw)
    records, audit = fetch_trading_notices(stock + '.TW', now=NOW, get=lambda url: raw)
    assert audit['status'] == 'success'
    assert len(records) == audit['record_count'] == expected['total'] > 0
    assert read_response(audit['raw_response_receipt']) == raw
    assert any(f'﹝第{clause}款﹞' in record['summary'] for record in records)
    for record, row in zip(records, expected['data']):
        text = row[4]
        for known in ('九', '十', '十一', '十二', '十三'):
            text = text.replace(f"<font color='#FF0000'>﹝第{known}款﹞</font>", f'﹝第{known}款﹞')
        assert record['summary'] == text and '<' not in record['text']
        assert verified_notice_record(record, {'ticker': stock + '.TW'}) == stock
        assert record['trading_notice_receipt']['original']['raw_response_sha256'] == sha256(raw).hexdigest()


@pytest.mark.parametrize('change', ['attribute', 'case', 'encoded', 'nested', 'other_clause', 'removed_words'])
def test_new_clauses_do_not_admit_unknown_markup(change):
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices
    p = json.loads((FIXTURES / 'twse_6504_trading_notices_markup_20261014.json').read_bytes())
    tag = "<font color='#FF0000'>﹝第九款﹞</font>"
    replacements = {
        'attribute': "<font color='#FF0000' onclick='bad()'>﹝第九款﹞</font>",
        'case': "<font color='#ff0000'>﹝第九款﹞</font>",
        'encoded': tag.replace('<', '&lt;').replace('>', '&gt;'),
        'nested': "<font color='#FF0000'><b>﹝第九款﹞</b></font>",
        'other_clause': "<font color='#FF0000'>﹝第八款﹞</font>",
        'removed_words': "<font color='#FF0000'></font>",
    }
    p['data'][0][4] = p['data'][0][4].replace(tag, replacements[change])
    rows, audit = fetch_trading_notices('6504.TW', now=NOW, get=lambda url: json.dumps(p, ensure_ascii=False).encode())
    assert rows == [] and audit['status'] == 'error' and audit['record_count'] == 0
