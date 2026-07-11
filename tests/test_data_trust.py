import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import data_trust  # noqa: E402
import data_fetch.audit_helpers as audit_helpers  # noqa: E402
import report_reproducibility  # noqa: E402
from data_fetch.constants import DATA_SCHEMA_VERSION  # noqa: E402
from fixtures.data_payloads import fresh_audited_payload, provider_sla_alert, stale_audited_payload  # noqa: E402


class BrokenTruthText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise ValueError("text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenTruthInt:
    def __init__(self, value: int):
        self.value = value

    def __bool__(self):
        raise ValueError("int truthiness unavailable")

    def __int__(self):
        return self.value


class BrokenTruthBool:
    def __bool__(self):
        raise ValueError("bool truthiness unavailable")


class BrokenTruthDict(dict):
    def __bool__(self):
        raise ValueError("dict truthiness unavailable")


class BrokenGetDict(dict):
    def get(self, *_args, **_kwargs):
        raise RuntimeError("mapping get unavailable")


class BrokenString:
    def __init__(self, text: str = "broken"):
        self.text = text

    def __str__(self):
        raise ValueError(f"{self.text} string conversion unavailable")


class BrokenFloatScore:
    def __float__(self):
        raise RuntimeError("score conversion unavailable")


class BrokenTargetRows(list):
    def __iter__(self):
        yield {"target_price": "NT$120"}
        raise RuntimeError("target row iteration unavailable")


class BrokenTargetNativeRows(list):
    def __iter__(self):
        raise RuntimeError("target native row iterator accessor unavailable")


class BrokenTargetFirstNextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("target row first item unavailable")


class BrokenTargetFirstNextRows(list):
    def __iter__(self):
        return BrokenTargetFirstNextIterator()


class BrokenTargetMapping(dict):
    def items(self):
        yield ("recommendation", {"target_price": "NT$120"})
        raise RuntimeError("target mapping iteration unavailable")


class BrokenTargetNativeMapping(dict):
    def items(self):
        raise RuntimeError("target mapping items accessor unavailable")


class BrokenTargetFirstNextItems:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("target mapping first item unavailable")


class BrokenTargetFirstNextMapping(dict):
    def items(self):
        return BrokenTargetFirstNextItems()


class BrokenTargetItemsIterable:
    def __iter__(self):
        raise RuntimeError("target mapping items iterator unavailable")


class BrokenTargetItemsIterableMapping(dict):
    def items(self):
        return BrokenTargetItemsIterable()


class BrokenNativeRowsList(list):
    def __iter__(self):
        raise RuntimeError("native row list iterator accessor unavailable")


class BrokenNativeTextList(list):
    def __iter__(self):
        raise RuntimeError("native text list iterator accessor unavailable")


class BrokenProviderSlaFirstNextRowsIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("provider SLA row first item unavailable")


class BrokenProviderSlaFirstNextRowsList(list):
    def __iter__(self):
        return BrokenProviderSlaFirstNextRowsIterator()


class BrokenProviderSlaFirstNextTextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("provider SLA text first item unavailable")


class BrokenProviderSlaFirstNextTextList(list):
    def __iter__(self):
        return BrokenProviderSlaFirstNextTextIterator()


class BrokenNativeTuple(tuple):
    def __iter__(self):
        raise RuntimeError("native tuple iterator accessor unavailable")


class BrokenFirstNextIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("snapshot sequence first item unavailable")


class BrokenSnapshotFirstNextRows(list):
    def __iter__(self):
        return BrokenFirstNextIterator()


class BrokenNativeSnapshotMapping(dict):
    def items(self):
        raise RuntimeError("native snapshot mapping items accessor unavailable")


class BrokenItemsIterable:
    def __iter__(self):
        raise RuntimeError("snapshot mapping items iterable unavailable")


class BrokenSnapshotItemsIterableMapping(dict):
    def items(self):
        return BrokenItemsIterable()


class BrokenSnapshotFirstNextItems:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("snapshot mapping first item unavailable")


class BrokenSnapshotFirstNextMapping(dict):
    def items(self):
        return BrokenSnapshotFirstNextItems()


def test_source_audit_success_error_and_skipped_cache_entries():
    data = {
        "ticker": "2330.TW",
        "current_price": 100,
        "years": ["2024", "2025"],
        "revenue_history": [10, 12],
        "net_income_history": [2, 3],
        "recent_catalysts": [{"title": "cached"}],
        "source_freshness": {
            "market_data": {"fetched_at_epoch": 100.0, "stale": False},
            "financial_statements": {"fetched_at_epoch": 100.0, "stale": False},
            "recent_catalysts": {"fetched_at_epoch": 100.0, "stale": False},
        },
    }

    audit_helpers._append_source_fetch_audit(
        data,
        "market_data",
        "yfinance",
        data_trust.AUDIT_STATUS_SUCCESS,
        fetched_at_epoch=100.0,
        started_at_epoch=99.5,
        finished_at_epoch=100.0,
    )
    audit_helpers._append_source_fetch_audit(
        data,
        "financial_statements",
        "yfinance",
        data_trust.AUDIT_STATUS_ERROR,
        fetched_at_epoch=100.0,
        started_at_epoch=99.0,
        finished_at_epoch=100.0,
        record_count=0,
        error_kind="missing_data",
        message="annual statement missing",
    )
    audit_helpers._append_skipped_fresh_cache_audit(data, ("recent_catalysts",), now_epoch=105.0)

    entries = data["source_audit"]
    assert entries[0]["status"] == "success"
    assert entries[0]["duration_ms"] == 500
    assert entries[1]["status"] == "error"
    assert entries[1]["error_kind"] == "missing_data"
    assert entries[2]["status"] == "skipped_fresh_cache"
    assert entries[2]["cache_hit"] is True


def test_source_audit_entry_text_fields_do_not_depend_on_truthiness():
    entry = data_trust.build_source_audit_entry(
        BrokenTruthText("market_data"),
        BrokenTruthText("fallback-provider"),
        "error",
        record_count=0,
        error_kind=BrokenTruthText("ConnectionError"),
        message=BrokenTruthText("temporary provider failure"),
    )

    assert entry["source"] == "market_data"
    assert entry["provider"] == "fallback-provider"
    assert entry["error_kind"] == "ConnectionError"
    assert entry["message"] == "temporary provider failure"


def test_source_audit_entry_status_uses_safe_text_conversion():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        BrokenTruthText("success"),
        record_count=1,
    )

    assert entry["status"] == "success"


