"""Conservative daily-OHLC execution simulation; never infer intrabar order."""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date

from trade_execution_contract import evaluate_trade_execution
from trade_price_inputs import NUMBER


SCHEMA_VERSION = "trade_path_backtest.v1"
FINAL_STATUSES = {"target_first", "stop_first", "horizon_exit", "not_entered", "no_trade", "ambiguous"}
_PRICE = rf"(?:NT\$|TWD|\$)?\s*{NUMBER}\s*(?:元|TWD)?"
_PLAIN_ENTRY = re.compile(rf"\s*{_PRICE}(?:\s*(?:[-–—－−~～至到]|\bto\b)\s*{_PRICE})?\s*", re.I)
_STOP_ENTRY = re.compile(rf"\s*(突破|站上|站回|跌破|above|below)\s*{_PRICE}\s*", re.I)


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and not isinstance(value, bool) else None
    except (TypeError, ValueError, OverflowError):
        return None


def evaluate_trade_path(
    *, bars, generated_date: date, as_of: date, direction, entry_zone=None,
    target_price=None, stop_loss=None, horizon_trading_days=5, transaction_cost=None,
    benchmark_return_pct=None,
) -> dict:
    """Evaluate the first N observed sessions AFTER the report date.

    Entry assumes a resting order filled on entry-zone touch. An open inside the
    zone fills at that open; intraday touches use the unfavorable endpoint of
    the observed bar/entry-zone overlap, never an untraded zone endpoint.
    Intraday entry plus any same-bar exit is ambiguous. Once held, gap stop fills
    at the adverse open, while target gaps use the conservative planned target.
    Returns are per-position gross price returns, excluding dividends/financing.
    """
    if isinstance(horizon_trading_days, bool) or not isinstance(horizon_trading_days, int) or not 1 <= horizon_trading_days <= 252:
        raise ValueError("horizon_trading_days must be an integer between 1 and 252")
    result = {
        "schema_version": SCHEMA_VERSION, "horizon_trading_days": horizon_trading_days,
        "horizon_months": None, "status": "pending", "reason": "horizon_not_observed",
        "outcome": None, "strategy_roi_pct": None, "net_strategy_roi_pct": None,
        "excess_return_pct": None, "max_drawdown_pct": None, "market_return_pct": None,
        "entry_price": None, "entry_date": None, "exit_price": None, "exit_date": None,
        "evaluation_date": None, "return_basis": "per_position_gross_price_return",
        "execution_assumption": "entry_zone_touch_conservative_daily_ohlc",
        "benchmark_return_pct": _number(benchmark_return_pct),
        "transaction_cost": None,
    }

    def finish(status, reason, exit_price=None, exit_date=None):
        result.update(status=status, reason=reason, exit_price=exit_price, exit_date=exit_date)
        if status in {"not_entered", "no_trade"}:
            result.update(strategy_roi_pct=0.0, net_strategy_roi_pct=0.0,
                          position_assumption="cash_no_position_zero_interest")
        elif exit_price is not None:
            sign = 1 if direction == "Long" else -1
            roi = sign * (exit_price / result["entry_price"] - 1) * 100
            result["strategy_roi_pct"] = round(roi, 4)
            result["outcome"] = "hit" if roi > 0 else "miss"
            if result["transaction_cost"] is not None:
                result["net_strategy_roi_pct"] = round(roi - result["transaction_cost"] / result["entry_price"] * 100, 4)
        if result["strategy_roi_pct"] is not None and result["benchmark_return_pct"] is not None:
            result["excess_return_pct"] = round(result["strategy_roi_pct"] - result["benchmark_return_pct"], 4)
        return result

    rows = []
    seen = set()
    for row in bars if isinstance(bars, list) else []:
        try:
            day = date.fromisoformat(str(row["date"])[:10])
        except (KeyError, TypeError, ValueError):
            return finish("insufficient_data", "invalid_bar_date")
        if not generated_date < day <= as_of:
            continue
        if day in seen:
            return finish("insufficient_data", "duplicate_bar_date")
        seen.add(day)
        rows.append((day, row))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return finish("insufficient_data", "missing_ohlc")
    if len(rows) < horizon_trading_days:
        return result
    rows = rows[:horizon_trading_days]
    result["evaluation_date"] = rows[-1][0].isoformat()
    if direction == "Neutral":
        return finish("no_trade", "explicit_observation_plan")
    contract = evaluate_trade_execution(direction=direction, entry_zone=entry_zone,
                                       target_price=target_price, stop_loss=stop_loss,
                                       transaction_cost=transaction_cost)
    if contract["issues"]:
        result["contract_issues"] = contract["issues"]
        return finish("insufficient_data", "unexecutable_price_contract")
    details = contract["details"]
    result["transaction_cost"] = details["transaction_cost"]
    entry_low, entry_high = details["entry_range"]
    target = details["target_range"][0 if direction == "Long" else 1]
    stop = details["stop_range"][0 if direction == "Long" else 1]
    entry_text = unicodedata.normalize("NFKC", str(entry_zone))
    trigger = _STOP_ENTRY.fullmatch(entry_text)
    # A numeric parser validates prices, not event prerequisites. Only these
    # complete price-only grammars have a defined OHLC execution meaning.
    if not trigger and not _PLAIN_ENTRY.fullmatch(entry_text):
        return finish("insufficient_data", "unsupported_conditional_entry")
    trigger_direction = ("below" if trigger[1].lower() in {"跌破", "below"} else "above") if trigger else None
    if trigger:
        result["execution_assumption"] = "price_stop_trigger_daily_ohlc"
    for day, raw in rows:
        values = [_number(raw.get(key)) for key in ("open", "high", "low", "close")]
        if any(value is None or value <= 0 for value in values):
            return finish("insufficient_data", "missing_ohlc")
        opened, high, low, close = values
        if not low <= min(opened, close) <= max(opened, close) <= high:
            return finish("insufficient_data", "inconsistent_ohlc")
        had_position = result["entry_price"] is not None
        if not had_position:
            if trigger_direction:
                threshold = entry_low
                triggered = low <= threshold if trigger_direction == "below" else high >= threshold
                if not triggered:
                    continue
                entry_at_open = opened <= threshold if trigger_direction == "below" else opened >= threshold
                fill = opened if entry_at_open else threshold
            else:
                if high < entry_low or low > entry_high:
                    continue
                entry_at_open = entry_low <= opened <= entry_high
                fill = opened if entry_at_open else (min(entry_high, high) if direction == "Long" else max(entry_low, low))
            if not (stop < fill < target if direction == "Long" else target < fill < stop):
                return finish("insufficient_data", "gap_entry_outside_execution_levels")
            result["entry_price"] = fill
            result["entry_date"] = day.isoformat()
        else:
            entry_at_open = False
        stop_hit = low <= stop if direction == "Long" else high >= stop
        target_hit = high >= target if direction == "Long" else low <= target
        gap_stop = opened <= stop if direction == "Long" else opened >= stop
        gap_target = opened >= target if direction == "Long" else opened <= target
        if had_position and gap_stop:
            return finish("stop_first", "gap_through_stop", opened, day.isoformat())
        if had_position and gap_target:
            return finish("target_first", "gap_through_target_conservative_fill", target, day.isoformat())
        if not had_position and not entry_at_open and (stop_hit or target_hit):
            return finish("ambiguous", "entry_exit_order_unknown")
        if stop_hit and target_hit:
            return finish("ambiguous", "target_stop_same_bar")
        if stop_hit:
            return finish("stop_first", "stop_touched_first", stop, day.isoformat())
        if target_hit:
            return finish("target_first", "target_touched_first", target, day.isoformat())
    if result["entry_price"] is None:
        return finish("not_entered", "entry_zone_not_touched")
    return finish("horizon_exit", "session_horizon_close", close, rows[-1][0].isoformat())
