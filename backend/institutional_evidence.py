"""Institutional net-flow claims bound to explicit population, period and unit."""
from __future__ import annotations

import math
import re
from datetime import date

from financial_claim_context import is_actual_claim, sentence_span

_PROVIDER = "FinMind TaiwanStockInstitutionalInvestorsBuySell"
_CATEGORIES = {"foreign", "investment_trust", "dealer"}
_UNITS = {"shares": 1, "thousand_shares": 1000}
_POP = re.compile(r"三大法人|三類法人|法人合計|法人總計|法人|外資|投信|自營商")
_POPULATIONS = {"外資": "foreign", "投信": "investment_trust", "自營商": "dealer"}
_CLAIM = re.compile(
    r"(?P<verb>淨買超|淨賣超|買賣超|買超|賣超|淨買入|淨賣出)"
    r"(?:(?!融資|融券)[^\d。；;\n]){0,12}?(?P<number>[+\-−]?\d[\d,]*(?:\.\d+)?)"
    r"(?P<scale>千|萬)?(?P<unit>股|張)(?![A-Za-z])"
)
_WINDOW = re.compile(r"(?:近|最近|過去)(?P<n>\d+)(?:個)?(?:交易)?日")
_DATE = re.compile(r"(?:(?P<year>20\d{2})[年/\-])?(?P<month>\d{1,2})[月/\-](?P<day>\d{1,2})日?")