def test_source_audit_entry_record_count_does_not_depend_on_truthiness():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        record_count=BrokenTruthInt(7),
    )

    assert entry["record_count"] == 7


def test_source_audit_entry_bool_fields_do_not_depend_on_truthiness():
    entry = data_trust.build_source_audit_entry(
        "market_data",
        "fallback-provider",
        "success",
        cache_hit=BrokenTruthBool(),
        stale=BrokenTruthBool(),
    )

    assert entry["cache_hit"] is False
    assert entry["stale"] is False


def test_source_record_count_source_key_does_not_depend_on_truthiness():
    count = data_trust.source_record_count(
        BrokenTruthText("market_data"),
        {
            "current_price": 100,
            "market_cap_raw": 200,
            "pe_ratio_raw": None,
            "pb_ratio": "N/A",
            "price_history": [99, 100],
        },
    )

    assert count == 3


def test_normalize_data_trust_uses_dict_native_field_reads():
    alert = {"provider": "yfinance", "alert_level": "warning"}

    normalized = data_trust.normalize_data_trust(
        BrokenGetDict(
            {
                "status": "partial",
                "critical_failures": ["financial_statements"],
                "stale_sources": ["market_data"],
                "last_market_data_at": "2026-06-07T01:00:00+00:00",
                "notes": ["核心來源部分降級。"],
                "reason_codes": ["provider_sla_warning"],
                "score": 72,
                "score_reasons": ["manual score"],
                "provider_sla_alerts": [alert],
            }
        )
    )

    assert normalized == {
        "status": "partial",
        "critical_failures": ["financial_statements"],
        "stale_sources": ["market_data"],
        "last_market_data_at": "2026-06-07T01:00:00+00:00",
        "notes": ["核心來源部分降級。"],
        "reason_codes": ["provider_sla_warning"],
        "score": 72,
        "score_reasons": ["manual score"],
        "provider_sla_alerts": [alert],
    }


def test_normalize_data_trust_reason_codes_do_not_depend_on_truthiness():
    normalized = data_trust.normalize_data_trust(
        {
            "status": "fresh",
            "score": 90,
            "reason_codes": BrokenTruthText("manual_reason"),
        }
    )

    assert normalized["reason_codes"] == ["manual_reason"]


def test_data_trust_statuses_fresh_stale_error_unknown():
    fresh = fresh_audited_payload(provider="yfinance")
    fresh_trust = data_trust.build_data_trust(fresh)
    assert fresh_trust["status"] == "fresh"
    assert fresh_trust["score"] >= 90
    assert "fresh_core_sources" in fresh_trust["reason_codes"]

    stale = stale_audited_payload(source="market_data")
    stale_trust = data_trust.build_data_trust(stale)
    assert stale_trust["status"] == "stale"
    assert 0 <= stale_trust["score"] < fresh_trust["score"]
    assert "market_data" in stale_trust["stale_sources"]

    error = {
        "source_audit": [
            data_trust.build_source_audit_entry("market_data", "yfinance", "error", record_count=0),
            data_trust.build_source_audit_entry("financial_statements", "yfinance", "error", record_count=0),
        ]
    }
    trust = data_trust.build_data_trust(error)
    assert trust["status"] == "error"
    assert trust["score"] <= 20
    assert trust["critical_failures"] == ["market_data", "financial_statements"]

    unknown = data_trust.build_data_trust({})
    assert unknown["status"] == "unknown"
    assert unknown["score"] == 35
    assert unknown["score_reasons"]
    assert "missing_data_trust_snapshot" in unknown["reason_codes"]


def test_optional_not_configured_sources_do_not_degrade_fresh_core_data(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "recent_catalysts",
            "Alternative Search",
            "not_configured",
            record_count=0,
            message="Alternative Search 未設定，僅略過補充催化劑。",
        )
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert "optional_source_not_configured:recent_catalysts" in trust["reason_codes"]
    assert "recent_catalysts" not in trust["critical_failures"]
    assert any("補充來源未設定" in note for note in trust["notes"])


