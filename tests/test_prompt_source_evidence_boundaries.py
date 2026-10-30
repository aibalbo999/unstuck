"""Shared prompts preserve source level, observation dates and time precision."""

from copy import deepcopy
import json

import pytest

from prompt_builder import format_data_for_prompt
from prompt_rules import build_final_audit_preflight_rule, build_output_cleanliness_rule


SOURCE_LIMITS = (
    'headline_or_snippet', 'RSS', '官方原件', '前序 Agent',
    '不同觀測日期', '確切等待季數', '條件式情境', 'unassessed', 'caution',
)


def test_common_output_contract_preserves_evidence_strength_and_uncertainty():
    text = build_output_cleanliness_rule()
    for limitation in SOURCE_LIMITS:
        assert limitation in text
    assert '不是已核實政策或官方公告' in text
    assert '不構成獨立佐證' in text


@pytest.mark.parametrize('agent,pipeline', [(11, 'v1'), (1, 'v1'), (6, 'v1'),
                                          (7, 'v1'), (16, 'v2'), (19, 'v3'), (24, 'v4')])
def test_preflight_rechecks_source_strength_for_primary_and_final_roles(agent, pipeline):
    text = build_final_audit_preflight_rule(agent, pipeline)
    assert '來源層級、觀測日期與時間精度' in text
    assert '前序 Agent' in text
    assert '未評估' in text


@pytest.mark.parametrize('options', [{}, {'compact': True}, {'dense': True},
                                    {'role_scoped': True}, {'compact_json': True}])
def test_financial_prompt_keeps_raw_news_and_dates_without_promoting_them(options):
    news = {'tag': 'monetary_policy', 'headline': 'Fed raises rates, headline only',
            'source': 'RSS', 'summary': 'Only a feed snippet is available',
            'content_validation_level': 'headline_or_snippet', 'published_at': '2026-10-20',
            'url': 'https://example.test/news'}
    data = {
        'ticker': '1623.TW', 'company_name': '大東電',
        'international_news_context': {'topics': [news], 'coverage_notes': ['未讀官方原件']},
        'global_market_context': {'items': [
            {'metric': 'interest_rate', 'value': 4.8, 'as_of': '2026-09-01'},
            {'metric': 'interest_rate', 'value': 5.1, 'as_of': '2026-10-01'},
        ]},
        'recent_catalysts': [{'title': '擴廠規劃', 'timeframe': '2027 H1'}],
    }
    before = deepcopy(data)
    text = format_data_for_prompt(data, **options)
    result = json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])
    # These records are never table-packed at the optional-context paths.
    assert result['international_news_context']['topics'] == [news]
    assert result['global_market_context']['items'] == data['global_market_context']['items']
    assert result['market_catalysts']['items'] == data['recent_catalysts']
    for limitation in ('headline_or_snippet', '官方原件', '不同觀測日期', '確切等待季數', '條件式情境'):
        assert limitation in text.split('【使用規則】', 1)[1]
    assert data == before
