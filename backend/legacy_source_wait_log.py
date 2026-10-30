"""Bounded scope/reason diagnostics; never log source payloads or numeric quotes."""
import re

def source_wait_log(wait):
    scope=str(wait.get('scope_id') or '')
    ticker=str(wait.get('ticker') or '')
    day=str(wait.get('maturity_date') or '')
    reason=str((wait.get('source_gate') or {}).get('reason') or '')
    scope=scope if re.fullmatch(r'[0-9a-f]{64}',scope) else 'unknown'
    ticker=ticker if re.fullmatch(r'[0-9]{4}\.(?:TW|TWO)',ticker) else 'unknown'
    day=day if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',day) else 'unknown'
    reason=reason if re.fullmatch(r'[a-z][a-z0-9_]{0,95}',reason) else 'source_evidence_unavailable'
    return ('歷史證據來源等待：scope_id='+scope+' ticker='+ticker+' maturity_date='+day+
            ' reason='+reason+' retryable_source_wait=true attempt_recorded=false')


def validation_rejection_log(item):
    """Validation rejection is a recorded unscored result, not an exception."""
    def safe(key, pattern):
        value = str(item.get(key) or '')
        return value if re.fullmatch(pattern, value) else 'unknown'
    return ('歷史證據驗證拒絕：scope_id=' + safe('scope_id', r'[0-9a-f]{64}') +
            ' ticker=' + safe('ticker', r'[0-9]{4}\.(?:TW|TWO)') +
            ' evidence_session=' + safe('evidence_session', r'[0-9]{4}-[0-9]{2}-[0-9]{2}') +
            ' reason=' + safe('reason', r'[a-z][a-z0-9_]{0,95}') +
            ' validation_rejected=true scored=false exception=false')


def revision_exception_log(item):
    def safe(key, pattern):
        value = str(item.get(key) or '')
        return value if re.fullmatch(pattern, value) else 'unknown'
    return ('歷史證據執行錯誤：scope_id=' + safe('scope_id', r'[0-9a-f]{64}') +
            ' ticker=' + safe('ticker', r'[0-9]{4}\.(?:TW|TWO)') +
            ' evidence_session=' + safe('evidence_session', r'[0-9]{4}-[0-9]{2}-[0-9]{2}') +
            ' stage=' + safe('stage', r'[a-z_]{1,40}') +
            ' exception_type=' + safe('exception_type', r'[A-Za-z][A-Za-z0-9_]{0,60}') +
            ' scored=false exception=true')
