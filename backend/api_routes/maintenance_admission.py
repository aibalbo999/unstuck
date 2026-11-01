"""Short synchronous API admission, without leaking control-plane details."""

from contextlib import contextmanager

from fastapi import HTTPException

import maintenance_guard


@contextmanager
def analysis_admission():
    """Never hold this context across an await or a streamed response."""
    try:
        with maintenance_guard.admission():
            yield
    except maintenance_guard.MaintenanceError:
        raise HTTPException(
            status_code=503,
            detail="系統維護中或維護狀態尚未確認，暫停建立及重新排入分析工作；既有工作仍可查詢或取消。",
        ) from None
