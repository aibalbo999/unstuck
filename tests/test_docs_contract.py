import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_operator_docs_and_demo_script_are_discoverable():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for relative in [
        "docs/architecture.md",
        "docs/operator-guide.md",
        "docs/api.md",
        "scripts/demo_report.sh",
    ]:
        assert (ROOT / relative).exists(), relative
        assert relative in readme


def test_design_system_contract_is_discoverable_and_operational():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    checkpoints = (ROOT / "docs" / "frontend-design-checkpoints.md").read_text(encoding="utf-8")
    base_css = (ROOT / "backend" / "static" / "styles" / "base.css").read_text(encoding="utf-8")

    assert "DESIGN.md" in readme
    assert "DESIGN.md" in checkpoints
    for heading in ["## 受眾與工作流", "## 字體與層級", "## 色彩與資料狀態", "## 版面與密度", "## 可及性與互動", "## 驗證門檻"]:
        assert heading in design
    assert "Inter" in design and "Outfit" in design
    assert "44px" in design
    assert "prefers-reduced-motion" in design
    for token in ["--bg-dark", "--text-primary", "--text-secondary", "--accent", "--primary-action"]:
        assert token in base_css


def test_architecture_doc_names_runtime_boundaries():
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

    assert "AnalysisPipelineRunner" in architecture
    assert "StockDataService" in architecture
    assert "decision_freshness" in architecture
    assert "mutation token" in architecture


def test_report_quality_docs_cover_snapshot_integrity_contract():
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    checkpoints = (ROOT / "docs" / "frontend-design-checkpoints.md").read_text(encoding="utf-8")

    for document in [api_reference, operator_guide, architecture]:
        assert "snapshot_integrity" in document
        assert "verified" in document
        assert "unverified" in document
        assert "invalid" in document
    for document in [api_reference, operator_guide]:
        assert "Report preview reading boundaries include snapshot integrity mismatch details" in document
        assert "Report preview reading boundaries derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes" in document
        assert "Report preview reading boundaries prefer hash mismatch details over default generic snapshot integrity errors" in document
        assert "Report preview reading boundaries treat `snapshot_integrity.valid=false` as blocked" in document
        assert "Report preview reading boundaries remove default generic snapshot integrity blocker text" in document
        assert "Report preview reading boundaries deduplicate repeated snapshot integrity error details" in document
        assert "Report reading notice quality gate record detection accepts mapping-safe gate payloads" in document
        assert "Report reading notice snapshot integrity checks treat `valid=false` as blocked" in document
        assert "Report reading notice snapshot integrity checks let invalid `data.snapshot_integrity` override a conflicting verified top-level record" in document
        assert "Report reading notice snapshot integrity checks preserve the most specific invalid snapshot integrity detail" in document
        assert "Report reading notice snapshot integrity checks accept mapping-safe snapshot integrity payloads" in document
        assert "Report reading notice snapshot integrity checks downgrade recorded non-verified snapshots to warning" in document
        assert "Report reading notice snapshot integrity details deduplicate repeated error entries" in document
        assert "Report reading notice snapshot integrity details derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes" in document
        assert "Report reading notice snapshot integrity details prefer hash mismatch details over default generic snapshot integrity errors" in document
        assert "Report reading notice snapshot integrity details remove default generic blocker text" in document
        assert "Report view and HTML download paths re-check the current `.data.json` snapshot integrity" in document
        assert "Report Markdown download paths re-check the current `.data.json` snapshot integrity" in document
        assert "Report artifact view and download paths treat malformed or non-object `.data.json` snapshots as blocked" in document
        assert "Report artifact view and download paths treat missing `.data.json` snapshots as warning" in document
        assert "Report artifact view and download paths honor invalid `snapshot_integrity` recorded inside `.data.json`" in document
        assert "Report artifact view and download paths also honor invalid `data.snapshot_integrity` recorded inside `.data.json`" in document
        assert "Report artifact view and download paths let any recorded invalid snapshot integrity override a conflicting verified record" in document
        assert "Report artifact view and download paths preserve the most specific invalid snapshot integrity detail" in document
        assert "Report artifact view and download paths treat default generic snapshot integrity blocker text as less specific" in document
        assert "Report artifact view and download paths derive a `snapshot_hash mismatch` detail from recorded invalid snapshot integrity hashes" in document
        assert "Report artifact view and download paths prefer recorded hash mismatch details over default generic snapshot integrity errors" in document
        assert "Report artifact view and download paths remove default generic snapshot integrity errors when the same recorded error list also contains specific details" in document
        assert "Report artifact view and download paths deduplicate recorded snapshot integrity error details" in document
    assert "test_report_reading_boundary_downgrades_unverified_and_blocks_invalid_snapshots" in checkpoints


def test_report_artifact_docs_cover_partitioned_maintenance_contract():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

    for document in [readme, api_reference, operator_guide, architecture]:
        assert "YYYY-MM/TICKER" in document
        assert "分層" in document
    assert "verify-snapshots" in readme
    assert "storage-summary" in readme
    assert "遞迴" in api_reference
    assert "遞迴" in operator_guide


def test_default_server_binding_is_localhost_only():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    launcher = (ROOT / "start_mac.command").read_text(encoding="utf-8")

    assert 'SERVER_HOST="127.0.0.1"' in launcher
    assert 'LAN_ACCESS="${LAN_ACCESS:-0}"' in launcher
    assert '--host "$SERVER_HOST"' in launcher
    assert "--host 127.0.0.1" in readme
    assert "LAN_ACCESS=1" in readme
    assert "--host 0.0.0.0" not in readme