def test_optional_degraded_enrichment_is_not_treated_as_core_failure(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "peer_discovery",
            "Alternative Search",
            "degraded_enrichment",
            record_count=0,
            message="同業搜尋補充來源降級，核心財務資料仍可用。",
        )
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert "optional_source_degraded:peer_discovery" in trust["reason_codes"]
    assert "peer_discovery" not in trust["critical_failures"]
    assert any("補充來源降級" in note for note in trust["notes"])


def test_optional_stale_enrichment_sources_do_not_degrade_fresh_core_data(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_freshness"].update(
        {
            "recent_catalysts": {
                "stale": True,
                "fetched_at": "2026-06-01T00:00:00+00:00",
                "fetched_at_epoch": 1780243200,
            },
            "social_sentiment": {
                "stale": True,
                "fetched_at": "2026-06-01T00:00:00+00:00",
                "fetched_at_epoch": 1780243200,
            },
        }
    )
    payload["source_audit"].extend(
        [
            data_trust.build_source_audit_entry(
                "recent_catalysts",
                "cache",
                "unavailable",
                record_count=1,
                cache_hit=True,
                stale=True,
            ),
            data_trust.build_source_audit_entry(
                "social_sentiment",
                "cache",
                "unavailable",
                record_count=1,
                cache_hit=True,
                stale=True,
            ),
        ]
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert trust["stale_sources"] == []
    assert "optional_source_stale:recent_catalysts" in trust["reason_codes"]
    assert "optional_source_stale:social_sentiment" in trust["reason_codes"]
    assert not any(code.startswith("source_stale:") for code in trust["reason_codes"])


def test_optional_source_errors_do_not_degrade_fresh_core_data(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "recent_catalysts",
            "News/Search providers",
            "error",
            record_count=0,
            error_kind="ConnectionError",
            message="補充新聞來源暫時無法連線。",
        )
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "optional_source_error:recent_catalysts" in trust["reason_codes"]
    assert "source_error:recent_catalysts" not in trust["reason_codes"]


def test_data_trust_audit_source_text_does_not_depend_on_truthiness(monkeypatch):
    import provider_sla

    monkeypatch.setattr(provider_sla, "get_provider_sla_alerts", lambda limit=100: [])
    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        {
            "source": BrokenTruthText("market_data"),
            "provider": "fallback-quote",
            "status": "error",
            "record_count": 0,
            "stale": False,
        }
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "partial"
    assert "source_error:market_data" in trust["reason_codes"]


def test_provider_sla_warning_notes_current_provider_without_downgrade(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [provider_sla_alert(provider="fake-yfinance", level="warning", attempts=3)],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_warning_note" in trust["reason_codes"]
    assert any("來源健康度觀察" in note for note in trust["notes"])


def test_core_provider_sla_critical_is_notice_when_current_fetch_succeeded(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=20)],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert "provider_sla_core_health_notice" in trust["reason_codes"]
    assert any("本次資料抓取成功" in note for note in trust["notes"])


def test_core_provider_sla_critical_for_failed_secondary_provider_is_notice_when_source_succeeded(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "market_data",
            "fallback-quote",
            "unavailable",
            record_count=0,
            message="備援 quote provider 本次未回傳。",
        )
    )
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [
            provider_sla_alert(source="market_data", provider="fallback-quote", level="critical", attempts=20)
        ],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert "provider_sla_core_health_notice" in trust["reason_codes"]


def test_optional_provider_sla_critical_is_notice_without_global_downgrade(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_audit"].extend(
        [
            data_trust.build_source_audit_entry(
                "recent_catalysts",
                "cache",
                "skipped_fresh_cache",
                record_count=1,
                cache_hit=True,
            ),
            data_trust.build_source_audit_entry(
                "social_sentiment",
                "cache",
                "skipped_fresh_cache",
                record_count=1,
                cache_hit=True,
            ),
        ]
    )
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [
            provider_sla_alert(source="recent_catalysts", provider="cache", level="critical", attempts=20),
            provider_sla_alert(source="social_sentiment", provider="cache", level="critical", attempts=20),
        ],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "fresh"
    assert trust["score"] >= 90
    assert "provider_sla_critical" not in trust["reason_codes"]
    assert "provider_sla_optional_critical" in trust["reason_codes"]
    assert any("補充來源健康度警示" in note for note in trust["notes"])