def _map(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        return None


def institutional_evidence_records(data):
    """Project only explicitly unit-named, source-identified existing observations."""
    data = _map(data)
    context = _map(data.get("short_term_market_context")) or data
    typed = _map(context.get("institutional_evidence"))
    if isinstance(typed.get("records"), list):
        # Preserve indexes: a malformed row must not make a citation point at its neighbour.
        return [r if isinstance(r, dict) else {} for r in typed["records"]]
    raw = _map(context.get("institutional_trading")) or _map(data.get("institutional_trading"))
    if raw.get("source") != _PROVIDER:
        return []
    latest = _date(raw.get("latest_date"))
    lookback = _number(raw.get("lookback_trading_days"))
    records = []

    def add(path, value, unit, population, window, observed):
        value = _number(value)
        if value is not None and observed and window:
            records.append({"path": "institutional_trading." + path, "value": value,
                            "unit": unit, "population": population, "window": window,
                            "observed_at": observed, "provider": raw["source"]})

    window = {"kind": "trailing_trading_days", "trading_days": int(lookback)} if lookback and lookback > 0 and lookback.is_integer() else None
    for unit in _UNITS:
        field = f"net_buy_{unit}_by_category"
        for category, value in _map(raw.get(field)).items():
            if category in _CATEGORIES:
                add(f"{field}.{category}", value, unit, category, window, latest)
        field = f"total_net_buy_{unit}"
        add(field, raw.get(field), unit, "total", window, latest)
    if lookback is not None and lookback >= 5:
        add("last_5_trading_days_net_buy_thousand_shares", raw.get("last_5_trading_days_net_buy_thousand_shares"),
            "thousand_shares", "total", {"kind": "trailing_trading_days", "trading_days": 5}, latest)
    daily = raw.get("daily_total_net_buy_last_10")
    for i, row in enumerate(daily if isinstance(daily, list) else []):
        row = _map(row); observed = _date(row.get("date"))
        add(f"daily_total_net_buy_last_10[{i}].net_buy_thousand_shares", row.get("net_buy_thousand_shares"),
            "thousand_shares", "total", {"kind": "day", "date": observed}, observed)
    return records


def _valid_record(record):
    window = _map(record.get("window"))
    unit = record.get("unit")
    return (isinstance(unit, str) and unit in _UNITS and _number(record.get("value")) is not None
            and isinstance(record.get("population"), str) and record["population"] in {"total", *_CATEGORIES}
            and isinstance(record.get("provider"), str) and bool(record["provider"])
            and bool(_date(record.get("observed_at")))
            and (window.get("kind") == "day" and window.get("date") == record.get("observed_at")
                 or window.get("kind") == "trailing_trading_days"
                 and _number(window.get("trading_days")) is not None and _number(window["trading_days"]) > 0
                 and _number(window["trading_days"]).is_integer()))


def _claimed_date(match, records):
    if match['year']:
        try:
            return date(int(match['year']), int(match['month']), int(match['day'])).isoformat()
        except ValueError:
            return None
    matches = {r['observed_at'] for r in records
               if int(r['observed_at'][5:7]) == int(match['month'])
               and int(r['observed_at'][8:10]) == int(match['day'])}
    return next(iter(matches)) if len(matches) == 1 else None


def _claim_window(prefix, records):
    periods = list(_WINDOW.finditer(prefix))
    dates = list(_DATE.finditer(prefix))
    if periods:
        # A lookback's as-of date limits observation freshness, not its duration.
        # Keep explicit single-day dates, even when another as-of date follows.
        dates = [m for m in dates if not re.search(r"截至[:：]?$", prefix[:m.start()])]
    # Only an explicit later single-day marker can supersede an earlier lookback.
    if dates and (not periods or dates[-1].start() > periods[-1].start()):
        last = dates[-1]
        if re.search(r"(?:至|到|[-～~])$", prefix[:last.start()]):
            return None
        observed = _claimed_date(last, records)
        return {"kind": "day", "date": observed} if observed else None
    if periods:
        return {"kind": "trailing_trading_days", "trading_days": int(periods[-1]['n'])}
    if re.search(r"今日|當日|最新交易日", prefix):
        observed = max((r['observed_at'] for r in records), default=None)
        return {"kind": "day", "date": observed} if observed else None
    return None


def _claim_population(prefix, populations):
    if _enumerated_total(prefix, populations):
        return "total"
    group = [populations[-1]]
    for previous in reversed(populations[:-1]):
        if not re.fullmatch(r"[與及和、/,，]+", prefix[previous.end():group[0].start()]):
            break
        group.insert(0, previous)
    if len(group) == 1:
        return _POPULATIONS.get(group[0].group(), "total")
    # No subgroup aggregation or inference from the final named participant.
    if (len(group) == 3 and {_POPULATIONS.get(m.group()) for m in group} == _CATEGORIES
            and "合計" in prefix[group[-1].end():]):
        return "total"
    return None


def _enumerated_total(prefix, populations):
    """A terminal total after three dated-window components has its own subject."""
    total = re.search(r"[，,](?:合計總?|總計)$", prefix)
    periods = list(_WINDOW.finditer(prefix))
    if not total or not periods:
        return False
    members = [p for p in populations if periods[-1].end() <= p.start() < total.start()]
    if len(members) != 3 or {_POPULATIONS.get(p.group()) for p in members} != _CATEGORIES:
        return False
    # The window must precede every component; no date or window switch inside.
    if _DATE.search(prefix[members[0].end():total.start()]):
        return False
    for i, member in enumerate(members):
        end = members[i+1].start() if i < 2 else total.start()
        if not re.search(r"[+\-−]?\d[\d,]*(?:\.\d+)?(?:千|萬)?(?:股|張)", prefix[member.end():end]):
            return False
    return True


def institutional_evidence_issues(text, data, *, allowed_paths=None):
    """Check actual numeric net-flow assertions; never infer unrecorded subgroup flows.

    allowed_paths limits checks to cited records in a visible trade-source catalog.
    Omission means all records are eligible; an empty collection means no evidence.
    Empty issues do not certify nonnumeric qualitative/trend claims as supported.
    """
    data = _map(data)
    records = institutional_evidence_records(data)
    eligible = []
    for i, record in enumerate(records):
        ref = f"short_term_market_context.institutional_evidence.records[{i}]"
        if allowed_paths is not None and not any(
            isinstance(path, str) and path in (record.get("path"), ref, ref + ".value")
            for path in allowed_paths
        ):
            continue
        if _valid_record(record):
            eligible.append({**record, "value": _number(record["value"])})
    text = re.sub(r"[^\S\n]+|[*`]", "", str(text or ""))
    ticker = str(data.get("ticker") or _map(data.get("short_term_market_context")).get("ticker")
                 or _map(data.get("company")).get("ticker") or "").upper()
    taiwan = ticker.endswith((".TW", ".TWO"))
    issues = []
    for match in _CLAIM.finditer(text):
        if not is_actual_claim(text, match.start(), match.end()):
            continue
        start, end = sentence_span(text, match.start(), match.end())
        prefix = text[start:match.start()]
        populations = list(_POP.finditer(prefix))
        if not populations:
            continue
        population = _claim_population(prefix, populations)
        window = _claim_window(prefix, eligible)
        candidates = [r for r in eligible if r["population"] == population and r["window"] == window]
        if window and window.get("kind") == "trailing_trading_days":
            dates = list(_DATE.finditer(prefix))
            suffix = text[match.end():end]
            if re.search(r"截至|日期為", suffix):
                dates += list(_DATE.finditer(suffix))
            if dates:
                observed = _claimed_date(dates[-1], eligible)
                candidates = [r for r in candidates if r['observed_at'] == observed]
        if not candidates:
            issues.append("法人證據紅線：主體／日期／期間缺少同語意來源，不得將法人合計借作外資、投信或自營商分項，或混用單日與多日累計。")
            continue
        if match["unit"] == "張" and not taiwan:
            issues.append("法人單位紅線：標的市場未確認，不能假定1張=1000股。")
            continue
        value = float(match["number"].replace(",", "").replace("−", "-"))
        if "賣" in match["verb"] and match["verb"] != "買賣超":
            value = -abs(value)
        value *= {None: 1, "千": 1000, "萬": 10000}[match["scale"]] * (1000 if match["unit"] == "張" else 1)
        if not any(abs(value - r["value"] * _UNITS[r["unit"]]) <= max(0.0051 * _UNITS[r["unit"]], abs(r["value"] * _UNITS[r["unit"]]) * 0.0001) for r in candidates):
            issues.append("法人單位／數值紅線：同主體同期間淨額不符；千股=1000股，台股1張=1000股，千張=1000000股，買超／賣超正負方向不可混用。")
    return list(dict.fromkeys(issues))


__all__ = ["institutional_evidence_records", "institutional_evidence_issues"]
