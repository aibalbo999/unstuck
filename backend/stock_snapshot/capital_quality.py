from __future__ import annotations

from typing import Any

from .utils import _metric, _number, _pct_points, _percent_change, _percent_of, _signed_percent_label


def _share_statistics(data: dict[str, Any]) -> dict[str, Any]:
    shares_outstanding = _number(data.get("shares_outstanding_raw"), data.get("shares_raw"), data.get("shares_outstanding"))
    float_shares = _number(data.get("float_shares"))
    insider_pct = _pct_points(data.get("held_percent_insiders"), data.get("insider_ownership_pct"))
    institutional_pct = _pct_points(data.get("held_percent_institutions"), data.get("institutional_ownership_pct"))
    shares_short = _number(data.get("shares_short"))
    short_ratio = _number(data.get("short_ratio"))
    short_percent = _pct_points(data.get("short_percent_of_float"))
    float_pct = _percent_of(float_shares, shares_outstanding)
    has_data = any(
        value is not None
        for value in (
            shares_outstanding,
            float_shares,
            float_pct,
            insider_pct,
            institutional_pct,
            shares_short,
            short_ratio,
            short_percent,
        )
    )
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "股本結構不足",
            "shares_outstanding": None,
            "float_shares": None,
            "float_pct_of_shares": None,
            "insider_ownership_pct": None,
            "institutional_ownership_pct": None,
            "short_interest": {},
            "signals": [],
        }
    return {
        "status": "available",
        "label": _share_statistics_label(institutional_pct, insider_pct, short_percent),
        "shares_outstanding": shares_outstanding,
        "float_shares": float_shares,
        "float_pct_of_shares": float_pct,
        "insider_ownership_pct": insider_pct,
        "institutional_ownership_pct": institutional_pct,
        "short_interest": {
            "shares_short": shares_short,
            "short_ratio": short_ratio,
            "short_percent_of_float_pct": short_percent,
        },
        "signals": _share_statistics_signals(float_pct, institutional_pct, short_percent, insider_pct),
    }

def _share_statistics_label(
    institutional_pct: float | None,
    insider_pct: float | None,
    short_percent: float | None,
) -> str:
    if short_percent is not None and short_percent >= 10:
        return "放空壓力高"
    if institutional_pct is not None and institutional_pct >= 50:
        return "機構持股高"
    if insider_pct is not None and insider_pct >= 10:
        return "內部人持股高"
    return "股本結構"

def _share_statistics_signals(
    float_pct: float | None,
    institutional_pct: float | None,
    short_percent: float | None,
    insider_pct: float | None,
) -> list[str]:
    signals = []
    if float_pct is not None:
        signals.append(f"流通股 {float_pct:.1f}%")
    if institutional_pct is not None:
        signals.append(f"機構持股 {institutional_pct:.1f}%")
    if short_percent is not None:
        signals.append(f"空單占流通股 {short_percent:.1f}%")
    if insider_pct is not None:
        signals.append(f"內部人持股 {insider_pct:.1f}%")
    return signals[:3]

def _risk_liquidity(data: dict[str, Any], *, current_price: float | None) -> dict[str, Any]:
    beta = _metric(data.get("beta_raw"), data.get("beta"))
    week_52_high = _number(data.get("week_52_high"))
    volume = _number(data.get("volume"))
    avg_volume = _number(data.get("avg_volume"), data.get("average_volume"))
    volume_vs_avg = _percent_change(volume, avg_volume)
    drawdown = _percent_change(current_price, week_52_high)
    debt_to_equity = _pct_points(data.get("debt_to_equity_raw"), data.get("debt_to_equity"))
    current_ratio = _metric(data.get("current_ratio_raw"), data.get("current_ratio"))
    has_data = any(
        value is not None
        for value in (
            beta.get("value"),
            drawdown,
            volume_vs_avg,
            debt_to_equity,
            current_ratio.get("value"),
        )
    )
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "風險資料不足",
            "beta": {},
            "drawdown_from_52w_high_pct": None,
            "volume_vs_avg_pct": None,
            "debt_to_equity_pct": None,
            "current_ratio": {},
            "signals": [],
        }
    return {
        "status": "available",
        "label": _risk_liquidity_label(
            beta.get("value"),
            volume_vs_avg,
            debt_to_equity,
            current_ratio.get("value"),
        ),
        "beta": beta,
        "drawdown_from_52w_high_pct": drawdown,
        "volume_vs_avg_pct": volume_vs_avg,
        "debt_to_equity_pct": debt_to_equity,
        "current_ratio": current_ratio,
        "signals": _risk_liquidity_signals(beta.get("value"), drawdown, volume_vs_avg, debt_to_equity, current_ratio.get("value")),
    }

