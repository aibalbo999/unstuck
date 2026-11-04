"""Current annual provider-call failure, separate from retained data delivery."""
from provider_correlation import current_correlation,current_source_identity

POLICY='annual-current-attempt-stale-fallback:v1'
ATTEMPT_KIND='provider_invocation'
OWNER=('annual_workforce','TWSE/TPEx annual workforce OpenAPI')
PRODUCERS={OWNER,('esg_occupational_safety','TWSE/TPEx annual ESG occupational safety OpenAPI')}
_IDS=('ticker','fetch_id','operation_id')


def _marked(entry):
    return (entry.get('acquisition_count_policy')==POLICY
        and isinstance(entry.get('source'),str)and isinstance(entry.get('provider'),str)
        and(entry['source'],entry['provider'])in PRODUCERS
        and entry.get('acquisition_attempt_kind')==ATTEMPT_KIND
        and type(entry.get('acquisition_record_count'))is int and entry['acquisition_record_count']==0
        and entry.get('event_kind')=='fetch'
        and entry.get('cache_hit')is True and entry.get('stale')is True
        and(entry.get('http_request_sent')is None or entry.get('http_request_sent')is True)
        and entry.get('status')in{'error','unavailable','degraded_enrichment'}
        and isinstance(entry.get('error_kind'),str)and bool(entry['error_kind'])
        and all(isinstance(entry.get(k),str)and bool(entry[k])for k in _IDS))


def mark_failed_refresh(entry,request_evidence,*,ticker):
    """Only the actually entered failed callback may mark its retained result."""
    context=current_correlation()
    if (request_evidence.get('_annual_attempt_entered')is not True
            or request_evidence.get('_annual_attempt_failed')is not True
            or current_source_identity()!=OWNER or context.get('ticker')!=ticker
            or not all(isinstance(context.get(k),str)and context[k]for k in _IDS)):
        return entry
    candidate={**entry,**{k:context[k]for k in _IDS},'acquisition_count_policy':POLICY,
        'acquisition_attempt_kind':ATTEMPT_KIND,'acquisition_record_count':0}
    return candidate if _marked(candidate)else entry


def current_delivery(entry):
    """Do not trust incoming context flags or historical cached HTTP booleans."""
    if not _marked(entry):return None
    context=current_correlation()
    return all(context.get(k)==entry[k]for k in('ticker','fetch_id'))


def failed_operation_key(row):
    details=row.get('details')or{}
    if not isinstance(details,dict)or details.get('acquisition_count_policy')!=POLICY:return None
    entry={**details,'source':row.get('source'),'provider':row.get('provider'),'status':row.get('status')}
    if details.get('acquisition_context_current')is not True or not _marked(entry):return None
    return (entry['source'],entry['provider'],*(entry[k]for k in _IDS))
