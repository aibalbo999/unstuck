"""Narrative CapEx needs explicit purchase components, not a nearby total."""
from copy import deepcopy
import pytest

from test_capex_period_binding import projected
from evidence_financial_amounts import extract_financial_amounts

PREFIXED = ('- 資本支出與投資效率：TTM 期間購置不動產、廠房及設備（PPE）支出為 '
            '0.51391 億元，加計無形資產購置 0.06123 億元後，總資本支出約 0.57514 億元。')
POSTFIXED = ('在官方個別 TTM 期間（2025-07-01 至 2026-06-30），總資本支出（CapEx）約為 '
             '0.57514 億元（含 PPE 0.51391 億元與無形資產 0.06123 億元），這是為了確保未來產能領先。')


def selected(text):
    values = [c for c in extract_financial_amounts(text, []) if c.get('financial_capex')]
    assert values
    return values[-1]


def resolve(text, data=None):
    from evidence_capex_narrative_scope import resolve_capex_narrative_scope
    return resolve_capex_narrative_scope(selected(text), projected() if data is None else data)


@pytest.mark.parametrize('text', [PREFIXED, POSTFIXED])
def test_explicit_purchase_components_return_only_replayed_period_and_definition(text):
    data = projected(); before = deepcopy(data); claim = selected(text); original = deepcopy(claim)
    resolved = resolve(text, data)
    assert resolved['financial_capex_definition'] == 'ppe_and_intangible_purchase'
    assert resolved['financial_period_text'] == '官方個別TTM(2025-07-01至2026-06-30)'
    assert resolved['component_evidence']['ppe_purchase']['source_signed_raw_twd'] == -51391000
    assert resolved['component_evidence']['intangible_purchase']['source_signed_raw_twd'] == -6123000
    assert resolved['total_amount_verified'] is False
    assert data == before and claim == original


def test_rounded_components_use_exact_display_rounding_not_percent_tolerance():
    assert resolve(PREFIXED.replace('0.51391', '0.51').replace('0.06123', '0.06'))
    assert resolve(PREFIXED.replace('0.51391', '0.51390')) is None


@pytest.mark.parametrize('text', [
    '官方個別TTM（2025-07-01至2026-06-30）資本支出0.57514億元。',
    '官方個別TTM（2025-07-01至2026-06-30）營業現金流淨流出1.90億元，加計總資本支出0.58億元。',
    '在資本支出（2025-07-01至2026-06-30總資本支出約0.575億元）與營運資金占用下，現金流尚未轉正。',
    PREFIXED.replace('TTM期間', '2025年度').replace('TTM 期間', '2025年度'),
    PREFIXED.replace('TTM 期間', '未知公司TTM期間'),
    PREFIXED.replace('TTM 期間', '同業華通TTM期間'),
    PREFIXED.replace('TTM 期間', '合併TTM期間'),
    PREFIXED.replace('TTM 期間', '預期TTM期間'),
    PREFIXED.replace('TTM 期間', '若TTM期間'),
    PREFIXED.replace('0.51391', '-0.51391'),
    PREFIXED.replace('0.06123', '0.6123'),
    PREFIXED.replace('0.06123', '0'),
    POSTFIXED.replace('2025-07-01', '2024-07-01'),
    POSTFIXED.replace('2026-06-30', '2025-06-30'),
    POSTFIXED.replace('含 PPE', '含同業PPE'),
    POSTFIXED.replace('無形資產 0.06123', '無形資產（餘額）0.06123'),
    POSTFIXED.replace('億元與無形', '億美元與無形'),
    POSTFIXED.replace('這是為了確保未來產能領先', '此為合併報表口徑'),
    POSTFIXED.replace('這是為了確保未來產能領先', '此為台積電資料'),
    POSTFIXED.replace('這是為了確保未來產能領先', '預計還有新資本支出'),
    '# 同業華通\n' + POSTFIXED,
    '# 預期情境\n' + POSTFIXED,
    '同業華通：\n' + POSTFIXED,
])
def test_unbound_components_or_scope_do_not_gain_definition(text):
    assert resolve(text) is None


def test_missing_or_mutated_original_reference_does_not_gain_components():
    data = projected()
    data['official_financial_projection']['reference']['quarterly_document']['sha256'] = '0' * 64
    assert resolve(PREFIXED, data) is None


def test_root_can_validate_total_without_changing_original_claim():
    from evidence_official_financial_claims import official_capex_claim
    data = projected()
    original = selected(PREFIXED.replace('0.57514', '5.7514'))
    resolved = resolve(PREFIXED.replace('0.57514', '5.7514'), data)
    rebound = {**original, **{k:resolved[k] for k in ('financial_period_text', 'financial_capex_definition')},
               'financial_amount_suffix': ''}
    checked = official_capex_claim(rebound, data, tolerance_pct=1)
    assert checked['status'] == 'mismatch' and original['reported_value'] == 5.7514