def test_provider_sla_critical_downgrades_current_provider_trust(monkeypatch):
    import provider_sla

    payload = fresh_audited_payload(provider="fake-yfinance")
    payload["source_freshness"]["market_data"] = {
        "stale": True,
        "fetched_at": "2026-06-01T00:00:00+00:00",
        "fetched_at_epoch": 1780243200,
    }
    payload["source_audit"].append(
        data_trust.build_source_audit_entry(
            "market_data",
            "fake-yfinance",
            "unavailable",
            record_count=0,
            stale=True,
        )
    )
    monkeypatch.setattr(
        provider_sla,
        "get_provider_sla_alerts",
        lambda limit=100: [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)],
    )

    trust = data_trust.build_data_trust(payload)

    assert trust["status"] == "partial"
    assert trust["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in trust["reason_codes"]
    assert any("來源健康度警示" in note for note in trust["notes"])


def test_provider_sla_row_mapping_get_failures_do_not_interrupt_trust_downgrade():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            BrokenGetDict(
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            )
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [
        BrokenGetDict(
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "alert_level": "critical",
                "alert_message": "success rate low",
                "success_rate": 0.4,
                "last_status": "error",
                "alert_basis": "last_24h",
                "windows": {"last_24h": {"attempts": 3}},
            }
        )
    ]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert result["provider_sla_alerts"][0]["evidence_attempts"] == 3
    assert "provider_sla_critical" in result["reason_codes"]
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_source_data_get_failure_does_not_interrupt_trust_downgrade():
    import data_trust_sla_policy

    payload = BrokenGetDict(
        {
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        }
    )
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_nested_window_get_failure_falls_back_to_alert_attempts():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alert = provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)
    alert["windows"] = BrokenGetDict({"last_24h": {"attempts": 3}})

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=[alert])

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["evidence_attempts"] == 3
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_source_audit_native_lists_preserve_downgrade_evidence():
    import data_trust_sla_policy

    payload = {
        "source_audit": BrokenNativeRowsList(
            [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        )
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_alert_native_lists_preserve_downgrade_evidence():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = BrokenNativeRowsList([provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)])

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_source_audit_rows_survive_first_next_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": BrokenProviderSlaFirstNextRowsList(
            [
                {
                    "source": "market_data",
                    "provider": "fake-yfinance",
                    "status": "unavailable",
                    "record_count": 0,
                    "stale": True,
                }
            ]
        )
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_alert_rows_survive_first_next_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {"status": "fresh", "notes": [], "reason_codes": []}
    alerts = BrokenProviderSlaFirstNextRowsList(
        [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]
    )

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert result["provider_sla_alerts"][0]["provider"] == "fake-yfinance"
    assert "provider_sla_critical" in result["reason_codes"]


def test_provider_sla_trust_metadata_native_lists_preserve_existing_context():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {
        "status": "fresh",
        "notes": BrokenNativeTextList(["既有資料可信度備註"]),
        "reason_codes": BrokenNativeTextList(["existing_manual_review"]),
    }
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert "existing_manual_review" in result["reason_codes"]
    assert "provider_sla_critical" in result["reason_codes"]
    assert result["notes"][0] == "既有資料可信度備註"
    assert any("來源健康度警示" in note for note in result["notes"])


def test_provider_sla_trust_metadata_survives_first_next_iterator_failures():
    import data_trust_sla_policy

    payload = {
        "source_audit": [
            {
                "source": "market_data",
                "provider": "fake-yfinance",
                "status": "unavailable",
                "record_count": 0,
                "stale": True,
            }
        ]
    }
    trust = {
        "status": "fresh",
        "notes": BrokenProviderSlaFirstNextTextList(["既有資料可信度備註"]),
        "reason_codes": BrokenProviderSlaFirstNextTextList(["existing_manual_review"]),
    }
    alerts = [provider_sla_alert(provider="fake-yfinance", level="critical", attempts=3)]

    result = data_trust_sla_policy.apply_provider_sla_to_trust(payload, trust, alerts=alerts)

    assert result["status"] == "partial"
    assert "existing_manual_review" in result["reason_codes"]
    assert "provider_sla_critical" in result["reason_codes"]
    assert result["notes"][0] == "既有資料可信度備註"
    assert any("來源健康度警示" in note for note in result["notes"])


def test_data_snapshot_sanitizes_sensitive_keys():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEST",
            "pipeline_id": "v1",
            "deterministic_fallbacks": [
                {
                    "agent_num": 14,
                    "trigger": "repair_429_failure",
                    "message": "已套用 deterministic 三情境估值 fallback",
                }
            ],
            "data": {
                "ticker": "TEST",
                "api_key": "SHOULD_NOT_APPEAR",
                "nested": {
                    "prompt": "DO NOT SAVE PROMPT",
                    "safe_value": 123,
                },
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        }
    )
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert "SHOULD_NOT_APPEAR" not in encoded
    assert "DO NOT SAVE PROMPT" not in encoded
    assert snapshot["data"]["nested"]["safe_value"] == 123
    assert snapshot["deterministic_fallbacks"][0]["trigger"] == "repair_429_failure"
    assert snapshot["snapshot_hash"] == data_trust.snapshot_content_hash(snapshot)
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True
    tampered = dict(snapshot)
    tampered["ticker"] = "TAMPERED"
    assert data_trust.validate_data_snapshot(tampered)["valid"] is False


