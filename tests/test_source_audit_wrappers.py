import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import source_audit  # noqa: E402
from data_trust import (  # noqa: E402
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
)
from data_fetch.market_sources.common import _run_named_fetches  # noqa: E402


def test_audited_fetch_records_success_error_and_unavailable():
    success = source_audit.audited_fetch(
        "recent_catalysts",
        "fake provider",
        lambda: [{"title": "A"}, {"title": "B"}],
        default=[],
    )
    assert success["value"] == [{"title": "A"}, {"title": "B"}]
    assert success["audit"]["status"] == AUDIT_STATUS_SUCCESS
    assert success["audit"]["provider"] == "fake provider"
    assert success["audit"]["record_count"] == 2
    assert success["audit"]["duration_ms"] >= 0

    unavailable = source_audit.audited_fetch(
        "peer_discovery",
        "fake provider",
        lambda: [],
        default=[],
    )
    assert unavailable["value"] == []
    assert unavailable["audit"]["status"] == AUDIT_STATUS_UNAVAILABLE
    assert unavailable["audit"]["record_count"] == 0

    def boom():
        raise RuntimeError("provider exploded")

    failed = source_audit.audited_fetch(
        "market_data",
        "fake provider",
        boom,
        default={"fallback": True},
    )
    assert failed["value"] == {"fallback": True}
    assert failed["audit"]["status"] == AUDIT_STATUS_ERROR
    assert failed["audit"]["error_kind"] == "RuntimeError"
    assert "provider exploded" in failed["audit"]["message"]


def test_audited_fetch_async_records_cache_hit():
    async def fake_async():
        return ["cached headline"]

    result = asyncio.run(
        source_audit.audited_fetch_async(
            "recent_catalysts",
            "async fake",
            fake_async,
            default=[],
            cache_hit=True,
        )
    )

    assert result["value"] == ["cached headline"]
    assert result["audit"]["status"] == AUDIT_STATUS_SUCCESS
    assert result["audit"]["cache_hit"] is True


def test_run_named_fetches_include_audit_preserves_old_mode():
    def boom():
        raise ValueError("bad source")

    fetches = {
        "ok": (lambda: [1, 2], (), [], "ok warning", "recent_catalysts", "fake ok"),
        "empty": (lambda: [], (), [], "empty warning", "peer_discovery", "fake empty"),
        "boom": (boom, (), [], "boom warning", "market_data", "fake boom"),
    }

    audited = _run_named_fetches(fetches, max_workers=2, include_audit=True)
    assert audited["values"]["ok"] == [1, 2]
    assert audited["values"]["empty"] == []
    assert audited["values"]["boom"] == []

    statuses = {entry["provider"]: entry["status"] for entry in audited["audit"]}
    assert statuses["fake ok"] == AUDIT_STATUS_SUCCESS
    assert statuses["fake empty"] == AUDIT_STATUS_UNAVAILABLE
    assert statuses["fake boom"] == AUDIT_STATUS_ERROR

    legacy = _run_named_fetches({"ok": (lambda: [1], (), [], "legacy warning")}, max_workers=1)
    assert legacy == {"ok": [1]}
