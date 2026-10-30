"""Bind per-security calendar explanations to consistent saved identities."""


def _map(value):
    return value if isinstance(value, dict) else {}


def _ticker(value):
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    symbol, _, market = value.rpartition(".")
    return value if symbol and market in {"TW", "TWO"} else None


def bound_report_ticker(snapshot, *, expected_ticker=None, metadata=None):
    """Data identity is required; optional headers cannot contradict it.

    This only binds the calendar market, never the truth of source values or
    saved admission/quality labels. Missing headers do not invent identities.
    """
    snapshot = _map(snapshot)
    data = _map(snapshot.get("data"))
    ticker = _ticker(data.get("ticker"))
    if ticker is None or (expected_ticker is not None and _ticker(expected_ticker) != ticker):
        return None
    institution = _map(data.get("institutional_trading"))
    scopes = (snapshot, _map(metadata), _map(data.get("daily_market_data")), institution,
              _map(institution.get("latest_official_observation")))
    if any("ticker" in scope and _ticker(scope["ticker"]) != ticker for scope in scopes):
        return None
    return ticker
