"""Read-only explanation of saved mode-D Neutral decisions, separate from quality.

Recorded attribution is not proof of a counterfactual trading direction.  Never
infer an original candidate or an acquisition failure from a current warning.
"""
from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

from report_freshness_summary import safe_bool

_TZ = ZoneInfo('Asia/Taipei')
_DATA_LIMIT = re.compile(
    r'資料(?:不足|缺漏|缺失|不完整|過期)|(?:等待|待|補齊).{0,18}資料可信度|'
    r'資料(?:可信度|新鮮度).{0,18}(?:恢復|不足|異常|stale)|來源異常|'
    r'(?:等待|待|需).{0,24}(?:資料|數據).{0,16}(?:恢復|更新|補齊)|'
    r'(?:事件)?日曆.{0,8}(?:缺漏|缺失|未取得)|'
    r'(?:data_trust|institutional_trading).{0,60}(?:stale|過期)', re.I)
_FIELDS = ('core_catalyst', 'observed_signal', 'recheck_condition')


def _map(value):
    return value if isinstance(value, dict) else {}


def _saved_setup(snapshot):
    context = _map(snapshot.get('rerun_context'))
    outputs = _map(context.get('structured_outputs'))
    role = _map(outputs.get('24', outputs.get(24)))
    parsed = _map(_map(context.get('parsed')).get('trade_setup'))
    data_parsed = _map(_map(_map(snapshot.get('data')).get('parsed')).get('trade_setup'))
    setup = parsed or data_parsed or role
    assessment = _map(setup.get('source_assessment'))
    # Older snapshots saved the receipt on role 24 only. Reuse it solely when
    # direction and saved conclusion agree with the setup shown in the card.
    same_setup = (role.get('trade_direction') == setup.get('trade_direction')
                  and role.get('core_catalyst') == setup.get('core_catalyst'))
    if not assessment and same_setup:
        assessment = _map(role.get('source_assessment'))
    return setup, assessment


def build_neutral_explanation(snapshot, *, direction: str) -> dict:
    snapshot = _map(snapshot)
    pipeline = snapshot.get('pipeline') or snapshot.get('pipeline_id') or _map(snapshot.get('rerun_context')).get('pipeline_id')
    if pipeline != 'v4' or direction != 'Neutral':
        return {}
    setup, assessment = _saved_setup(snapshot)
    if setup.get('trade_direction') not in (None, '', 'Neutral'):
        return _result('unknown', '保存方向與目前顯示不一致；觀望原因未確認。')
    completion = _map(assessment.get('output_completion'))
    original = assessment.get('original_direction')
    original = original if isinstance(original, str) and original in {'Long', 'Short', 'Neutral'} else 'unknown'
    evidence = [{'field': field, 'text': str(setup[field])[:700]} for field in _FIELDS
                if isinstance(setup.get(field), str) and setup[field].strip()]
    if assessment.get('origin') == 'local_deterministic_fallback' or completion.get('status') in ('local_fallback', 'incomplete', 'truncated'):
        result = _result('model_incomplete', '本機保守備援或輸出未完成；模型結論未完成，不能當成模型成功判斷觀望。',
                         basis='saved_output_completion', model_completed=False)
    elif assessment.get('status') == 'degraded':
        changed = original in {'Long', 'Short'} if original != 'unknown' else None
        detail = ('模型原先已選 Neutral；另有引用／語意退件，不代表這次檢查改變方向。' if original == 'Neutral'
                  else f'保存的 {original} 候選未通過來源／語意檢查，已降為 Neutral；不代表修復後可恢復原方向。' if changed
                  else '有來源／語意退件收據，但原方向未保存，不能推定方向是否被改變。')
        result = _result('source_rejection', detail, basis='saved_source_assessment',
                         direction_changed_by_gate=changed)
    else:
        explicit = [item for item in evidence if _DATA_LIMIT.search(item['text'])]
        legacy_prefix = str(setup.get('core_catalyst') or '').startswith(('來源不足，原方向不可執行', '資料不足，原方向不可執行'))
        if explicit or legacy_prefix:
            result = _result('data_wait', '原文明示資料不足、可信度／新鮮度或執行資料缺漏；這是保存的等待原因，未重新測試目前來源。',
                             basis='saved_explicit_data_limitation')
            evidence = explicit or evidence[:1]
        elif assessment.get('status') == 'observation' and evidence:
            result = _result('market_conditions', '原報告主要等待量價、均線、籌碼或催化條件；原因分類不代表整份報告品質通過。',
                             basis='saved_observation_assessment')
        else:
            result = _result('unknown', '舊版缺少完整來源／退件原因收據，無法確認是市場觀望、資料問題或模型限制。')
    codes = assessment.get('reason_codes')
    result.update(original_direction=original, source_status=str(assessment.get('status') or 'unrecorded'),
                  reason_codes=[code for code in codes[:20] if isinstance(code, str)] if isinstance(codes, list) else [],
                  evidence=evidence)
    if completion.get('status') == 'complete' and result['model_completed'] is not False:
        result['model_completed'] = True
    return result


def _result(category, summary, **fields):
    labels = {'model_incomplete': '模型結論未完成', 'source_rejection': '引用／語意退件',
              'data_wait': '資料等待', 'market_conditions': '市場條件觀望', 'unknown': '觀望原因未確認'}
    return {'schema_version': 'report-neutral-explanation.v1', 'category': category,
            'label': labels[category], 'summary': summary, 'basis': 'missing_saved_receipt',
            'original_direction': 'unknown', 'direction_changed_by_gate': None,
            'model_completed': None, 'quality_certified': False, 'evidence': [], **fields}


def build_analysis_age(snapshot, *, now: datetime | None = None, analysis_text_stale=False) -> dict:
    """Calendar age from recorded analysis time only; file mtime is never used."""
    snapshot = _map(snapshot)
    field = 'conclusion_generated_at' if snapshot.get('conclusion_generated_at') else 'generated_at'
    raw = snapshot.get(field)
    result = {'status': 'unknown', 'analysis_generated_at': raw if isinstance(raw, str) else '',
              'basis': f'snapshot.{field}' if raw else 'missing_saved_timestamp',
              'age_calendar_days': None, 'over_14_calendar_days': None, 'precision': 'unknown',
              'snapshot_refreshed_at': str(snapshot.get('snapshot_refreshed_at') or ''),
              'conclusion_stale': safe_bool(analysis_text_stale) or safe_bool(snapshot.get('refreshed_without_analysis_rerun'))
                  or snapshot.get('decision_validity_status') == 'needs_rerun'}
    if field == 'generated_at' and result['conclusion_stale']:
        # After a source-only refresh, generated_at may date the data snapshot.
        # Without the saved conclusion timestamp it cannot date the analysis.
        return {**result, 'analysis_generated_at': '', 'basis': 'missing_original_conclusion_timestamp'}
    if not isinstance(raw, str) or not raw.strip():
        return result
    try:
        observed = datetime.fromisoformat(raw.strip().replace('Z', '+00:00'))
        observed = observed.replace(tzinfo=_TZ) if observed.tzinfo is None else observed.astimezone(_TZ)
        moment = now or datetime.now(_TZ)
        moment = moment.replace(tzinfo=_TZ) if moment.tzinfo is None else moment.astimezone(_TZ)
        days = (moment.date() - observed.date()).days
        if observed > moment:
            return result
    except (ValueError, TypeError, OverflowError):
        return result
    return {**result, 'status': 'recorded', 'precision': 'date' if len(raw.strip()) == 10 else 'datetime',
            'age_calendar_days': days, 'over_14_calendar_days': days > 14}
