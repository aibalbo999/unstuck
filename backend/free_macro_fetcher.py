"""Bounded, globally cached public macro acquisition; no model calls.

The macro source router uses this collector only for missing components. Cache replay preserves
original provenance but never becomes a new HTTP attempt. No automatic retries.
"""
from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
from functools import lru_cache
import math
import time

import httpx

from free_macro_original_parsers import bls_cpi, cboe_vix, fed_h15

DEFINITIONS = {
    "vix": ("Cboe", "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", cboe_vix, 2_000_000, 86400),
    "us_cpi_yoy": ("BLS", "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0", bls_cpi, 2_000_000, 7*86400),
    "us_10y_yield": ("FederalReserve", "https://www.federalreserve.gov/releases/h15/data/FRB_h15_xml.zip", fed_h15, 16_000_000, 86400),
}
FRESHNESS_SECONDS = 6 * 3600


@lru_cache(maxsize=6)
def _parsed_original(parser, raw, asof):
    # Raw bytes, parser identity and evaluation date all bind this bounded memo.
    # The persistent original is still hash-checked before every cache read.
    return parser(raw, asof)


def _parse_original(parser, raw, asof):
    return deepcopy(_parsed_original(parser, raw, asof))


def _read_original(url, *, provider, maximum, timeout, trace=None):
    from external_http_client import proxy_url_for_request
    from provider_throttle import enforce_provider_throttle, mark_rate_limit_cooldown
    enforce_provider_throttle(provider)
    if provider == "BLS":
        from bls_request_admission import BlsAdmissionStore
        BlsAdmissionStore().reserve()
    trace = {} if trace is None else trace
    started = time.monotonic()
    kwargs = {"timeout": timeout, "follow_redirects": False}
    proxy = proxy_url_for_request(url, provider)
    if proxy:
        kwargs["proxy"] = proxy
    try:
        with httpx.Client(**kwargs) as client:
            trace["http_request_sent"] = True
            with client.stream("GET", url) as response:
                trace["http_status"] = response.status_code
                if str(response.url) != url or response.history or getattr(response, "from_cache", False):
                    raise ValueError("macro HTTP identity or cache origin differs")
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("macro HTTP response must be 200")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > maximum or time.monotonic() - started > timeout:
                        raise ValueError("macro original exceeds byte or total time limit")
                    chunks.append(chunk)
                if not size or time.monotonic() - started > timeout:
                    raise ValueError("macro original empty or deadline expired")
                trace.update(response_complete=True, response_bytes=size)
                return b"".join(chunks), time.time()
    except Exception as exc:
        mark_rate_limit_cooldown(provider, exc)
        raise


def fetch_free_macro_component(name, *, timeout=15, use_cache=True):
    """Fetch one fixed official/public series through normal shared admission."""
    if name not in DEFINITIONS:
        raise ValueError("unknown free macro component")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("timeout must be finite and between zero and 30 seconds")
    from shared_provider_cache import shared_fetch
    from official_response_evidence import archive_response, read_response
    from source_observation_freshness import observation_recency
    provider, url, parser, maximum, retention = DEFINITIONS[name]
    attempted = False
    trace = {"http_request_sent": False}

    def acquire():
        nonlocal attempted
        # This flag records admission intent, not proof that a socket was sent.
        attempted = True
        body, retrieved = _read_original(url, provider=provider, maximum=maximum, timeout=timeout, trace=trace)
        asof = datetime.fromtimestamp(retrieved, timezone.utc).date()
        observation = _parse_original(parser, body, asof)
        receipt = archive_response(body, source_url=url, retrieved_at=retrieved,
                                   evidence_kind="decoded_complete_http_response_body", max_bytes=maximum)
        if receipt.get("status") != "archived" or read_response(receipt, max_bytes=maximum) != body:
            raise ValueError("macro original archive unavailable")
        receipt.update(http_status_observed=True, response_complete=True, cache_hit=False, request_method="GET")
        return {**observation, "original_receipt": receipt, "source_url": url}

    observation, meta = shared_fetch(
        f"free-macro-qualified:v1:{name}", acquire,
        freshness_seconds=FRESHNESS_SECONDS, retention_seconds=retention, error_retry_seconds=900,
        use_cache=use_cache, lock_wait_seconds=2,
    )
    qualification_error = None
    if observation:
        try:
            receipt = observation["original_receipt"]
            if (receipt.get("source_url") != url or receipt.get("http_status") != 200
                    or receipt.get("response_complete") is not True
                    or receipt.get("http_status_observed") is not True):
                raise ValueError("cached macro receipt differs")
            # Re-evaluate date at read time; retained old originals cannot become fresh.
            replay = _parse_original(parser, read_response(receipt, max_bytes=maximum), datetime.now(timezone.utc).date())
            if any(observation.get(key) != value for key, value in replay.items()):
                raise ValueError("macro cache and original differ")
        except Exception:
            qualification_error = "original_replay_failed"
            observation = None
    recency = observation_recency(
        observation.get("date") if observation else None, ticker="US", now_epoch=time.time(),
        max_age_days=90 if name == "us_cpi_yoy" else 7,
    )
    stale = bool(meta.get("stale")) or recency["observation_status"] != "recent"
    return {"status": "unavailable" if not observation else "stale" if stale else "success",
            "provider": provider, "source_url": url, "observation": observation,
            "cache_hit": bool(meta.get("cache_hit")), "stale": stale,
            "acquisition_attempted": attempted,
            "new_original_acquired": bool(trace.get("response_complete") and observation and not meta.get("cache_hit")),
            "metadata": {**meta, **recency}, "qualification_error": qualification_error,
            "transport": trace}