def test_data_snapshot_integrity_hash_metadata_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v1",
            "data": {
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    snapshot["snapshot_hash"] = BrokenTruthText(snapshot["snapshot_hash"])

    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_data_snapshot_validators_use_dict_native_field_reads():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "VALID",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "VALID",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenGetDict(snapshot)

    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True
    assert data_trust.validate_data_snapshot(wrapped_snapshot) == {"valid": True, "errors": []}


def test_data_snapshot_content_hash_keys_use_safe_text_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v1",
            "data": {
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    expected_hash = snapshot["snapshot_hash"]
    snapshot[BrokenString("bad hash key")] = "SHOULD_NOT_APPEAR"

    integrity = data_trust.verify_data_snapshot_integrity(snapshot)

    assert integrity["valid"] is True
    assert integrity["hash"] == expected_hash


def test_data_snapshot_content_hash_uses_safe_mapping_items():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenNativeSnapshotMapping(snapshot)

    assert data_trust.snapshot_content_hash(wrapped_snapshot) == snapshot["snapshot_hash"]
    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True


def test_data_snapshot_content_hash_survives_first_next_mapping_failures():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "HASH",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "HASH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    wrapped_snapshot = BrokenSnapshotFirstNextMapping(snapshot)

    assert data_trust.snapshot_content_hash(wrapped_snapshot) == snapshot["snapshot_hash"]
    assert data_trust.verify_data_snapshot_integrity(wrapped_snapshot)["valid"] is True


def test_data_snapshot_size_governance_uses_sanitized_snapshot_keys():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "SIZE",
            "pipeline_id": "v1",
            "data": {
                "ticker": "SIZE",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    snapshot[BrokenString("bad governance key")] = "SHOULD_NOT_APPEAR"

    governed = data_trust.apply_snapshot_size_governance(snapshot, max_bytes=100_000)
    encoded = json.dumps(governed, ensure_ascii=False)

    assert "SHOULD_NOT_APPEAR" not in encoded
    assert data_trust.verify_data_snapshot_integrity(governed)["valid"] is True


def test_data_snapshot_size_bytes_uses_sanitized_snapshot_keys():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "SIZE",
            "pipeline_id": "v1",
            "data": {
                "ticker": "SIZE",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    snapshot[BrokenString("bad size key")] = "SHOULD_NOT_APPEAR"

    assert data_trust.snapshot_size_bytes(snapshot) == data_trust.snapshot_size_bytes(
        data_trust.sanitize_for_snapshot(snapshot)
    )


def test_data_snapshot_identity_fields_do_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": BrokenTruthText("CTX"),
            "company_name": BrokenTruthText("Context Co"),
            "pipeline_id": BrokenTruthText("v2"),
            "data": {
                "ticker": "DATA",
                "company_name": "Data Co",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["ticker"] == "CTX"
    assert snapshot["company_name"] == "Context Co"
    assert snapshot["pipeline"] == "v2"


def test_data_snapshot_build_uses_dict_native_context_and_data_reads():
    snapshot = data_trust.build_data_snapshot(
        BrokenGetDict(
            {
                "ticker": "2330.TW",
                "company_name": "台積電",
                "pipeline_id": "v2",
                "pipeline_label": "完整分析",
                "agent_sequence": [1, 16],
                "conclusion_generated_at": "2026-06-07T00:00:00+00:00",
                "snapshot_refreshed_at": "2026-06-07T00:05:00+00:00",
                "decision_validity_status": "stale",
                "requires_rerun_reason": "market_data_changed",
                "refreshed_from_report": "2330_v2.html",
                "refreshed_without_analysis_rerun": True,
                "analysis_text_stale_message": "價格已刷新，結論待重跑。",
                "analyses": {16: "final recommendation"},
                "structured_outputs": {16: {"recommendation": {"target_price": "NT$120"}}},
                "parsed": {"recommendation": {"target_price": "NT$120"}},
                "deterministic_fallbacks": ["valuation_fallback"],
                "report_lint": {"status": "passed"},
                "content_credibility": {"status": "passed"},
                "report_conformance": {"status": "passed"},
                "data": BrokenGetDict(
                    {
                        "data_schema_version": DATA_SCHEMA_VERSION,
                        "ticker": "DATA",
                        "company_name": "Data Co",
                        "source_freshness": {"market_data": {"status": "fresh"}},
                        "source_audit": [],
                        "data_source_notes": ["來源已核對"],
                        "data_trust": BrokenGetDict(
                            {
                                "status": "fresh",
                                "score": 90,
                                "reason_codes": ["fresh_core_sources"],
                            }
                        ),
                    }
                ),
            }
        ),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["ticker"] == "2330.TW"
    assert snapshot["company_name"] == "台積電"
    assert snapshot["pipeline"] == "v2"
    assert snapshot["snapshot_refreshed_at"] == "2026-06-07T00:05:00+00:00"
    assert snapshot["decision_validity_status"] == "stale"
    assert snapshot["requires_rerun_reason"] == "market_data_changed"
    assert snapshot["refreshed_without_analysis_rerun"] is True
    assert snapshot["data_schema_version"] == DATA_SCHEMA_VERSION
    assert snapshot["source_freshness"] == {"market_data": {"status": "fresh"}}
    assert snapshot["data_source_notes"] == ["來源已核對"]
    assert snapshot["deterministic_fallbacks"] == ["valuation_fallback"]
    assert snapshot["report_lint"] == {"status": "passed"}
    assert snapshot["content_credibility"] == {"status": "passed"}
    assert snapshot["report_conformance"] == {"status": "passed"}
    assert snapshot["rerun_context"]["analyses"] == {"16": "final recommendation"}
    assert snapshot["rerun_context"]["pipeline_label"] == "完整分析"
    assert snapshot["data_confidence_score"] == 90
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_data_snapshot_reproducibility_source_audit_fields_do_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "AUDIT",
            "pipeline_id": "v2",
            "data": {
                "ticker": "AUDIT",
                "source_audit": [
                    {
                        "provider": BrokenTruthText(" yfinance "),
                        "fetched_at": BrokenTruthText("2026-06-07T00:00:00+00:00"),
                    },
                    {
                        "provider": BrokenTruthText(" yfinance "),
                        "fetched_at": BrokenTruthText("2026-06-07T01:00:00+00:00"),
                    },
                ],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    packet = snapshot["reproducibility_packet"]

    assert packet["provider_list"] == ["yfinance"]
    assert packet["source_data_time"] == "2026-06-07T01:00:00+00:00"


def test_reproducibility_packet_uses_dict_native_mapping_reads():
    packet = report_reproducibility.build_reproducibility_packet(
        BrokenGetDict(
            {
                "ticker": "2330.TW",
                "prompt_version": "runtime-rules:test",
                "pipeline_id": "v2",
                "code_commit": "abc123",
                "metadata": BrokenGetDict({"model_id": "gemini-test-model"}),
                "data": BrokenGetDict(
                    {
                        "ticker": "DATA",
                        "pipeline_id": "v1",
                        "source_audit": [
                            BrokenGetDict(
                                {
                                    "provider": " yfinance ",
                                    "fetched_at": "2026-06-07T01:00:00+00:00",
                                }
                            )
                        ],
                    }
                ),
            }
        ),
        data_trust.unknown_data_trust(),
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert packet == {
        "ticker": "2330.TW",
        "data_snapshot_hash": "",
        "prompt_version": "runtime-rules:test",
        "prompt_fingerprint": "",
        "model_id": "gemini-test-model",
        "pipeline_id": "v2",
        "code_commit": "abc123",
        "code_dirty": None,
        "generated_at": "2026-06-07T00:10:00+00:00",
        "provider_list": ["yfinance"],
        "source_data_time": "2026-06-07T01:00:00+00:00",
    }


def test_data_snapshot_sanitizer_tolerates_malformed_string_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "SAFE",
            "pipeline_id": "v1",
            "data": {
                "ticker": "SAFE",
                "nested": {
                    BrokenString("bad key"): "SHOULD_NOT_APPEAR",
                    "bad_value": BrokenString("bad value"),
                    "safe_value": 123,
                },
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert "SHOULD_NOT_APPEAR" not in encoded
    assert snapshot["data"]["nested"]["bad_value"] == ""
    assert snapshot["data"]["nested"]["safe_value"] == 123


def test_data_snapshot_sanitizer_only_preserves_sha256_prompt_fingerprints():
    assert data_trust.sanitize_for_snapshot({"prompt_fingerprint": "A" * 64}) == {
        "prompt_fingerprint": "a" * 64,
    }
    assert data_trust.sanitize_for_snapshot({"prompt_fingerprint": "not-a-sha256"}) == {}


def test_data_snapshot_sanitizer_native_sequences_preserve_items():
    sanitized = data_trust.sanitize_for_snapshot(
        {
            "list_rows": BrokenNativeRowsList([{"provider": "yfinance"}]),
            "tuple_rows": BrokenNativeTuple(({"provider": "TWSE"},)),
        }
    )

    assert sanitized == {
        "list_rows": [{"provider": "yfinance"}],
        "tuple_rows": [{"provider": "TWSE"}],
    }


def test_data_snapshot_sanitizer_native_sequences_preserve_items_when_first_next_fails():
    sanitized = data_trust.sanitize_for_snapshot(
        {
            "list_rows": BrokenSnapshotFirstNextRows([{"provider": "TPEX"}]),
        }
    )

    assert sanitized == {
        "list_rows": [{"provider": "TPEX"}],
    }


def test_data_snapshot_sanitizer_native_mappings_preserve_items():
    sanitized = data_trust.sanitize_for_snapshot(
        BrokenNativeSnapshotMapping(
            {
                "provider": "yfinance",
                "nested": {"fetched_at": "2026-06-07T00:00:00+00:00"},
            }
        )
    )

    assert sanitized == {
        "provider": "yfinance",
        "nested": {"fetched_at": "2026-06-07T00:00:00+00:00"},
    }


def test_data_snapshot_sanitizer_native_mappings_preserve_items_when_items_iterable_fails():
    sanitized = data_trust.sanitize_for_snapshot(
        BrokenSnapshotItemsIterableMapping(
            {
                "provider": "TWSE",
                "nested": {"fetched_at": "2026-06-07T01:00:00+00:00"},
            }
        )
    )

    assert sanitized == {
        "provider": "TWSE",
        "nested": {"fetched_at": "2026-06-07T01:00:00+00:00"},
    }


def test_data_snapshot_saves_sanitized_rerun_context():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEST",
            "pipeline_id": "v2",
            "analyses": {
                11: "macro analysis",
                16: "final recommendation",
            },
            "structured_outputs": {
                16: {
                    "recommendation": {"建議": "持有"},
                    "retry_metadata": "SHOULD_NOT_APPEAR",
                }
            },
            "parsed": {"recommendation": {"建議": "持有"}},
            "prompt": "DO NOT SAVE PROMPT",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TEST",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        }
    )
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert snapshot["snapshot_schema_version"] == data_trust.DATA_SNAPSHOT_SCHEMA_VERSION
    assert snapshot["rerun_context"]["analyses"]["11"] == "macro analysis"
    assert snapshot["rerun_context"]["structured_outputs"]["16"]["recommendation"]["建議"] == "持有"
    assert "DO NOT SAVE PROMPT" not in encoded
    assert "SHOULD_NOT_APPEAR" not in encoded


def test_data_snapshot_rerun_context_text_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEXT",
            "pipeline_id": "v2",
            "analyses": {11: BrokenTruthText("macro analysis")},
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TEXT",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["rerun_context"]["analyses"]["11"] == "macro analysis"


def test_data_snapshot_rerun_context_agent_keys_use_safe_text_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TEXT",
            "pipeline_id": "v2",
            "analyses": {
                BrokenString("bad agent key"): "SHOULD_NOT_APPEAR",
                11: "macro analysis",
            },
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TEXT",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["rerun_context"]["analyses"] == {"11": "macro analysis"}
    assert "SHOULD_NOT_APPEAR" not in json.dumps(snapshot, ensure_ascii=False)


def test_data_snapshot_adds_confidence_guardrail_and_repro_packet(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v2",
        "prompt_version": "runtime-rules:test",
        "prompt_fingerprint": "a" * 64,
        "model_id": "gemini-test-model",
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "12個月": "NT$1,200",
                "信心": "8/10",
            },
            "price_targets": {
                "熊市情境": 900,
                "基本情境": 1100,
                "牛市情境": 1300,
            },
        },
        "structured_outputs": {
            16: {
                "recommendation": {
                    "target_price": "NT$1,200",
                }
            }
        },
        "data": {
            "data_schema_version": DATA_SCHEMA_VERSION,
            "ticker": "2330.TW",
            "company_name": "台積電",
            "source_freshness": {},
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "yfinance",
                    "status": "success",
                    "fetched_at": "2026-06-07T00:00:00+00:00",
                    "record_count": 1,
                },
                {
                    "source": "financial_statements",
                    "provider": "TWSE",
                    "status": "error",
                    "fetched_at": "2026-06-06T00:00:00+00:00",
                    "record_count": 0,
                },
            ],
            "data_trust": {
                "status": "error",
                "critical_failures": ["financial_statements"],
                "stale_sources": [],
                "last_market_data_at": "2026-06-07T00:00:00+00:00",
                "notes": ["核心財報來源異常。"],
                "score": 20,
            },
        },
    }

    snapshot = data_trust.build_data_snapshot(
        context,
        pipeline_id="v2",
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_confidence_score"] == 20
    guardrail = snapshot["conclusion_guardrails"]["explicit_target_price"]
    assert guardrail["allowed"] is False
    assert guardrail["min_data_confidence_score"] == 60
    assert "parsed.recommendation.12個月" in guardrail["detected_fields"]
    assert "parsed.price_targets.基本情境" in guardrail["detected_fields"]
    assert "structured_outputs.16.recommendation.target_price" in guardrail["detected_fields"]
    packet = snapshot["reproducibility_packet"]
    assert packet["ticker"] == "2330.TW"
    assert packet["data_snapshot_hash"] == snapshot["snapshot_hash"]
    assert packet["prompt_version"] == "runtime-rules:test"
    assert packet["prompt_fingerprint"] == "a" * 64
    assert packet["model_id"] == "gemini-test-model"
    assert packet["pipeline_id"] == "v2"
    assert packet["code_commit"] == "abc123"
    assert packet["generated_at"] == "2026-06-07T00:10:00+00:00"
    assert packet["provider_list"] == ["yfinance", "TWSE"]
    assert packet["source_data_time"] == "2026-06-07T00:00:00+00:00"
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_reproducibility_packet_preserves_dirty_code_state():
    packet = report_reproducibility.build_reproducibility_packet(
        {
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "code_commit": "abc123",
            "code_dirty": True,
            "data": {"ticker": "2330.TW", "source_audit": []},
        },
        {},
        "2026-06-07T00:10:00+00:00",
    )

    assert packet["code_commit"] == "abc123"
    assert packet["code_dirty"] is True


def test_data_snapshot_target_price_detector_tolerates_malformed_text_conversion():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TARGET",
            "pipeline_id": "v2",
            "parsed": {
                "recommendation": {
                    BrokenString("bad target key"): "SHOULD_NOT_APPEAR",
                    "target_price": BrokenString("bad target value"),
                    "safe_target_price": "NT$120",
                }
            },
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TARGET",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    detected_fields = snapshot["conclusion_guardrails"]["explicit_target_price"]["detected_fields"]

    assert detected_fields == ["parsed.recommendation.safe_target_price"]
    assert "SHOULD_NOT_APPEAR" not in json.dumps(snapshot, ensure_ascii=False)


def test_explicit_target_price_detector_uses_native_root_mapping_reads():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        BrokenGetDict(
            {
                "parsed": {"recommendation": {"target_price": "NT$120"}},
                "structured_outputs": {"forecast": {"price_targets": "NT$130"}},
            }
        )
    )

    assert fields == [
        "parsed.recommendation.target_price",
        "structured_outputs.forecast.price_targets",
    ]


def test_explicit_target_price_detector_preserves_valid_list_items_before_iterator_failure():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetRows()}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_native_lists_preserve_valid_items():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetNativeRows([{"target_price": "NT$120"}])}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_lists_survive_first_next_iterator_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": {"recommendation_targets": BrokenTargetFirstNextRows([{"target_price": "NT$120"}])}}
    )

    assert fields == ["parsed.recommendation_targets.0.target_price"]


def test_explicit_target_price_detector_preserves_valid_mapping_items_before_iterator_failure():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetMapping()}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_native_mappings_preserve_valid_items():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetNativeMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_mappings_survive_first_next_iterator_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetFirstNextMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_mappings_survive_items_iterable_failures():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {"parsed": BrokenTargetItemsIterableMapping({"recommendation": {"target_price": "NT$120"}})}
    )

    assert fields == ["parsed.recommendation.target_price"]


