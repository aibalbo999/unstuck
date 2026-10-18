"""Documented SDK quota signals, without inventing an HTTP response or reset."""

FINMIND_QUOTA_MESSAGE = 'Requests reach the upper limit. https://finmindtrade.com/'
FINMIND_SDK_ERROR = 'FinMind API unexpected response: ' + FINMIND_QUOTA_MESSAGE


def is_finmind_sdk_request_quota(exc: BaseException) -> bool:
    """Require the genuine decoder frame and original documented payload.

    FinMind 1.9.10 raises a plain Exception and drops the HTTP response. The
    payload's application status cannot be used as a native HTTP status.
    Saved text alone, wrapped exceptions and contradictory payloads remain
    unknown. No optional SDK import or body retention is needed here.
    """
    if (type(exc) is not Exception or len(exc.args) != 1
            or type(exc.args[0]) is not str or exc.args[0] != FINMIND_SDK_ERROR):
        return False
    trace = exc.__traceback__
    while trace is not None:
        frame = trace.tb_frame
        if (frame.f_globals.get('__name__') == 'FinMind.data.finmind_api'
                and frame.f_code.co_name == '_extract_data'):
            api = frame.f_globals.get('FinMindApi')
            decoder = vars(api).get('_extract_data') if isinstance(api, type) else None
            if frame.f_code is not getattr(decoder, '__code__', None):
                return False
            payload = frame.f_locals.get('response_json')
            if type(payload) is not dict or 'data' in payload:
                return False
            message = payload.get('msg') or payload.get('detail')
            if message != FINMIND_QUOTA_MESSAGE:
                return False
            return 'status' not in payload or type(payload['status']) is int and payload['status'] == 402
        trace = trace.tb_next
    return False
