import asyncio
import json
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from data_trust import data_snapshot_filename_for_report  # noqa: E402
from report_persistence import report_bundle_keys_for_filename  # noqa: E402
from storage.report_storage import InMemoryStorage  # noqa: E402


class LookupBrokenSourceAuditIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise KeyError("source audit sequence lookup unavailable")


class LookupBrokenSourceAuditList(list):
    def __iter__(self):
        return LookupBrokenSourceAuditIterator()


class LookupBrokenSourceAuditIterList(list):
    def __iter__(self):
        raise KeyError("source audit iterator lookup unavailable")


def test_refresh_data_diff_accepts_mapping_safe_snapshots():
    import report_refresh_service

    previous_snapshot = MappingProxyType(
        {
            "data_trust": MappingProxyType(
                {
                    "status": "stale",
                    "critical_failures": (),
                    "stale_sources": ("market_data",),
                    "reason_codes": ("source_stale:market_data",),
                }
            ),
            "source_audit": (
                MappingProxyType(
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "status": "error",
                        "message": "stale quote",
                    }
                ),
            ),
        }
    )
    refreshed_snapshot = MappingProxyType(
        {
            "data_trust": MappingProxyType(
                {
                    "status": "fresh",
                    "critical_failures": (),
                    "stale_sources": (),
                    "reason_codes": ("fresh_core_sources",),
                }
            ),
            "source_audit": (
                MappingProxyType(
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "status": "success",
                        "message": "fresh quote",
                    }
                ),
            ),
        }
    )

    diff = report_refresh_service.refresh_data_diff(previous_snapshot, refreshed_snapshot)

    assert diff["data_trust_status"] == {"before": "stale", "after": "fresh", "changed": True}
    assert diff["stale_sources"] == {"removed": ["market_data"], "added": []}
    assert diff["source_status_changes"] == [
        {
            "source": "market_data",
            "provider": "yfinance",
            "before": "error",
            "after": "success",
            "message": "fresh quote",
        }
    ]
    assert "可信度 stale → fresh" in diff["summary"]


def test_refresh_requires_analysis_rerun_accepts_mapping_safe_data_changes():
    import report_refresh_service

    previous_snapshot = MappingProxyType(
        {
            "data": MappingProxyType({"current_price": 100, "market_cap_raw": 1000}),
            "data_trust": MappingProxyType(
                {
                    "status": "fresh",
                    "critical_failures": (),
                    "stale_sources": (),
                    "reason_codes": ("fresh_core_sources",),
                }
            ),
        }
    )
    refreshed_snapshot = MappingProxyType(
        {
            "data": MappingProxyType({"current_price": 101, "market_cap_raw": 1000}),
            "data_trust": MappingProxyType(
                {
                    "status": "fresh",
                    "critical_failures": (),
                    "stale_sources": (),
                    "reason_codes": ("fresh_core_sources",),
                }
            ),
        }
    )

    assert report_refresh_service.refresh_requires_analysis_rerun(
        previous_snapshot,
        refreshed_snapshot,
        {"stale_sources": {"removed": [], "added": []}, "critical_failures": {"removed": [], "added": []}},
    ) is True