def test_explicit_target_price_detector_ignores_non_finite_numeric_targets():
    fields = report_reproducibility.detect_explicit_target_price_fields(
        {
            "parsed": {
                "recommendation": {
                    "nan_target_price": float("nan"),
                    "inf_target_price": float("inf"),
                    "negative_inf_target_price": float("-inf"),
                    "valid_target_price": 120.5,
                }
            }
        }
    )

    assert fields == ["parsed.recommendation.valid_target_price"]


def test_data_snapshot_existing_data_trust_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TRUST",
                "source_audit": [],
                "data_trust": BrokenTruthDict(
                    {
                        "status": "fresh",
                        "score": 90,
                        "reason_codes": ["manual_reason"],
                        "notes": ["manual trust snapshot"],
                    }
                ),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["reason_codes"] == ["manual_reason"]
    assert snapshot["data_confidence_score"] == 90


def test_data_snapshot_existing_data_trust_score_conversion_failure_uses_status_score():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "TRUST",
            "pipeline_id": "v2",
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "TRUST",
                "source_audit": [],
                "data_trust": {
                    "status": "fresh",
                    "score": BrokenFloatScore(),
                    "reason_codes": [],
                    "notes": ["manual trust snapshot"],
                },
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["data_trust"]["status"] == "fresh"
    assert snapshot["data_trust"]["score"] == 95
    assert snapshot["data_confidence_score"] == 95


