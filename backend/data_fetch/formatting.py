"""Formatting helpers for legacy-compatible financial payload fields."""


def format_number(num, unit="億", decimals=2):
    """Format numbers using the historical display strings."""
    try:
        if num == "N/A" or num is None:
            return "N/A"
        num = float(num)
        if unit == "億":
            val_yi = num / 1e8
            val_b = num / 1e9
            return f"NT${val_yi:.{decimals}f}億 ({val_b:.{decimals}f}B)"
        if unit == "兆":
            val_zhao = num / 1e12
            val_b = num / 1e9
            return f"NT${val_zhao:.{decimals}f}兆 ({val_b:.{decimals}f}B)"
        if unit == "%":
            return f"{num:.{decimals}f}%"
        return f"{num:.{decimals}f}"
    except Exception:
        return "N/A"


def format_pct(val):
    """Format a decimal ratio as a percentage string."""
    try:
        if val == "N/A" or val is None:
            return "N/A"
        return f"{float(val) * 100:.1f}%"
    except Exception:
        return "N/A"