def test_stale_sources_accepts_mapping_safe_fresh_source_audit():
    import report_refresh_service

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = MappingProxyType(
        {
            "source_audit": (
                MappingProxyType(
                    {
                        "source": "market_data",
                        "provider": "yfinance",
                        "status": "success",
                        "record_count": 1,
                        "fetched_at": fresh_time,
                    }
                ),
                MappingProxyType(
                    {
                        "source": "recent_catalysts",
                        "provider": "news",
                        "status": "success",
                        "record_count": 2,
                        "fetched_at": fresh_time,
                    }
                ),
            ),
        }
    )

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_preserves_native_source_audit_when_iterator_lookup_fails():
    import report_refresh_service

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": LookupBrokenSourceAuditList(
            [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "record_count": 1,
                    "fetched_at": fresh_time,
                },
                {
                    "source": "recent_catalysts",
                    "provider": "news",
                    "status": "success",
                    "record_count": 2,
                    "fetched_at": fresh_time,
                },
            ]
        ),
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_preserves_native_source_audit_when_iterator_creation_lookup_fails():
    import report_refresh_service

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": LookupBrokenSourceAuditIterList(
            [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "record_count": 1,
                    "fetched_at": fresh_time,
                },
                {
                    "source": "recent_catalysts",
                    "provider": "news",
                    "status": "success",
                    "record_count": 2,
                    "fetched_at": fresh_time,
                },
            ]
        ),
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_accepts_source_audit_rows_when_items_iter_lookup_fails():
    import report_refresh_service

    class LookupBrokenItemsIterable:
        def __iter__(self):
            raise KeyError("source audit row items iterable lookup unavailable")

    class LookupItemsIterableSourceAuditRow(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            return self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

        def items(self):
            return LookupBrokenItemsIterable()

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": [
            LookupItemsIterableSourceAuditRow(
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "record_count": 1,
                    "fetched_at": fresh_time,
                }
            ),
            LookupItemsIterableSourceAuditRow(
                {
                    "source": "recent_catalysts",
                    "provider": "news",
                    "status": "success",
                    "record_count": 2,
                    "fetched_at": fresh_time,
                }
            ),
        ],
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_accepts_source_audit_rows_when_mapping_key_hash_lookup_fails():
    import report_refresh_service

    class LookupBrokenKey:
        def __hash__(self):
            raise KeyError("source audit row mapping key hash lookup unavailable")

    class LookupKeyHashTraversalSourceAuditRow(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            if key in self._data:
                return self._data[key]
            raise KeyError(key)

        def __iter__(self):
            return iter((LookupBrokenKey(), *self._data.keys()))

        def __len__(self):
            return len(self._data) + 1

        def items(self):
            raise KeyError("source audit row items lookup unavailable")

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": [
            LookupKeyHashTraversalSourceAuditRow(
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "record_count": 1,
                    "fetched_at": fresh_time,
                }
            ),
            LookupKeyHashTraversalSourceAuditRow(
                {
                    "source": "recent_catalysts",
                    "provider": "news",
                    "status": "success",
                    "record_count": 2,
                    "fetched_at": fresh_time,
                }
            ),
        ],
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_accepts_source_audit_rows_when_item_pair_lookup_fails():
    import report_refresh_service

    class LookupBrokenItemPair:
        def __iter__(self):
            raise KeyError("source audit row item pair lookup unavailable")

    class LookupItemPairSourceAuditRow(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("source audit row mapping iterator unavailable")

        def __len__(self):
            return len(self._data) + 1

        def items(self):
            return [LookupBrokenItemPair(), *self._data.items()]

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": [
            LookupItemPairSourceAuditRow(
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "record_count": 1,
                    "fetched_at": fresh_time,
                }
            ),
            LookupItemPairSourceAuditRow(
                {
                    "source": "recent_catalysts",
                    "provider": "news",
                    "status": "success",
                    "record_count": 2,
                    "fetched_at": fresh_time,
                }
            ),
        ],
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_accepts_source_audit_rows_when_key_hash_lookup_fails():
    import report_refresh_service

    class LookupBrokenKey:
        def __hash__(self):
            raise KeyError("source audit row key hash lookup unavailable")

    class LookupKeyHashSourceAuditRow(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("source audit row mapping iterator unavailable")

        def __len__(self):
            return len(self._data) + 1

        def items(self):
            return [(LookupBrokenKey(), "BROKEN"), *self._data.items()]

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": [
            LookupKeyHashSourceAuditRow(
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "record_count": 1,
                    "fetched_at": fresh_time,
                }
            ),
            LookupKeyHashSourceAuditRow(
                {
                    "source": "recent_catalysts",
                    "provider": "news",
                    "status": "success",
                    "record_count": 2,
                    "fetched_at": fresh_time,
                }
            ),
        ],
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_stale_sources_parses_falsey_but_valid_source_audit_timestamps():
    import report_refresh_service

    class FalseyTimestamp:
        def __init__(self, value):
            self.value = value

        def __bool__(self):
            return False

        def __str__(self):
            return self.value

    fresh_time = datetime.now(timezone.utc).isoformat()
    previous_snapshot = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "yfinance",
                "status": "success",
                "record_count": 1,
                "fetched_at": FalseyTimestamp(fresh_time),
            },
            {
                "source": "recent_catalysts",
                "provider": "news",
                "status": "success",
                "record_count": 2,
                "fetched_at": FalseyTimestamp(fresh_time),
            },
        ],
    }

    assert report_refresh_service._stale_sources(previous_snapshot) == []