def test_data_snapshot_refresh_flag_does_not_depend_on_truthiness():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "REFRESH",
            "pipeline_id": "v2",
            "refreshed_without_analysis_rerun": BrokenTruthBool(),
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "REFRESH",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    assert snapshot["refreshed_without_analysis_rerun"] is False


def test_low_confidence_snapshot_allows_ranges_or_insufficient_data():
    snapshot = data_trust.build_data_snapshot(
        {
            "ticker": "RANGE",
            "pipeline_id": "v2",
            "parsed": {
                "recommendation": {
                    "12個月": "NT$90 至 NT$110",
                    "信心": "3/10",
                },
                "price_targets": {"基本情境": "資料不足，僅提供 NT$90-110 區間"},
            },
            "data": {
                "data_schema_version": DATA_SCHEMA_VERSION,
                "ticker": "RANGE",
                "source_audit": [],
                "data_trust": data_trust.unknown_data_trust(),
            },
        },
        generated_at="2026-06-07T00:10:00+00:00",
    )

    guardrail = snapshot["conclusion_guardrails"]["explicit_target_price"]
    assert snapshot["data_confidence_score"] == 35
    assert guardrail["allowed"] is False
    assert guardrail["detected_fields"] == []
    assert "資料不足" in guardrail["message"]
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


