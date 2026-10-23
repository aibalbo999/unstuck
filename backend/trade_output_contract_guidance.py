"""Prepare explicit field references without repairing or adopting rejected claims."""
from __future__ import annotations

import hashlib
import json

CORE_REFERENCE_TOKEN = '@observed_signal'
RESOLUTION_VERSION = 'trade-core-reference:v1'


def trade_fact_output_instruction(agent_num, data=None):
    """Role guidance refers to raw input paths, never generated Agent evidence."""
    if agent_num not in {22, 23, 24}:
        return ''
    common = ('【短線事實與判斷輸出契約】\n'
        '先列原始觀測，再另段解釋研究判斷；不得把其他 Agent 的 agent_reports、analyses、'
        'parsed 或 structured_outputs 生成文字當作獨立證據。價格目標／進出場是模型情境，'
        '不得用另一個 Agent 的同數值證明其已發生。每一個數值事實引用本次原始資料路徑，'
        '寫明日期、主體、期間、單位與價格／成交量基準；缺原件保留未知，不補造路徑或數字。'
        '不得為通過 gate 刪反證、改方向或把 Neutral 當作品質通過。\n')
    if agent_num in {22, 23}:
        role = ('技術事實只引用 data.technical_indicators、data.daily_market_data 的本次原始欄位；'
                '一個SMA/MACD數字一行，以確切指標名稱:value表達，不把價格支撐、預測或其他指標併為已觀測值。'
                if agent_num == 22 else
                '法人事實沿用上方逐項來源契約的 institutional_trading 原始 ref；'
                '保持合計／外資／投信／自營商主體、觀測日、單日／累計期間與股／千股單位，'
                '累計數字不能證明連續買超、交錯或趨勢。')
        return common + role + ('evidence_items 每筆 finding 僅寫該來源支持的事實，source_refs 列其確切原始路徑；'
            'freshness_note 記原觀測日期，counterevidence 保留限制；analysis_markdown 的數值事實逐項沿用相同引用，'
            '判斷、條件、情境另段標示，不自行新增 evidence_matrix 或聲稱已驗證。') + _upstream_fact_examples(agent_num, data)
    return common + ('observed_signal 是唯一已觀測事實文字，可含多項事實，但每項都需自己的 observed_source_refs；'
        '先核對事實後才寫完整「等待…後再重新評估」的純未來 recheck_condition。'
        'core_catalyst 若複述觀測，必須逐字包含完整 observed_signal，不得只取其中一項或重新改寫；'
        '事件與財務警示各留原欄。可選擇明示欄位引用：core_catalyst="@observed_signal"，'
        'core_catalyst_reference="observed_signal"，且 catalyst_source_refs 與 observed_source_refs 完全一致。'
        '系統僅在原觀測、引用與其他原有來源檢查全部通過後解析此引用；解析不等於整份品質通過。'
        '未選此方式時 core_catalyst_reference 為 null 或省略，原 exact matching 與所有 gate 保持；'
        '不可把不同事實的 core 加上 reference 來隱藏矛盾。無已觀測事實時 observed_signal=null，'
        '不要使用引用 token，core_catalyst 只寫完整未來等待條件。')


def _upstream_fact_examples(agent_num, data):
    """Examples carry only existing scoped raw facts, not generated conclusions."""
    if not isinstance(data, dict):
        return ''
    if agent_num == 23:
        # build_prompt already includes the complete typed institutional facts;
        # do not duplicate or replace that block with a truncated list here.
        return ''
    from evidence_technical_claims import technical_snapshot_values
    technical = data.get('technical_indicators')
    technical = technical if isinstance(technical, dict) else {}
    facts = []
    for item in technical_snapshot_values(technical):
        field = item['path'].rsplit('.', 1)[-1]
        label = 'SMA' + field[4:] if field.startswith('sma_') else field
        facts.append(f"- {technical['as_of']} {label}: {item['value']:.15g}元（source ref={item['path']}）")
    if not facts:
        return '\n本次沒有可逐項列出的原始事實示例；不得借用其他 Agent 產文補值。'
    return ('\n【本次原始欄位的有限事實句示例】\n'
        '僅示範保留原日期與欄位，未代表研究判斷、價格計畫或整份品質已通過；缺基準不補猜。\n'
        + '\n'.join(facts[:6]))


def prepare_core_reference(payload, context, raw_text):
    """Resolve only an explicit exact field copy after unmodified source checks.

    Ordinary claims, including mismatching summaries, are returned unchanged.
    The caller must withhold an unresolved token from publication.
    """
    reference = payload.get('core_catalyst_reference')
    core = payload.get('core_catalyst')
    observed = payload.get('observed_signal')
    if reference is None and core != CORE_REFERENCE_TOKEN:
        return payload, None
    if reference != 'observed_signal':
        return payload, {'status': 'unresolved', 'reason': 'invalid_core_catalyst_reference'}
    if core != CORE_REFERENCE_TOKEN and core != observed:
        # Do not rewrite, remove, or rescue a real conflicting original assertion.
        return payload, None
    if not isinstance(observed, str) or not observed.strip():
        return payload, {'status': 'unresolved', 'reason': 'missing_observed_signal'}
    if CORE_REFERENCE_TOKEN in observed:
        return payload, {'status': 'unresolved', 'reason': 'unresolved_observed_signal_reference'}
    refs = payload.get('observed_source_refs')
    if not isinstance(refs, list) or not refs or refs != payload.get('catalyst_source_refs'):
        return payload, {'status': 'unresolved', 'reason': 'core_reference_source_refs_mismatch'}
    candidate = {**payload, 'core_catalyst': observed}
    from trade_source_contract import bind_trade_payload, missing_trade_fields, SUPPORTED_VERSIONS
    manifest = context.get('_trade_source_manifest')
    if (not isinstance(manifest, dict) or manifest.get('version') not in SUPPORTED_VERSIONS
            or not manifest.get('visible') or missing_trade_fields(candidate, context=context)):
        return payload, {'status': 'unresolved', 'reason': 'unbound_or_incomplete_core_reference'}
    _, assessment = bind_trade_payload(candidate, context)
    if assessment.get('reason_codes') or assessment.get('status') not in {'source_bound', 'observation'}:
        return payload, {'status': 'unresolved', 'reason': 'core_reference_source_checks_failed',
                         'reason_codes': assessment.get('reason_codes', [])}
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    receipt = {'version': RESOLUTION_VERSION, 'status': 'resolved',
        'basis': 'explicit_field_reference_after_existing_source_checks',
        'field': 'observed_signal', 'original_core_catalyst': core,
        'raw_sha256': digest(raw_text), 'observed_sha256': digest(observed),
        'source_fingerprint': manifest.get('fingerprint'),
        'source_refs_sha256': digest(json.dumps(refs, ensure_ascii=False, separators=(',', ':')))}
    return candidate, receipt