def test_report_refresh_forces_quote_refresh_when_financial_statements_are_fresh(tmp_path):
    import report_refresh_service

    filename = "2308_TW_v2_report_20260626_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage = InMemoryStorage()
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    fresh_time = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    previous_snapshot = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline": "v2",
        "data": {"current_price": 100},
        "source_audit": [
            {"source": "financial_statements", "provider": "FinMind", "status": "success", "record_count": 1, "fetched_at": fresh_time},
            {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1, "fetched_at": fresh_time},
        ],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
    }
    storage.save_report(
        keys.data_key,
        json.dumps(previous_snapshot, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )

    seen_requests = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            seen_requests.append(request)
            return SimpleNamespace(
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "台達電",
                    "current_price": 101,
                    "source_audit": [],
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
                }
            )

    asyncio.run(
        report_refresh_service.refresh_report_data_snapshot(
            filename,
            output_dir=str(tmp_path),
            refresh_service=FakeRefreshService(),
            storage=storage,
        )
    )

    assert seen_requests
    assert seen_requests[0].ticker == "2308.TW"
    assert seen_requests[0].options.force_refresh is True
    assert "financial_statements" not in report_refresh_service._stale_sources(previous_snapshot)
    assert data_snapshot_filename_for_report(filename)


def test_report_refresh_accepts_mapping_safe_refreshed_data_payload(tmp_path):
    import report_refresh_service

    filename = "2308_TW_v2_report_20260626_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage = InMemoryStorage()
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    fresh_time = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    previous_snapshot = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline": "v2",
        "data": {"current_price": 100},
        "source_audit": [
            {"source": "market_data", "provider": "yfinance", "status": "success", "record_count": 1, "fetched_at": fresh_time},
            {"source": "recent_catalysts", "provider": "news", "status": "success", "record_count": 1, "fetched_at": fresh_time},
        ],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
    }
    storage.save_report(
        keys.data_key,
        json.dumps(previous_snapshot, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )

    class FakeRefreshService:
        async def fetch_async(self, request):
            return SimpleNamespace(
                data=MappingProxyType(
                    {
                        "data_schema_version": 4,
                        "ticker": request.ticker,
                        "company_name": "台達電",
                        "current_price": 101,
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "yfinance",
                                    "status": "success",
                                    "record_count": 1,
                                    "fetched_at": fresh_time,
                                }
                            ),
                        ),
                        "data_trust": MappingProxyType(
                            {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                        ),
                    }
                )
            )

    result = asyncio.run(
        report_refresh_service.refresh_report_data_snapshot(
            filename,
            output_dir=str(tmp_path),
            refresh_service=FakeRefreshService(),
            storage=storage,
            return_refreshed_data=True,
        )
    )

    saved_content = storage.get_report(keys.data_key)
    assert saved_content is not None
    saved_snapshot = json.loads(saved_content.content.decode("utf-8"))
    assert result["success"] is True
    assert result["refreshed_data"]["current_price"] == 101
    assert saved_snapshot["data"]["current_price"] == 101
    assert saved_snapshot["data_trust"]["status"] == "fresh"