def test_data_snapshot_accepts_legacy_v2_schema():
    snapshot = {
        "snapshot_schema_version": 2,
        "ticker": "TEST",
        "pipeline": "v1",
        "generated_at": "2026-06-07T00:00:00+00:00",
        "data_schema_version": DATA_SCHEMA_VERSION,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": data_trust.unknown_data_trust(),
        "data": {"ticker": "TEST"},
    }

    assert data_trust.validate_data_snapshot(snapshot)["valid"] is True


def test_data_snapshot_schema_validation_and_truncation():
    audit = [
        data_trust.build_source_audit_entry(
            "market_data",
            "fake",
            "success",
            record_count=2,
            message="kept in full audit",
        )
    ]
    context = {
        "ticker": "BIG",
        "pipeline_id": "v2",
        "data": {
            "data_schema_version": DATA_SCHEMA_VERSION,
            "ticker": "BIG",
            "company_name": "Big Fixture",
            "current_price": 100,
            "years": ["2024", "2025"],
            "revenue_history": [10, 12],
            "net_income_history": [2, 3],
            "source_freshness": {
                "market_data": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
                "financial_statements": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
            },
            "source_audit": audit,
            "data_trust": {
                "status": "fresh",
                "critical_failures": [],
                "stale_sources": [],
                "last_market_data_at": "2026-06-07T00:00:00+00:00",
                "notes": ["fixture"],
            },
            "recent_catalysts": [{"title": "x" * 180} for _ in range(20)],
            "peer_discovery_results": [{"title": "y" * 180} for _ in range(20)],
            "dynamic_peer_metrics": [{"name": "z" * 180} for _ in range(20)],
            "internal_retry_metadata": "SHOULD_NOT_APPEAR",
        },
    }

    snapshot = data_trust.build_data_snapshot(context, max_bytes=1600)
    encoded = json.dumps(snapshot, ensure_ascii=False)

    assert snapshot["snapshot_schema_version"] == data_trust.DATA_SNAPSHOT_SCHEMA_VERSION
    assert snapshot["snapshot_truncated"] is True
    assert snapshot["snapshot_size_bytes"] == data_trust.snapshot_size_bytes(snapshot)
    assert snapshot["snapshot_hash"] == data_trust.snapshot_content_hash(snapshot)
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True
    assert snapshot["snapshot_omitted_sections"]
    assert snapshot["source_audit"] == audit
    assert snapshot["data_trust"]["status"] == "fresh"
    assert "SHOULD_NOT_APPEAR" not in encoded
    assert data_trust.validate_data_snapshot(snapshot)["valid"] is True


def test_data_snapshot_schema_validation_rejects_old_shape():
    validation = data_trust.validate_data_snapshot({"ticker": "OLD"})

    assert validation["valid"] is False
    assert "unsupported snapshot_schema_version" in validation["errors"]
