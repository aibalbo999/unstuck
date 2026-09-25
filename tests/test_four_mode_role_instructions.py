"""Check the instructions delivered across modes, including runtime additions."""
import pytest


def request(agent, mode, *, analyses=None):
    from agent_runtime.generation_config import google_safe_agent_system_instruction
    from agent_runtime.prompting import build_prompt

    model = 'gemini-3.8-flash'
    data = {'ticker': '2330.TW', 'company_name': '台積電', 'current_price': 100,
            'data_trust': {'status': 'fresh', 'critical_failures': []}}
    context = {'pipeline_id': mode, '_prompt_model_id': model, 'analyses': analyses or {}}
    return google_safe_agent_system_instruction(agent, model), build_prompt(agent, data, context)


@pytest.mark.parametrize('agent,mode', [(3, 'v1'), (12, 'v2')])
def test_moat_roles_share_schema_dimensions_without_scoring_trend_or_forcing_dupont(agent, mode):
    from structured_output_valuation_models import MoatScores

    system, prompt = request(agent, mode)
    aliases = {field.alias or key for key, field in MoatScores.model_fields.items()}
    assert aliases == {'品牌影響力', '網路效應', '轉換成本', '成本優勢', '專利技術', '整體護城河'}
    assert all(name in system and name in prompt for name in aliases - {'整體護城河'})
    assert '趨勢不是評分維度' in prompt
    assert '不得重做杜邦' in system
    assert '至少明確寫出一項優勢與一項劣勢' not in system + prompt
    assert '5. **護城河趨勢' not in prompt


def test_a_final_receives_parallel_evidence_and_requires_reconciliation():
    _, prompt = request(7, 'v1', analyses={4: 'VALUATION_ASSUMPTION_VERSION_A', 5: 'GROWTH_CONSTRAINT_VERSION_B'})
    assert 'VALUATION_ASSUMPTION_VERSION_A' in prompt and 'GROWTH_CONSTRAINT_VERSION_B' in prompt
    assert all(term in prompt for term in ('基期', '期間', 'CapEx', '利潤率', '計算版本', '待重算'))
    assert '不得沿用舊價格冒充已重算' in prompt
    system, _ = request(4, 'v1')
    assert '與 Agent 5 平行' in system


def test_blind_financial_role_does_not_request_or_receive_upstream_summary():
    system, prompt = request(13, 'v2', analyses={11: 'UNAVAILABLE_MACRO_SUMMARY', 12: 'UNAVAILABLE_MOAT_SUMMARY'})
    assert 'UNAVAILABLE_' not in prompt
    assert '前序分析摘要：' not in prompt
    assert '盲讀' in system and '未評估' in system


@pytest.mark.parametrize('agent,mode', [(4, 'v1'), (14, 'v2')])
def test_valuation_roles_do_not_force_unavailable_growth_method_or_dcf_floor(agent, mode):
    system, prompt = request(agent, mode)
    delivered = system + prompt
    assert '可用性優先' in delivered and 'metric_status' in delivered
    assert '不得把 DCF 當作下行保護或現金流底線' in delivered
    assert '此時必須以 Forward P/E 相對估值' not in delivered
    assert 'DCF 作為**下行保護底線參考**' not in delivered
    assert '不自行創造折讓、權重或重算結果' in delivered


def test_b_growth_and_technical_roles_use_available_evidence_without_fixed_count():
    _, valuation = request(14, 'v2')
    assert '給出 3 個最具體的成長推手' not in valuation
    assert '可用性優先' in valuation and '不得' in valuation and '未評估' in valuation
    system, technical = request(15, 'v2')
    assert all(term in system + technical for term in ('1-3 個月', 'OHLCV', 'ATR', 'short_term_market_context'))
    assert 'P/E 河流圖位階與技術安全邊際' not in technical
    assert '不能作為價格支撐' in technical


@pytest.mark.parametrize('agent', [17, 18])
def test_c_evidence_roles_start_with_neutral_thesis_outcomes(agent):
    system, prompt = request(agent, 'v3')
    assert '支持／反駁／未評估' in system and '支持／反駁／未評估' in prompt
    for forced in ('正在炒作的夢想', '戳破夢想', '態度強硬', '最脆弱的泡沫假設'):
        assert forced not in system + prompt


def test_management_quotes_follow_actual_evidence_and_comparison_needs_two_transcripts():
    system, prompt = request(20, 'v1')
    assert '剛好 3 項' not in system + prompt
    assert '0–3' in prompt and '兩期' in system + prompt
    assert '逐字稿' in prompt and '日期' in prompt and '不得用新聞' in prompt


def test_debate_and_counterevidence_roles_do_not_claim_independent_sources():
    debate, prompt = request(6, 'v1')
    assert '不代表兩個獨立模型' in debate
    assert '未解爭點' in prompt
    independent, prompt = request(21, 'v3')
    assert '獨立職責' in independent and '不是盲評' in independent
    assert '不代表獨立來源' in independent
    assert '挑戰空方論點' in prompt


def test_b_position_instructions_do_not_invent_capital_or_holdings():
    system, prompt = request(16, 'v2')
    delivered = system + prompt
    for field in ('position_sizing_context', 'planning_context', 'sizing_evidence',
                  'capital_amount', 'risk_budget_amount', 'context_sha256', 'position_state'):
        assert field in delivered
    assert '不代表使用者' in delivered and '等待' in delivered
    assert '模型不得創造資金基準' in delivered
    assert '系統驗證' in delivered and '未知成本不是0' in delivered
    assert 'bounded repair' in delivered and '同步修正計畫與正文' in delivered
    assert '籌碼與 P/E 河流圖，短線下行支撐' not in delivered


def test_c_noncore_price_horizons_can_be_unassessed_without_waiving_short_gate():
    system, prompt = request(19, 'v3')
    delivered = system + prompt
    assert '給予一個合理的長期價值' not in delivered
    assert '回歸歷史估值中樞的價格' not in delivered
    assert 'N/A／未評估' in delivered
    assert '12 個月報酬' in delivered and 'target < entry < stop' in delivered
    assert 'downside_target' in delivered and '借券' in delivered


def test_d_instruction_keeps_observation_event_and_financial_risk_separate():
    system, prompt = request(24, 'v4')
    delivered = system + prompt
    for field in ('observed_signal', 'observed_source_refs', 'event_catalyst',
                  'recheck_condition', 'financial_risk_flags', 'core_catalyst', 'catalyst_source_refs'):
        assert field in delivered
    assert '在 core_catalyst 中附加' not in delivered
    assert 'core_catalyst 只用一句話描述未來' not in delivered
    assert '同一可見 event_calendar record' in delivered
    assert '模型只輸出 []' in delivered
    assert 'target < entry < stop' in delivered