def test_openapi_contract_covers_runtime_surface_and_mutation_security():
    import api

    schema = api.app.openapi()
    paths = schema["paths"]
    expected = {
        "/healthz": {"get"},
        "/readyz": {"get"},
        "/api/client-config": {"get"},
        "/api/stocks/{ticker}/snapshot": {"get"},
        "/api/analysis-jobs": {"post"},
        "/api/analysis-jobs/{job_id}": {"get"},
        "/api/analysis-jobs/{job_id}/events": {"get"},
        "/api/analysis-jobs/{job_id}/cancel": {"post"},
        "/api/report/{filename}/refresh/data": {"post"},
        "/api/report/{filename}/rerun": {"post"},
        "/api/reports": {"get"},
        "/api/reports/{filename}": {"delete"},
        "/api/watchlist": {"get", "post"},
        "/api/watchlist/symbols": {"get"},
        "/api/watchlist/import": {"post"},
        "/api/watchlist/daily-dashboard": {"get"},
        "/api/watchlist/portfolio/risk": {"post"},
        "/api/watchlist/run": {"post"},
        "/api/watchlist/{ticker}": {"delete"},
        "/api/maintenance/storage-summary": {"get"},
        "/api/maintenance/sqlite-maintenance": {"post"},
        "/api/observability/dashboard": {"get"},
        "/api/ops/dashboard": {"get"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods <= set(paths[path])

    analysis_job_schema = schema["components"]["schemas"]["AnalysisJobCreateRequest"]
    assert {"ticker", "pipeline_id", "force", "resume"} <= set(analysis_job_schema["properties"])

    operation_ids = [
        operation["operationId"]
        for operations in paths.values()
        for method, operation in operations.items()
        if method in {"get", "post", "delete", "put", "patch"}
    ]
    assert len(operation_ids) == len(set(operation_ids))

    security_scheme = schema["components"]["securitySchemes"]["MutationToken"]
    assert security_scheme == {"type": "apiKey", "in": "header", "name": "X-Mutation-Token"}
    for path, operations in paths.items():
        for method, operation in operations.items():
            if method in {"post", "delete", "put", "patch"} or path == "/api/maintenance/storage-summary":
                assert {"MutationToken": []} in operation.get("security", []), f"{method.upper()} {path}"


def test_analysis_job_docs_use_canonical_pipeline_ids():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    for document in [readme, api_reference]:
        assert '"pipeline_id":"v1"' in document
        assert '"pipeline_id":"mode_a"' not in document

    assert "`v1` / `v2` / `v3` / `v4`" in contract


def test_pipeline_mode_contract_documents_frontend_backend_drift_guard():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 前後端模式漂移閘門" in contract
    assert "tests/test_pipeline_mode_metadata_sync.py" in contract
    assert "這是 drift guard" in contract
    assert "尚未設計 API 或 build-time catalog" not in contract
    assert "仍需設計 API 或 build-time catalog" in contract


def test_stock_snapshot_endpoint_is_documented_for_consumer_stock_page():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")

    assert "/api/stocks/{ticker}/snapshot" in api_reference
    assert "股票快照" in api_reference
    assert "股票快照" in readme


def test_pipeline_mode_contract_has_decision_cues_for_mode_selection():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 模式選擇速記" in contract
    assert "先問：我現在要做哪種決策？" in contract
    for expected in [
        "`v1`：要不要納入長線研究清單",
        "`v2`：現在要進場、續抱、減碼或等待",
        "`v3`：敘事是否過熱、是否需要避險或反向觀察",
        "`v4`：未來 1-2 週是否有可執行事件窗口",
        "`both`：同一檔股票需要三視角交叉檢查",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_selection_decision_tree():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 模式選擇決策樹" in contract
    for expected in [
        "如果需要三視角交叉檢查，選 `both`",
        "如果核心問題是 1-2 週事件窗口，選 `v4`",
        "如果核心問題是敘事過熱、泡沫或避險，選 `v3`",
        "如果核心問題是今天或本週要不要交易，選 `v2`",
        "如果核心問題是是否值得長線研究，選 `v1`",
        "若仍不確定，先選 `v1` 建立基本面基準",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_quick_learning_card():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣速學卡" in contract
    assert "先問三題" in contract
    for expected in [
        "有沒有改 `[投資建議]`、prompt、parser regex、`content_credibility` 或 template decision heading",
        "有沒有改完整報告正文、Markdown/HTML 標題或 template 顯示文案",
        "是不是只改前端 filter、preview、compare 或 rerun CTA",
        "高顯著性機器契約通道",
        "混合層報告呈現通道",
        "低顯著性顯示層通道",
        "三道安檢通道",
        "不新增自動選測腳本",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_operation_flow():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣操作流程" in contract
    for expected in [
        "四步演算法",
        "步驟 1：定位改動層級",
        "步驟 2：選擇安檢通道",
        "步驟 3：執行最小測試命令",
        "步驟 4：記錄判讀與限制",
        "三個操作者情境",
        "情境 A：調整 parser、prompt、content credibility 或 decision heading",
        "情境 B：改完整報告模板或正文標題",
        "情境 C：只改前端顯示文案",
        "三條捷思規則",
        "`[` 或 `]` 出現契約詞就走高顯著性",
        "使用者會直接閱讀的報告正文先走混合層",
        "只在前端看得到且不被 parser 讀取才走低顯著性",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_maps_quality_signals_to_ci_lanes():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## Quality Signal 與 Repair Queue CI Lane Map" in contract
    for expected in [
        "content_credibility",
        "report_conformance",
        "evidence_exit_gate",
        "data_trust",
        "decision_freshness",
        "report_quality_repair_queue",
        "provider_impact",
        "outcome_calibration",
        "model_route_budget",
        "notification_delivery",
        "daily_decision_queue",
        "修改類型",
        "測試 lane",
        "tests/test_content_credibility.py",
        "tests/test_report_quality_repair_queue.py",
        "tests/test_provider_impact.py",
        "tests/test_outcome_calibration.py",
        "tests/test_model_route_budget.py",
        "tests/test_free_notification_plan.py",
        "tests/test_daily_decision_queue.py",
        "tests/test_runtime_observability.py",
        "tests/test_daily_decision_dashboard.py",
        "tests/test_runtime_paths.py",
        "tests/test_report_artifacts.py",
        "不得使用 `backend/cache/decision_tracking.sqlite3` 驗證 current state",
        "不得手拼 `backend/output/<filename>`",
    ]:
        assert expected in contract


def test_daily_decision_queue_docs_cover_report_repair_boundaries():
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    for document in (api_reference, operator_guide, contract):
        assert "blocks_auto_rerun" in document
        assert "reason_codes" in document
        assert "Daily decision queue display limits use integer-safe conversion" in document
        assert "Daily decision queue integer conversions ignore malformed conversion failures" in document
        assert "Daily decision queue integer conversions treat boolean values as malformed" in document
        assert "Daily decision queue integer conversions treat fractional float values as malformed" in document
        assert "Daily decision queue integer conversions treat fractional exact numeric values as malformed" in document
        assert "Shared integer conversion treats boolean values as malformed numeric input" in document
        assert "Shared integer conversion treats fractional float values as malformed numeric input" in document
        assert "Shared integer conversion treats fractional exact numeric values as malformed numeric input" in document
        assert "Shared text conversion treats boolean values as malformed text input" in document
        assert "Shared text conversion treats binary values as malformed text input" in document
        assert "Shared text conversion treats memory view values as malformed text input" in document
        assert "Report quality repair queue identity fields use shared text conversion" in document
        assert "Provider impact identity fields use shared text conversion" in document
        assert "Data trust scoring audit source names use shared text conversion" in document
        assert "Data trust reproducibility packet identity fields use shared text conversion" in document
        assert "Daily decision queue route warning projection suppresses `slow_route` latency warnings" in document
        assert "Daily decision queue notification delivery summary maps use mapping-safe conversion" in document
        assert "Daily decision queue notification delivery count fields use integer-safe conversion" in document
        assert "Daily decision queue notification delivery count fields and count maps use strict count conversion" in document
        assert "Daily decision queue notification delivery health fields use string-safe conversion" in document
        assert "Daily decision queue notification delivery nested count maps use mapping-safe conversion" in document
        assert "Daily decision queue notification delivery channel count maps use dict-safe conversion" in document
        assert "Daily decision queue notification delivery failure reason maps use truthiness-safe detail rendering" in document
        assert "Daily decision queue notification delivery failure reason item access failures fall back to native dict items" in document
        assert "Daily decision queue notification delivery failure reason count values fall back to integer-safe rendering" in document
        assert "Daily decision queue notification delivery failure reason unrenderable counts are omitted from reason detail" in document
        assert "Daily decision queue notification delivery failure reason non-positive counts are omitted from reason detail" in document
        assert "Daily decision queue notification delivery failure reason boolean counts are omitted from reason detail" in document
        assert "Daily decision queue notification delivery failure reason fractional counts are omitted from reason detail" in document
        assert "Daily decision queue notification delivery failure reason malformed keys are omitted from reason detail" in document
        assert "Daily decision queue notification delivery failure reason raw keys are omitted from reason detail" in document
        assert "Daily decision queue notification delivery failure reason duplicate buckets are aggregated in reason detail" in document
        assert "Daily decision queue notification delivery failure reason partial item failures fall back to native dict items" in document
        assert "Daily decision queue notification delivery attention context iterator failures fall back to native sequence items" in document
        assert "Daily decision queue notification delivery attention context partial iterator failures fall back to native sequence items" in document
        assert "Daily decision queue notification delivery attention context tuple payloads are preserved" in document
        assert "Daily decision queue notification delivery attention context mapping rows normalize to plain dicts" in document
        assert "Daily decision queue notification delivery attention context dict subclasses normalize to plain dicts" in document
        assert "Daily decision queue notification delivery attention context nested mappings normalize recursively to plain dicts" in document
        assert "Daily decision queue notification delivery attention context nested mapping item failures fall back to native dict items" in document
        assert "Daily decision queue notification delivery attention context nested sequence iterator failures fall back to native sequence items" in document
        assert "Shared sequence conversion treats lookup iterator failures as native-sequence fallbacks" in document
        assert "Shared sequence conversion treats lookup iterator creation failures as native-sequence fallbacks" in document
        assert "Daily decision queue report repair collections use iterator-safe dict-list conversion" in document
        assert "Daily decision queue report repair partial iterator failures fall back to native dict-list items" in document
        assert "Daily decision queue report repair reason code partial iterator failures fall back to native text-list items" in document
        assert "Shared mapping dict conversion normalizes dict subclasses to plain dict copies" in document
        assert "Shared mapping dict conversion uses mapping-item traversal when mapping key iteration fails" in document
        assert "Shared mapping dict conversion uses Mapping traversal when `.items()` lookup fails" in document
        assert "Shared mapping dict conversion uses Mapping traversal when `.items()` iterables fail lookup" in document
        assert "Shared mapping dict conversion skips lookup item failures during Mapping traversal" in document
        assert "Shared mapping dict conversion skips lookup key hash failures during Mapping traversal" in document
        assert "Shared mapping dict conversion preserves safely empty Mapping wrappers as plain empty dicts" in document
        assert "Shared mapping item conversion preserves partial dict-subclass items when native fallback is empty" in document
        assert "Shared mapping item conversion skips lookup item unpack failures" in document
        assert "Shared mapping item conversion skips lookup key hash failures" in document
        assert "Shared mapping item conversion skips string-like malformed item pairs" in document
        assert "Shared mapping item conversion skips unhashable malformed item keys" in document
        assert "Daily decision queue ops payloads use type-safe fallback" in document
        assert "Daily decision queue free-mode violation lists use string-safe conversion" in document
        assert "Daily decision queue free-mode can-run flags use bool-safe fallback" in document
        assert "Daily decision queue explicit backtest collections use iterator-safe dict-list conversion" in document
        assert "Daily decision queue backtest evaluation `details` use iterator-safe dict-list conversion" in document
        assert "Daily decision queue computed backtest report rows use iterator-safe dict-list conversion" in document
        assert "Daily decision queue computed backtest report artifact fields use string-safe conversion" in document
        assert "Daily decision queue computed backtest report date fields use string- and float-safe conversion" in document
        assert "Daily decision queue backtest due action text fields use string-safe conversion" in document
        assert "Daily decision queue rerun report collections use iterator-safe dict-list conversion" in document
        assert "Daily decision queue watchlist collections use iterator-safe dict-list conversion" in document
        assert "Daily decision queue screener candidate collections use iterator-safe dict-list conversion" in document
        assert "Daily decision queue screener candidate action text fields use string-safe conversion" in document
        assert "Daily decision queue report repair action `title` fields use string-safe conversion" in document
        assert "Daily decision queue report repair action `detail` fields use string-safe conversion" in document
        assert "Daily decision queue report repair `filename` and `report_filename` aliases use string-safe selection" in document
        assert "Daily decision queue report repair action `recommended_action` fields use string-safe conversion" in document
        assert "Daily decision queue report repair action `ticker` fields use string-safe conversion" in document
        assert "Daily decision queue report repair action `pipeline_id` fields use string-safe conversion" in document
        assert "Daily decision queue report repair action `priority_score` fields use integer-safe conversion" in document
        assert "Daily decision queue report repair action `severity` fields use string-safe conversion" in document
        assert "Daily decision queue report repair action `action_label` fields use string-safe conversion" in document
        assert "Daily decision queue rerun report action `ticker` fields use string-safe conversion" in document
        assert "Daily decision queue rerun report action `pipeline_id` fields use string-safe conversion" in document
        assert "Daily decision queue rerun report `filename` and `report_filename` aliases use string-safe selection" in document
        assert "Daily decision queue rerun report action `detail` fields use string-safe fallback" in document
        assert "Daily decision queue report key `ticker` fields use string-safe conversion" in document
        assert "Daily decision queue report key `pipeline_id` fields use string-safe conversion" in document
        assert "Daily decision dashboard report envelopes use mapping-safe conversion" in document
        assert "Daily decision dashboard report row collections use iterator-safe dict-list conversion" in document
        assert "Daily decision dashboard rerun report `filename` and `report_filename` aliases use string-safe selection" in document
        assert "Daily decision dashboard rerun reason fields use string-safe fallback" in document
        assert "Daily decision dashboard rerun freshness flags use bool-safe fallback" in document
        assert "Daily decision dashboard performance envelopes use mapping-safe conversion" in document
        assert "Daily decision dashboard watchlist envelopes use mapping-safe conversion" in document
        assert "Daily decision dashboard watchlist `decision_priority` fields use string-safe conversion" in document
        assert "Daily decision dashboard screener envelopes use mapping-safe conversion" in document
        assert "Daily decision dashboard screener quality-funnel maps use mapping-safe conversion" in document
        assert "Daily decision dashboard screener quality outcome fields use string-safe conversion" in document
        assert "Daily decision dashboard screener candidate text fields use string-safe conversion" in document
        assert "Daily decision dashboard screener score fields use conversion-safe fallback before top-candidate payload output" in document
        assert "Daily decision dashboard screener score fields use conversion-safe fallback" in document
        assert "Daily decision dashboard free-mode envelopes use mapping-safe conversion" in document
        assert "Daily decision dashboard free-mode violation lists use string-safe conversion" in document
        assert "Daily decision dashboard free-mode boolean flags use bool-safe fallback" in document
        assert "Daily decision dashboard decision freshness maps use mapping-safe conversion" in document
        assert "Daily decision queue provider impact ledger objects use type-safe fallback" in document
        assert "Daily decision queue provider impact ledger maps use mapping-safe conversion" in document
        assert "Daily decision queue provider impact summary maps use mapping-safe conversion" in document
        assert "Daily decision queue provider impact ledger `items` use iterator-safe dict-list conversion" in document
        assert "Daily decision queue provider impact `impacts[].message` fields use string-safe conversion" in document
        assert "Daily decision queue provider impact `filename` and `report_filename` aliases use string-safe selection" in document
        assert "Daily decision queue provider impact `blocks_auto_rerun` fields use bool-safe conversion" in document
        assert "Daily decision queue provider impact `recommended_action` fields use string-safe fallback" in document
        assert "Daily decision queue provider impact `ticker` fields use string-safe conversion" in document
        assert "Daily decision queue provider impact `pipeline_id` fields use string-safe conversion" in document
        assert "report repair" in document or "報告修復" in document


def test_notification_plan_docs_cover_report_repair_reason_codes_context():
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")
    expected = "`notification_plan.messages` and `delivery_outbox` preserve `reason_codes`"
    detail_expected = "`notification_plan.delivery_outbox` also preserves report repair action `detail`"

    assert expected in api_reference
    assert expected in operator_guide
    assert expected in contract
    assert detail_expected in api_reference
    assert detail_expected in operator_guide
    assert detail_expected in contract


def test_daily_dashboard_docs_cover_notification_delivery_outbox_contract():
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    env_expected = "Notification plan external channel env checks require concrete nonblank string values"
    env_container_expected = "Notification plan external channel env containers use mapping-safe conversion"

    for expected in ["delivery_outbox", "delivery_summary", "delivery_key", "message_id", "dedupe_key"]:
        assert expected in api_reference

    for expected in ["delivery_outbox", "delivery_status", "attempt_count", "channels[].missing_env"]:
        assert expected in operator_guide
    assert env_expected in api_reference
    assert env_expected in operator_guide

    for expected in ["side-effect-free", "enabled channels", "sender idempotency"]:
        assert expected in architecture
    assert env_container_expected in api_reference
    assert env_container_expected in operator_guide


def test_runtime_docs_cover_notification_delivery_audit_store():
    runtime_map = (ROOT / "docs" / "system-architecture-map.md").read_text(encoding="utf-8")
    api_reference = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    operator_guide = (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")

    for expected in ["notification_delivery_audit.py", "notification_delivery_audit", "operational.sqlite3"]:
        assert expected in runtime_map

    for expected in [
        "notification_delivery_audit",
        "operational.sqlite3",
        "attempt count",
        "response id",
        "reconcile_outbox_with_audit()",
        "already_sent = true",
        "should_send = false",
        "skip_reason = retry_wait",
        "retry_wait_seconds",
        "next_retry_at",
        "retry_exhausted = true",
        "skip_reason = retry_exhausted",
        "retry_exhausted_count",
        "attention_contexts",
        "The item preserves `failure_reason_counts` and `attention_contexts`",
        "render the same attention context summary in action detail",
        "maintenance chip reuses the daily queue attention context summary",
        "includes a human-readable original source label plus the raw source key",
        "Operator action and watchlist daily board `來源` labels use the same helper",
        "covers the no-action `monitor` fallback as `監控`",
        "`source_labels` for human-readable rendering while preserving raw source keys",
        "`source_texts` for label-plus-raw-key display while preserving raw source keys",
        "Notification message and `delivery_outbox` entries carry `source_label` and `source_text`",
        "The audit context snapshot also derives `source_label` and `source_text` from raw `source`",
        "Audit context snapshots ignore blank `source_label` and `source_text` before deriving fallback labels",
        "Audit context source display presence checks use string-safe text conversion before deriving fallback labels",
        "Audit context source key normalization uses string-safe text conversion before deriving fallback labels",
        "Audit context snapshot presence checks tolerate malformed equality comparisons before preserving optional outbox metadata",
        "Notification delivery attempt result fields use string-safe status, error, and response id conversion",
        "Notification delivery outbox identity fields use string-safe required text extraction",
        "Notification delivery audit persistence evaluates mapping outbox entries before identity and context extraction",
        "Notification delivery audit persistence rejects malformed mapping outbox entries with required identity errors",
        "Notification delivery audit listing uses string-safe integer limit conversion",
        "Notification delivery audit listing clamps explicit zero limits before querying records",
        "Notification delivery audit row timestamps use finite-float conversion before record output",
        "Notification delivery audit row text fields use string-safe conversion before record output",
        "Notification delivery audit row statuses are normalized before record output",
        "Notification delivery audit row delivery keys are stripped before record output",
        "Notification delivery audit row identity fields are stripped before record output",
        "Notification delivery audit text conversion decodes byte-like values before record output",
        "Notification delivery audit row attempt counts use string-safe integer conversion before record output",
        "Notification delivery audit context JSON parsing avoids truthiness checks before loading persisted context",
        "Notification delivery audit context JSON parsing uses string-safe conversion before loading persisted context",
        "Notification delivery audit context JSON parsing drops non-finite numeric values before record output",
        "Notification delivery reconcile preflight uses string-safe delivery key lookup",
        "Notification delivery reconcile preflight matches byte-like stored delivery keys before sending",
        "Notification delivery reconcile preflight matches whitespace-padded stored delivery keys before sending",
        "Notification delivery reconcile preflight matches control-whitespace-padded stored delivery keys before sending",
        "Notification delivery record upsert matches byte-like stored delivery keys before inserting",
        "Notification delivery record upsert matches whitespace-padded stored delivery keys before inserting",
        "Notification delivery record upsert matches control-whitespace-padded stored delivery keys before inserting",
        "Notification delivery reconcile preflight prefers sent duplicate decoded delivery keys before retrying",
        "Notification delivery reconcile preflight treats byte-like sent statuses as sent duplicate rows before retrying",
        "Notification delivery reconcile preflight treats normalized sent statuses as sent duplicate rows before retrying",
        "Notification delivery record upsert preserves sent duplicate identity fields before writing failed attempts",
        "Notification delivery record upsert preserves normalized sent duplicate statuses before writing failed attempts",
        "Notification delivery record upsert preserves sent duplicate decoded delivery keys before writing failed attempts",
        "Notification delivery record upsert preserves sent duplicate last errors before writing failed attempts",
        "Notification delivery record upsert preserves sent duplicate response ids before writing failed attempts",
        "Notification delivery record upsert preserves sent duplicate context snapshots before writing failed attempts",
        "Notification delivery reconcile preflight treats missing outbox entries as an empty list",
        "Notification delivery reconcile preflight evaluates tuple outbox entry batches before audit lookup",
        "Notification delivery reconcile preflight evaluates mapping outbox entries before audit lookup",
        "Notification delivery reconcile preflight skips malformed mapping outbox entries before audit lookup",
        "Notification delivery reconcile attempt counts use string-safe integer conversion",
        "Notification delivery reconcile retry budgets treat `None` max attempts as the default retry budget",
        "Notification delivery reconcile retry timestamps use string-safe float conversion",
        "Notification delivery reconcile success timestamps use finite-float conversion before sender preflight output",
        "Notification delivery reconcile retry backoff treats `None` as the default backoff window",
        "Notification delivery reconcile retry backoff uses finite-float conversion before wait calculation",
        "Notification delivery reconcile current time uses finite-float fallback before wait calculation",
        "Notification delivery reconcile statuses use string-safe text conversion",
        "Notification delivery reconcile statuses are normalized before retry and already-sent decisions",
        "Notification delivery reconcile text metadata uses string-safe conversion",
        "Notification delivery response ids are stripped before record and sender preflight output",
        "Notification delivery reconcile audit context uses dict-safe conversion",
        "Notification delivery audit context maps use JSON-safe dict conversion before reconcile and summary output",
        "Notification delivery audit context normalizes `reason_codes` with text-list safe conversion",
        "Notification delivery audit context enumerates outbox metadata with mapping-item safe conversion",
        "Notification delivery audit context ignores non-string outbox metadata keys before JSON serialization",
        "Notification delivery audit context normalizes metadata values before JSON serialization",
        "Notification delivery audit context preserves mapping metadata values before JSON serialization",
        "Notification delivery audit context drops whitespace-only metadata before JSON serialization",
        "Notification delivery audit context drops empty collection metadata after normalization",
        "Notification delivery audit context normalizes sequence metadata values with sequence-safe conversion",
        "Notification delivery audit context partial sequence metadata is normalized before empty collection filtering",
        "Notification delivery audit context drops non-finite numeric metadata before JSON serialization",
        "Notification attention context record serialization uses string-safe text, integer, and dict conversion",
        "Notification attention context identity fields are stripped before summary output",
        "Notification attention context limit handling treats `None` as the default cap before summary output",
        "Notification attention context record serialization normalizes failed statuses before projection",
        "Frontend attention context summaries prefer persisted `source_text` or `source_label` before local source maps",
        "Frontend attention context summaries ignore blank persisted `source_text` and `source_label` before local source maps",
        "Frontend `sourceLabels` is contract-tested against backend `SOURCE_LABELS`",
        "Frontend source label helpers trim raw source keys before lookup",
        "Backend `SOURCE_LABELS` is immutable and must cover every daily queue `SOURCE_ORDER` key",
        "Backend source label helpers trim raw source keys before lookup",
        "Backend source label helpers drop blank raw source keys before outputting display maps",
        "Backend source key helpers treat raw source key trim failures as blank keys",
        "Backend source key helpers require raw source key trim results to remain strings",
        "Backend source text normalization requires trim results to be plain strings",
        "Backend source display map helpers ignore non-mapping raw source distributions",
        "Backend source key helpers ignore non-string raw source keys before display maps",
        "Backend source count normalization ignores non-mapping raw source distributions",
        "Backend source count normalization drops non-positive raw source counts before outputting source distribution maps",
        "Backend source count normalization treats boolean and non-finite raw source counts as inactive",
        "Backend source count normalization treats fractional raw source counts as inactive",
        "Backend source count normalization requires non-string numeric raw source counts to equal their integer value",
        "Backend source count normalization treats raw source count conversion failures as inactive",
        "Backend source count normalization treats arithmetic raw source count conversion failures as inactive",
        "Backend source count normalization treats arbitrary `__int__` count objects as inactive before outputting source distribution maps",
        "Backend source count normalization accepts only plain string raw source counts",
        "Backend source display override helpers normalize active raw source keys before matching upstream overrides",
        "Backend source display override helpers ignore non-mapping active source distributions",
        "Backend source display override helpers safely trim override values and require trim results to remain strings",
        "Backend source display helpers ignore mapping accessor failures",
        "Backend source display helpers treat arithmetic mapping accessor failures as empty source distributions",
        "Backend source display helpers treat mapping attribute lookup failures as empty source distributions",
        "Backend source display helpers treat lookup failures as empty or skipped source entries",
        "Backend source display helpers ignore malformed mapping items",
        "Backend source display helpers ignore mapping item unpack failures",
        "Backend source display helpers preserve valid mapping items before iterator failures",
        "Backend source display helpers ignore malformed mapping keys",
        "Backend source display helpers preserve valid mapping keys before iterator failures",
        "Backend source display override helpers ignore non-string override values before fallback labels",
        "Daily decision queue notification delivery attention context iterator failures fall back to native sequence items",
        "Shared sequence conversion treats lookup iterator failures as native-sequence fallbacks",
        "Shared sequence conversion treats lookup iterator creation failures as native-sequence fallbacks",
        "Shared mapping dict conversion uses Mapping traversal when `.items()` iterables fail lookup",
        "Shared mapping dict conversion skips lookup key hash failures during Mapping traversal",
        "Shared mapping item conversion skips lookup item unpack failures",
        "Shared mapping item conversion skips lookup key hash failures",
        "`decision_queue.summary` exposes `source_labels` and `source_texts`",
        "`notification_plan.queue_context` preserves upstream `decision_queue.summary.source_labels` and `source_texts`",
        "`notification_plan.queue_context` fills missing `source_labels` and `source_texts` from raw `sources` while preserving upstream overrides",
        "`notification_plan.queue_context` ignores blank upstream source display overrides so fallback labels stay readable",
        "`notification_plan.queue_context` drops upstream source display overrides for keys absent from raw `sources`",
        "`notification_plan.queue_context` trims raw source distribution keys before exposing `sources`, `source_labels`, and `source_texts`",
        "`notification_plan.queue_context` maps non-string legacy action source keys to `unknown` before exposing source distribution maps",
        "`notification_plan.queue_context` uses a string-safe legacy action type filter before excluding `monitor` fallback actions",
        "`notification_plan.queue_context` treats numeric conversion failures as zero before exposing count and priority fields",
        "`notification_plan.queue_context` uses strict count conversion before exposing count and priority fields",
        "Notification plan numeric conversion treats fractional float, Decimal, and Fraction values as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata",
        "Notification plan numeric conversion treats negative values as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata",
        "Notification plan numeric conversion treats arbitrary `__int__` adapter objects as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata",
        "Notification messages and `delivery_outbox` entries preserve action-provided `source_label` and `source_text` before fallback labels",
        "Notification messages and `delivery_outbox` entries ignore blank action-provided `source_label` and `source_text` before fallback labels",
        "Notification messages and `delivery_outbox` entries trim raw action `source` keys before exposing source display context",
        "Notification source display override values are trimmed before `queue_context`, `messages`, and `delivery_outbox` expose them",
        "Notification messages and `delivery_outbox` entries drop blank action `source` keys before exposing source display context",
        "Notification messages and `delivery_outbox` entries drop orphan `source_label` and `source_text` fields when an action has no valid raw `source`",
        "Notification messages and `delivery_outbox` entries ignore non-string action-provided `source_label` and `source_text` before fallback labels",
        "Notification messages treat malformed dedupe identity values as fallback identity parts before exposing `dedupe_key` and `message_id`",
        "Notification identity branch selection sanitizes report, ticker, pipeline, route, and warning identifiers before choosing fallback identity parts",
        "Notification identity parts use shared text conversion before composing `dedupe_key`, `message_id`, and `delivery_key`",
        "Notification identity parts use identity and type-based empty checks before composing `dedupe_key`, `message_id`, and `delivery_key`",
        "Notification messages normalize `filename` and `report_filename` aliases with string-safe selection before exposing message and `delivery_outbox` report context",
        "Notification message numeric metadata uses strict count conversion before exposing `priority_score` and `horizon_months`",
        "Notification message text metadata uses shared text conversion before exposing ticker, filename, report, pipeline, route, warning, recommended action, severity, and action label fields",
        "Notification message boolean metadata uses explicit bool-text conversion before exposing `blocks_auto_rerun`",
        "Notification message and `delivery_outbox` context presence checks tolerate malformed equality comparisons before carrying optional metadata",
        "Notification message and `delivery_outbox` context presence checks use identity and type-based empty checks before carrying optional metadata",
        "Notification suppression flag checks use explicit bool-text conversion before message filtering",
        "Notification plan boolean conversion treats arbitrary string-like objects as malformed before message metadata or suppression checks",
        "Notification action type lookups trim raw `type` before suppression, legacy queue context, CTA defaults, target defaults, and message envelope output",
        "Notification plan external channel env checks require concrete nonblank string values before enabling SMTP, Telegram, Discord, or Slack",
        "Notification plan external channel env containers use mapping-safe conversion before missing-env checks",
        "Notification plan action collections use iterator-safe dict-list conversion before message and `delivery_outbox` assembly",
        "Notification plan action collections accept list or tuple payloads before message and `delivery_outbox` assembly",
        "Notification plan decision queue context uses mapping-safe conversion before reading `decision_queue`, `summary`, and `sources`",
        "Notification plan dashboard payloads use mapping-safe conversion before reading `decision_queue` or legacy `actions`",
        "Notification messages ignore malformed action-provided `dedupe_key` and `message_id` overrides before falling back to derived delivery identity",
        "Notification operator CTA metadata selection uses string-safe action/label fallbacks",
        "Notification target metadata selection uses string-safe panel/tab fallbacks",
        "Notification custom CTA and target metadata selection trims action-provided values before fallback selection",
        "Notification message envelope selection uses string-safe type/title/detail fallbacks",
        "Notification message envelope selection uses shared text conversion for type/title/detail fields",
        "Notification message envelope selection trims type/title/detail fields before fallback selection",
        "queue rank, displayed count, and top-priority flag",
        "falls back to channel/status/attempt metadata",
        "still avoids rendering raw `last_error`",
        "context snapshot",
        "audit_context",
    ]:
        assert expected in operator_guide

    for expected in [
        "notification_delivery",
        "sender audit health",
        "fix_notification_delivery",
        "suppress_notification = true",
        "failed_count",
        "retry_exhausted_count",
        "channel_counts",
        "failure_reason_counts",
        "attention_contexts",
        "dashboard `status` 會升為 `warning`",
        "stock_agent_notification_delivery_count",
        "stock_agent_notification_delivery_channel_count",
        "stock_agent_notification_delivery_failure_reason_count",
        "stock_agent_notification_delivery_health",
        "Notification delivery summary fetch failures fall back to empty delivery summaries for Prometheus",
        "Ops dashboard notification delivery summary fetch failures fall back to empty delivery summaries",
        "Ops dashboard API quota payload failures fall back to empty quota services",
        "Ops dashboard malformed API quota payloads fall back to empty quota services",
        "Ops dashboard API quota service lists use list-of-dict safe conversion before payload output",
        "Ops dashboard API quota numeric and observation fields use strict string/count conversion before payload output",
        "Ops dashboard job snapshot failures fall back to empty job sections",
        "Ops dashboard malformed job payloads fall back to empty job sections",
        "Ops dashboard nested job sections use dict-safe conversion before payload output",
        "Ops dashboard job unavailable status flags use bool-safe conversion",
        "Ops dashboard stuck job count status aggregation uses dict- and integer-safe conversion",
        "Ops dashboard stuck job count fields use strict count conversion before status and payload output",
        "Ops dashboard malformed provider payloads fall back to an empty last_24h provider state",
        "Ops dashboard provider selected windows use string-safe conversion before payload output",
        "Ops dashboard malformed provider alert lists fall back to empty alerts",
        "Ops dashboard provider alert impact classification uses string-safe source conversion",
        "Ops dashboard provider alert level comparison uses string-safe conversion before status and count aggregation",
        "Ops dashboard provider alert success-rate fields use finite-float conversion before payload output",
        "Ops dashboard provider alert text and window fields use string- and dict-safe conversion before payload output",
        "Provider SLA dashboard alert payload fields use dict-native field reads before impact classification",
        "Notification delivery observability summaries use dict-safe conversion before rendering dashboard and Prometheus maps",
        "Notification delivery observability fields use dict-native field reads before attention, dashboard, and Prometheus rendering",
        "Notification delivery observability counts use integer-safe conversion before rendering dashboard and Prometheus gauges",
        "Notification delivery observability counts use strict count conversion before rendering dashboard and Prometheus gauges",
        "Notification delivery dashboard count maps use shared text keys and integer-safe values before payload output",
        "Notification delivery Prometheus channel and reason labels use shared text conversion with unknown fallback",
        "Prometheus label rendering uses shared text conversion with unknown fallback",
        "Prometheus provider summary fetch failures fall back to empty provider series",
        "Prometheus provider summary non-iterable payloads fall back to empty provider series",
        "Prometheus provider summary iterator failures preserve provider rows parsed before the failure",
        "Prometheus queue snapshot fetch failures fall back to unknown/zero queue gauges",
        "Ops dashboard queue snapshot fetch failures fall back to an unavailable unknown queue status",
        "Ops dashboard queue availability uses bool-safe conversion before status aggregation and payload output",
        "Ops dashboard queue metadata uses string-, integer-, and dict-safe conversion before payload output",
        "Ops dashboard named queue details use string-key and dict-safe conversion before payload output",
        "Ops dashboard named queue detail fields use integer-, string-, and registry-map safe conversion before payload output",
        "Ops dashboard queue integer fields use strict count conversion before payload output",
        "Ops dashboard queue supplemental fields use integer-, float-, string-, and registry-map safe conversion before payload output",
        "Ops dashboard queue text metadata uses shared text conversion before payload output",
        "Ops dashboard queue age fields use finite-float conversion before payload output",
        "Ops dashboard queue age fields use strict finite-float conversion before payload output",
        "Observability dashboard and Prometheus payload shaping uses payload-safe mapping conversion",
        "Ops dashboard free mode provider summaries use dict-, list-, bool-, and string-safe conversion before payload output",
        "Ops dashboard free mode violations use string-safe conversion before payload output",
        "Ops dashboard free mode provider tiers and violations use shared text conversion instead of persistence JSON pruning",
        "Prometheus queue snapshots use dict-safe conversion before rendering queue gauges",
        "Prometheus queue backend and queue name rendering uses string-safe conversion",
        "Prometheus queue availability rendering uses bool-safe conversion",
        "Prometheus named queue depth maps use payload-safe conversion",
        "Prometheus queue depth gauges use strict count conversion",
        "Prometheus integer gauges use integer-safe conversion",
        "Prometheus float gauges use float-safe conversion",
        "Prometheus provider numeric gauges use strict numeric conversion",
        "Prometheus provider rows use dict-safe conversion before rendering provider gauges",
        "Analysis job status rows use mapping-safe fallback",
        "Analysis job status serializer fields use JSON-safe fallback",
        "Analysis job by-id cancellation rows use mapping-safe fallback",
        "Analysis job by-id cancellation fallback results use bool-safe fallback",
        "Analysis job by-id cancellation service results use mapping-safe fallback",
        "Analysis job by-id cancellation service fields use JSON-safe fallback",
        "Analysis job cancellation service rows use mapping-safe fallback",
        "Analysis job cancellation service request ids use safe text fallback",
        "Analysis job cancellation service status checks use safe text fallback",
        "Analysis job cancellation queue cancel accessors use safe getattr",
        "Analysis job serialization rows use mapping-safe fallback",
        "Analysis job serialization status fields use safe text fallback",
        "Analysis job serialization status fields trim whitespace",
        "Analysis job serialization status fields normalize known status casing",
        "Analysis job serialization identity fields use safe text fallback",
        "Analysis job serialization identity URL helper fields use path-segment fallback",
        "Analysis job serialization public URL helper segments reject whitespace",
        "Analysis job serialization public URL helper segments reject encoded percent tokens",
        "Analysis job serialization report filename fields use safe text fallback",
        "Analysis job serialization report filename fields use path-segment fallback",
        "Analysis job serialization report filename fields use URL-delimiter fallback",
        "Analysis job serialization report filename fields use control-character fallback",
        "Analysis job serialization report filename fields use percent-encoded delimiter fallback",
        "Analysis job serialization pipeline fields use safe text fallback",
        "Analysis job serialization ticker fields use safe text fallback",
        "Analysis job serialization timestamp fields use finite-float fallback",
        "Analysis job serialization timestamp empty checks use type-safe string guards",
        "Analysis job serialization error fields use safe sanitizer fallback",
        "Analysis job lifecycle result rows use mapping-safe fallback",
        "Analysis job create handler results use mapping-safe fallback",
        "Analysis job create handler fields use serializer-backed JSON-safe fallback",
        "Analysis job create route normalized pipeline ids use safe text fallback",
        "Analysis job id builder input fields use safe text fallback",
        "Analysis job id builder force flags use bool-safe fallback",
        "Analysis job lifecycle identity fields use safe text fallback",
        "Analysis job lifecycle status fields use safe text fallback",
        "Analysis job input pipeline fields use safe text fallback",
        "Analysis job input ticker fields use safe text fallback",
        "Analysis job input force flags use bool-safe fallback",
        "Analysis job input arbitrary object force flags use conservative bool fallback",
        "Analysis job input binary or container force flags use conservative bool fallback",
        "Analysis job input string force flags use bool-text fallback",
        "Analysis job input non-finite numeric force flags use finite-number fallback",
        "Analysis job input numeric force flags accept only explicit zero or one",
        "Analysis job input Fraction force flags use the same explicit zero-or-one fallback",
        "Analysis job input Decimal force flags use the same explicit zero-or-one fallback",
        "Analysis job input complex force flags use conservative bool fallback",
        "Analysis job input resume flags use bool-safe fallback",
        "Analysis job lifecycle created flags use explicit boolean selection",
        "Analysis job queue task identity fields use safe text fallback",
        "Analysis job queue task identity fields use path-segment fallback",
        "Analysis job queue task lookup ids use safe text fallback",
        "Analysis job queue task status fields use safe text fallback",
        "Analysis job queue task status fetch failures return unknown inspection results",
        "Analysis job queue task status accessors return unknown inspection results",
        "Analysis job queue task status properties return unknown inspection results",
        "Analysis job queue metadata fetch failures return unknown inspection results",
        "Analysis job child queue fetch-job metadata failures return unknown inspection results",
        "Analysis job queue deduplication uses identity-only comparison",
        "Analysis job queue enqueue failure messages use safe text fallback",
        "Analysis job legacy create fallback identity fields use safe text fallback",
        "Analysis job legacy create fallback queue enqueue failure messages use safe text fallback",
        "Analysis job legacy create fallback serializer fields use JSON-safe fallback",
        "Analysis SSE setup job rows use mapping-safe fallback",
        "Analysis SSE intro identity fields use safe text fallback",
        "Legacy analysis job rows use mapping-safe fallback",
        "Legacy analysis requested-job identity validation uses safe text fallback",
        "Legacy analysis requested-job ticker validation uses safe text fallback",
        "Legacy analysis requested-job pipeline validation uses safe text fallback",
        "Legacy analysis active-job identity validation uses safe text fallback",
        "Legacy analysis create handler results use mapping-safe fallback",
        "Legacy analysis fallback queue enqueue failure messages use safe text fallback",
        "Legacy analysis API key readiness checks use strict bool fallback",
        "Legacy analysis missing API key messages use safe text fallback",
        "Legacy analysis normalized pipeline ids use safe text fallback",
        "Legacy analysis intro pipeline sequence values use sequence- and text-safe fallback",
        "Legacy analysis intro pipeline label values use safe text fallback",
        "Legacy analysis intro agent total values use integer-safe fallback",
        "Legacy analysis resume id parsing treats negative `Last-Event-ID` values",
        "Legacy analysis cancel normalized pipeline ids use safe text fallback",
        "Legacy analysis cancel ticker validation uses safe text fallback",
        "Legacy analysis cancel pipeline validation uses safe text fallback",
        "Legacy analysis cancel result handling uses bool-safe fallback",
        "Analysis SSE resume id parsing ignores malformed `since_id` values",
        "Analysis SSE resume id parsing treats negative `since_id`",
        "Analysis SSE resume id parsing treats boolean `since_id`",
        "Analysis SSE stream replay payloads use mapping-safe fallback",
        "Analysis SSE stream replay event rows use mapping-safe fallback",
        "Analysis SSE stream replay event id fields use integer-safe fallback",
        "Analysis SSE stream replay payload type fields use safe text fallback",
        "Analysis SSE stream replay message fields use safe text fallback",
        "Analysis SSE stream replay control fields use safe text fallback",
        "Analysis SSE stream replay done identity fields use safe text fallback",
        "Analysis SSE stream replay report artifact filename fields use safe text fallback",
        "Analysis SSE stream replay progress text fields use safe text fallback",
        "Analysis SSE stream replay telemetry text fields use safe text fallback",
        "Analysis SSE stream replay telemetry metric fields use finite-float, integer-, and bool-safe fallback",
        "Analysis job telemetry setup rows use mapping-safe fallback",
        "Analysis job telemetry serializer results use mapping-safe fallback",
        "Analysis job telemetry serializer fields use JSON-safe fallback",
        "Analysis job telemetry request ids use safe text fallback",
        "Analysis node telemetry row collections use iterable-safe fallback",
        "Analysis node telemetry row collection iterators preserve valid rows before iteration failures",
        "Analysis node telemetry rows use mapping-safe fallback",
        "Analysis node telemetry text fields use safe text fallback",
        "Analysis node telemetry timestamp fields use conservative object fallback",
        "Analysis node telemetry metric fields use integer- and bool-safe fallback",
        "Analysis node telemetry optional metric fields reject fractional numeric values",
        "Analysis node telemetry optional metric fields reject fractional exact numeric values",
        "Analysis node telemetry optional metric fields use conservative object fallback",
        "Analysis node telemetry optional metric fields reject negative values",
        "Analysis node telemetry retry count fields reject fractional numeric values",
        "Analysis node telemetry retry count fields reject negative values",
        "Analysis node telemetry bool fields use strict bool fallback",
        "Analysis node telemetry bool numeric fields accept only explicit zero or one",
        "Analysis node telemetry bool exact numeric fields use the same explicit zero-or-one contract",
        "Analysis node telemetry arbitrary object bool fields use conservative fallback",
        "Analysis SSE stream replay metadata fields use snapshot-safe fallback",
        "Analysis SSE stream replay structured report fields use snapshot-safe fallback",
        "Analysis SSE stream replay done aggregate fields use snapshot-safe fallback",
        "Analysis SSE stream replay workflow retry thread ids use safe text fallback",
        "Analysis SSE stream replay count fields use integer-safe fallback",
        "Analysis SSE stream replay pipeline count fields use integer-safe fallback",
        "Analysis SSE terminal fallback error messages use safe text fallback",
        "Analysis SSE terminal fallback cancellation messages use safe text fallback",
        "Analysis SSE terminal fallback done identity fields use safe text fallback",
        "Analysis SSE terminal polling status checks use safe text fallback",
        "Analysis SSE terminal fallback persistence checks use mapping-safe event rows",
        "Analysis SSE event collections use sequence-safe fallback",
        "Analysis SSE missing or empty job rows after stream setup emit terminal error fallbacks",
        "Report conformance quality gate inputs use dict-native field reads",
        "Report conformance quality gate inputs accept mapping-safe wrappers",
        "Report conformance quality gate issue lists use sequence-safe conversion",
        "Report conformance visible artifact and gate status text fields use safe text fallback",
        "Report content credibility evidence matrix rows use sequence-safe conversion",
        "Report content credibility evidence matrix row maps use mapping-safe conversion",
        "Report content credibility quality gate inputs use mapping-safe conversion",
        "Report content credibility recommendation and gate text fields use safe text fallback",
        "Report renderer lint repair result fields use dict-native field reads",
        "Report execution summary quality gate fields use dict-native field reads",
        "Report execution summary quality gate child maps use mapping-safe conversion",
        "Report execution summary text fields use shared text conversion",
        "Report execution summary Markdown text fields collapse embedded newlines",
        "Report mode template display fields use shared text conversion",
        "Report mode template visual focus and reading path fields use shared text-list conversion",
        "Report mode template Markdown display fields collapse embedded newlines",
        "Report summary and decision discipline display fields use shared text conversion",
        "Report tear-sheet recent catalyst rows use dict-list safe conversion",
        "Report investment-thesis final-audit warning rows use text-list safe conversion",
        "Report investment-thesis final-audit critical rows use text-list safe conversion",
        "Report investment-thesis agent analysis text uses truthiness-safe fallback",
        "Report investment-thesis current price display uses truthiness-safe fallback",
        "Report investment-thesis moat score display uses shared text conversion",
        "Report investment-thesis prebuilt payloads use mapping-safe conversion",
        "Report Markdown renderer prebuilt investment-thesis payloads use mapping-safe handoff",
        "Report PE river chart payload uses truthiness-safe mapping handoff",
        "Report PE river chart payload accepts mapping-safe chart wrappers",
        "Report investment-thesis source audit rows use dict-list safe conversion",
        "Report investment-thesis history series use sequence-safe conversion",
        "Report investment-thesis Markdown list fields use text- and dict-list safe conversion",
        "Report investment-thesis Markdown display fields collapse embedded newlines",
        "Report investment-thesis recommendation and trade setup mappings use mapping-item safe conversion",
        "Report investment-thesis structured scenario triggers use dict-list safe conversion",
        "Report investment-thesis data trust status uses text-safe comparison",
        "Report HTML sanitizer uses truthiness-safe string conversion",
        "Report plain-text sanitizer uses truthiness-safe string conversion",
        "Report cover image URL sanitizer uses truthiness-safe string conversion",
        "Report next catalyst list fields use dict-list safe conversion",
        "Report structured-output child maps use mapping-safe conversion",
        "Report structured-output schema-derived next catalysts accept mapping-safe root payloads",
        "Report structured-output schema-derived next catalysts treat null catalyst lists as derivable",
        "Report structured-output schema-derived next catalysts treat non-list catalyst payloads as derivable",
        "Report structured-output schema-derived next catalysts treat non-mapping catalyst rows as derivable",
        "Report structured-output schema-derived next catalysts keep valid mapping catalyst rows",
        "Report structured-output schema-derived next catalysts filter schema-invalid mapping catalyst rows",
        "Report structured-output catalyst text fields use safe text fallback",
        "Report structured-output scenario-trigger text fields use safe text fallback",
        "Report structured-output schema-derived next catalysts use safe scenario-trigger text",
        "Report structured-output schema-derived next catalysts enforce scenario-trigger minimum lengths",
        "Report structured-output schema-derived scenario triggers use minimum fallback",
        "Report structured-output schema-derived scenario trigger collections use list-safe fallback",
        "Report structured-output scenario-trigger collections use missing-field fallback",
        "Report structured-output missing scenario-trigger fallback drives schema-derived next catalysts",
        "Report structured-output schema-derived next catalysts truncate overlong scenario-trigger lists",
        "Report structured-output executive-thesis root payloads use mapping-safe fallback",
        "Report structured-output executive-thesis text fields use safe text fallback",
        "Report structured-output executive-thesis resolved-contradiction list items use safe text fallback",
        "Report structured-output confidence-basis lists use safe text conversion",
        "Report structured-output confidence-basis required lists use minimum fallback",
        "Report structured-output confidence-basis required list collections use list-safe fallback",
        "Report structured-output confidence-basis root payloads use mapping-safe fallback",
        "Report structured-output confidence-basis objects use missing-field fallback",
        "Report structured-output reasoning steps use safe text conversion",
        "Report structured-output reasoning steps use minimum fallback",
        "Report structured-output reasoning step collections use list-safe fallback",
        "Report structured-output recommendation labels use canonical alias normalization",
        "Report structured-output recommendation labels use missing-field fallback",
        "Report structured-output recommendation text fields use safe text fallback",
        "Report structured-output recommendation text fields use missing-field fallback",
        "Report structured-output analysis markdown uses safe text fallback",
        "Report structured-output analysis markdown fields use missing-field fallback",
        "Report structured-output recommendation root payloads use mapping-safe fallback",
        "Report structured-output recommendation objects use missing-field fallback",
        "Report structured-output recommendation field root payloads use mapping-safe fallback",
        "Report structured-output bubble-sniper root payloads use mapping-safe fallback",
        "Report structured-output bubble-sniper recommendation field root payloads use mapping-safe fallback",
        "Report structured-output moat analysis markdown uses safe text fallback",
        "Report structured-output moat root payloads use mapping-safe fallback",
        "Report structured-output moat reasoning steps use minimum fallback",
        "Report structured-output moat reasoning-step collections use list-safe fallback",
        "Report structured-output moat-score containers use mapping-safe fallback",
        "Report structured-output moat-score containers use missing-field fallback",
        "Report structured-output moat-score values use safe number fallback",
        "Report structured-output price-target analysis markdown uses safe text fallback",
        "Report structured-output price-target root payloads use mapping-safe fallback",
        "Report structured-output price-target containers use mapping-safe fallback",
        "Report structured-output price-target containers use missing-field fallback",
        "Report structured-output price-target direct target containers use mapping-safe fallback",
        "Report structured-output price-target text fields use safe text fallback",
        "Report structured-output price-target valuation-summary containers use mapping-safe fallback",
        "Report structured-output price-target valuation-summary containers use missing-field fallback",
        "Report structured-output price-target direct valuation-summary containers use mapping-safe fallback",
        "Report structured-output price-target valuation-summary boolean fields use bool-safe fallback",
        "Report structured-output price-target values use safe number fallback",
        "Report structured-output price-target DCF scenario values use safe number fallback",
        "Report structured-output price-target DCF scenario rows use row-safe filtering",
        "Report structured-output price-target DCF scenario names use enum-safe filtering",
        "Report structured-output price-target direct DCF scenario names use enum-safe fallback",
        "Report structured-output price-target DCF scenario collections use list-safe fallback",
        "Report structured-output price-target direct DCF scenario root payloads use mapping-safe fallback",
        "Report structured-output management-sentiment analysis markdown uses safe text fallback",
        "Report structured-output management-sentiment root payloads use mapping-safe fallback",
        "Report structured-output management-sentiment text fields use safe text fallback",
        "Report structured-output management-highlight root payloads use mapping-safe fallback",
        "Report structured-output management-sentiment highlight rows use row-safe fallback",
        "Report structured-output management-sentiment highlight collections use list-safe fallback",
        "Report structured-output management-sentiment highlight collections use missing-field fallback",
        "Report structured-output management-sentiment short highlight collections use minimum-count fallback",
        "Report structured-output management-sentiment confidence uses safe number fallback",
        "Report structured-output downside-risk analysis markdown uses safe text fallback",
        "Report structured-output downside-risk root payloads use mapping-safe fallback",
        "Report structured-output downside-risk root rows use mapping-safe fallback",
        "Report structured-output downside-risk text fields use safe text fallback",
        "Report structured-output downside-risk rows use row-safe fallback",
        "Report structured-output downside-risk collections use list-safe fallback",
        "Report structured-output downside-risk collections use missing-field fallback",
        "Report structured-output downside-risk short collections use minimum-count fallback",
        "Report structured-output downside-risk confidence uses safe number fallback",
        "Report structured-output trade-plan text fields use safe text fallback",
        "Report structured-output trade-plan root payloads use mapping-safe fallback",
        "Report structured-output normalizer payloads use mapping-safe conversion",
        "Report structured-output normalizer scalar root payloads use schema fallback",
        "Report structured-output normalizer reasoning steps use safe text conversion",
        "Report structured-output normalizer reasoning steps use minimum fallback",
        "Report structured-output normalizer reasoning-step empty lists use minimum fallback",
        "Report structured-output normalizer reasoning-step null values use minimum fallback",
        "Report structured-output normalizer reasoning-step scalar objects use minimum fallback",
        "Report structured-output normalizer scenario trigger rows use dict-list and safe text conversion",
        "Report structured-output normalizer scenario trigger non-mapping rows use sequence-safe fallback",
        "Report structured-output normalizer scenario trigger mapping fields use minimum fallback",
        "Report structured-output normalizer scenario trigger mapping fields enforce schema minimum lengths",
        "Report structured-output normalizer scenario trigger fallback rows use schema-safe placeholder text",
        "Report structured-output normalizer scenario trigger empty lists use minimum fallback",
        "Report structured-output normalizer scenario trigger null values use minimum fallback",
        "Report structured-output normalizer scenario trigger scalar collections use minimum fallback",
        "Report structured-output normalizer scenario trigger lists use schema-limit truncation",
        "Report structured-output normalizer scenario trigger fallback rows are deferred",
        "Report structured-output normalizer confidence-basis lists use safe text conversion",
        "Report structured-output normalizer confidence-basis required lists use minimum fallback",
        "Report structured-output normalizer confidence-basis required list collections use list-safe fallback",
        "Report structured-output normalizer confidence-basis empty required lists use minimum fallback",
        "Report structured-output normalizer recommendation text fields use safe text conversion",
        "Report structured-output normalizer bubble-sniper recommendation labels use avoid fallback",
        "Report structured-output normalizer next-catalyst text fields use safe text conversion",
        "Report structured-output normalizer next-catalyst trigger fields enforce schema minimum length",
        "Report structured-output normalizer next-catalyst fallback rows use schema-safe trigger text",
        "Report structured-output normalizer next-catalyst rows use sequence-safe fallback",
        "Report structured-output normalizer next-catalyst empty lists derive from scenario triggers",
        "Report structured-output normalizer empty next-catalyst lists derive from missing scenario-trigger fallback",
        "Report structured-output normalizer next-catalyst fallback rows are deferred",
        "Report structured-output normalizer price-target numbers exclude boolean values",
        "Report structured-output normalizer price-target values use safe number fallback",
        "Report structured-output normalizer price-target missing objects use validated fallback targets",
        "Report structured-output normalizer moat-score numbers exclude boolean values",
        "Report structured-output normalizer moat-score fields use safe number fallback",
        "Report structured-output normalizer moat-score missing objects use validated fallback scores",
        "Report structured-output normalizer moat analysis markdown uses safe text conversion",
        "Report moat legacy text surfaces reasoning steps from structured outputs",
        "Report legacy reasoning-step text skips single-character fragments",
        "Report structured-output normalizer management-confidence numbers exclude boolean values",
        "Report structured-output normalizer management-confidence numbers use safe fallback",
        "Report management-sentiment legacy text surfaces confidence from structured outputs",
        "Report management-sentiment legacy text uses quote fallback for empty highlights",
        "Report management-sentiment legacy text uses highlight fallback for single-character fragments",
        "Report management-sentiment legacy text uses fallback row for empty highlights",
        "Report management-sentiment legacy text uses guidance-tone fallback for invalid metadata",
        "Report management-sentiment legacy text uses analysis body fallback for single-character fragments",
        "Report structured-output normalizer management-sentiment text fields use safe text conversion",
        "Report structured-output normalizer management-sentiment highlight rows use sequence-safe fallback",
        "Report structured-output normalizer management-sentiment highlight collections use missing-field fallback",
        "Report structured-output normalizer management-sentiment empty highlight lists use minimum fallback",
        "Report structured-output normalizer management-sentiment highlight fallback rows are deferred",
        "Report structured-output normalizer downside-risk confidence numbers exclude boolean values",
        "Report structured-output normalizer downside-risk confidence preserves explicit zero values",
        "Report structured-output normalizer downside-risk confidence numbers use safe fallback",
        "Report structured-output normalizer downside-risk text fields use safe text conversion",
        "Report structured-output normalizer downside-risk rows use sequence-safe fallback",
        "Report structured-output normalizer downside-risk collections use missing-field fallback",
        "Report structured-output normalizer downside-risk empty lists use minimum fallback",
        "Report structured-output normalizer downside-risk fallback rows are deferred",
        "Report structured-output legacy price-target rendering uses exception-safe number conversion",
        "Report structured-output legacy price-target rendering excludes non-finite numbers",
        "Report structured-output legacy price-target rendering preserves single scientific-notation numeric strings",
        "Report valuation legacy text uses fallback row for empty price targets",
        "Report structured-output normalizer price-target scenario keys use safe text conversion",
        "Report structured-output normalizer price-target reasoning fields use safe text conversion",
        "Report structured-output normalizer valuation-summary text fields use safe text conversion",
        "Report structured-output normalizer valuation-summary boolean fields use bool-safe conversion",
        "Report structured-output normalizer DCF scenario rows use safe finite-number conversion",
        "Report structured-output normalizer DCF scenario numeric fields use safe number fallback",
        "Report structured-output normalizer trade-plan text fields use safe text conversion",
        "Report structured-output normalizer trade-plan enum fields use literal fallback",
        "Report structured-output normalizer trade-plan analysis markdown uses safe text projection",
        "Report Agent 19 required structured sections use dict-list safe scenario triggers",
        "Report Agent 19 required structured trigger rows collapse embedded newlines",
        "Report Agent 19 required structured trigger rows use action fallback",
        "Report recommendation block skips mapping-safe nested confidence-basis maps",
        "Report recommendation block display keys use shared text conversion",
        "Report recommendation block uses fallback row for empty standard recommendations",
        "Report Agent 19 recommendation ordered values use shared text conversion",
        "Report recommendation block Markdown display rows collapse embedded newlines",
        "Report recommendation tail basis and trigger fields use shared text conversion",
        "Report recommendation tail confidence-basis bullets skip single-character fragments in legacy reports",
        "Report recommendation tail trigger actions use fallback text in legacy reports",
        "Report recommendation tail trigger conditions skip single-character fragments in legacy reports",
        "Report recommendation tail trigger actions use fallback for single-character fragments in legacy reports",
        "Report recommendation tail omits empty basis and trigger sections in legacy text",
        "Report recommendation tail Markdown fields collapse embedded newlines",
        "Report recommendation legacy text surfaces next catalysts from structured outputs",
        "Report recommendation legacy text uses trigger fallback for blank next catalysts",
        "Report recommendation legacy text uses impact-direction fallback for invalid next catalysts",
        "Report recommendation legacy text uses trigger-length fallback for too-short next catalysts",
        "Report recommendation legacy text surfaces reasoning steps from structured outputs",
        "Report downside-risk legacy text surfaces thesis summaries from structured outputs",
        "Report downside-risk legacy text uses thesis-summary fallback for single-character fragments",
        "Report downside-risk legacy text uses analysis body fallback for single-character fragments",
        "Report downside-risk legacy text uses fallback row for empty risk lists",
        "Report valuation legacy text surfaces valuation reasoning from structured outputs",
        "Report valuation legacy text surfaces DCF scenario assumptions from structured outputs",
        "Report downside-risk legacy text surfaces risk priority metadata from structured outputs",
        "Report downside-risk legacy text separates impact from evidence in risk rows",
        "Report downside-risk legacy text uses evidence fallback for single-character fragments",
        "Report downside-risk legacy text uses title fallback for single-character fragments",
        "Report downside-risk legacy text omits impact for single-character fragments",
        "Report downside-risk legacy text uses severity fallback for invalid metadata",
        "Report downside-risk legacy text uses confidence fallback for invalid metadata",
        "Report legacy score and valuation fields use shared display conversion",
        "Report moat score legacy text uses semantic key fallback",
        "Report moat score legacy text uses key fallback for single-character fragments",
        "Report moat score legacy text uses fallback row for empty scores",
        "Report valuation summary legacy text uses semantic key fallback",
        "Report valuation summary legacy text uses fallback for single-character fragments",
        "Report legacy score and valuation Markdown key-value fields collapse embedded newlines",
        "Report legacy analysis markdown body uses shared text conversion",
        "Report legacy structured display fields use shared text conversion",
        "Report short-term trade-plan legacy text preserves analysis body fallback",
        "Report short-term trade-plan legacy text uses enum fallback for invalid metadata",
        "Report short-term trade-plan legacy text uses field fallback for single-character fragments",
        "Report short-term trade-plan legacy text uses analysis body fallback for single-character fragments",
        "Report legacy structured Markdown display fields collapse embedded newlines",
        "Report analysis overlay display fields use shared text conversion",
        "Report analysis overlay display fields collapse embedded newlines",
        "Report analysis overlay list fields use dict-list safe conversion",
        "Report analysis overlay structured-output maps use mapping-safe conversion",
        "Report analysis overlay data child maps use mapping-safe conversion",
        "Report analysis overlay financial history sequences use sequence-safe conversion",
        "Report key evidence source audit child maps use mapping-safe conversion",
        "Analysis job status rows use mapping-safe fallback",
        "Analysis job status serializer fields use JSON-safe fallback",
        "Analysis job by-id cancellation rows use mapping-safe fallback",
        "Analysis job by-id cancellation fallback results use bool-safe fallback",
        "Analysis job by-id cancellation service results use mapping-safe fallback",
        "Analysis job by-id cancellation service fields use JSON-safe fallback",
        "Analysis job cancellation service rows use mapping-safe fallback",
        "Analysis job cancellation service request ids use safe text fallback",
        "Analysis job cancellation service status checks use safe text fallback",
        "Analysis job cancellation queue cancel accessors use safe getattr",
        "Analysis job serialization rows use mapping-safe fallback",
        "Analysis job serialization status fields use safe text fallback",
        "Analysis job serialization status fields trim whitespace",
        "Analysis job serialization status fields normalize known status casing",
        "Analysis job serialization identity fields use safe text fallback",
        "Analysis job serialization identity URL helper fields use path-segment fallback",
        "Analysis job serialization public URL helper segments reject whitespace",
        "Analysis job serialization public URL helper segments reject encoded percent tokens",
        "Analysis job serialization report filename fields use safe text fallback",
        "Analysis job serialization report filename fields use path-segment fallback",
        "Analysis job serialization report filename fields use URL-delimiter fallback",
        "Analysis job serialization report filename fields use control-character fallback",
        "Analysis job serialization report filename fields use percent-encoded delimiter fallback",
        "Analysis job serialization pipeline fields use safe text fallback",
        "Analysis job serialization ticker fields use safe text fallback",
        "Analysis job serialization timestamp fields use finite-float fallback",
        "Analysis job serialization timestamp empty checks use type-safe string guards",
        "Analysis job serialization error fields use safe sanitizer fallback",
        "Analysis job lifecycle result rows use mapping-safe fallback",
        "Analysis job create handler results use mapping-safe fallback",
        "Analysis job create handler fields use serializer-backed JSON-safe fallback",
        "Analysis job create route normalized pipeline ids use safe text fallback",
        "Analysis job id builder input fields use safe text fallback",
        "Analysis job id builder force flags use bool-safe fallback",
        "Analysis job lifecycle identity fields use safe text fallback",
        "Analysis job lifecycle status fields use safe text fallback",
        "Analysis job input pipeline fields use safe text fallback",
        "Analysis job input ticker fields use safe text fallback",
        "Analysis job input force flags use bool-safe fallback",
        "Analysis job input arbitrary object force flags use conservative bool fallback",
        "Analysis job input binary or container force flags use conservative bool fallback",
        "Analysis job input string force flags use bool-text fallback",
        "Analysis job input non-finite numeric force flags use finite-number fallback",
        "Analysis job input numeric force flags accept only explicit zero or one",
        "Analysis job input Fraction force flags use the same explicit zero-or-one fallback",
        "Analysis job input Decimal force flags use the same explicit zero-or-one fallback",
        "Analysis job input complex force flags use conservative bool fallback",
        "Analysis job input resume flags use bool-safe fallback",
        "Analysis job lifecycle created flags use explicit boolean selection",
        "Analysis job queue task identity fields use safe text fallback",
        "Analysis job queue task identity fields use path-segment fallback",
        "Analysis job queue task lookup ids use safe text fallback",
        "Analysis job queue task status fields use safe text fallback",
        "Analysis job queue task status fetch failures return unknown inspection results",
        "Analysis job queue task status accessors return unknown inspection results",
        "Analysis job queue task status properties return unknown inspection results",
        "Analysis job queue metadata fetch failures return unknown inspection results",
        "Analysis job child queue fetch-job metadata failures return unknown inspection results",
        "Analysis job queue deduplication uses identity-only comparison",
        "Analysis job queue enqueue failure messages use safe text fallback",
        "Analysis job legacy create fallback identity fields use safe text fallback",
        "Analysis job legacy create fallback queue enqueue failure messages use safe text fallback",
        "Analysis job legacy create fallback serializer fields use JSON-safe fallback",
        "Analysis SSE setup job rows use mapping-safe fallback",
        "Analysis SSE intro identity fields use safe text fallback",
        "Legacy analysis job rows use mapping-safe fallback",
        "Legacy analysis requested-job identity validation uses safe text fallback",
        "Legacy analysis requested-job ticker validation uses safe text fallback",
        "Legacy analysis requested-job pipeline validation uses safe text fallback",
        "Legacy analysis active-job identity validation uses safe text fallback",
        "Legacy analysis create handler results use mapping-safe fallback",
        "Legacy analysis fallback queue enqueue failure messages use safe text fallback",
        "Legacy analysis API key readiness checks use strict bool fallback",
        "Legacy analysis missing API key messages use safe text fallback",
        "Legacy analysis normalized pipeline ids use safe text fallback",
        "Legacy analysis intro pipeline sequence values use sequence- and text-safe fallback",
        "Legacy analysis intro pipeline label values use safe text fallback",
        "Legacy analysis intro agent total values use integer-safe fallback",
        "Legacy analysis resume id parsing treats negative `Last-Event-ID` values",
        "Legacy analysis cancel normalized pipeline ids use safe text fallback",
        "Legacy analysis cancel ticker validation uses safe text fallback",
        "Legacy analysis cancel pipeline validation uses safe text fallback",
        "Legacy analysis cancel result handling uses bool-safe fallback",
        "Analysis SSE resume id parsing ignores malformed `since_id` values",
        "Analysis SSE resume id parsing treats negative `since_id`",
        "Analysis SSE resume id parsing treats boolean `since_id`",
        "Analysis SSE stream replay payloads use mapping-safe fallback",
        "Analysis SSE stream replay event rows use mapping-safe fallback",
        "Analysis SSE stream replay event id fields use integer-safe fallback",
        "Analysis SSE stream replay payload type fields use safe text fallback",
        "Analysis SSE stream replay message fields use safe text fallback",
        "Analysis SSE stream replay control fields use safe text fallback",
        "Analysis SSE stream replay done identity fields use safe text fallback",
        "Analysis SSE stream replay report artifact filename fields use safe text fallback",
        "Analysis SSE stream replay progress text fields use safe text fallback",
        "Analysis SSE stream replay telemetry text fields use safe text fallback",
        "Analysis SSE stream replay telemetry metric fields use finite-float, integer-, and bool-safe fallback",
        "Analysis job telemetry setup rows use mapping-safe fallback",
        "Analysis job telemetry serializer results use mapping-safe fallback",
        "Analysis job telemetry serializer fields use JSON-safe fallback",
        "Analysis job telemetry request ids use safe text fallback",
        "Analysis node telemetry row collections use iterable-safe fallback",
        "Analysis node telemetry row collection iterators preserve valid rows before iteration failures",
        "Analysis node telemetry rows use mapping-safe fallback",
        "Analysis node telemetry text fields use safe text fallback",
        "Analysis node telemetry timestamp fields use conservative object fallback",
        "Analysis node telemetry metric fields use integer- and bool-safe fallback",
        "Analysis node telemetry optional metric fields reject fractional numeric values",
        "Analysis node telemetry optional metric fields reject fractional exact numeric values",
        "Analysis node telemetry optional metric fields use conservative object fallback",
        "Analysis node telemetry optional metric fields reject negative values",
        "Analysis node telemetry retry count fields reject fractional numeric values",
        "Analysis node telemetry retry count fields reject negative values",
        "Analysis node telemetry bool fields use strict bool fallback",
        "Analysis node telemetry bool numeric fields accept only explicit zero or one",
        "Analysis node telemetry bool exact numeric fields use the same explicit zero-or-one contract",
        "Analysis node telemetry arbitrary object bool fields use conservative fallback",
        "Analysis SSE stream replay metadata fields use snapshot-safe fallback",
        "Analysis SSE stream replay structured report fields use snapshot-safe fallback",
        "Analysis SSE stream replay done aggregate fields use snapshot-safe fallback",
        "Analysis SSE stream replay workflow retry thread ids use safe text fallback",
        "Analysis SSE stream replay count fields use integer-safe fallback",
        "Analysis SSE stream replay pipeline count fields use integer-safe fallback",
        "Analysis SSE terminal fallback error messages use safe text fallback",
        "Analysis SSE terminal fallback cancellation messages use safe text fallback",
        "Analysis SSE terminal fallback done identity fields use safe text fallback",
        "Analysis SSE terminal polling status checks use safe text fallback",
        "Analysis SSE terminal fallback persistence checks use mapping-safe event rows",
        "Analysis SSE event collections use sequence-safe fallback",
        "Analysis SSE missing or empty job rows after stream setup emit terminal error fallbacks",
        "Report source audit table child maps use mapping-safe conversion",
        "Report TWSE official availability banner source audit rows use dict-list safe conversion",
        "Report data trust quant metrics child maps use mapping-safe conversion",
        "Report data trust Markdown summary bullets collapse embedded newlines",
        "Report bundle data trust property accepts mapping-safe snapshot maps",
        "Report persistence accepts mapping-safe data snapshot payloads before saving",
        "Report refresh diffs accept mapping-safe data snapshot payloads before comparing",
        "Report refresh stale-source detection accepts mapping-safe data snapshot payloads",
        "Report refresh source audit sequences treat lookup iterator failures as native-sequence fallbacks",
        "Report refresh source audit sequences treat lookup iterator creation failures as native-sequence fallbacks",
        "Report refresh source audit rows use Mapping traversal when `.items()` iterables fail lookup",
        "Report refresh source audit rows skip lookup item unpack failures",
        "Report refresh source audit rows skip lookup key hash failures",
        "Report refresh source audit rows skip Mapping traversal key hash failures",
        "Report refresh source audit timestamps use safe text conversion",
        "Report refresh refreshed-data payloads accept mapping-safe provider/cache responses",
        "Report rerun refreshed-data payloads accept mapping-safe provider/cache responses",
        "Report rerun existing snapshot data payloads use mapping-safe snapshot normalization",
        "Report final-recommendation rerun context data uses mapping-safe snapshot normalization",
        "Report final-recommendation rerun context accepts mapping-safe rerun context payloads",
        "Report rerun renderer snapshots use mapping-safe snapshot normalization",
        "Report rerun render contexts use mapping-safe top-level normalization",
        "Report rerun progress events accept mapping-safe payloads before job-store persistence",
        "Report rerun progress event details use snapshot-safe normalization",
        "Report rerun scalar progress fallbacks use integer-safe conversion",
        "Report rerun progress event scope fields use safe text fallback",
        "Report rerun progress event control fields use safe text fallback",
        "Report rerun progress event count fields use integer-safe normalization",
        "Report rerun progress event message fields use safe text fallback",
        "Report rerun progress event name fields use safe text fallback",
        "Report rerun progress event detail fields use safe text fallback",
        "Report rerun progress event agent number fields use integer-safe normalization",
        "Report rerun progress event pipeline identity fields use safe text fallback",
        "Report rerun progress event metadata fields use mapping-safe normalization",
        "Report rerun API key failure events preserve source filenames",
        "Report rerun queue enqueue failure events preserve source filenames",
        "Report rerun queue enqueue failure messages use safe text fallback",
        "Report rerun attached job created flags use explicit boolean selection",
        "Report rerun attached job status checks use safe text fallback",
        "Report rerun stream replay payloads use mapping-safe fallback",
        "Report rerun stream replay payload type fields use safe text fallback",
        "Report rerun stream replay control fields use safe text fallback",
        "Report rerun stream replay message fields use safe text fallback",
        "Report rerun stream replay progress text fields use safe text fallback",
        "Report rerun stream replay filename fields use safe text fallback",
        "Report rerun stream replay context fields use safe text fallback",
        "Report rerun stream replay count fields use integer-safe fallback",
        "Report rerun stream replay status code fields use integer-safe fallback",
        "Report rerun stream replay structured fields use snapshot-safe normalization",
        "Report rerun stream replay event rows use mapping-safe fallback",
        "Report rerun stream replay event id fields use integer-safe fallback",
        "Report rerun stream event collections use sequence-safe fallback",
        "Report rerun stream resume id parsing treats negative `Last-Event-ID` values",
        "Report rerun stream missing job rows after SSE setup emit and persist terminal error fallbacks",
        "Report rerun stream malformed job rows after SSE setup emit terminal error fallbacks",
        "Report rerun stream terminal fallback events preserve rerun scope and source filenames",
        "Report rerun stream terminal fallback messages and filenames use safe text normalization",
        "Report rerun stream terminal polling status checks use safe text fallback",
        "Report rerun stream terminal fallback scopes use safe text fallback",
        "Report rerun stream task validation uses safe text fallback",
        "Report rerun stream setup job rows use mapping-safe fallback",
        "Report rerun stream task ticker validation uses safe text fallback",
        "Report rerun cancel job rows use mapping-safe fallback",
        "Report rerun cancel task validation uses safe text fallback",
        "Report rerun cancel task ticker validation uses safe text fallback",
        "Report rerun source filename fields use safe text normalization",
        "Report rerun cancellation messages use safe text fallback",
        "Report rerun invalid scope errors are handled inside the job-store terminal event flow",
        "Report rerun HTTP error details use safe text fallback",
        "Report rerun HTTP error status codes use integer-safe fallback",
        "Report rerun unexpected exception messages use safe text fallback",
        "Report rerun completion results use mapping-safe snapshot normalization",
        "Report rerun completion structured result fields use mapping-safe normalization",
        "Report rerun completion identity fields use safe text normalization",
        "Report refresh rerun checks accept mapping-safe data snapshot payloads before comparing",
        "Report trust controls data and context maps use mapping-safe conversion",
        "Report trust controls generated-at fields use safe text conversion",
        "Report trust controls Markdown reproducibility fields collapse embedded newlines",
        "Report price target card and chart payload values use JSON-safe numeric conversion",
        "Report chart payload series fields use JSON-safe text and finite-number conversion",
        "Report moat score normalization excludes boolean values",
        "Report price history chart payload accepts mapping-safe chart wrappers",
        "Report price history chart series fields use sequence-safe truthiness fallback",
        "Report price history chart date fields use safe text conversion",
        "Report price history chart mapping keys use future-date filtering",
        "Report PE river chart payload uses truthiness-safe mapping handoff",
        "Report PE river chart payload accepts mapping-safe chart wrappers",
        "Report current price chart literals use finite-number conversion",
        "Report recommendation banner target and confidence fields use shared text conversion",
        "Report executive synthesis text fields use shared text conversion",
        "Report cover metadata uses mapping-safe conversion",
        "Report parsed payload and child maps use mapping-safe conversion",
        "Report data payload and child maps use mapping-safe conversion",
        "Report Markdown renderer data and parsed payload maps use mapping-safe conversion",
        "Report Markdown renderer reference source table cells escape table separators",
        "Report Markdown renderer single-line fields collapse embedded newlines",
        "Report Markdown renderer prebuilt investment-thesis payloads use mapping-safe handoff",
        "Report agent output maps use mapping-safe conversion",
        "Report agent output child maps use mapping-safe conversion",
        "Report agent output maps preserve string-key agent ids",
        "Report agent sequence ids normalize string values",
        "Report agent sequence payloads fall back to pipeline defaults",
        "Report tear-sheet target price display avoids duplicate currency prefixes",
        "Report audit banner final-audit child maps use mapping-safe conversion",
        "Report audit banner abnormality list fields use list-safe conversion",
        "Report audit banner abnormality list fields use truthiness-safe conversion",
        "Report audit banner abnormality text fields use shared text conversion",
        "Report audit banner Markdown abnormality bullets collapse embedded newlines",
        "Report reading notice quality gate text fields use shared text conversion",
        "Report reading notice Markdown gate text collapses embedded newlines",
        "Report reading notice quality gate record detection accepts mapping-safe gate payloads",
        "Report preview reading boundaries derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes",
        "Report preview reading boundaries prefer hash mismatch details over default generic snapshot integrity errors",
        "Report preview reading boundaries remove default generic snapshot integrity blocker text",
        "Report preview reading boundaries deduplicate repeated snapshot integrity error details",
        "Report reading notice snapshot integrity checks treat `valid=false` as blocked",
        "Report reading notice snapshot integrity checks let invalid `data.snapshot_integrity` override a conflicting verified top-level record",
        "Report reading notice snapshot integrity checks preserve the most specific invalid snapshot integrity detail",
        "Report reading notice snapshot integrity checks accept mapping-safe snapshot integrity payloads",
        "Report reading notice snapshot integrity checks downgrade recorded non-verified snapshots to warning",
        "Report reading notice snapshot integrity details deduplicate repeated error entries",
        "Report reading notice snapshot integrity details derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes",
        "Report reading notice snapshot integrity details prefer hash mismatch details over default generic snapshot integrity errors",
        "Report reading notice snapshot integrity details remove default generic blocker text",
        "Report view and HTML download paths re-check the current `.data.json` snapshot integrity",
        "Report Markdown download paths re-check the current `.data.json` snapshot integrity",
        "Report artifact view and download paths treat malformed or non-object `.data.json` snapshots as blocked",
        "Report artifact view and download paths treat missing `.data.json` snapshots as warning",
        "Report artifact view and download paths honor invalid `snapshot_integrity` recorded inside `.data.json`",
        "Report artifact view and download paths also honor invalid `data.snapshot_integrity` recorded inside `.data.json`",
        "Report artifact view and download paths let any recorded invalid snapshot integrity override a conflicting verified record",
        "Report artifact view and download paths preserve the most specific invalid snapshot integrity detail",
        "Report artifact view and download paths treat default generic snapshot integrity blocker text as less specific",
        "Report artifact view and download paths derive a `snapshot_hash mismatch` detail from recorded invalid snapshot integrity hashes",
        "Report artifact view and download paths prefer recorded hash mismatch details over default generic snapshot integrity errors",
        "Report artifact view and download paths remove default generic snapshot integrity errors when the same recorded error list also contains specific details",
        "Report artifact view and download paths deduplicate recorded snapshot integrity error details",
        "Report quality repair queue quality gate fields use dict-native field reads",
        "Report quality repair queue report identity fields use string-safe conversion",
        "Report quality repair queue quality gate text fields use string-safe conversion",
        "Report quality repair queue quality gate text fields treat lookup string conversion failures as blank",
        "Report quality repair queue reason codes use string-safe conversion",
        "Report quality repair queue stale source lists use string-safe conversion",
        "Report quality repair queue text list tuple sequences are evaluated before action prioritization",
        "Report quality repair queue reports envelopes use mapping-safe conversion",
        "Report quality repair queue snapshot integrity maps use mapping-safe conversion",
        "Report quality repair queue quality gate child maps use mapping-safe conversion",
        "Report quality repair queue quality gate child maps use Mapping traversal when `.items()` lookup fails",
        "Report quality repair queue quality gate child maps skip lookup item failures during Mapping traversal",
        "Report quality repair queue snapshot integrity verifier results treat `valid=false` as invalid",
        "Report quality repair queue snapshot integrity verifier results let `valid=false` override non-invalid status text",
        "Report quality repair queue snapshot integrity error details use string-safe conversion",
        "Report quality repair queue derives a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes",
        "Report quality repair queue prefers hash mismatch details over default generic snapshot integrity errors",
        "Report quality repair queue removes default generic snapshot integrity error details when specific provider or hash details exist",
        "Report quality repair queue deduplicates repeated snapshot integrity error details",
        "Shared mapping list conversions use native list and tuple iterators when iterator accessors fail",
        "Shared mapping text list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Shared mapping text list conversions treat lookup iterator failures as native-list fallbacks",
        "Shared mapping dict list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Shared mapping dict list conversions treat lookup iterator failures as native-list fallbacks",
        "Shared mapping traversal falls back to native dict items when custom items iterators fail before yielding",
        "Report quality repair queue provider alert lists preserve valid entries before iterator failures",
        "Report quality repair queue report collections preserve valid reports before iterator failures",
        "Report quality repair queue decision freshness detail fields use string-safe conversion",
        "Report quality repair queue decision freshness flags use bool-safe conversion",
        "Report quality repair queue decision freshness flags treat lookup truthiness failures as false",
        "Report quality repair queue limit uses integer-safe conversion",
        "Report quality repair queue limit uses the default cap on lookup integer conversion failures",
        "Outcome calibration quality signal fields use dict-native field reads",
        "Outcome calibration report identity fields use string-safe conversion",
        "Outcome calibration data trust score fields use float-safe fallback",
        "Outcome calibration row collections use list-safe normalization",
        "Outcome calibration decision freshness flags use bool-safe conversion",
        "Outcome calibration matched reports use dict-safe fallback",
        "Outcome calibration numeric fields use conversion-safe fallback",
        "Strategy evaluator numeric fields use conversion-safe fallback",
        "Strategy evaluator artifact fields use dict-native field reads",
        "Strategy evaluator hit flags use bool-safe fallback",
        "Strategy evaluator artifact iterators preserve valid entries before alpha model comparison",
        "Strategy evaluator artifact tuple sequences are evaluated before alpha model comparison",
        "Provider impact report fields use dict-native field reads",
        "Provider impact report, data trust, and alert maps use mapping-safe conversion",
        "Provider impact report, data trust, and alert maps use Mapping traversal when `.items()` lookup fails",
        "Provider impact report, data trust, and alert maps skip lookup item failures during Mapping traversal",
        "Provider impact report identity fields use string-safe conversion before provider recovery output",
        "Provider impact ticker identity uses string-safe conversion before provider recovery output",
        "Provider impact current fetch fields use bool-, integer-, and string-safe conversion",
        "Provider impact current fetch fields treat lookup integer and bool conversion failures as empty current-fetch evidence",
        "Provider impact alert text fields use string-safe conversion",
        "Provider impact reason codes use string-safe conversion",
        "Provider impact reason code iterators preserve valid entries before failures",
        "Provider impact text list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Provider impact text list conversions treat lookup iterator failures as native-list fallbacks",
        "Provider impact text list conversions treat lookup iterator creation failures as native-list fallbacks",
        "Provider impact alert iterators preserve valid entries before failures",
        "Provider impact ledger report iterators preserve valid reports before failures",
        "Provider impact ledger reports envelopes use mapping-safe conversion",
        "Provider impact tuple sequences are evaluated before provider recovery decisions",
        "Provider impact list conversions use native list and tuple iterators when iterator accessors fail",
        "Provider impact dict list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Provider impact dict list conversions treat lookup iterator failures as native-list fallbacks",
        "Provider impact dict list conversions treat lookup iterator creation failures as native-list fallbacks",
        "Provider impact ledger sort keys use string-safe conversion before ordering",
        "Daily decision queue action fields use dict-native field reads",
        "Notification plan action fields use dict-native field reads",
        "Notification delivery audit context fields use dict-native field reads",
        "Provider SLA window alert enrichment uses integer-, float-, and string-safe conversion",
        "Provider SLA alert policy basis selection uses dict-, integer-, float-, and string-safe conversion",
        "Data trust provider SLA evidence attempts use truthiness-safe integer and basis text conversion",
        "Data trust provider SLA evidence attempts treat lookup integer conversion failures as zero evidence",
        "Data trust provider SLA nested window maps use dict-safe conversion before evidence attempts",
        "Data trust provider SLA row maps fall back to native dict items when copy lookups fail",
        "Data trust provider SLA alert matching uses string-safe source, provider, level, and message conversion",
        "Data trust provider SLA source audit entries use string-, integer-, and bool-safe conversion",
        "Data trust provider SLA source audit entries treat lookup integer and bool conversion failures as empty current-fetch evidence",
        "Data trust provider SLA trust metadata uses list- and string-safe conversion",
        "Data trust provider SLA trust metadata uses shared text conversion",
        "Data trust provider SLA alert collections use iterable-safe conversion",
        "Data trust provider SLA source audit collections use iterable-safe conversion",
        "Data trust provider SLA rows use dict-safe conversion before matching current source audit entries and provider alerts",
        "Data trust provider SLA source data uses dict-safe conversion before reading current source audit rows",
        "Data trust provider SLA alert fetch failures fall back to existing trust",
        "Data trust provider SLA policy failures fall back to base trust before final score calculation",
        "Data trust provider SLA policy lookup failures fall back to base trust before final score calculation",
        "Data trust provider SLA policy failure fallback uses an unmutated base trust snapshot before final score calculation",
        "Data trust post-SLA status fields use canonical status normalization before final score calculation",
        "Data trust post-SLA list metadata fields are written back after string-list normalization before final score calculation",
        "Data trust post-SLA market timestamp fields use shared text normalization before final score output",
        "Data trust post-SLA provider SLA alert metadata uses dict-list normalization before final score output",
        "Data trust provider SLA trust metadata iterators preserve valid entries before failures",
        "Data trust provider SLA list conversions use native list and tuple iterators when iterator accessors fail",
        "Data trust provider SLA dict row conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Data trust provider SLA dict row conversions treat lookup iterator failures as native-list fallbacks",
        "Data trust provider SLA dict row conversions treat lookup iterator creation failures as native-list fallbacks",
        "Data trust provider SLA text list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Data trust provider SLA text list conversions treat lookup iterator failures as native-list fallbacks",
        "Data trust provider SLA text list conversions treat lookup iterator creation failures as native-list fallbacks",
        "Data trust normalization note fields use string-list conversion",
        "Data trust normalization provider SLA alert lists use dict-list safe conversion",
        "Data trust scoring audit source names use string-safe conversion",
        "Data trust audit entry text fields use string-safe conversion",
        "Data trust audit entry text fields use shared text conversion",
        "Data trust source audit append preserves tuple audit batches",
        "Report key evidence source fields use shared text conversion",
        "Report key evidence aggregated stale flags use bool-safe conversion",
        "Report key evidence data field presence checks ignore malformed scalar values",
        "Report key evidence data field presence checks use strip-safe shared text conversion",
        "Report key evidence Markdown cells escape table separators",
        "Report source audit table fields use shared text conversion",
        "Report source audit Markdown cells escape table separators",
        "Report source evidence numeric and boolean fields use safe conversion",
        "Report data trust summary fields use shared text conversion",
        "Report data trust quant fallback fields use truthiness-safe list conversion",
        "Report evidence matrix payload source fields use shared text conversion",
        "Report evidence matrix payload message fallback uses truthiness-safe field selection",
        "Report evidence matrix payload message fallback skips text-empty malformed values",
        "Report evidence matrix payload message presence checks use length-safe fallback",
        "Report evidence matrix payload message presence checks use strip-safe shared text conversion",
        "Report evidence matrix source audit child maps use mapping-safe conversion",
        "Report evidence matrix source row labels use shared text conversion",
        "Report evidence matrix Markdown cells use shared text conversion",
        "Report evidence matrix HTML cells use shared text conversion",
        "Report evidence matrix row fetched-at fields use truthiness-safe text conversion",
        "Report evidence matrix row status fields use truthiness-safe text conversion",
        "Report evidence matrix row provider fields use truthiness-safe text conversion",
        "Report evidence matrix stale-source flags use bool-safe conversion",
        "Report evidence matrix price-target basis excludes boolean values",
        "Report evidence matrix price-target basis excludes non-finite numeric values",
        "Report evidence matrix price-target scenario keys skip malformed text",
        "Report evidence matrix recommendation-basis keys use shared text conversion",
        "Report evidence matrix recommendation-basis values use equality-safe text checks",
        "Report evidence matrix recommendation-basis string values use strip-safe shared text conversion",
        "Report evidence matrix moat-score basis skips malformed metric keys",
        "Report evidence matrix limitation notes use shared text conversion",
        "Report evidence matrix limitation notes use text-list safe conversion",
        "Data trust audit entry status uses string-safe conversion",
        "Data trust audit entry duration fields ignore boolean millisecond overrides before epoch delta fallback",
        "Data trust audit entry duration fields ignore non-finite millisecond overrides before epoch delta fallback",
        "Data trust audit entry duration fields ignore overflowing millisecond overrides before epoch delta fallback",
        "Data trust audit entry duration fields ignore non-finite epoch timestamps before delta calculation",
        "Data trust audit entry duration fields ignore overflowing epoch timestamps before delta calculation",
        "Data trust audit entry duration fields reject out-of-range epoch timestamps before delta calculation",
        "Data trust audit entry fetched-at fields use shared text conversion before epoch fallback",
        "Data trust audit entry fetched-at epoch fallback validates explicit epoch values before finished-at fallback",
        "Data trust audit entry fetched-at epoch fallback treats out-of-range epoch values as malformed",
        "Data trust audit entry finished-at current-time fallback validates epoch values before source audit output",
        "Data trust audit entry record counts use integer-safe conversion",
        "Data trust audit entry record counts treat boolean values as malformed counts",
        "Data trust audit entry record counts treat fractional numeric values as malformed counts",
        "Data trust audit entry boolean fields use bool-safe conversion",
        "Data trust audit entry boolean fields treat lookup truthiness failures as false",
        "Data trust audit entry boolean text fields parse explicit false strings before truthiness fallback",
        "Data trust audit entry boolean binary fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean non-finite numeric fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean numeric fields only accept explicit zero or one values before truthiness fallback",
        "Data trust audit entry boolean real-number fields apply the same explicit zero or one contract",
        "Data trust audit entry boolean overflowing real-number fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean numeric text fields apply the same finite zero or one contract",
        "Data trust audit entry boolean free-form text fields are treated as malformed after explicit true, false, and numeric parsing",
        "Data trust audit entry boolean complex fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean container fields are treated as malformed before truthiness fallback",
        "Prompt source audit summary fields use string-, integer-, and bool-safe conversion",
        "Prompt source audit summary text fields use shared text conversion",
        "Prompt source audit root source data uses dict-native field reads",
        "Prompt source audit entry fields use dict-native field reads",
        "Prompt data trust list fields use truthiness- and iterator-safe conversion",
        "Prompt data trust source data uses dict-native field reads",
        "Prompt data trust fields use dict-native field reads",
        "Prompt company identity mapping uses truthiness-safe handoff",
        "Prompt company identity fields use dict-native field reads",
        "Prompt company identity source data uses dict-native field reads",
        "Prompt company metadata source data uses dict-native field reads",
        "Agent runtime identity guard uses truthiness-safe company identity handoff",
        "Agent runtime identity guard mapping length checks tolerate malformed length access",
        "Agent runtime identity guard mapping access uses dict-native field reads",
        "Agent runtime identity guard ticker fields use string-safe conversion",
        "Agent runtime identity guard text fields use string-safe conversion",
        "Agent runtime identity guard alias lists use iterator-safe string conversion",
        "Agent runtime identity guard alias native lists preserve limits",
        "Agent runtime identity guard templates use string-safe formatting",
        "Agent runtime identity guard runtime rules use dict-native field reads",
        "Agent runtime identity guard values use dict-native field reads",
        "Agent runtime identity guard source data uses dict-native field reads",
        "Agent runtime RAG context mapping uses truthiness-safe handoff",
        "Agent runtime RAG context text uses string-safe conversion",
        "Agent runtime temporal memory reflection prompt uses string-safe conversion",
        "Agent runtime temporal memory backtests use iterator- and JSON-safe conversion",
        "Agent runtime prompt safety helpers are split from prompt assembly",
        "Agent runtime top-level rule sections use dict-native field reads",
        "Agent runtime prompt JSON dict items use dict-native field reads",
        "Agent runtime prompt JSON sequence items use native iterators",
        "Agent runtime prompt JSON collection items use native iterators",
        "Agent runtime structured instructions mappings use dict-native traversal",
        "Agent runtime rule section mappings use dict-native lookup",
        "Agent runtime rule block configs use dict-native field reads",
        "Agent runtime rule list mappings use dict-native field reads",
        "Agent runtime state view uses JSON-safe conversion",
        "Agent runtime forensic warning uses string-safe conversion",
        "Agent runtime retry and audit instruction fields use string-safe conversion",
        "Agent runtime final audit mappings use dict-native field reads",
        "Agent runtime final audit pipeline id uses string-safe conversion",
        "Agent runtime final audit rule lists use string-safe conversion",
        "Agent runtime prompt rule blocks use string-safe conversion",
        "Agent runtime output cleanliness mappings use dict-native field reads",
        "Agent runtime output cleanliness rules use string-safe conversion",
        "Agent runtime assistant task prompt mappings use dict-native field reads",
        "Agent runtime assistant task prompts use string-safe conversion",
        "Agent runtime primary probe flag uses bool-safe conversion",
        "Prompt freshness mappings use truthiness-safe handoff",
        "Prompt freshness source data uses dict-native field reads",
        "Prompt market data source data uses dict-native field reads",
        "Prompt valuation metrics source data uses dict-native field reads",
        "Prompt TTM financials source data uses dict-native field reads",
        "Prompt cash flow source data uses dict-native field reads",
        "Prompt balance sheet source data uses dict-native field reads",
        "Prompt growth source data uses dict-native field reads",
        "Prompt financial history source data uses dict-native field reads",
        "Prompt institutional trading mapping uses truthiness-safe handoff",
        "Prompt institutional trading source data uses dict-native field reads",
        "Prompt full market catalyst items use truthiness- and iterator-safe conversion",
        "Prompt market catalyst source data uses dict-native field reads",
        "Prompt peer context source data uses dict-native field reads",
        "Prompt full dynamic peer metrics use truthiness- and iterator-safe conversion",
        "Prompt full peer discovery results use truthiness- and iterator-safe conversion",
        "Prompt supplemental source data uses dict-native field reads",
        "Prompt full recent monthly revenue text uses truthiness- and iterator-safe conversion",
        "Prompt full data quality notes use truthiness- and iterator-safe conversion",
        "Prompt PE river chart source data uses dict-native field reads",
        "Prompt full PE river chart mapping uses truthiness-safe handoff",
        "Prompt compact list fields use truthiness- and iterator-safe conversion",
        "Prompt compact PE river chart mapping uses truthiness-safe handoff",
        "Prompt compact PE river chart fields use dict-native field reads",
        "Prompt compact PE river years use truthiness- and iterator-safe tail conversion",
        "Prompt cross-check source data uses dict-native field reads",
        "Prompt history rows use truthiness- and iterator-safe year conversion",
        "Prompt history value fields use truthiness- and iterator-safe sequence conversion",
        "Prompt history source data uses dict-native field reads",
        "Prompt agent context fields use truthiness-safe presence checks",
        "Prompt agent context source data uses dict-native field reads",
        "Prompt data trust payload accepts mapping-safe trust maps before prompt output",
        "Data trust string list conversion uses string-safe conversion",
        "Data trust string list conversion uses native list and tuple iterator fallback",
        "Data trust string list conversion drops non-finite numeric items",
        "Data trust score normalization uses float-safe conversion",
        "Data trust score normalization treats lookup conversion failures as malformed scores",
        "Data trust score normalization treats boolean score values as malformed",
        "Data trust normalization accepts mapping-safe trust payloads before field normalization",
        "Data trust normalization uses dict-native trust field reads",
        "Data trust normalization market timestamp fields use shared text conversion",
        "Data trust build source payloads accept mapping-safe inputs before scoring",
        "Data trust build source data uses mapping- and dict-list-safe conversion",
        "Data trust build source freshness child maps use mapping-safe conversion",
        "Data trust build source freshness stale flags use bool-safe conversion",
        "Data trust build data source notes use string-list conversion",
        "Data trust latest audit rows use mapping-safe conversion",
        "Data trust optional source status selection uses mapping-safe row conversion",
        "Data trust usable critical data checks use mapping-safe audit conversion",
        "Data trust source audit status comparisons use string-safe conversion",
        "Data trust last-market timestamp fallback uses string-safe conversion",
        "Data trust post-SLA trust metadata uses mapping-safe conversion",
        "Data trust snapshot existing trust selection uses dict-safe conversion",
        "Data trust snapshot existing trust selection accepts mapping-safe payloads",
        "Data trust snapshot root context accepts mapping-safe payloads before metadata selection",
        "Data trust snapshot source data accepts mapping-safe payloads before trust scoring",
        "Data trust snapshot refresh flags use bool-safe conversion",
        "Data trust snapshot refresh flags treat lookup truthiness failures as false",
        "Data trust snapshot rerun context text uses string-safe conversion",
        "Data trust snapshot sanitizer uses string-safe key and value conversion",
        "Data trust snapshot sanitizer uses native list and tuple iterators when iterator accessors fail",
        "Data trust snapshot sanitizer falls back to native list and tuple iterators when custom sequence iterators fail before yielding",
        "Data trust snapshot sanitizer uses native dict items when items accessors fail",
        "Data trust snapshot sanitizer falls back to native dict items when custom items iterables fail",
        "Data trust snapshot integrity hash lookup uses string-safe conversion",
        "Snapshot maintenance verify-snapshots uses verifier-derived hash presence",
        "Data trust snapshot integrity and schema validators use dict-native snapshot field reads",
        "Data trust snapshot integrity and schema validators fall back to item lookup when mapping field accessors fail",
        "Data trust snapshot rerun context agent keys use string-safe conversion",
        "Data trust snapshot content hash keys use string-safe conversion",
        "Data trust snapshot content hashing uses iterator-safe mapping traversal",
        "Data trust snapshot content hash accepts mapping snapshot wrappers before integrity verification",
        "Data trust snapshot size governance uses snapshot sanitizer input",
        "Data trust snapshot size byte calculation uses snapshot sanitizer input",
        "Data trust snapshot builds use dict-native context and data field reads",
        "Data trust snapshot identity fields use string-safe context/data selection",
        "Data trust snapshot identity fields use shared text conversion",
        "Data trust reproducibility source audit metadata uses string-safe provider and timestamp extraction",
        "Data trust reproducibility source audit metadata uses dict-list safe conversion",
        "Data trust reproducibility source audit helpers accept mapping-safe data wrappers",
        "Data trust reproducibility packets use dict-native context, data, source audit, and metadata field reads",
        "Data trust reproducibility packets accept mapping-safe context, data, source audit, and metadata wrappers",
        "Data trust reproducibility packets preserve validated full prompt fingerprints",
        "Prompt fingerprints cover agent templates, state-view policy, system prompts, and runtime prompt rules",
        "Prompt identity and prompt injection share one process-stable runtime-rule snapshot",
        "Runtime code provenance records commit and dirty state once per workflow",
        "Data trust explicit target price detection uses dict-native root field reads",
        "Data trust explicit target price detection accepts mapping-safe root and nested maps",
        "Data trust explicit target price detection uses string-safe key and value conversion",
        "Data trust explicit target price detection preserves valid list items before iterator failures",
        "Data trust explicit target price detection accepts tuple sequences before guardrail output",
        "Data trust explicit target price detection uses native list iterators when iterator accessors fail",
        "Data trust explicit target price detection uses native list iterators when custom iterators fail before yielding",
        "Data trust explicit target price detection treats lookup list iterator failures as native list fallbacks",
        "Data trust explicit target price detection preserves valid mapping items before iterator failures",
        "Data trust explicit target price detection uses native dict items when items accessors fail",
        "Data trust explicit target price detection uses native dict items when custom items iterables fail to create iterators",
        "Data trust explicit target price detection uses native dict items when custom items iterators fail before yielding",
        "Data trust explicit target price detection treats lookup mapping item failures as native dict item fallbacks",
        "Data trust explicit target price detection ignores non-finite numeric targets",
        "Data trust source record counting uses string-safe source keys",
        "Data trust source record counting normalizes root data maps before field reads",
        "Data trust source record counting normalizes institutional trading maps before field reads",
        "Data trust source record counting ignores empty institutional trading daily-only payloads before fallback counting",
        "Data trust source record counting normalizes global market context maps before field reads",
        "Data trust source record counting normalizes international news context maps before field reads",
        "Data trust source record counting normalizes P/E river chart maps before field reads",
        "Data trust source record counting normalizes P/E river chart band maps before counting valuation rows",
        "Data trust source record counting falls back from empty P/E river chart band series to year or EPS rows",
        "Data trust source record counting normalizes default source mapping values before counting keys",
        "Data trust source record counting counts only default source mapping keys with present child values",
        "Data trust source record counting uses sequence-safe tuple value presence checks",
        "Data trust source record counting uses item-aware sequence value presence checks",
        "Data trust source record counting uses mapping-safe value presence checks",
        "Data trust source record counting uses child-aware mapping value presence checks",
        "Data trust source record counting uses set-aware value presence checks",
        "Data trust source record counting treats boolean scalar values as missing evidence",
        "Data trust source record counting treats non-finite numeric scalar values as missing evidence",
        "Data trust source record counting treats overflowing numeric scalar values as missing evidence",
        "Data trust source record counting treats non-finite numeric string values as missing evidence",
        "Data trust source record counting treats placeholder string values as missing evidence",
        "Data trust source record counting treats non-finite Decimal scalar values as missing evidence",
        "Data trust source record counting treats binary scalar values as missing evidence",
        "Data trust source record counting treats complex scalar values as missing evidence",
        "Data trust source record counting uses native list and tuple iterator fallback",
        "Data trust source record counting treats tuple source values as row batches",
        "Data trust source record counting treats set and frozenset source values as row batches",
        "Data trust source record counting uses native set and frozenset iterator fallback",
        "Data trust source record counting treats lookup set iterator failures as native set and frozenset fallbacks",
        "Data trust source record counting uses truthiness-safe value presence checks",
        "Provider SLA window selection uses string-safe conversion",
        "Provider SLA window maps use dict-safe conversion",
        "Provider SLA nested window numeric fields use integer- and finite-float-safe conversion",
        "Provider SLA numeric field shaping uses dict-safe row conversion before provider and window output",
        "Provider SLA numeric field shaping uses strict numeric conversion before provider and window output",
        "Provider SLA nested window maps keep only canonical `last_1h`, `last_24h`, and `last_7d` buckets",
        "Provider SLA nested window keys use shared text conversion",
        "Provider SLA selected-window helper output normalizes nested `windows` maps",
        "Provider SLA selected-window numeric fields use integer- and finite-float-safe conversion",
        "Provider SLA provider rows use dict-safe conversion before window selection",
        "Provider SLA alert projection uses dict-safe row conversion and string-safe alert-level conversion",
        "Provider SLA alert projection output fields use string-, finite-float-, and dict-safe conversion",
        "Provider SLA alert projection text fields use shared text conversion",
        "Provider SLA all-window cumulative alerts reuse the same safe alert projection",
        "Provider SLA all-window provider summaries use dict-safe row conversion before returning dashboard payloads",
        "Provider SLA all-window provider numeric fields use integer- and finite-float-safe conversion",
        "Provider SLA payload summary fetch failures fall back to empty provider lists",
        "Provider SLA payload alert fetch failures fall back to empty alert lists",
        "Prometheus provider alert level rendering uses string-safe conversion",
        "Notification delivery failure reason bucketing uses shared text conversion",
        "Notification delivery summary channel counts use string-safe channel conversion",
        "Notification delivery summary status counts use string-safe status conversion",
        "低基數",
        "raw `last_error`",
        'state="ok"',
        'state="warning"',
        "one-hot",
        "context snapshot",
        "attention_contexts",
        "Audit context source key normalization uses string-safe text conversion before deriving fallback labels",
        "Audit context snapshot presence checks tolerate malformed equality comparisons before preserving optional outbox metadata",
        "Notification delivery attempt result fields use string-safe status, error, and response id conversion",
        "Notification delivery outbox identity fields use string-safe required text extraction",
        "Notification delivery audit persistence evaluates mapping outbox entries before identity and context extraction",
        "Notification delivery audit persistence rejects malformed mapping outbox entries with required identity errors",
        "Notification delivery audit listing uses string-safe integer limit conversion",
        "Notification delivery reconcile preflight uses string-safe delivery key lookup",
        "Notification delivery reconcile preflight treats missing outbox entries as an empty list",
        "Notification delivery reconcile preflight evaluates tuple outbox entry batches before audit lookup",
        "Notification delivery reconcile preflight evaluates mapping outbox entries before audit lookup",
        "Notification delivery reconcile preflight skips malformed mapping outbox entries before audit lookup",
        "Notification delivery reconcile attempt counts use string-safe integer conversion",
        "Notification delivery reconcile retry budgets treat `None` max attempts as the default retry budget",
        "Notification delivery reconcile retry timestamps use string-safe float conversion",
        "Notification delivery reconcile retry backoff treats `None` as the default backoff window",
        "Notification delivery reconcile statuses use string-safe text conversion",
        "Notification delivery reconcile text metadata uses string-safe conversion",
        "Notification delivery response ids are stripped before record and sender preflight output",
        "Notification delivery reconcile audit context uses dict-safe conversion",
        "Notification delivery audit context maps use JSON-safe dict conversion before reconcile and summary output",
        "Notification delivery audit context preserves mapping metadata values before JSON serialization",
        "Notification delivery audit context drops whitespace-only metadata before JSON serialization",
        "Notification delivery audit context drops empty collection metadata after normalization",
        "Notification delivery audit context partial sequence metadata is normalized before empty collection filtering",
        "Notification delivery audit context JSON parsing uses string-safe conversion before loading persisted context",
        "Notification attention context record serialization uses string-safe text, integer, and dict conversion",
        "Notification attention context identity fields are stripped before summary output",
        "Notification attention context limit handling treats `None` as the default cap before summary output",
        "`decision_queue.summary` exposes `source_labels` and `source_texts`",
    ]:
        assert expected in api_reference

    for expected in [
        "/metrics",
        "stock_agent_notification_delivery_count",
        "stock_agent_notification_delivery_channel_count",
        "stock_agent_notification_delivery_failure_reason_count",
        "stock_agent_notification_delivery_health",
        "Notification delivery summary fetch failures fall back to empty delivery summaries for Prometheus",
        "Ops dashboard notification delivery summary fetch failures fall back to empty delivery summaries",
        "Ops dashboard API quota payload failures fall back to empty quota services",
        "Ops dashboard malformed API quota payloads fall back to empty quota services",
        "Ops dashboard API quota service lists use list-of-dict safe conversion before payload output",
        "Ops dashboard API quota numeric and observation fields use strict string/count conversion before payload output",
        "Ops dashboard job snapshot failures fall back to empty job sections",
        "Ops dashboard malformed job payloads fall back to empty job sections",
        "Ops dashboard nested job sections use dict-safe conversion before payload output",
        "Ops dashboard job unavailable status flags use bool-safe conversion",
        "Ops dashboard stuck job count status aggregation uses dict- and integer-safe conversion",
        "Ops dashboard stuck job count fields use strict count conversion before status and payload output",
        "Ops dashboard malformed provider payloads fall back to an empty last_24h provider state",
        "Ops dashboard provider selected windows use string-safe conversion before payload output",
        "Ops dashboard malformed provider alert lists fall back to empty alerts",
        "Ops dashboard provider alert impact classification uses string-safe source conversion",
        "Ops dashboard provider alert level comparison uses string-safe conversion before status and count aggregation",
        "Ops dashboard provider alert success-rate fields use finite-float conversion before payload output",
        "Ops dashboard provider alert text and window fields use string- and dict-safe conversion before payload output",
        "Provider SLA dashboard alert payload fields use dict-native field reads before impact classification",
        "Notification delivery observability summaries use dict-safe conversion before rendering dashboard and Prometheus maps",
        "Notification delivery observability fields use dict-native field reads before attention, dashboard, and Prometheus rendering",
        "Notification delivery observability counts use integer-safe conversion before rendering dashboard and Prometheus gauges",
        "Notification delivery observability counts use strict count conversion before rendering dashboard and Prometheus gauges",
        "Notification delivery dashboard count maps use shared text keys and integer-safe values before payload output",
        "Notification delivery Prometheus channel and reason labels use shared text conversion with unknown fallback",
        "Prometheus label rendering uses shared text conversion with unknown fallback",
        "Prometheus provider summary fetch failures fall back to empty provider series",
        "Prometheus provider summary non-iterable payloads fall back to empty provider series",
        "Prometheus provider summary iterator failures preserve provider rows parsed before the failure",
        "Prometheus queue snapshot fetch failures fall back to unknown/zero queue gauges",
        "Ops dashboard queue snapshot fetch failures fall back to an unavailable unknown queue status",
        "Ops dashboard queue availability uses bool-safe conversion before status aggregation and payload output",
        "Ops dashboard queue metadata uses string-, integer-, and dict-safe conversion before payload output",
        "Ops dashboard named queue details use string-key and dict-safe conversion before payload output",
        "Ops dashboard named queue detail fields use integer-, string-, and registry-map safe conversion before payload output",
        "Ops dashboard queue integer fields use strict count conversion before payload output",
        "Ops dashboard queue supplemental fields use integer-, float-, string-, and registry-map safe conversion before payload output",
        "Ops dashboard queue text metadata uses shared text conversion before payload output",
        "Ops dashboard queue age fields use finite-float conversion before payload output",
        "Ops dashboard queue age fields use strict finite-float conversion before payload output",
        "Observability dashboard and Prometheus payload shaping uses payload-safe mapping conversion",
        "Ops dashboard free mode provider summaries use dict-, list-, bool-, and string-safe conversion before payload output",
        "Ops dashboard free mode violations use string-safe conversion before payload output",
        "Ops dashboard free mode provider tiers and violations use shared text conversion instead of persistence JSON pruning",
        "Prometheus queue snapshots use dict-safe conversion before rendering queue gauges",
        "Prometheus queue backend and queue name rendering uses string-safe conversion",
        "Prometheus queue availability rendering uses bool-safe conversion",
        "Prometheus named queue depth maps use payload-safe conversion",
        "Prometheus queue depth gauges use strict count conversion",
        "Prometheus integer gauges use integer-safe conversion",
        "Prometheus float gauges use float-safe conversion",
        "Prometheus provider numeric gauges use strict numeric conversion",
        "Prometheus provider rows use dict-safe conversion before rendering provider gauges",
        "Report conformance quality gate inputs use dict-native field reads",
        "Report conformance quality gate inputs accept mapping-safe wrappers",
        "Report conformance quality gate issue lists use sequence-safe conversion",
        "Report conformance visible artifact and gate status text fields use safe text fallback",
        "Report content credibility evidence matrix rows use sequence-safe conversion",
        "Report content credibility evidence matrix row maps use mapping-safe conversion",
        "Report content credibility quality gate inputs use mapping-safe conversion",
        "Report content credibility recommendation and gate text fields use safe text fallback",
        "Report renderer lint repair result fields use dict-native field reads",
        "Report execution summary quality gate fields use dict-native field reads",
        "Report execution summary quality gate child maps use mapping-safe conversion",
        "Report execution summary text fields use shared text conversion",
        "Report execution summary Markdown text fields collapse embedded newlines",
        "Report mode template display fields use shared text conversion",
        "Report mode template visual focus and reading path fields use shared text-list conversion",
        "Report mode template Markdown display fields collapse embedded newlines",
        "Report summary and decision discipline display fields use shared text conversion",
        "Report tear-sheet recent catalyst rows use dict-list safe conversion",
        "Report investment-thesis final-audit warning rows use text-list safe conversion",
        "Report investment-thesis final-audit critical rows use text-list safe conversion",
        "Report investment-thesis agent analysis text uses truthiness-safe fallback",
        "Report investment-thesis current price display uses truthiness-safe fallback",
        "Report investment-thesis moat score display uses shared text conversion",
        "Report investment-thesis prebuilt payloads use mapping-safe conversion",
        "Report Markdown renderer prebuilt investment-thesis payloads use mapping-safe handoff",
        "Report PE river chart payload uses truthiness-safe mapping handoff",
        "Report PE river chart payload accepts mapping-safe chart wrappers",
        "Report investment-thesis source audit rows use dict-list safe conversion",
        "Report investment-thesis history series use sequence-safe conversion",
        "Report investment-thesis Markdown list fields use text- and dict-list safe conversion",
        "Report investment-thesis Markdown display fields collapse embedded newlines",
        "Report investment-thesis recommendation and trade setup mappings use mapping-item safe conversion",
        "Report investment-thesis structured scenario triggers use dict-list safe conversion",
        "Report investment-thesis data trust status uses text-safe comparison",
        "Report HTML sanitizer uses truthiness-safe string conversion",
        "Report plain-text sanitizer uses truthiness-safe string conversion",
        "Report cover image URL sanitizer uses truthiness-safe string conversion",
        "Report next catalyst list fields use dict-list safe conversion",
        "Report structured-output child maps use mapping-safe conversion",
        "Report structured-output schema-derived next catalysts accept mapping-safe root payloads",
        "Report structured-output schema-derived next catalysts treat null catalyst lists as derivable",
        "Report structured-output schema-derived next catalysts treat non-list catalyst payloads as derivable",
        "Report structured-output schema-derived next catalysts treat non-mapping catalyst rows as derivable",
        "Report structured-output schema-derived next catalysts keep valid mapping catalyst rows",
        "Report structured-output schema-derived next catalysts filter schema-invalid mapping catalyst rows",
        "Report structured-output catalyst text fields use safe text fallback",
        "Report structured-output scenario-trigger text fields use safe text fallback",
        "Report structured-output schema-derived next catalysts use safe scenario-trigger text",
        "Report structured-output schema-derived next catalysts enforce scenario-trigger minimum lengths",
        "Report structured-output schema-derived scenario triggers use minimum fallback",
        "Report structured-output schema-derived scenario trigger collections use list-safe fallback",
        "Report structured-output scenario-trigger collections use missing-field fallback",
        "Report structured-output missing scenario-trigger fallback drives schema-derived next catalysts",
        "Report structured-output schema-derived next catalysts truncate overlong scenario-trigger lists",
        "Report structured-output executive-thesis root payloads use mapping-safe fallback",
        "Report structured-output executive-thesis text fields use safe text fallback",
        "Report structured-output executive-thesis resolved-contradiction list items use safe text fallback",
        "Report structured-output confidence-basis lists use safe text conversion",
        "Report structured-output confidence-basis required lists use minimum fallback",
        "Report structured-output confidence-basis required list collections use list-safe fallback",
        "Report structured-output confidence-basis root payloads use mapping-safe fallback",
        "Report structured-output confidence-basis objects use missing-field fallback",
        "Report structured-output reasoning steps use safe text conversion",
        "Report structured-output reasoning steps use minimum fallback",
        "Report structured-output reasoning step collections use list-safe fallback",
        "Report structured-output recommendation labels use canonical alias normalization",
        "Report structured-output recommendation labels use missing-field fallback",
        "Report structured-output recommendation text fields use safe text fallback",
        "Report structured-output recommendation text fields use missing-field fallback",
        "Report structured-output analysis markdown uses safe text fallback",
        "Report structured-output analysis markdown fields use missing-field fallback",
        "Report structured-output recommendation root payloads use mapping-safe fallback",
        "Report structured-output recommendation objects use missing-field fallback",
        "Report structured-output recommendation field root payloads use mapping-safe fallback",
        "Report structured-output bubble-sniper root payloads use mapping-safe fallback",
        "Report structured-output bubble-sniper recommendation field root payloads use mapping-safe fallback",
        "Report structured-output moat analysis markdown uses safe text fallback",
        "Report structured-output moat root payloads use mapping-safe fallback",
        "Report structured-output moat reasoning steps use minimum fallback",
        "Report structured-output moat reasoning-step collections use list-safe fallback",
        "Report structured-output moat-score containers use mapping-safe fallback",
        "Report structured-output moat-score containers use missing-field fallback",
        "Report structured-output moat-score values use safe number fallback",
        "Report structured-output price-target analysis markdown uses safe text fallback",
        "Report structured-output price-target root payloads use mapping-safe fallback",
        "Report structured-output price-target containers use mapping-safe fallback",
        "Report structured-output price-target containers use missing-field fallback",
        "Report structured-output price-target direct target containers use mapping-safe fallback",
        "Report structured-output price-target text fields use safe text fallback",
        "Report structured-output price-target valuation-summary containers use mapping-safe fallback",
        "Report structured-output price-target valuation-summary containers use missing-field fallback",
        "Report structured-output price-target direct valuation-summary containers use mapping-safe fallback",
        "Report structured-output price-target valuation-summary boolean fields use bool-safe fallback",
        "Report structured-output price-target values use safe number fallback",
        "Report structured-output price-target DCF scenario values use safe number fallback",
        "Report structured-output price-target DCF scenario rows use row-safe filtering",
        "Report structured-output price-target DCF scenario names use enum-safe filtering",
        "Report structured-output price-target direct DCF scenario names use enum-safe fallback",
        "Report structured-output price-target DCF scenario collections use list-safe fallback",
        "Report structured-output price-target direct DCF scenario root payloads use mapping-safe fallback",
        "Report structured-output management-sentiment analysis markdown uses safe text fallback",
        "Report structured-output management-sentiment root payloads use mapping-safe fallback",
        "Report structured-output management-sentiment text fields use safe text fallback",
        "Report structured-output management-highlight root payloads use mapping-safe fallback",
        "Report structured-output management-sentiment highlight rows use row-safe fallback",
        "Report structured-output management-sentiment highlight collections use list-safe fallback",
        "Report structured-output management-sentiment highlight collections use missing-field fallback",
        "Report structured-output management-sentiment short highlight collections use minimum-count fallback",
        "Report structured-output management-sentiment confidence uses safe number fallback",
        "Report structured-output downside-risk analysis markdown uses safe text fallback",
        "Report structured-output downside-risk root payloads use mapping-safe fallback",
        "Report structured-output downside-risk root rows use mapping-safe fallback",
        "Report structured-output downside-risk text fields use safe text fallback",
        "Report structured-output downside-risk rows use row-safe fallback",
        "Report structured-output downside-risk collections use list-safe fallback",
        "Report structured-output downside-risk collections use missing-field fallback",
        "Report structured-output downside-risk short collections use minimum-count fallback",
        "Report structured-output downside-risk confidence uses safe number fallback",
        "Report structured-output trade-plan text fields use safe text fallback",
        "Report structured-output trade-plan root payloads use mapping-safe fallback",
        "Report structured-output normalizer payloads use mapping-safe conversion",
        "Report structured-output normalizer scalar root payloads use schema fallback",
        "Report structured-output normalizer reasoning steps use safe text conversion",
        "Report structured-output normalizer reasoning-step empty lists use minimum fallback",
        "Report structured-output normalizer reasoning-step null values use minimum fallback",
        "Report structured-output normalizer reasoning-step scalar objects use minimum fallback",
        "Report structured-output normalizer scenario trigger rows use dict-list and safe text conversion",
        "Report structured-output normalizer scenario trigger mapping fields use minimum fallback",
        "Report structured-output normalizer scenario trigger mapping fields enforce schema minimum lengths",
        "Report structured-output normalizer scenario trigger fallback rows use schema-safe placeholder text",
        "Report structured-output normalizer scenario trigger empty lists use minimum fallback",
        "Report structured-output normalizer scenario trigger null values use minimum fallback",
        "Report structured-output normalizer scenario trigger scalar collections use minimum fallback",
        "Report structured-output normalizer scenario trigger lists use schema-limit truncation",
        "Report structured-output normalizer scenario trigger fallback rows are deferred",
        "Report structured-output normalizer confidence-basis lists use safe text conversion",
        "Report structured-output normalizer confidence-basis required lists use minimum fallback",
        "Report structured-output normalizer confidence-basis required list collections use list-safe fallback",
        "Report structured-output normalizer confidence-basis empty required lists use minimum fallback",
        "Report structured-output normalizer recommendation text fields use safe text conversion",
        "Report structured-output normalizer bubble-sniper recommendation labels use avoid fallback",
        "Report structured-output normalizer next-catalyst text fields use safe text conversion",
        "Report structured-output normalizer next-catalyst trigger fields enforce schema minimum length",
        "Report structured-output normalizer next-catalyst fallback rows use schema-safe trigger text",
        "Report structured-output normalizer next-catalyst empty lists derive from scenario triggers",
        "Report structured-output normalizer empty next-catalyst lists derive from missing scenario-trigger fallback",
        "Report structured-output normalizer next-catalyst fallback rows are deferred",
        "Report structured-output normalizer price-target numbers exclude boolean values",
        "Report structured-output normalizer price-target values use safe number fallback",
        "Report structured-output normalizer price-target missing objects use validated fallback targets",
        "Report structured-output normalizer moat-score numbers exclude boolean values",
        "Report structured-output normalizer moat-score fields use safe number fallback",
        "Report structured-output normalizer moat-score missing objects use validated fallback scores",
        "Report structured-output normalizer moat analysis markdown uses safe text conversion",
        "Report moat legacy text surfaces reasoning steps from structured outputs",
        "Report legacy reasoning-step text skips single-character fragments",
        "Report structured-output normalizer management-confidence numbers exclude boolean values",
        "Report structured-output normalizer management-confidence numbers use safe fallback",
        "Report management-sentiment legacy text surfaces confidence from structured outputs",
        "Report management-sentiment legacy text uses quote fallback for empty highlights",
        "Report management-sentiment legacy text uses highlight fallback for single-character fragments",
        "Report management-sentiment legacy text uses fallback row for empty highlights",
        "Report management-sentiment legacy text uses guidance-tone fallback for invalid metadata",
        "Report management-sentiment legacy text uses analysis body fallback for single-character fragments",
        "Report structured-output normalizer management-sentiment text fields use safe text conversion",
        "Report structured-output normalizer management-sentiment highlight rows use sequence-safe fallback",
        "Report structured-output normalizer management-sentiment highlight collections use missing-field fallback",
        "Report structured-output normalizer management-sentiment empty highlight lists use minimum fallback",
        "Report structured-output normalizer management-sentiment highlight fallback rows are deferred",
        "Report structured-output normalizer downside-risk confidence numbers exclude boolean values",
        "Report structured-output normalizer downside-risk confidence preserves explicit zero values",
        "Report structured-output normalizer downside-risk confidence numbers use safe fallback",
        "Report structured-output normalizer downside-risk text fields use safe text conversion",
        "Report structured-output normalizer downside-risk collections use missing-field fallback",
        "Report structured-output normalizer downside-risk empty lists use minimum fallback",
        "Report structured-output normalizer downside-risk fallback rows are deferred",
        "Report structured-output legacy price-target rendering uses exception-safe number conversion",
        "Report structured-output legacy price-target rendering excludes non-finite numbers",
        "Report structured-output legacy price-target rendering preserves single scientific-notation numeric strings",
        "Report valuation legacy text uses fallback row for empty price targets",
        "Report structured-output normalizer price-target scenario keys use safe text conversion",
        "Report structured-output normalizer price-target reasoning fields use safe text conversion",
        "Report structured-output normalizer valuation-summary text fields use safe text conversion",
        "Report structured-output normalizer valuation-summary boolean fields use bool-safe conversion",
        "Report structured-output normalizer DCF scenario rows use safe finite-number conversion",
        "Report structured-output normalizer DCF scenario numeric fields use safe number fallback",
        "Report structured-output normalizer trade-plan text fields use safe text conversion",
        "Report structured-output normalizer trade-plan enum fields use literal fallback",
        "Report structured-output normalizer trade-plan analysis markdown uses safe text projection",
        "Report Agent 19 required structured sections use dict-list safe scenario triggers",
        "Report Agent 19 required structured trigger rows collapse embedded newlines",
        "Report Agent 19 required structured trigger rows use action fallback",
        "Report recommendation block skips mapping-safe nested confidence-basis maps",
        "Report recommendation block display keys use shared text conversion",
        "Report recommendation block uses fallback row for empty standard recommendations",
        "Report Agent 19 recommendation ordered values use shared text conversion",
        "Report recommendation block Markdown display rows collapse embedded newlines",
        "Report recommendation tail basis and trigger fields use shared text conversion",
        "Report recommendation tail confidence-basis bullets skip single-character fragments in legacy reports",
        "Report recommendation tail trigger actions use fallback text in legacy reports",
        "Report recommendation tail trigger conditions skip single-character fragments in legacy reports",
        "Report recommendation tail trigger actions use fallback for single-character fragments in legacy reports",
        "Report recommendation tail omits empty basis and trigger sections in legacy text",
        "Report recommendation tail Markdown fields collapse embedded newlines",
        "Report legacy score and valuation fields use shared display conversion",
        "Report moat score legacy text uses semantic key fallback",
        "Report moat score legacy text uses key fallback for single-character fragments",
        "Report moat score legacy text uses fallback row for empty scores",
        "Report valuation summary legacy text uses semantic key fallback",
        "Report valuation summary legacy text uses fallback for single-character fragments",
        "Report legacy score and valuation Markdown key-value fields collapse embedded newlines",
        "Report legacy analysis markdown body uses shared text conversion",
        "Report legacy structured display fields use shared text conversion",
        "Report short-term trade-plan legacy text preserves analysis body fallback",
        "Report short-term trade-plan legacy text uses enum fallback for invalid metadata",
        "Report short-term trade-plan legacy text uses field fallback for single-character fragments",
        "Report short-term trade-plan legacy text uses analysis body fallback for single-character fragments",
        "Report legacy structured Markdown display fields collapse embedded newlines",
        "Report analysis overlay display fields use shared text conversion",
        "Report analysis overlay display fields collapse embedded newlines",
        "Report analysis overlay list fields use dict-list safe conversion",
        "Report analysis overlay structured-output maps use mapping-safe conversion",
        "Report analysis overlay data child maps use mapping-safe conversion",
        "Report analysis overlay financial history sequences use sequence-safe conversion",
        "Report key evidence source audit child maps use mapping-safe conversion",
        "Report source audit table child maps use mapping-safe conversion",
        "Report TWSE official availability banner source audit rows use dict-list safe conversion",
        "Report data trust quant metrics child maps use mapping-safe conversion",
        "Report data trust Markdown summary bullets collapse embedded newlines",
        "Report bundle data trust property accepts mapping-safe snapshot maps",
        "Report persistence accepts mapping-safe data snapshot payloads before saving",
        "Report refresh diffs accept mapping-safe data snapshot payloads before comparing",
        "Report refresh stale-source detection accepts mapping-safe data snapshot payloads",
        "Report refresh source audit sequences treat lookup iterator failures as native-sequence fallbacks",
        "Report refresh source audit sequences treat lookup iterator creation failures as native-sequence fallbacks",
        "Report refresh source audit rows use Mapping traversal when `.items()` iterables fail lookup",
        "Report refresh source audit rows skip lookup item unpack failures",
        "Report refresh source audit rows skip lookup key hash failures",
        "Report refresh source audit rows skip Mapping traversal key hash failures",
        "Report refresh source audit timestamps use safe text conversion",
        "Report refresh refreshed-data payloads accept mapping-safe provider/cache responses",
        "Report rerun refreshed-data payloads accept mapping-safe provider/cache responses",
        "Report rerun existing snapshot data payloads use mapping-safe snapshot normalization",
        "Report final-recommendation rerun context data uses mapping-safe snapshot normalization",
        "Report final-recommendation rerun context accepts mapping-safe rerun context payloads",
        "Report rerun renderer snapshots use mapping-safe snapshot normalization",
        "Report rerun render contexts use mapping-safe top-level normalization",
        "Report rerun progress events accept mapping-safe payloads before job-store persistence",
        "Report rerun progress event details use snapshot-safe normalization",
        "Report rerun scalar progress fallbacks use integer-safe conversion",
        "Report rerun progress event scope fields use safe text fallback",
        "Report rerun progress event control fields use safe text fallback",
        "Report rerun progress event count fields use integer-safe normalization",
        "Report rerun progress event message fields use safe text fallback",
        "Report rerun progress event name fields use safe text fallback",
        "Report rerun progress event detail fields use safe text fallback",
        "Report rerun progress event agent number fields use integer-safe normalization",
        "Report rerun progress event pipeline identity fields use safe text fallback",
        "Report rerun progress event metadata fields use mapping-safe normalization",
        "Report rerun API key failure events preserve source filenames",
        "Report rerun queue enqueue failure events preserve source filenames",
        "Report rerun queue enqueue failure messages use safe text fallback",
        "Report rerun attached job created flags use explicit boolean selection",
        "Report rerun attached job status checks use safe text fallback",
        "Report rerun stream replay payloads use mapping-safe fallback",
        "Report rerun stream replay payload type fields use safe text fallback",
        "Report rerun stream replay control fields use safe text fallback",
        "Report rerun stream replay message fields use safe text fallback",
        "Report rerun stream replay progress text fields use safe text fallback",
        "Report rerun stream replay filename fields use safe text fallback",
        "Report rerun stream replay context fields use safe text fallback",
        "Report rerun stream replay count fields use integer-safe fallback",
        "Report rerun stream replay status code fields use integer-safe fallback",
        "Report rerun stream replay structured fields use snapshot-safe normalization",
        "Report rerun stream replay event rows use mapping-safe fallback",
        "Report rerun stream replay event id fields use integer-safe fallback",
        "Report rerun stream event collections use sequence-safe fallback",
        "Report rerun stream resume id parsing treats negative `Last-Event-ID` values",
        "Report rerun stream missing job rows after SSE setup emit and persist terminal error fallbacks",
        "Report rerun stream malformed job rows after SSE setup emit terminal error fallbacks",
        "Report rerun stream terminal fallback events preserve rerun scope and source filenames",
        "Report rerun stream terminal fallback messages and filenames use safe text normalization",
        "Report rerun stream terminal polling status checks use safe text fallback",
        "Report rerun stream terminal fallback scopes use safe text fallback",
        "Report rerun stream task validation uses safe text fallback",
        "Report rerun stream setup job rows use mapping-safe fallback",
        "Report rerun stream task ticker validation uses safe text fallback",
        "Report rerun cancel job rows use mapping-safe fallback",
        "Report rerun cancel task validation uses safe text fallback",
        "Report rerun cancel task ticker validation uses safe text fallback",
        "Report rerun source filename fields use safe text normalization",
        "Report rerun cancellation messages use safe text fallback",
        "Report rerun invalid scope errors are handled inside the job-store terminal event flow",
        "Report rerun HTTP error details use safe text fallback",
        "Report rerun HTTP error status codes use integer-safe fallback",
        "Report rerun unexpected exception messages use safe text fallback",
        "Report rerun completion results use mapping-safe snapshot normalization",
        "Report rerun completion structured result fields use mapping-safe normalization",
        "Report rerun completion identity fields use safe text normalization",
        "Report refresh rerun checks accept mapping-safe data snapshot payloads before comparing",
        "Report trust controls data and context maps use mapping-safe conversion",
        "Report trust controls generated-at fields use safe text conversion",
        "Report trust controls Markdown reproducibility fields collapse embedded newlines",
        "Report price target card and chart payload values use JSON-safe numeric conversion",
        "Report chart payload series fields use JSON-safe text and finite-number conversion",
        "Report price history chart payload accepts mapping-safe chart wrappers",
        "Report price history chart series fields use sequence-safe truthiness fallback",
        "Report price history chart date fields use safe text conversion",
        "Report price history chart mapping keys use future-date filtering",
        "Report PE river chart payload uses truthiness-safe mapping handoff",
        "Report PE river chart payload accepts mapping-safe chart wrappers",
        "Report current price chart literals use finite-number conversion",
        "Report recommendation banner target and confidence fields use shared text conversion",
        "Report executive synthesis text fields use shared text conversion",
        "Report cover metadata uses mapping-safe conversion",
        "Report parsed payload and child maps use mapping-safe conversion",
        "Report data payload and child maps use mapping-safe conversion",
        "Report Markdown renderer data and parsed payload maps use mapping-safe conversion",
        "Report Markdown renderer reference source table cells escape table separators",
        "Report Markdown renderer single-line fields collapse embedded newlines",
        "Report Markdown renderer prebuilt investment-thesis payloads use mapping-safe handoff",
        "Report agent output maps use mapping-safe conversion",
        "Report agent output child maps use mapping-safe conversion",
        "Report agent output maps preserve string-key agent ids",
        "Report agent sequence ids normalize string values",
        "Report agent sequence payloads fall back to pipeline defaults",
        "Report tear-sheet target price display avoids duplicate currency prefixes",
        "Report audit banner final-audit child maps use mapping-safe conversion",
        "Report audit banner abnormality list fields use list-safe conversion",
        "Report audit banner abnormality list fields use truthiness-safe conversion",
        "Report audit banner abnormality text fields use shared text conversion",
        "Report audit banner Markdown abnormality bullets collapse embedded newlines",
        "Report reading notice quality gate text fields use shared text conversion",
        "Report reading notice Markdown gate text collapses embedded newlines",
        "Report reading notice quality gate record detection accepts mapping-safe gate payloads",
        "Report preview reading boundaries derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes",
        "Report preview reading boundaries prefer hash mismatch details over default generic snapshot integrity errors",
        "Report preview reading boundaries remove default generic snapshot integrity blocker text",
        "Report preview reading boundaries deduplicate repeated snapshot integrity error details",
        "Report reading notice snapshot integrity checks treat `valid=false` as blocked",
        "Report reading notice snapshot integrity checks let invalid `data.snapshot_integrity` override a conflicting verified top-level record",
        "Report reading notice snapshot integrity checks preserve the most specific invalid snapshot integrity detail",
        "Report reading notice snapshot integrity checks accept mapping-safe snapshot integrity payloads",
        "Report reading notice snapshot integrity checks downgrade recorded non-verified snapshots to warning",
        "Report reading notice snapshot integrity details deduplicate repeated error entries",
        "Report reading notice snapshot integrity details derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes",
        "Report reading notice snapshot integrity details prefer hash mismatch details over default generic snapshot integrity errors",
        "Report reading notice snapshot integrity details remove default generic blocker text",
        "Report view and HTML download paths re-check the current `.data.json` snapshot integrity",
        "Report Markdown download paths re-check the current `.data.json` snapshot integrity",
        "Report artifact view and download paths treat malformed or non-object `.data.json` snapshots as blocked",
        "Report artifact view and download paths treat missing `.data.json` snapshots as warning",
        "Report artifact view and download paths honor invalid `snapshot_integrity` recorded inside `.data.json`",
        "Report artifact view and download paths also honor invalid `data.snapshot_integrity` recorded inside `.data.json`",
        "Report artifact view and download paths let any recorded invalid snapshot integrity override a conflicting verified record",
        "Report artifact view and download paths preserve the most specific invalid snapshot integrity detail",
        "Report artifact view and download paths treat default generic snapshot integrity blocker text as less specific",
        "Report artifact view and download paths derive a `snapshot_hash mismatch` detail from recorded invalid snapshot integrity hashes",
        "Report artifact view and download paths prefer recorded hash mismatch details over default generic snapshot integrity errors",
        "Report artifact view and download paths remove default generic snapshot integrity errors when the same recorded error list also contains specific details",
        "Report artifact view and download paths deduplicate recorded snapshot integrity error details",
        "Report quality repair queue quality gate fields use dict-native field reads",
        "Report quality repair queue report identity fields use string-safe conversion",
        "Report quality repair queue quality gate text fields use string-safe conversion",
        "Report quality repair queue quality gate text fields treat lookup string conversion failures as blank",
        "Report quality repair queue reason codes use string-safe conversion",
        "Report quality repair queue stale source lists use string-safe conversion",
        "Report quality repair queue text list tuple sequences are evaluated before action prioritization",
        "Report quality repair queue reports envelopes use mapping-safe conversion",
        "Report quality repair queue snapshot integrity maps use mapping-safe conversion",
        "Report quality repair queue quality gate child maps use mapping-safe conversion",
        "Report quality repair queue quality gate child maps use Mapping traversal when `.items()` lookup fails",
        "Report quality repair queue quality gate child maps skip lookup item failures during Mapping traversal",
        "Report quality repair queue snapshot integrity verifier results treat `valid=false` as invalid",
        "Report quality repair queue snapshot integrity verifier results let `valid=false` override non-invalid status text",
        "Report quality repair queue snapshot integrity error details use string-safe conversion",
        "Report quality repair queue derives a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes",
        "Report quality repair queue prefers hash mismatch details over default generic snapshot integrity errors",
        "Report quality repair queue removes default generic snapshot integrity error details when specific provider or hash details exist",
        "Report quality repair queue deduplicates repeated snapshot integrity error details",
        "Shared mapping list conversions use native list and tuple iterators when iterator accessors fail",
        "Shared mapping text list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Shared mapping text list conversions treat lookup iterator failures as native-list fallbacks",
        "Shared mapping dict list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Shared mapping dict list conversions treat lookup iterator failures as native-list fallbacks",
        "Shared mapping traversal falls back to native dict items when custom items iterators fail before yielding",
        "Report quality repair queue provider alert lists preserve valid entries before iterator failures",
        "Report quality repair queue report collections preserve valid reports before iterator failures",
        "Report quality repair queue decision freshness detail fields use string-safe conversion",
        "Report quality repair queue decision freshness flags use bool-safe conversion",
        "Report quality repair queue decision freshness flags treat lookup truthiness failures as false",
        "Report quality repair queue limit uses integer-safe conversion",
        "Report quality repair queue limit uses the default cap on lookup integer conversion failures",
        "Outcome calibration quality signal fields use dict-native field reads",
        "Outcome calibration report identity fields use string-safe conversion",
        "Outcome calibration data trust score fields use float-safe fallback",
        "Outcome calibration row collections use list-safe normalization",
        "Outcome calibration decision freshness flags use bool-safe conversion",
        "Outcome calibration matched reports use dict-safe fallback",
        "Outcome calibration numeric fields use conversion-safe fallback",
        "Strategy evaluator numeric fields use conversion-safe fallback",
        "Strategy evaluator artifact fields use dict-native field reads",
        "Strategy evaluator hit flags use bool-safe fallback",
        "Strategy evaluator artifact iterators preserve valid entries before alpha model comparison",
        "Strategy evaluator artifact tuple sequences are evaluated before alpha model comparison",
        "Provider impact report fields use dict-native field reads",
        "Provider impact report, data trust, and alert maps use mapping-safe conversion",
        "Provider impact report, data trust, and alert maps use Mapping traversal when `.items()` lookup fails",
        "Provider impact report, data trust, and alert maps skip lookup item failures during Mapping traversal",
        "Provider impact report identity fields use string-safe conversion before provider recovery output",
        "Provider impact ticker identity uses string-safe conversion before provider recovery output",
        "Provider impact current fetch fields use bool-, integer-, and string-safe conversion",
        "Provider impact current fetch fields treat lookup integer and bool conversion failures as empty current-fetch evidence",
        "Provider impact alert text fields use string-safe conversion",
        "Provider impact reason codes use string-safe conversion",
        "Provider impact reason code iterators preserve valid entries before failures",
        "Provider impact text list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Provider impact text list conversions treat lookup iterator failures as native-list fallbacks",
        "Provider impact text list conversions treat lookup iterator creation failures as native-list fallbacks",
        "Provider impact alert iterators preserve valid entries before failures",
        "Provider impact ledger report iterators preserve valid reports before failures",
        "Provider impact ledger reports envelopes use mapping-safe conversion",
        "Provider impact tuple sequences are evaluated before provider recovery decisions",
        "Provider impact list conversions use native list and tuple iterators when iterator accessors fail",
        "Provider impact dict list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Provider impact dict list conversions treat lookup iterator failures as native-list fallbacks",
        "Provider impact dict list conversions treat lookup iterator creation failures as native-list fallbacks",
        "Provider impact ledger sort keys use string-safe conversion before ordering",
        "Daily decision queue action fields use dict-native field reads",
        "Notification plan action fields use dict-native field reads",
        "Notification delivery audit context fields use dict-native field reads",
        "Provider SLA window alert enrichment uses integer-, float-, and string-safe conversion",
        "Provider SLA alert policy basis selection uses dict-, integer-, float-, and string-safe conversion",
        "Data trust provider SLA evidence attempts use truthiness-safe integer and basis text conversion",
        "Data trust provider SLA evidence attempts treat lookup integer conversion failures as zero evidence",
        "Data trust provider SLA nested window maps use dict-safe conversion before evidence attempts",
        "Data trust provider SLA row maps fall back to native dict items when copy lookups fail",
        "Data trust provider SLA alert matching uses string-safe source, provider, level, and message conversion",
        "Data trust provider SLA source audit entries use string-, integer-, and bool-safe conversion",
        "Data trust provider SLA source audit entries treat lookup integer and bool conversion failures as empty current-fetch evidence",
        "Data trust provider SLA trust metadata uses list- and string-safe conversion",
        "Data trust provider SLA trust metadata uses shared text conversion",
        "Data trust provider SLA alert collections use iterable-safe conversion",
        "Data trust provider SLA source audit collections use iterable-safe conversion",
        "Data trust provider SLA rows use dict-safe conversion before matching current source audit entries and provider alerts",
        "Data trust provider SLA source data uses dict-safe conversion before reading current source audit rows",
        "Data trust provider SLA alert fetch failures fall back to existing trust",
        "Data trust provider SLA policy failures fall back to base trust before final score calculation",
        "Data trust provider SLA policy lookup failures fall back to base trust before final score calculation",
        "Data trust provider SLA policy failure fallback uses an unmutated base trust snapshot before final score calculation",
        "Data trust post-SLA status fields use canonical status normalization before final score calculation",
        "Data trust post-SLA list metadata fields are written back after string-list normalization before final score calculation",
        "Data trust post-SLA market timestamp fields use shared text normalization before final score output",
        "Data trust post-SLA provider SLA alert metadata uses dict-list normalization before final score output",
        "Data trust provider SLA trust metadata iterators preserve valid entries before failures",
        "Data trust provider SLA list conversions use native list and tuple iterators when iterator accessors fail",
        "Data trust provider SLA dict row conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Data trust provider SLA dict row conversions treat lookup iterator failures as native-list fallbacks",
        "Data trust provider SLA dict row conversions treat lookup iterator creation failures as native-list fallbacks",
        "Data trust provider SLA text list conversions use native list and tuple iterators when custom iterators fail before yielding",
        "Data trust provider SLA text list conversions treat lookup iterator failures as native-list fallbacks",
        "Data trust provider SLA text list conversions treat lookup iterator creation failures as native-list fallbacks",
        "Data trust normalization note fields use string-list conversion",
        "Data trust normalization provider SLA alert lists use dict-list safe conversion",
        "Data trust scoring audit source names use string-safe conversion",
        "Data trust audit entry text fields use string-safe conversion",
        "Data trust audit entry text fields use shared text conversion",
        "Data trust source audit append preserves tuple audit batches",
        "Report key evidence source fields use shared text conversion",
        "Report key evidence aggregated stale flags use bool-safe conversion",
        "Report key evidence data field presence checks ignore malformed scalar values",
        "Report key evidence data field presence checks use strip-safe shared text conversion",
        "Report key evidence Markdown cells escape table separators",
        "Report source audit table fields use shared text conversion",
        "Report source audit Markdown cells escape table separators",
        "Report source evidence numeric and boolean fields use safe conversion",
        "Report data trust summary fields use shared text conversion",
        "Report data trust quant fallback fields use truthiness-safe list conversion",
        "Report evidence matrix payload source fields use shared text conversion",
        "Report evidence matrix payload message fallback uses truthiness-safe field selection",
        "Report evidence matrix payload message fallback skips text-empty malformed values",
        "Report evidence matrix payload message presence checks use length-safe fallback",
        "Report evidence matrix payload message presence checks use strip-safe shared text conversion",
        "Report evidence matrix source audit child maps use mapping-safe conversion",
        "Report evidence matrix source row labels use shared text conversion",
        "Report evidence matrix Markdown cells use shared text conversion",
        "Report evidence matrix HTML cells use shared text conversion",
        "Report evidence matrix row fetched-at fields use truthiness-safe text conversion",
        "Report evidence matrix row status fields use truthiness-safe text conversion",
        "Report evidence matrix row provider fields use truthiness-safe text conversion",
        "Report evidence matrix stale-source flags use bool-safe conversion",
        "Report evidence matrix price-target basis excludes boolean values",
        "Report evidence matrix price-target basis excludes non-finite numeric values",
        "Report evidence matrix price-target scenario keys skip malformed text",
        "Report evidence matrix recommendation-basis keys use shared text conversion",
        "Report evidence matrix recommendation-basis values use equality-safe text checks",
        "Report evidence matrix recommendation-basis string values use strip-safe shared text conversion",
        "Report evidence matrix moat-score basis skips malformed metric keys",
        "Report evidence matrix limitation notes use shared text conversion",
        "Report evidence matrix limitation notes use text-list safe conversion",
        "Data trust audit entry status uses string-safe conversion",
        "Data trust audit entry duration fields ignore boolean millisecond overrides before epoch delta fallback",
        "Data trust audit entry duration fields ignore non-finite millisecond overrides before epoch delta fallback",
        "Data trust audit entry duration fields ignore overflowing millisecond overrides before epoch delta fallback",
        "Data trust audit entry duration fields ignore non-finite epoch timestamps before delta calculation",
        "Data trust audit entry duration fields ignore overflowing epoch timestamps before delta calculation",
        "Data trust audit entry duration fields reject out-of-range epoch timestamps before delta calculation",
        "Data trust audit entry fetched-at fields use shared text conversion before epoch fallback",
        "Data trust audit entry fetched-at epoch fallback validates explicit epoch values before finished-at fallback",
        "Data trust audit entry fetched-at epoch fallback treats out-of-range epoch values as malformed",
        "Data trust audit entry finished-at current-time fallback validates epoch values before source audit output",
        "Data trust audit entry record counts use integer-safe conversion",
        "Data trust audit entry record counts treat boolean values as malformed counts",
        "Data trust audit entry record counts treat fractional numeric values as malformed counts",
        "Data trust audit entry boolean fields use bool-safe conversion",
        "Data trust audit entry boolean fields treat lookup truthiness failures as false",
        "Data trust audit entry boolean text fields parse explicit false strings before truthiness fallback",
        "Data trust audit entry boolean binary fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean non-finite numeric fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean numeric fields only accept explicit zero or one values before truthiness fallback",
        "Data trust audit entry boolean real-number fields apply the same explicit zero or one contract",
        "Data trust audit entry boolean overflowing real-number fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean numeric text fields apply the same finite zero or one contract",
        "Data trust audit entry boolean free-form text fields are treated as malformed after explicit true, false, and numeric parsing",
        "Data trust audit entry boolean complex fields are treated as malformed before truthiness fallback",
        "Data trust audit entry boolean container fields are treated as malformed before truthiness fallback",
        "Prompt source audit summary fields use string-, integer-, and bool-safe conversion",
        "Prompt source audit summary text fields use shared text conversion",
        "Prompt source audit root source data uses dict-native field reads",
        "Prompt source audit entry fields use dict-native field reads",
        "Prompt data trust list fields use truthiness- and iterator-safe conversion",
        "Prompt data trust source data uses dict-native field reads",
        "Prompt data trust fields use dict-native field reads",
        "Prompt company identity mapping uses truthiness-safe handoff",
        "Prompt company identity fields use dict-native field reads",
        "Prompt company identity source data uses dict-native field reads",
        "Prompt company metadata source data uses dict-native field reads",
        "Agent runtime identity guard uses truthiness-safe company identity handoff",
        "Agent runtime identity guard mapping length checks tolerate malformed length access",
        "Agent runtime identity guard mapping access uses dict-native field reads",
        "Agent runtime identity guard ticker fields use string-safe conversion",
        "Agent runtime identity guard text fields use string-safe conversion",
        "Agent runtime identity guard alias lists use iterator-safe string conversion",
        "Agent runtime identity guard alias native lists preserve limits",
        "Agent runtime identity guard templates use string-safe formatting",
        "Agent runtime identity guard runtime rules use dict-native field reads",
        "Agent runtime identity guard values use dict-native field reads",
        "Agent runtime identity guard source data uses dict-native field reads",
        "Agent runtime RAG context mapping uses truthiness-safe handoff",
        "Agent runtime RAG context text uses string-safe conversion",
        "Agent runtime temporal memory reflection prompt uses string-safe conversion",
        "Agent runtime temporal memory backtests use iterator- and JSON-safe conversion",
        "Agent runtime prompt safety helpers are split from prompt assembly",
        "Agent runtime top-level rule sections use dict-native field reads",
        "Agent runtime prompt JSON dict items use dict-native field reads",
        "Agent runtime prompt JSON sequence items use native iterators",
        "Agent runtime prompt JSON collection items use native iterators",
        "Agent runtime structured instructions mappings use dict-native traversal",
        "Agent runtime rule section mappings use dict-native lookup",
        "Agent runtime rule block configs use dict-native field reads",
        "Agent runtime rule list mappings use dict-native field reads",
        "Agent runtime state view uses JSON-safe conversion",
        "Agent runtime forensic warning uses string-safe conversion",
        "Agent runtime retry and audit instruction fields use string-safe conversion",
        "Agent runtime final audit mappings use dict-native field reads",
        "Agent runtime final audit pipeline id uses string-safe conversion",
        "Agent runtime final audit rule lists use string-safe conversion",
        "Agent runtime prompt rule blocks use string-safe conversion",
        "Agent runtime output cleanliness mappings use dict-native field reads",
        "Agent runtime output cleanliness rules use string-safe conversion",
        "Agent runtime assistant task prompt mappings use dict-native field reads",
        "Agent runtime assistant task prompts use string-safe conversion",
        "Agent runtime primary probe flag uses bool-safe conversion",
        "Prompt freshness mappings use truthiness-safe handoff",
        "Prompt freshness source data uses dict-native field reads",
        "Prompt market data source data uses dict-native field reads",
        "Prompt valuation metrics source data uses dict-native field reads",
        "Prompt TTM financials source data uses dict-native field reads",
        "Prompt cash flow source data uses dict-native field reads",
        "Prompt balance sheet source data uses dict-native field reads",
        "Prompt growth source data uses dict-native field reads",
        "Prompt financial history source data uses dict-native field reads",
        "Prompt institutional trading mapping uses truthiness-safe handoff",
        "Prompt institutional trading source data uses dict-native field reads",
        "Prompt full market catalyst items use truthiness- and iterator-safe conversion",
        "Prompt market catalyst source data uses dict-native field reads",
        "Prompt peer context source data uses dict-native field reads",
        "Prompt full dynamic peer metrics use truthiness- and iterator-safe conversion",
        "Prompt full peer discovery results use truthiness- and iterator-safe conversion",
        "Prompt supplemental source data uses dict-native field reads",
        "Prompt full recent monthly revenue text uses truthiness- and iterator-safe conversion",
        "Prompt full data quality notes use truthiness- and iterator-safe conversion",
        "Prompt PE river chart source data uses dict-native field reads",
        "Prompt full PE river chart mapping uses truthiness-safe handoff",
        "Prompt compact list fields use truthiness- and iterator-safe conversion",
        "Prompt compact PE river chart mapping uses truthiness-safe handoff",
        "Prompt compact PE river chart fields use dict-native field reads",
        "Prompt compact PE river years use truthiness- and iterator-safe tail conversion",
        "Prompt cross-check source data uses dict-native field reads",
        "Prompt history rows use truthiness- and iterator-safe year conversion",
        "Prompt history value fields use truthiness- and iterator-safe sequence conversion",
        "Prompt history source data uses dict-native field reads",
        "Prompt agent context fields use truthiness-safe presence checks",
        "Prompt agent context source data uses dict-native field reads",
        "Prompt data trust payload accepts mapping-safe trust maps before prompt output",
        "Data trust string list conversion uses string-safe conversion",
        "Data trust string list conversion uses native list and tuple iterator fallback",
        "Data trust string list conversion drops non-finite numeric items",
        "Data trust score normalization uses float-safe conversion",
        "Data trust score normalization treats lookup conversion failures as malformed scores",
        "Data trust score normalization treats boolean score values as malformed",
        "Data trust normalization accepts mapping-safe trust payloads before field normalization",
        "Data trust normalization uses dict-native trust field reads",
        "Data trust normalization market timestamp fields use shared text conversion",
        "Data trust build source payloads accept mapping-safe inputs before scoring",
        "Data trust build source data uses mapping- and dict-list-safe conversion",
        "Data trust build source freshness child maps use mapping-safe conversion",
        "Data trust build source freshness stale flags use bool-safe conversion",
        "Data trust build data source notes use string-list conversion",
        "Data trust latest audit rows use mapping-safe conversion",
        "Data trust optional source status selection uses mapping-safe row conversion",
        "Data trust usable critical data checks use mapping-safe audit conversion",
        "Data trust source audit status comparisons use string-safe conversion",
        "Data trust last-market timestamp fallback uses string-safe conversion",
        "Data trust post-SLA trust metadata uses mapping-safe conversion",
        "Data trust snapshot existing trust selection uses dict-safe conversion",
        "Data trust snapshot existing trust selection accepts mapping-safe payloads",
        "Data trust snapshot root context accepts mapping-safe payloads before metadata selection",
        "Data trust snapshot source data accepts mapping-safe payloads before trust scoring",
        "Data trust snapshot refresh flags use bool-safe conversion",
        "Data trust snapshot refresh flags treat lookup truthiness failures as false",
        "Data trust snapshot rerun context text uses string-safe conversion",
        "Data trust snapshot sanitizer uses string-safe key and value conversion",
        "Data trust snapshot sanitizer uses native list and tuple iterators when iterator accessors fail",
        "Data trust snapshot sanitizer falls back to native list and tuple iterators when custom sequence iterators fail before yielding",
        "Data trust snapshot sanitizer uses native dict items when items accessors fail",
        "Data trust snapshot sanitizer falls back to native dict items when custom items iterables fail",
        "Data trust snapshot integrity hash lookup uses string-safe conversion",
        "Snapshot maintenance verify-snapshots uses verifier-derived hash presence",
        "Data trust snapshot integrity and schema validators use dict-native snapshot field reads",
        "Data trust snapshot integrity and schema validators fall back to item lookup when mapping field accessors fail",
        "Data trust snapshot rerun context agent keys use string-safe conversion",
        "Data trust snapshot content hash keys use string-safe conversion",
        "Data trust snapshot content hashing uses iterator-safe mapping traversal",
        "Data trust snapshot content hash accepts mapping snapshot wrappers before integrity verification",
        "Data trust snapshot size governance uses snapshot sanitizer input",
        "Data trust snapshot size byte calculation uses snapshot sanitizer input",
        "Data trust snapshot builds use dict-native context and data field reads",
        "Data trust snapshot identity fields use string-safe context/data selection",
        "Data trust snapshot identity fields use shared text conversion",
        "Data trust reproducibility source audit metadata uses string-safe provider and timestamp extraction",
        "Data trust reproducibility source audit metadata uses dict-list safe conversion",
        "Data trust reproducibility source audit helpers accept mapping-safe data wrappers",
        "Data trust reproducibility packets use dict-native context, data, source audit, and metadata field reads",
        "Data trust reproducibility packets accept mapping-safe context, data, source audit, and metadata wrappers",
        "Data trust reproducibility packets preserve validated full prompt fingerprints",
        "Prompt fingerprints cover agent templates, state-view policy, system prompts, and runtime prompt rules",
        "Prompt identity and prompt injection share one process-stable runtime-rule snapshot",
        "Runtime code provenance records commit and dirty state once per workflow",
        "Data trust explicit target price detection uses dict-native root field reads",
        "Data trust explicit target price detection accepts mapping-safe root and nested maps",
        "Data trust explicit target price detection uses string-safe key and value conversion",
        "Data trust explicit target price detection preserves valid list items before iterator failures",
        "Data trust explicit target price detection accepts tuple sequences before guardrail output",
        "Data trust explicit target price detection uses native list iterators when iterator accessors fail",
        "Data trust explicit target price detection uses native list iterators when custom iterators fail before yielding",
        "Data trust explicit target price detection treats lookup list iterator failures as native list fallbacks",
        "Data trust explicit target price detection preserves valid mapping items before iterator failures",
        "Data trust explicit target price detection uses native dict items when items accessors fail",
        "Data trust explicit target price detection uses native dict items when custom items iterables fail to create iterators",
        "Data trust explicit target price detection uses native dict items when custom items iterators fail before yielding",
        "Data trust explicit target price detection treats lookup mapping item failures as native dict item fallbacks",
        "Data trust explicit target price detection ignores non-finite numeric targets",
        "Data trust source record counting uses string-safe source keys",
        "Data trust source record counting normalizes root data maps before field reads",
        "Data trust source record counting normalizes institutional trading maps before field reads",
        "Data trust source record counting ignores empty institutional trading daily-only payloads before fallback counting",
        "Data trust source record counting normalizes global market context maps before field reads",
        "Data trust source record counting normalizes international news context maps before field reads",
        "Data trust source record counting normalizes P/E river chart maps before field reads",
        "Data trust source record counting normalizes P/E river chart band maps before counting valuation rows",
        "Data trust source record counting falls back from empty P/E river chart band series to year or EPS rows",
        "Data trust source record counting normalizes default source mapping values before counting keys",
        "Data trust source record counting counts only default source mapping keys with present child values",
        "Data trust source record counting uses sequence-safe tuple value presence checks",
        "Data trust source record counting uses item-aware sequence value presence checks",
        "Data trust source record counting uses mapping-safe value presence checks",
        "Data trust source record counting uses child-aware mapping value presence checks",
        "Data trust source record counting uses set-aware value presence checks",
        "Data trust source record counting treats boolean scalar values as missing evidence",
        "Data trust source record counting treats non-finite numeric scalar values as missing evidence",
        "Data trust source record counting treats overflowing numeric scalar values as missing evidence",
        "Data trust source record counting treats non-finite numeric string values as missing evidence",
        "Data trust source record counting treats placeholder string values as missing evidence",
        "Data trust source record counting treats non-finite Decimal scalar values as missing evidence",
        "Data trust source record counting treats binary scalar values as missing evidence",
        "Data trust source record counting treats complex scalar values as missing evidence",
        "Data trust source record counting uses native list and tuple iterator fallback",
        "Data trust source record counting treats tuple source values as row batches",
        "Data trust source record counting treats set and frozenset source values as row batches",
        "Data trust source record counting uses native set and frozenset iterator fallback",
        "Data trust source record counting treats lookup set iterator failures as native set and frozenset fallbacks",
        "Data trust source record counting uses truthiness-safe value presence checks",
        "Provider SLA window selection uses string-safe conversion",
        "Provider SLA window maps use dict-safe conversion",
        "Provider SLA nested window numeric fields use integer- and finite-float-safe conversion",
        "Provider SLA numeric field shaping uses dict-safe row conversion before provider and window output",
        "Provider SLA numeric field shaping uses strict numeric conversion before provider and window output",
        "Provider SLA nested window maps keep only canonical `last_1h`, `last_24h`, and `last_7d` buckets",
        "Provider SLA nested window keys use shared text conversion",
        "Provider SLA selected-window helper output normalizes nested `windows` maps",
        "Provider SLA selected-window numeric fields use integer- and finite-float-safe conversion",
        "Provider SLA provider rows use dict-safe conversion before window selection",
        "Provider SLA alert projection uses dict-safe row conversion and string-safe alert-level conversion",
        "Provider SLA alert projection output fields use string-, finite-float-, and dict-safe conversion",
        "Provider SLA alert projection text fields use shared text conversion",
        "Provider SLA all-window cumulative alerts reuse the same safe alert projection",
        "Provider SLA all-window provider summaries use dict-safe row conversion before returning dashboard payloads",
        "Provider SLA all-window provider numeric fields use integer- and finite-float-safe conversion",
        "Provider SLA payload summary fetch failures fall back to empty provider lists",
        "Provider SLA payload alert fetch failures fall back to empty alert lists",
        "Prometheus provider alert level rendering uses string-safe conversion",
        "Notification delivery failure reason bucketing uses shared text conversion",
        "Notification delivery summary channel counts use string-safe channel conversion",
        "Notification delivery summary status counts use string-safe status conversion",
        "low-cardinality",
        "failure_reason_counts",
        'state="ok"',
        'state="warning"',
    ]:
        assert expected in operator_guide

    for expected in [
        "notification_delivery_audit",
        "notification_delivery` health",
        "attention_contexts",
        "fix_notification_delivery",
        "suppress_notification = true",
        "operational.sqlite3",
        "one row per `delivery_key`",
        "reconcile_outbox_with_audit()",
        "should_send = false",
        "skip_reason = retry_wait",
        "retry_wait_seconds",
        "next_retry_at",
        "retry_exhausted = true",
        "context snapshot",
    ]:
        assert expected in architecture


def test_pipeline_mode_contract_has_contract_matrix_adoption_observation_board():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣採用觀測板" in contract
    for expected in [
        "最佳化目標",
        "降低錯選測試命令",
        "減少跨層改動漏跑測試",
        "保留人工判斷責任",
        "可觀察假說",
        "假說 1：四步流程會降低第一次選測摩擦",
        "假說 2：三個操作者情境會降低錯選通道",
        "假說 3：三條捷思規則會減少低顯著性誤用",
        "採用訊號矩陣",
        "綠色",
        "黃色",
        "紅色",
        "不新增遙測或自動化蒐集",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_case_model():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣案例模型" in contract
    for expected in [
        "三類案例模型",
        "模型 A：高顯著性機器契約案例",
        "模型 B：混合層報告呈現案例",
        "模型 C：低顯著性顯示層案例",
        "代表性抽樣規則",
        "每次契約相關變更至少對照一個案例模型",
        "跨層改動同時抽樣兩個模型",
        "不以單一綠燈案例代表所有未來改動",
        "案例卡格式",
        "改動描述",
        "選擇通道",
        "必跑命令",
        "採用訊號",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_comparison_feedback_design():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣比較與回饋設計" in contract
    for expected in [
        "比較組設計",
        "基準組：只使用速學卡與操作流程",
        "介入組：使用案例模型與案例卡",
        "比較指標",
        "錯選通道",
        "漏跑命令",
        "判讀限制缺漏",
        "介入方案",
        "改檔前先填案例卡",
        "跨層改動強制列出兩個模型",
        "訪談回饋題",
        "你能否在 2 分鐘內選出通道",
        "哪一條規則讓你猶豫",
        "不新增產品遙測",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_observation_replication_rules():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣觀察與複製準則" in contract
    for expected in [
        "觀察記錄欄位",
        "變更案例",
        "實際選擇通道",
        "實際執行命令",
        "觀察結果",
        "複製檢查清單",
        "同一案例模型",
        "同一必跑命令",
        "同一判讀限制",
        "可複製完成條件",
        "下一位操作者不用讀完整 HCS 附件",
        "不把觀察紀錄當成測試替代品",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_reader_path():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣讀者路徑" in contract
    for expected in [
        "三種受眾",
        "一般改文案者",
        "報告模板維護者",
        "parser/prompt 維護者",
        "閱讀順序",
        "先讀速學卡",
        "再用操作流程",
        "最後填案例卡",
        "語意邊界",
        "文件契約不是自動化保證",
        "觀察紀錄不是測試替代品",
        "低顯著性不代表低責任",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_maintenance_guide():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣維護導覽" in contract
    for expected in [
        "章節導覽",
        "先判斷改動層級",
        "再選案例模型",
        "最後確認模式對照",
        "專業維護語氣",
        "只證明已知契約未回退",
        "不得宣稱投資語意安全",
        "跨層改動需列出多組命令",
        "核心論點",
        "契約矩陣的目的不是自動化選測",
        "先保留人工判斷，再用最小測試驗證",
        "碰到 parser/prompt/template，優先視為契約變更",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_one_page_summary():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣一頁摘要" in contract
    for expected in [
        "短版摘要",
        "先看是否碰 parser/prompt/template",
        "再看使用者是否會直接閱讀",
        "最後看是否只在前端顯示",
        "建議表達",
        "我選擇的通道是",
        "我已執行的命令是",
        "不得解讀為",
        "媒介取捨",
        "文字與表格優先",
        "暫不新增圖像或多媒體",
        "避免圖像把人工判斷包成自動流程",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_ethics_boundary():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣倫理邊界" in contract
    for expected in [
        "倫理底線",
        "不得把測試綠燈寫成投資建議安全",
        "不得把責任轉嫁給工具或文件",
        "不得用低顯著性通道淡化使用者風險",
        "必要時要說不",
        "缺少 parser/prompt/template 證據時不可合併高顯著性改動",
        "若報告文案可能被讀成交易指令，先補責任邊界",
        "倫理判斷",
        "允許發布的敘述",
        "禁止發布的敘述",
        "升級條件",
        "從低顯著性升級為混合層",
        "從混合層升級為高顯著性",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_system_risk_boundary():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣系統風險邊界" in contract
    for expected in [
        "複雜因果圖譜",
        "局部測試綠燈可能仍產生使用者誤解",
        "文件紀錄可能降低漏跑測試但不保證採用",
        "前端語氣改善可能與完整報告正文仍不一致",
        "湧現風險",
        "多個低顯著性改動累積成高風險",
        "跨模式文案一致但責任邊界變模糊",
        "觀察紀錄增加但實際驗證減少",
        "分析層次",
        "文件層",
        "測試層",
        "runtime 層",
        "使用者行為層",
        "不得用下一層證據替代上一層證據",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_system_relationship_map():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣系統關係圖" in contract
    for expected in [
        "維護網絡",
        "前端顯示層",
        "報告模板層",
        "parser/prompt 層",
        "測試矩陣",
        "使用者判讀",
        "系統動力學",
        "語氣改善降低權威感但可能增加契約漂移",
        "更多觀察紀錄降低漏跑但可能增加形式化",
        "更嚴格升級條件降低錯放但可能增加維護成本",
        "系統圖像",
        "改動先定位層級",
        "證據再對齊層次",
        "宣稱最後受倫理邊界限制",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_review_dialogue():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣 review 對話" in contract
    for expected in [
        "補證據協商",
        "先承認改動目的",
        "再指出缺少的證據層",
        "最後提出最小補證據路徑",
        "說服原則",
        "把補跑命令說成降低錯放風險",
        "把升級通道說成保護 parser/prompt/template",
        "把拆分改動說成降低 review 成本",
        "形塑行為",
        "預設使用一頁摘要句型",
        "跨層改動預設填案例卡",
        "紅色或黃色採用訊號不得合併",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_review_conformity_guard():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣 review 防從眾檢查" in contract
    for expected in [
        "防從眾檢查",
        "不得用多數人同意取代證據層",
        "不得用前例綠燈取代本次改動層級",
        "不得用測試全綠取代不得解讀為",
        "差異保留",
        "高顯著性、混合層、低顯著性不得合併敘述",
        "長線、交易、逆勢、短線模式要保留不同責任邊界",
        "文件層、測試層、runtime 層與使用者行為層要分開回報",
        "情緒智商",
        "先命名壓力",
        "再回到最小補證據路徑",
        "最後用限制句收尾",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_review_responsibility_map():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣 review 責任分工" in contract
    for expected in [
        "領導原則",
        "主責先宣告改動層級",
        "review 主導者必須要求升級通道",
        "完成敘述必須保留不得解讀為",
        "權力動態",
        "不得用職位或資深度取代證據",
        "低權限操作者可以引用契約矩陣要求補證據",
        "高權限操作者不得覆蓋紅色或黃色採用訊號",
        "責任",
        "改動者負責描述改動層級",
        "reviewer 負責核對通道與命令",
        "合併者負責確認限制句存在",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_review_self_audit_strategy():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣 review 自我稽核與收尾策略" in contract
    for expected in [
        "自我覺察",
        "契約矩陣不是自動化審核器",
        "規則變多可能增加官僚成本",
        "低顯著性顯示層不得被迫跑高顯著性全矩陣",
        "制定策略",
        "先選最小足夠路徑",
        "高風險升級、低風險保留輕量通道",
        "第 2 輪互動思考收尾條件",
        "完成倫理邊界、系統風險、系統關係、review 對話、防從眾、責任分工與自我稽核",
        "下一輪入口是第 3 輪批判思考",
        "不得宣稱 HCS Plus 完成",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_contract_matrix_round3_problem_radar():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪問題雷達" in contract
    for expected in [
        "重新拆解",
        "矩陣過重",
        "維護者是否能在 2 分鐘內選到通道",
        "低顯著性是否被高顯著性流程拖慢",
        "責任分工是否讓限制句真的出現",
        "關鍵問題",
        "哪個規則可以被一頁摘要取代",
        "哪個情境必須保留完整矩陣",
        "哪個證據層仍然沒有 runtime 驗證",
        "差距分析",
        "已完成",
        "仍缺口",
        "最小下一步",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_variable_bias_guardrails():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪變數與偏誤降低護欄" in contract
    for expected in [
        "變數分析",
        "改動層級",
        "證據層",
        "可逆性",
        "時程壓力",
        "偏誤辨識",
        "過度升級偏誤",
        "過度降級偏誤",
        "工具化幻覺",
        "綠燈擴張偏誤",
        "偏誤降低",
        "一頁摘要優先",
        "跨層改動升級",
        "證據分層回報",
        "限制句必填",
        "案例卡觸發",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_decision_purpose_utility():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪分流決策與效用校準" in contract
    for expected in [
        "決策樹",
        "只碰前端顯示層",
        "一頁摘要與低顯著性命令",
        "碰 parser/prompt/template",
        "高顯著性機器契約通道",
        "碰完整報告正文或報告模板",
        "混合層報告呈現通道",
        "跨層改動",
        "案例卡或拆分 patch",
        "目的校準",
        "降低 2 分鐘選通道摩擦",
        "保住高顯著性契約",
        "防止綠燈擴張",
        "保留低顯著性效率",
        "效用校準",
        "規則",
        "預期效用",
        "成本",
        "升級或停用條件",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_evidence_observation_stats():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪證據校準與觀測統計" in contract
    for expected in [
        "信賴區間",
        "目前樣本",
        "不可外推",
        "觀察窗口",
        "相關性",
        "選通道時間",
        "錯選通道",
        "限制句出現率",
        "不代表因果",
        "描述統計",
        "樣本數",
        "中位選通道時間",
        "錯選率",
        "跨層改動比例",
        "案例卡觸發率",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_probability_regression_significance_thresholds():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪風險機率與顯著性門檻" in contract
    for expected in [
        "機率",
        "錯選率",
        "限制句缺漏率",
        "案例卡漏觸發率",
        "風險機率",
        "迴歸",
        "連續兩個觀察窗口",
        "回歸監測",
        "顯著性",
        "小樣本",
        "至少 5 個案例",
        "升級門檻",
        "調整決策樹",
        "不得宣稱改善",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_evidence_rules_induction_boundaries():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪證據規則與外推邊界" in contract
    for expected in [
        "證據基礎",
        "可接受證據",
        "文件契約測試",
        "觀察窗口紀錄",
        "案例卡",
        "不可作為證據",
        "單次綠燈",
        "未標樣本數",
        "演繹",
        "若碰 parser/prompt/template",
        "立即升級",
        "若少於至少 5 個案例",
        "只能描述個案",
        "歸納",
        "外推邊界",
        "不得外推",
        "真實使用者理解",
        "runtime 安全",
        "生成報告母體",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_fallacy_source_context_boundaries():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪反謬誤與來源情境邊界" in contract
    for expected in [
        "謬誤",
        "測試綠燈謬誤",
        "樣本數謬誤",
        "案例代表性謬誤",
        "錯誤推論",
        "來源品質",
        "高品質來源",
        "次級來源",
        "不得作為完成證據",
        "情境脈絡",
        "只適用於契約相關變更",
        "不適用於一般 UI 文案",
        "需要人工 review",
        "不得替代 runtime 驗證",
        "不得替代使用者研究",
        "完成回報限制句",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_burden_estimate_interpretation_frame():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪負擔估算與完成詮釋框架" in contract
    for expected in [
        "批判",
        "矩陣過重",
        "必留護欄",
        "可短句替代",
        "可延後工具化",
        "估算",
        "完成回報成本",
        "2 分鐘",
        "3 分鐘",
        "低風險 UI",
        "高風險契約",
        "詮釋框架",
        "文件契約通過",
        "觀察窗口",
        "runtime 驗證",
        "使用者研究",
        "不得宣稱安全",
        "不得宣稱理解改善",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_closing_verification_checkpoint():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪收尾與可重跑驗證" in contract
    for expected in [
        "合理收尾",
        "第 3 輪批判思考完成：26/26",
        "不新增自動選測腳本",
        "保留人工判斷",
        "可重跑驗證",
        "tests/test_hcs_plus_state.py",
        "tests/test_docs_contract.py",
        "不得宣稱 HCS Plus 完成",
        "第 3 輪創意思考",
        "失敗即回到批判思考",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_creative_learning_entry():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪創意學習入口" in contract
    for expected in [
        "學習科學",
        "三層學習路徑",
        "10 秒判斷",
        "90 秒執行",
        "5 分鐘復盤",
        "限制條件",
        "不改 runtime 行為",
        "不新增自動選測腳本",
        "不新增遙測",
        "不替代人工 review",
        "類比",
        "登機前安檢",
        "快速通道",
        "人工複檢",
        "證據托盤",
        "不把安檢通過解讀成航程安全",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_operation_algorithm_and_heuristics():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪操作演算法與捷思規則" in contract
    for expected in [
        "演算法",
        "四步操作演算法",
        "步驟 1：10 秒判斷",
        "步驟 2：選擇通道",
        "步驟 3：裝好證據托盤",
        "步驟 4：完成回報",
        "設計思考",
        "三個操作者情境",
        "情境 A：只改低風險 UI",
        "情境 B：改報告模板或正文呈現",
        "情境 C：改 parser、prompt、template 或核心契約詞",
        "捷思法",
        "三條快速規則",
        "有核心契約詞就先人工複檢",
        "只在前端顯示才走快速通道",
        "缺少限制句就不得完成",
        "不得替代 runtime 驗證",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_adoption_optimization_signal_board():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪採用最佳化與訊號板" in contract
    for expected in [
        "最佳化",
        "採用摩擦",
        "錯選通道",
        "漏跑命令",
        "限制句缺漏",
        "案例卡漏補",
        "假說發展",
        "假說 1：四步操作會降低錯選通道",
        "假說 2：證據托盤會降低漏跑命令",
        "假說 3：三條快速規則會降低限制句缺漏",
        "資料視覺化",
        "採用訊號板",
        "綠色",
        "黃色",
        "紅色",
        "人工觀察",
        "不新增遙測",
        "不得宣稱改善",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_case_models_sampling_cards():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪案例模型與抽樣案例卡" in contract
    for expected in [
        "建模",
        "代表性案例模型",
        "模型 A：低風險快速通道案例",
        "模型 B：混合層報告呈現案例",
        "模型 C：高風險契約人工複檢案例",
        "模型 D：紅色阻擋案例",
        "抽樣",
        "代表性抽樣規則",
        "每個觀察窗口",
        "黃色或紅色必抽",
        "少於 5 個案例不得宣稱趨勢",
        "個案研究",
        "案例卡格式",
        "改動描述",
        "改動層級",
        "選擇通道",
        "證據托盤",
        "採用訊號",
        "限制句",
        "補救行動",
        "不可外推",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_comparison_intervention_feedback_design():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪比較與介入回饋設計" in contract
    for expected in [
        "比較組",
        "基準組",
        "介入組",
        "錯選通道率",
        "漏跑命令率",
        "限制句缺漏率",
        "案例卡補救率",
        "不得宣稱因果改善",
        "介入研究",
        "最小介入方案",
        "改檔前 60 秒案例模型選擇",
        "完成回報三欄補強",
        "黃色或紅色補救回放",
        "介入停止條件",
        "訪談調查",
        "操作者回饋題",
        "你能否在 2 分鐘內選出通道",
        "哪個案例模型最難判斷",
        "案例卡是否暴露漏跑命令或限制句缺漏",
        "不新增產品遙測",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_observation_replication_rules():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪觀察與複製準則" in contract
    for expected in [
        "觀察研究",
        "觀察記錄欄位",
        "觀察窗口",
        "變更案例 ID",
        "選定案例模型",
        "實際選擇通道",
        "實際執行命令",
        "完成回報三欄",
        "觀察結果",
        "操作者回饋摘要",
        "補救行動",
        "不可外推",
        "研究複製",
        "複製檢查清單",
        "同一觀察窗口定義",
        "同一案例模型選項",
        "同一指標口徑",
        "同一介入停止條件",
        "同一限制句",
        "可複製完成條件",
        "下一位操作者不用讀完整 HCS 附件",
        "不新增產品遙測",
        "不得替代 pytest 或人工 review",
        "不得宣稱改善",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_reader_semantic_entry():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪讀者語意入口" in contract
    for expected in [
        "受眾",
        "低風險 UI 維護者",
        "報告呈現維護者",
        "契約複檢維護者",
        "觀察流程維護者",
        "組成",
        "第一步：先判斷讀者角色",
        "第二步：只讀對應入口",
        "第三步：補齊觀察欄位",
        "第四步：用限制句收尾",
        "語意含義",
        "讀者角色不是權限等級",
        "入口不是自動判斷器",
        "觀察欄位不是 pytest",
        "複製成功不是改善證明",
        "低風險不代表低責任",
        "不得宣稱 runtime 安全",
        "不得宣稱使用者理解改善",
        "不得宣稱 HCS Plus 完成",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_maintenance_guide_core_argument():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪維護導覽與核心論點" in contract
    for expected in [
        "組織結構",
        "章節導覽",
        "先定位讀者角色",
        "再選通道與案例模型",
        "接著補觀察欄位",
        "最後用限制句與核心論點收尾",
        "專業性",
        "維護語氣",
        "只描述觀察窗口",
        "明列未跑命令",
        "把紅色訊號說成停止條件",
        "不得把測試綠燈寫成安全證明",
        "論點",
        "核心主張",
        "契約矩陣的目的不是提高文件厚度",
        "讓低風險改動更快收尾",
        "讓高風險契約更早升級",
        "讓觀察紀錄可複製但不被誤讀",
        "不得宣稱改善",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_short_report_media_choice():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪短版回報與媒介取捨" in contract
    for expected in [
        "溝通設計",
        "一頁摘要",
        "先說本次改動層級",
        "再列已跑命令與未跑命令",
        "最後寫不得解讀為",
        "表達",
        "建議句型",
        "我選擇的通道是",
        "我已執行的命令是",
        "本次不得解讀為",
        "媒介",
        "文字與表格優先",
        "不要新增圖像流程",
        "不要用多媒體替代限制句",
        "多媒體",
        "暫不新增圖像或多媒體",
        "保留可搜尋文字",
        "保留 pytest 與人工 review",
        "完成第 3 輪溝通思考",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_ethics_stop_and_responsibility_judgment():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪倫理阻擋與責任判斷" in contract
    for expected in [
        "倫理考量",
        "短版回報倫理底線",
        "不得把短版回報寫成安全背書",
        "不得把責任轉嫁給文件、工具或測試",
        "不得用快速通道淡化高風險契約",
        "倫理勇氣",
        "必要時要說不",
        "缺少 parser/prompt/template 證據時停止合併",
        "報告文案像交易指令時先補責任邊界",
        "高風險契約被降級時回到人工複檢",
        "倫理判斷",
        "允許回報",
        "禁止回報",
        "升級判斷",
        "低風險改動若碰到使用者行動暗示",
        "混合層若碰到核心契約詞",
        "文件或觀察若被拿來宣稱 runtime 行為",
        "不得宣稱使用者已理解",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_system_causality_evidence_layers():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪系統因果與證據層次" in contract
    for expected in [
        "複雜因果",
        "局部綠燈因果圖",
        "文件契約通過可能造成流程已安全的錯誤推論",
        "前端測試通過可能造成 parser/prompt 已安全的錯誤推論",
        "倫理阻擋存在可能造成高風險已被完全阻擋的錯誤推論",
        "湧現特性",
        "低風險快速通道累積成高風險語氣漂移",
        "案例卡增加但實際驗證減少",
        "阻擋規則存在但 reviewer 不敢啟用",
        "分析層次",
        "文件層",
        "測試層",
        "runtime 層",
        "使用者行為層",
        "同層證據只能支持同層宣稱",
        "跨層宣稱必須升級驗證",
        "不得用文件完整替代 runtime 驗證",
        "不得用測試通過宣稱使用者理解",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_maintenance_network_dynamics_image():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪維護網絡與動態圖像" in contract
    for expected in [
        "網絡",
        "維護網絡",
        "文件層節點",
        "測試層節點",
        "runtime 層節點",
        "使用者行為層節點",
        "reviewer 阻擋節點",
        "系統動力學",
        "快速通道摩擦降低回路",
        "案例卡形式化回路",
        "阻擋勇氣回路",
        "跨層宣稱升級回路",
        "系統圖像",
        "先定位證據層",
        "再連到網絡節點",
        "接著判斷動態回路",
        "最後決定維持同層宣稱或升級驗證",
        "不得把網絡圖像當成自動審核器",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_review_dialogue_default_behavior():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪 review 對話與預設行為" in contract
    for expected in [
        "談判",
        "補證據協商",
        "不降低標準",
        "我可以接受同層宣稱，但跨層宣稱需要補證據",
        "若要保留快速通道，請移除 runtime 或使用者行為宣稱",
        "若要宣稱 parser/prompt 安全，請補高顯著性命令或拆分改動",
        "說服",
        "說服不是美化風險",
        "先承認已完成的證據",
        "再指出缺口",
        "接著提出最小可接受補證據",
        "最後寫不得解讀為",
        "降低說不成本",
        "形塑行為",
        "預設行為",
        "完成回報預設三欄",
        "本次宣稱層級",
        "已補證據",
        "仍不得解讀為",
        "黃色：同層宣稱可合併但補限制句",
        "紅色：停止合併、補跑 pytest 或人工 review、拆分 patch",
        "跨層宣稱預設升級",
        "不得把好聽句型當成證據",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_conformity_difference_emotion_guard():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪防從眾、差異訊號與情緒調節" in contract
    for expected in [
        "從眾",
        "防從眾檢查",
        "多數同意不是證據",
        "前例綠燈不是本次綠燈",
        "測試全綠不是限制句",
        "快要合併不是降低標準的理由",
        "差異",
        "差異訊號",
        "改動層級差異",
        "證據層差異",
        "pipeline 模式差異",
        "風險顏色差異",
        "不得把黃色與紅色訊號寫成綠色",
        "情緒智商",
        "高壓語氣處理",
        "先命名壓力來源",
        "再回到預設三欄",
        "接著保留最小補證據路徑",
        "最後用冷靜限制句收尾",
        "不得用趕時間取代證據層",
        "不得用情緒安撫取代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_role_responsibility_power_guard():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪角色責任與權力護欄" in contract
    for expected in [
        "領導原則",
        "證據領導",
        "主責先宣告本次宣稱層級",
        "review 主導者維持升級權",
        "合併者確認紅色與黃色訊號已處理",
        "不以速度領導取代證據領導",
        "權力動態",
        "合併權限不能覆蓋紅色訊號",
        "資深度不能把前例綠燈變成通行證",
        "低權限操作者可以引用契約要求補證據",
        "權威催促必須回到預設三欄",
        "責任",
        "改動者負責本次宣稱層級與已補證據",
        "reviewer 負責仍不得解讀為",
        "合併者負責未跑命令與剩餘風險",
        "問題可追溯到角色責任",
        "不得把責任轉嫁給文件、工具或測試",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_round3_self_audit_and_closing_strategy():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣第 3 輪自我稽核與收尾策略" in contract
    for expected in [
        "自我覺察",
        "角色責任不是流程越多越好",
        "輕量使用邊界",
        "低風險同層改動只需完成回報三欄",
        "黃色訊號補限制句或最小證據",
        "紅色訊號才要求停止合併、補跑 pytest 或拆分 patch",
        "不把角色責任變成形式簽核",
        "不把文件完整當成自動審核器",
        "制定策略",
        "第 3 輪互動思考收尾條件",
        "20/20 單項完成",
        "證據層與角色責任已可追溯",
        "下一步進入三習慣綜合優化",
        "綜合優化候選：#可驗證性、#溝通設計、#系統圖像",
        "不得宣稱 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_verification_communication_system_view():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 1 次：驗證、溝通與系統圖像收斂" in contract
    for expected in [
        "綜合視角",
        "#可驗證性",
        "#溝通設計",
        "#系統圖像",
        "最終操作收斂",
        "驗證閘門",
        "不跑命令不能宣稱通過",
        "文件契約只支持文件層宣稱",
        "完成回報格式",
        "本次宣稱層級",
        "已補證據",
        "仍不得解讀為",
        "下一個可執行行動",
        "系統圖像收斂",
        "前端顯示層",
        "報告呈現層",
        "機器契約層",
        "維運決策層",
        "驗收標準",
        "每個完成宣稱都有對應命令或限制句",
        "高顯著性機器契約改動仍跑 parser、prompt、template 與 audit 回歸",
        "低風險同層改動保持輕量三欄",
        "不得把綜合優化第 1 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_evidence_audience_responsibility():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 2 次：證據來源、讀者角色與責任承接" in contract
    for expected in [
        "綜合視角",
        "#證據基礎",
        "#受眾",
        "#責任",
        "證據來源分級",
        "直接證據",
        "間接證據",
        "缺口證據",
        "未跑命令",
        "讀者角色分流",
        "低風險 UI 維護者",
        "報告呈現維護者",
        "機器契約維護者",
        "維運決策維護者",
        "合併者",
        "責任承接",
        "改動者負責證據來源與宣稱層級",
        "reviewer 負責讀者是否會誤讀",
        "合併者負責未跑命令與剩餘風險是否可接受",
        "未跑命令不能消失",
        "剩餘風險必須留到下一步",
        "不得把使用者理解、安全或投資判斷外推",
        "不得把綜合優化第 2 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_bias_learning_strategy():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 3 次：偏誤防線、速學入口與策略收斂" in contract
    for expected in [
        "綜合視角",
        "#偏誤降低",
        "#學習科學",
        "#制定策略",
        "偏誤防線",
        "表格打勾偏誤",
        "證據漂白偏誤",
        "升級逃避偏誤",
        "流程膨脹偏誤",
        "速學入口",
        "10 秒定位",
        "90 秒分流",
        "5 分鐘復盤",
        "策略收斂",
        "低風險維持輕量",
        "高顯著性必須升級",
        "未跑命令留到下一步",
        "策略膨脹必須刪減",
        "不得把矩陣完成誤讀為證據充分",
        "不得把速學入口替代完整契約",
        "不得把綜合優化第 3 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_goal_utility_reasonability():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 4 次：目標校準、效用門檻與合理性審核" in contract
    for expected in [
        "綜合視角",
        "#目的",
        "#效用",
        "#合理性",
        "目標校準",
        "股票研究系統核心目標",
        "使用者決策用途",
        "維護者合併判斷",
        "契約安全邊界",
        "效用門檻",
        "降低錯選模式",
        "降低漏跑命令",
        "降低跨層外推",
        "降低維護成本",
        "合理性審核",
        "必要性",
        "比例性",
        "可驗證性",
        "可逆性",
        "低效用規則必須刪減",
        "高成本規則必須有證據",
        "目的不明不能加入矩陣",
        "不得讓契約矩陣服務文件本身",
        "不得把效用推論寫成已證明改善",
        "不得把綜合優化第 4 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_constraints_decision_optimization():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 5 次：限制邊界、分流決策與成本最佳化" in contract
    for expected in [
        "綜合視角",
        "#限制條件",
        "#決策樹",
        "#最佳化",
        "限制邊界",
        "硬限制",
        "軟限制",
        "升級限制",
        "停用限制",
        "不得新增 runtime、遙測或自動選測工具",
        "不得替代 pytest 或人工 review",
        "不得生成交易指令或安全背書",
        "分流決策",
        "第一步：判斷改動層級",
        "第二步：判斷顯著性",
        "第三步：判斷證據缺口",
        "第四步：選擇輕量、升級、拆分或刪減",
        "成本最佳化",
        "保留低風險輕量通道",
        "合併重複規則",
        "刪除低效用規則",
        "延後無證據規則",
        "不得為了最佳化而降低高顯著性驗證",
        "不得把決策樹當成自動選測工具",
        "不得把綜合優化第 5 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_source_context_critique():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 6 次：來源分級、適用情境與批判反證" in contract
    for expected in [
        "綜合視角",
        "#來源品質",
        "#情境脈絡",
        "#批判",
        "來源分級",
        "高可信來源",
        "可用但有限來源",
        "不得作為完成證據",
        "缺口來源",
        "適用情境",
        "低風險同層文件改動",
        "報告呈現或使用者語意改動",
        "機器契約或高顯著性改動",
        "維運決策或排程風險改動",
        "批判反證",
        "反問一：這條規則可能在哪裡失效",
        "反問二：目前證據是否只支持文件存在",
        "反問三：是否有更小的限制句或刪減方式",
        "來源品質不足必須降級宣稱",
        "情境不符必須改走升級或拆分",
        "批判反證未處理不得合併高顯著性規則",
        "不得把歷史紀錄當成新證據",
        "不得把適用情境擴張到 runtime 或使用者理解",
        "不得把綜合優化第 6 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_estimation_confidence_interpretation():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 7 次：把握校準、信心邊界與解讀框架" in contract
    for expected in [
        "綜合視角",
        "#估算",
        "#信賴區間",
        "#詮釋框架",
        "把握估算",
        "估算等級",
        "高把握",
        "中把握",
        "低把握",
        "不得宣稱",
        "信心邊界",
        "適用層級",
        "證據覆蓋",
        "剩餘不確定",
        "不得跨過未測層",
        "解讀框架",
        "已驗證",
        "有限支持",
        "暫定假設",
        "未證明",
        "每個完成宣稱必須同時寫出把握等級、信心邊界與解讀框架",
        "低把握不得升格為完成",
        "信心邊界不得跨過未測層",
        "解讀框架不得替代 pytest、人工 review 或 runtime 驗證",
        "不得把估算寫成精確量化承諾",
        "不得把綜合優化第 7 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_correlation_summary_significance():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻" in contract
    for expected in [
        "綜合視角",
        "#相關性",
        "#描述統計",
        "#顯著性",
        "關聯檢核",
        "規則關聯",
        "強支撐",
        "弱支撐",
        "衝突支撐",
        "無關",
        "分布摘要",
        "完成分布",
        "缺口分布",
        "驗證分布",
        "風險分布",
        "顯著性門檻",
        "升級訊號",
        "保留訊號",
        "降級訊號",
        "刪減訊號",
        "只有強支撐且跨多個來源層級的關聯才能升級成矩陣規則",
        "分布摘要只能描述目前文件與測試覆蓋",
        "顯著性門檻不得替代 pytest、人工 review 或 runtime 驗證",
        "不得把相關性解讀為因果",
        "不得把描述統計解讀為改善證明",
        "不得把綜合優化第 8 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_probability_regression_fallacy():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線" in contract
    for expected in [
        "綜合視角",
        "#機率",
        "#迴歸",
        "#謬誤",
        "概率語言",
        "概率等級",
        "高可能",
        "中可能",
        "低可能",
        "未知或不得推定",
        "不得使用精確百分比",
        "迴歸風險",
        "舊問題",
        "回到過度宣稱",
        "回到跨層外推",
        "回到流程膨脹",
        "回到弱證據升級",
        "謬誤防線",
        "相關不等於因果",
        "通過測試不等於 runtime 安全",
        "文件完整不等於使用者理解",
        "歷史紀錄不等於新證據",
        "不得把概率語言寫成保證",
        "不得把迴歸風險寫成已修復",
        "不得把謬誤清單替代 pytest、人工 review 或 runtime 驗證",
        "不得把綜合優化第 9 次解讀為 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract


def test_pipeline_mode_contract_has_integrated_final_reasonability_verification_strategy():
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 契約矩陣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略" in contract
    for expected in [
        "綜合視角",
        "#合理性",
        "#可驗證性",
        "#制定策略",
        "合理性收尾",
        "核心目標",
        "使用者決策用途",
        "維護者合併判斷",
        "契約安全邊界",
        "完成定義",
        "三輪 HCS 思考習慣",
        "十次三習慣綜合優化",
        "每批至少一次實際檔案修改與驗證",
        "最終專案內容",
        "決策紀錄",
        "風險與驗收標準",
        "下一步可執行行動",
        "驗證門檻",
        "聚焦測試",
        "回歸集合",
        "diff check",
        "strict log",
        "狀態表",
        "契約章節",
        "維護策略",
        "文件與測試契約優先",
        "例外升級",
        "定期複檢",
        "完成只代表 HCS Plus 自主優化流程完成",
        "不得把第 10 次收尾解讀為 runtime 安全或使用者理解已驗證",
        "不得新增 runtime、遙測或自動選測工具",
    ]:
        assert expected in contract