def _risk_liquidity_label(
    beta: float | None,
    volume_vs_avg: float | None,
    debt_to_equity: float | None,
    current_ratio: float | None,
) -> str:
    if volume_vs_avg is not None and volume_vs_avg >= 20:
        return "流動性活躍"
    if beta is not None and beta >= 1.5:
        return "波動偏高"
    if debt_to_equity is not None and debt_to_equity >= 100:
        return "槓桿偏高"
    if current_ratio is not None and current_ratio < 1:
        return "流動性偏緊"
    return "風險摘要"

def _risk_liquidity_signals(
    beta: float | None,
    drawdown: float | None,
    volume_vs_avg: float | None,
    debt_to_equity: float | None,
    current_ratio: float | None,
) -> list[str]:
    signals = []
    if beta is not None:
        signals.append(f"Beta {beta:.2f}")
    if drawdown is not None:
        signals.append(f"距52週高點 {_signed_percent_label(drawdown)}")
    if volume_vs_avg is not None:
        signals.append(f"成交量較均量 {_signed_percent_label(volume_vs_avg)}")
    if debt_to_equity is not None:
        signals.append(f"D/E {debt_to_equity:.1f}%")
    if current_ratio is not None:
        signals.append(f"流動比率 {current_ratio:.2f}")
    return signals[:3]

def _profitability_quality(data: dict[str, Any]) -> dict[str, Any]:
    gross_margin = _pct_points(data.get("gross_margin_raw"), data.get("gross_margin"))
    operating_margin = _pct_points(data.get("operating_margin_raw"), data.get("operating_margin"))
    net_margin = _pct_points(data.get("profit_margin_raw"), data.get("profit_margin"))
    roe = _pct_points(data.get("roe_raw"), data.get("roe"))
    roa = _pct_points(data.get("roa_raw"), data.get("roa"))
    free_cash_flow = _number(data.get("free_cash_flow_raw"), data.get("free_cash_flow"))
    revenue = _number(data.get("revenue_ttm_raw"), data.get("revenue_ttm"))
    fcf_margin = _percent_of(free_cash_flow, revenue)
    has_data = any(
        value is not None
        for value in (
            gross_margin,
            operating_margin,
            net_margin,
            roe,
            roa,
            fcf_margin,
        )
    )
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "獲利品質不足",
            "gross_margin_pct": None,
            "operating_margin_pct": None,
            "net_margin_pct": None,
            "roe_pct": None,
            "roa_pct": None,
            "fcf_margin_pct": None,
            "signals": [],
        }
    return {
        "status": "available",
        "label": _profitability_quality_label(net_margin, roe, fcf_margin),
        "gross_margin_pct": gross_margin,
        "operating_margin_pct": operating_margin,
        "net_margin_pct": net_margin,
        "roe_pct": roe,
        "roa_pct": roa,
        "fcf_margin_pct": fcf_margin,
        "signals": _profitability_quality_signals(roe, net_margin, fcf_margin, gross_margin),
    }

def _profitability_quality_label(
    net_margin: float | None,
    roe: float | None,
    fcf_margin: float | None,
) -> str:
    if (net_margin is not None and net_margin < 0) or (fcf_margin is not None and fcf_margin < 0):
        return "獲利承壓"
    if (
        net_margin is not None
        and net_margin >= 20
        and roe is not None
        and roe >= 15
        and (fcf_margin is None or fcf_margin > 0)
    ):
        return "獲利品質強"
    return "獲利品質"

def _profitability_quality_signals(
    roe: float | None,
    net_margin: float | None,
    fcf_margin: float | None,
    gross_margin: float | None,
) -> list[str]:
    signals = []
    if roe is not None:
        signals.append(f"ROE {roe:.1f}%")
    if net_margin is not None:
        signals.append(f"淨利率 {net_margin:.1f}%")
    if fcf_margin is not None:
        signals.append(f"FCF margin {fcf_margin:.1f}%")
    if gross_margin is not None:
        signals.append(f"毛利率 {gross_margin:.1f}%")
    return signals[:3]
