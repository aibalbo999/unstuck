import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import data_trust  # noqa: E402
import data_fetch.audit_helpers as audit_helpers  # noqa: E402
from data_fetch.constants import DATA_SCHEMA_VERSION  # noqa: E402
from fixtures.data_payloads import fresh_audited_payload, provider_sla_alert, stale_audited_payload  # noqa: E402


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


def test_data_snapshot_adds_confidence_guardrail_and_repro_packet(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v2",
        "prompt_version": "runtime-rules:test",
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
    assert packet["model_id"] == "gemini-test-model"
    assert packet["pipeline_id"] == "v2"
    assert packet["code_commit"] == "abc123"
    assert packet["generated_at"] == "2026-06-07T00:10:00+00:00"
    assert packet["provider_list"] == ["yfinance", "TWSE"]
    assert packet["source_data_time"] == "2026-06-07T00:00:00+00:00"
    assert data_trust.verify_data_snapshot_integrity(snapshot)["valid"] is True


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
