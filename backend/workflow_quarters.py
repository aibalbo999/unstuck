"""Quarter helpers for workflow reconciliation."""

from __future__ import annotations

from datetime import date
from typing import Any


def latest_closed_quarter_for_reconciliation(data: dict[str, Any]) -> tuple[int, int]:
    year = data.get("year") or data.get("fiscal_year")
    season = data.get("season") or data.get("quarter")
    try:
        year_int = int(year)
        season_int = int(season)
    except (TypeError, ValueError):
        today = date.today()
        current_quarter = (today.month - 1) // 3 + 1
        closed_quarter = current_quarter - 1
        closed_year = today.year
        if closed_quarter == 0:
            closed_quarter = 4
            closed_year -= 1
        return closed_year, closed_quarter
    if season_int not in {1, 2, 3, 4}:
        return latest_closed_quarter_for_reconciliation({})
    return year_int, season_int
