"""Best-effort, bounded guard observations; never quota or request accounting."""
import re
import time

_OUTCOMES = {'admitted', 'blocked', 'success', 'provider_503', 'provider_429',
             'provider_rpd', 'released_error', 'released_without_outcome'}
_TRANSITIONS = {'unchanged', 'admitted', 'blocked', 'probe_admitted', 'opened',
                'reopened', 'recovered', 'probe_released', 'failure_observed'}


def observe_transition(model, outcome, result, *, attempt_id, admission_generation, probe,
                       provider_status=None):
    try:
        from api_usage_store import record_api_usage
        from provider_correlation import current_correlation

        if outcome not in _OUTCOMES or not re.fullmatch(r"google:[A-Za-z0-9._/-]{1,120}", model):
            return
        if not re.fullmatch(r"[a-f0-9]{32}", attempt_id):
            return
        observed_at = time.time()
        wait = max(float(result['wait']), 0.0)
        metadata = {
            "schema_version": 1, "attempt_id": attempt_id,
            "admission_generation": int(admission_generation),
            "generation": int(result['generation']), "probe": bool(probe),
            "outcome": outcome, "retry_wait_seconds": wait,
            "transition": result.get('transition') if result.get('transition') in _TRANSITIONS else 'unknown',
            "observed_at": observed_at,
            "retry_not_before": observed_at + wait if wait else None,
            "deadline_basis": "observed_remaining_guard_wait",
        }
        # Only current identity is inherited, never headers/error text/key hashes.
        correlation = current_correlation()
        for field in ('job_id', 'ticker'):
            if isinstance(correlation.get(field), str):
                metadata[field] = correlation[field][:160]
        if provider_status in {429, 503}:
            metadata['provider_status_code'] = provider_status
        record_api_usage(service='Gemini / Google AI', provider='google_ai',
                         operation='llm_congestion_transition', status='observed',
                         units=0, model_id=model.removeprefix('google:'),
                         metadata=metadata, created_at=observed_at)
    except Exception:
        # Guard decisions and original provider exceptions always take precedence.
        return
