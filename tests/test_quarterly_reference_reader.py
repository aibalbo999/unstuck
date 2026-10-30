from copy import deepcopy
import hashlib
import json

import pytest

from report_reader_assets import inject_reader, reader_observations
from test_report_reader_narrative_semantics import browser, page, _fixture, _load


def projected():
    return {
        'status': 'quarterly_originals_verified', 'report_scope': 'individual',
        'period_start': '2025-07-01', 'period_end': '2026-06-30',
        'acquired_at': '2026-10-23T17:30:00+08:00',
        'cashflows': {'ttm': {'operating_cash_flow': -189755000, 'ppe_purchase': -51391000,
                             'intangible_purchase': -6123000, 'free_cash_flow': -247269000}},
        'balance': {'as_of': '2026-06-30', 'total_liabilities': 3831832000,
                    'equity': 4102306000, 'interest_bearing_debt_including_leases': 2898373000},
        'ratios': {'debt_including_leases_to_equity_pct': 70.65228,
                   'total_liabilities_to_equity_pct': 93.406},
        'raw_scalar_period_verified': False,
    }


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_official_supplement_is_visible_without_rewriting_original_claim_or_quality(page, monkeypatch, mode):
    from data_fetch.market_sources import tewc_quarterly_reference as source
    monkeypatch.setattr(source, 'replay_reference', lambda review, ticker: projected())
    original = '原即期 FCF -4.61 億元；D/E 70.65%（總負債／股東權益）。'
    snapshot = {'data': {'ticker': '1623.TW', 'financial_currency': 'TWD',
                         'free_cash_flow_raw': -461411616},
                '_reader_quarterly_financial_review': {'fixture': True},
                'evidence_exit_gate': {'verdict': 'caution'}}
    before = deepcopy(snapshot)
    _load(page, inject_reader(_fixture(original, mode=mode), snapshot=snapshot))
    disclosures = page.locator('.reader-limits details:not([open]) > summary')
    for disclosure in disclosures.all():
        disclosure.click()
    limits = page.locator('.reader-limits').inner_text()
    for text in ('2025-07-01 至 2026-06-30', '-247,269,000', '70.65%', '93.41%',
                 '所列五項借款與租賃負債合計', '上述借款與租賃負債／權益',
                 '總負債／權益', '不能將原即期數值補標為此期間'):
        assert text in limits
    assert original in page.locator('.executive-thesis').all_text_contents()
    visible = page.locator('.executive-thesis').first.inner_text()
    assert '-4.61 億元' in visible and '70.65%（總負債／股東權益）' in visible
    assert any('品質 gate 未通過' in value for value in page.locator('.report-reading-notice-note').all_text_contents())
    assert snapshot == before


def test_invalid_supplement_never_uses_claimed_success_values(monkeypatch):
    from data_fetch.market_sources import tewc_quarterly_reference as source
    calls = []
    def reject(review, ticker):
        calls.append((review, ticker))
        return {'status': 'unverified', 'reason': '原件無法核對'}
    monkeypatch.setattr(source, 'replay_reference', reject)
    forged = projected()
    result = reader_observations({'data': {'ticker': '1623.TW'},
                                 '_reader_quarterly_financial_review': forged})
    assert calls == [(forged, '1623.TW')]
    assert result['evidence_gaps']['cash_flow']['quarterly_reference'] == {
        'status': 'unverified', 'reason': '原件無法核對'}


def test_quarterly_review_is_loaded_only_for_same_report_data(tmp_path):
    from report_reader_migration import _reader_snapshot
    from report_evidence_review import SCHEMA, review_key
    from test_report_reader_migration import fixture_bundle
    storage, _, name, html_key, _ = fixture_bundle(tmp_path)
    key = html_key.replace('.html', '.data.json')
    raw = storage.get_report(key).content
    review = {'schema': SCHEMA, 'filename': name, 'data_file_sha256': hashlib.sha256(raw).hexdigest(),
              'institutional_reports': [], 'quarterly_financial_review': {'fixture': True}}
    storage.save_report(review_key(key), json.dumps(review).encode(), content_type='application/json')
    assert _reader_snapshot(storage, name)[0]['_reader_quarterly_financial_review'] == {'fixture': True}
    storage.save_report(key, raw + b' ', content_type='application/json')
    assert '_reader_quarterly_financial_review' not in _reader_snapshot(storage, name)[0]
