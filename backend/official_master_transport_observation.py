"""Finite observations for the two existing anonymous TWSE master endpoints.

Timings describe this native curl attempt only. Missing values stay missing;
zero is not evidence that a DNS/TCP/TLS phase failed or was skipped. These
diagnostics never establish complete content, issuer identity or acquisition.
"""
import math

MASTER_ENDPOINTS = frozenset({
    'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv',
    'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
})
TIMINGS = ('time_namelookup', 'time_connect', 'time_appconnect',
           'time_starttransfer', 'time_total')


def sanitize_observation(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in TIMINGS:
        item = value.get(key)
        try:
            valid = type(item) in (int, float) and math.isfinite(item) and 0 <= item <= 3600
        except OverflowError:
            valid = False
        if valid:
            result[key] = item
    for key, low, high in (('process_exit_code', -255, 255), ('response_bytes', 0, 100_000_000)):
        item = value.get(key)
        if type(item) is int and low <= item <= high:
            result[key] = item
    version = value.get('http_version')
    if type(version) is str and version in {'1', '1.0', '1.1', '2', '3'}:
        result['http_version'] = version
    return result


def observe_transfer(url, parts, returncode, metadata):
    if not isinstance(url, str) or url not in MASTER_ENDPOINTS or parts.get('process_started') is not True:
        return {}
    # Captured bytes may be partial on timeout/size refusal. Do not call them
    # a complete response or replace the validator's declared wire size.
    body = parts.get('body')
    return sanitize_observation({
        **(metadata if isinstance(metadata, dict) else {}),
        'process_exit_code': returncode,
        'response_bytes': len(body) if isinstance(body, bytes) else None,
    })
