# API Reference

The API is local-first and intended for the bundled UI or trusted local automation.
FastAPI exposes the machine-readable contract at `/openapi.json`; mutating operations are annotated with the `MutationToken` API-key security scheme using the `X-Mutation-Token` header.

## Read Endpoints

`GET /api/observability/model-routes` returns the `model_route_budget.v1` telemetry section used by the operator panel. It reports `slow_route`, `retry_storm`, and `quality_gate_failures`; `slow_route` is maintenance evidence and remains outside the daily decision queue.

```bash
curl http://127.0.0.1:8080/api/reports
curl http://127.0.0.1:8080/api/observability/provider-sla
curl http://127.0.0.1:8080/api/observability/active-jobs
curl http://127.0.0.1:8080/api/observability/api-quotas
curl 'http://127.0.0.1:8080/api/observability/model-routes?telemetry_limit=5000'
curl http://127.0.0.1:8080/api/watchlist
curl 'http://127.0.0.1:8080/api/watchlist/report-quality-audit/historical?item_limit=0'
curl http://127.0.0.1:8080/api/stocks/2330.TW/snapshot
```

LLM quota observations are local ledger evidence, not provider-authoritative quota. Explicit per-key/model RPD responses use the existing reset-time disable; generic project/model quota exhaustion opens a Redis-backed model-scoped circuit only after the configured key retry budget is exhausted. While open, later jobs do not send another request for that model and may use the configured fallback route. Other models and 5xx retry handling remain independent.

The Gemini usage object also exposes `observed_model_calls` and `observed_model_quota_errors`, keyed by model id. The latter counts local `quota_error` and `rate_limited` ledger events in the same reset window; zero values are retained for models with calls but no observed quota errors. The UI derives a model-level error rate from these two maps. This is diagnostic evidence for routing and retry review, not official provider quota or a reason to disable a key/model by itself.

Report rows include:

- `data_trust`: data-source quality and freshness.
- `snapshot_integrity`: whether the current data snapshot still matches its own content hash; `verified` is hash-checked, `unverified` is legacy or missing a hash, and `invalid` must be manually reviewed before reuse.
- `decision_tracking`: performance since the report recommendation.
- `decision_freshness`: whether the conclusion still matches the current data snapshot.

When a snapshot has a non-empty `rerun_context.parsed`, report-history rows perform a read-only current-rule `content_credibility` projection. A recorded gate is merged with that projection so newly detected blockers/warnings are visible while previously recorded findings are retained. The optional `content_credibility_projection` object reports `status=projected|available|unavailable`, `source=snapshot.rerun_context`, and the persisted gate status. `available` means the deterministic check can run but the persisted gate is still missing; it never counts as saved quality metadata, writes the snapshot, repairs the artifact, enqueues a rerun, or changes the queue.

The read-only `report_quality_audit.items[]` payload exposes `missing_quality_fields` beside `detail` and `reason_codes`, and preserves the repair item's `severity` and `action_label` so queue consumers can distinguish a blocked manual review without parsing prose. For indexed audits, `artifact_quality_summary` may also report that Markdown/HTML contains visible gate summary markers and which gate labels were found; this is artifact evidence for manual review only, not reconstructed structured metadata and not proof that a gate passed. The audit envelope also exposes `items_returned` and `items_truncated`, because the full audit may cap item details for the UI while retaining the complete missing count. This is the exact list of absent quality gates for manual review; consumers must not reconstruct gate payloads from HTML or Markdown text or treat a truncated item list as the full set. The historical audit renderer also checks `items_total`, `items_returned`, `items_limit`, and `items_truncated` together; contradictory bounds are labeled as requiring range confirmation rather than being shown as a complete list, and that warning takes precedence over a page-number range when both apply.

The watchlist quality summary accepts `quality_metadata_coverage_pct` only when it is a finite percentage from 0 through 100; an out-of-range value is omitted from the display rather than presented as verified coverage.

The watchlist quality summary renders `quality_metadata_missing_reports`, `snapshot_invalid_reports`, and `snapshot_unverified_reports` only as finite non-negative integers; malformed or fractional count values are omitted rather than presented as report counts.

The freshness and current-quality projections use the same finite non-negative integer contract for aggregate counts and bounded item totals; fractional or malformed distributions are omitted from the UI rather than rounded into a seemingly valid scope.

The watchlist repair sample label applies the same finite non-negative integer contract to `repair_queue.summary.sampled_reports`; fractional or malformed sample sizes are omitted rather than floored into a misleading scope.

The read-only `repair_sample_overlap` label applies that contract to `audit_gap_reports`, `audit_gap_reports_in_repair_sample`, `audit_gap_reports_outside_repair_sample`, and `audit_gap_items_returned`; if any displayed overlap count is malformed or fractional, the overlap sentence is omitted instead of flooring a partial statistic.

The historical quality audit renderer applies the same finite non-negative integer contract to audit, gap, provenance, rerun, review, version, artifact, snapshot, pipeline, and bounded item counts; malformed or fractional values are omitted, and invalid core scope counts show `資料需確認` instead of being floored into a report count. The core scope requires `quality_metadata_missing_reports <= audited_reports`; when `verified_snapshot_reports` is present, it additionally requires `quality_metadata_missing_reports <= verified_snapshot_reports <= audited_reports`; when `quality_metadata_complete_reports` is present, it must not exceed `audited_reports` and, when verified scope is present, must satisfy `quality_metadata_complete_reports + quality_metadata_missing_reports = verified_snapshot_reports`. When verified, invalid-snapshot, and unverified-snapshot counts are all present, they must sum to `audited_reports`. When `items_total` is present, it must equal `quality_metadata_missing_reports`; when `items_returned` is present, it must equal the actual `items[]` length; when total, returned, and offset are present, the returned window must remain within total. A contradictory payload is not presented as a valid gap total.

Historical quality review summaries and review/missing-field/version filter counts also require finite non-negative integers; malformed `event_count` or `event_id` values are omitted from ordinal labels, while an active filter with an invalid count remains available with `資料需確認`.

For `status=complete`, the watchlist overlap label also requires `audit_gap_reports_in_repair_sample + audit_gap_reports_outside_repair_sample` to equal `audit_gap_reports`; contradictory integer counts are omitted rather than presented as an exact split.

The same `status=complete` label requires `audit_gap_items_returned` to equal `audit_gap_reports`; a supposedly complete envelope with missing gap items is omitted rather than treated as a full comparison.

For missing metadata after a refresh, `items[]` may include `rerun_context_status=present|partial|missing|artifact_fallback_available`, `rerun_execution_status=full_rerun_required|partial_rerun_available|partial_rerun_review_required|partial_rerun_unavailable`, plus `snapshot_rerun_context_status` and `artifact_rerun_context_status` when the corresponding evidence was checked. The context status describes persisted analyses, structured outputs, parsed recommendation, or recoverable preceding Agent sections; `artifact_fallback_available` means the Markdown artifact contains that preceding context, but does not authorize a partial rerun. `rerun_execution_status` is the actual read-only strategy signal: when freshness marks the conclusion stale it is `full_rerun_required`, even if artifact context is present. These fields are not gate results; they do not enqueue a rerun, approve a report, or change `blocks_auto_rerun`.

For verified report rows with missing structured quality metadata, `/api/reports` may also expose `missing_quality_fields`, `quality_metadata_provenance`, `quality_metadata_refresh_provenance`, `refreshed_from_report`, `snapshot_refreshed_at`, and `artifact_quality_summary`. These fields are read-only evidence context for the preview badge. `quality_metadata_refresh_provenance` records the three gate states that were present or missing in the snapshot immediately before a data-only refresh; it does not reconstruct a gate, prove when a gap was introduced, or authorize rerun. `artifact_quality_summary` reuses the same marker lookup as the quality audit; it is not a reconstructed gate payload or automatic approval. Complete rows do not need these gap-only fields.

The frontend uses the same evidence context for report preview, daily targets, and historical targets. A verified row with a structured gap may expose a clickable preview badge that opens the existing filename/pipeline-scoped historical audit; its detail, accessible label, title, and `data-quality-evidence-detail` prefer `report_quality_evidence.context(report).detail`, so a policy wording change cannot make preview evidence drift from the audit targets. The preview keeps its compact inline badge rather than reusing target-only HTML. These fields state that artifact markers are for manual checking only and do not prove a gate passed. History and daily targets repeat the short limitation visibly and in aria context. When `rerun_context_status` is present, the shared evidence context also labels context availability and the separate `rerun_execution_status` strategy. If the strategy is `full_rerun_required`, preview disables the final-agent rerun control and keeps the full-rerun path visible; artifact context never overrides freshness. Daily targets present review status, evidence context, rerun strategy, and the manual-only artifact warning as separate visual elements while retaining the same title/aria/data detail. The daily dashboard projects its existing quality-audit envelope as a scope-first summary with separate readable items, while retaining a text fallback when the audit is unavailable; this does not change the response numbers or create a second quality scope. When history applies `review_status` and `missing_field` together, the renderer places both active scope labels before the existing summary fields and only changes their reading order on narrow screens; it does not change the response numbers or filter semantics. This is navigation and presentation only; it does not write review events, repair artifacts, enqueue reruns, or change the report index.

The daily dashboard deliberately has two report-quality scopes: `report_quality_audit` covers every latest ticker/pipeline index row, while `repair_queue.summary.sampled_reports` describes the recent report sample used for repair actions. The watchlist summary labels the repair sample size when both are present, so `quality_metadata_missing_reports` must not be interpreted as a count already covered by the repair queue. `repair_queue.summary.items_limit`, `items_returned`, and `items_truncated` describe the bounded repair-item list separately from the full `action_required` count; a truncated list must not be treated as the complete repair sample. The watchlist quality-gap summary also checks `items_total`, `items_returned`, `items_limit`, and `items_truncated` together; contradictory bounds are labeled as requiring range confirmation rather than silently treating visible rows as the complete gap list. `report_quality_audit.repair_sample_overlap` is a read-only comparison by filename/pipeline: `status=complete` exposes exact `audit_gap_reports_in_repair_sample` and `audit_gap_reports_outside_repair_sample`, while `status=partial` reports only the returned audit items and deliberately omits an exact outside count because unexpanded gaps were not compared. When the latest audit details are complete and untruncated, those current gap items may also appear as `source=report_quality_audit`, `type=manual_review` in `decision_queue` for read-only operator triage; overlapping repair-sample items remain the repair source. Partial or unavailable audit details and historical audit items stay out of the daily queue. This is a read-only operator action and does not enqueue reruns or write review events, artifacts, indexes, or repair state.

`missing_quality_field_counts` groups the missing-report count by `report_conformance`, `evidence_exit_gate`, and `content_credibility`. It counts only verified snapshots and is a summary of missing evidence, not a pass/fail result or an instruction to rerun.

`quality_metadata_missing_by_rerun_execution` groups missing-metadata items by their read-only rerun strategy: `full_rerun_required`, `partial_rerun_available`, `partial_rerun_review_required`, `partial_rerun_unavailable`, or `not_evaluated`. When present, the strategy buckets form a complete partition of `quality_metadata_missing_reports`; clients omit the strategy summary when the map is malformed or inconsistent. `not_evaluated` means the item has no enough refresh provenance to expose a strategy; it must not be interpreted as local rerun being unavailable. This is an operational ordering signal, not an enqueue command; `full_rerun_required` remains authoritative when freshness is stale even if artifact context is available.

`quality_metadata_missing_by_rerun_context` groups the same verified missing-metadata items by context evidence: `present`, `partial`, `artifact_fallback_available`, `missing`, or `not_evaluated`. When present, the context buckets form a complete partition of `quality_metadata_missing_reports`; clients omit the context summary when the map is malformed or inconsistent. `artifact_fallback_available` means a recoverable preceding Agent section is visible in the artifact; it does not authorize a partial rerun. `not_evaluated` means the item did not expose a trustworthy context status, not that context is missing. This is a read-only preparation summary and does not change `rerun_execution_status`, freshness, review, or queue behavior; the map is repeated in `quality_metadata_by_pipeline`.

`quality_metadata_missing_by_provenance` groups missing metadata reports into `before_refresh`, `after_refresh`, and `no_refresh_provenance`. When present, the three buckets form a complete partition of `quality_metadata_missing_reports`; clients omit the provenance summary when the map is malformed or inconsistent. `before_refresh` means the optional pre-refresh trace already listed the current missing gate; it is evidence about ordering, not a reconstructed gate result. `after_refresh` means that the snapshot has a `refreshed_from_report` attribution but no matching pre-refresh evidence; it does not prove that refresh caused the metadata gap. `no_refresh_provenance` means the snapshot has no refresh classification; it does not prove that the snapshot was never refreshed. Each returned item repeats this as `quality_metadata_provenance` and includes `refreshed_from_report` and `snapshot_refreshed_at` when available. The UI labels the three states as `刷新前已有缺口`、`有刷新歸因` and `未標記刷新來源`.

When `quality_metadata_refresh_provenance` is present, its `source` is `previous_snapshot_before_refresh`, `recorded_fields` contains gate states accepted by the current contract, and `missing_fields` contains gates that were already absent before the data refresh. If the current gap is covered by that pre-refresh list, the repair item uses `quality_metadata_before_refresh`; otherwise the existing `quality_metadata_after_refresh` classification remains neutral. This evidence is optional and read-only; older snapshots without it keep the neutral classification.

`quality_metadata_missing_by_version_status` groups missing metadata by `current`, `historical`, or `unknown`; when present, those buckets form a complete partition of `quality_metadata_missing_reports`, and clients omit the version summary when the map is malformed or inconsistent. Each affected item also exposes `report_version_status`. `current` is the latest indexed row for that ticker/pipeline, `historical` is an older indexed version, and `unknown` means the caller did not provide enough index scope to determine version order. Historical coverage can contain old-version gaps that no longer describe the current report, so consumers must read this distribution before treating the coverage percentage as current report readiness.

`artifact_quality_summary_by_status` counts the artifact marker evidence for all missing-metadata rows before `items[]` pagination: `present`, `not_found`, and `unavailable`. `present` means Markdown/HTML contains visible gate summary markers for manual review only; it is not a structured gate pass, and zero counts do not prove that an artifact is absent when the row has no readable artifact summary.

`artifact_quality_summary_by_field` counts visible marker evidence by quality field across the same full missing-metadata set: `report_conformance`, `evidence_exit_gate`, and `content_credibility`. The field counts may be lower than `present`; this difference is intentional and makes partial artifact evidence explicit instead of implying all three gates are available.

Repeated read-only quality audits may reuse an in-process row derivation cache for up to 15 seconds when the report-index artifact fingerprint is unchanged. The cache is bounded, invalidates when indexed timestamps or artifact hashes change, and never writes artifacts, indexes, queues, or rerun state.

The indexed quality-audit path reads persisted `content_credibility` metadata directly and skips the current-rule projection used by ordinary report-history rows. This keeps audit coverage tied to saved gate metadata and avoids spending projection cost on a read-only envelope that does not consume it; the normal report-history path still exposes `content_credibility_projection` when a recorded gate exists.

`quality_metadata_by_pipeline` repeats the same audit counts per `pipeline_id`, including its own `verified_snapshot_reports`, `quality_metadata_coverage_pct`, `quality_metadata_coverage_basis`, missing-gate counts, rerun execution distribution, and rerun context distribution. The pipeline entries are a complete partition of the top-level audit scope, so their `quality_metadata_missing_reports` must add back to the top-level missing count; clients omit both pipeline gap and pipeline context summaries when entries are malformed, incomplete, or arithmetically inconsistent. Pipeline context is shown only when every entry has a valid `quality_metadata_missing_by_rerun_context` map whose counts add back to that pipeline's missing count. History and daily summaries use the context distribution to show which mode has artifact fallback or no local context; this makes a full historical response sufficient for pipeline prioritization without issuing one request per mode.

`quality_review_by_status` counts the current revision-scoped review state for missing-metadata reports only: `pending`, `approved_with_gap`, `rejected`, and `deferred`. When present, those buckets form a complete partition of `quality_metadata_missing_reports`, and clients omit review progress when the map is malformed or inconsistent. The same map is included under each pipeline summary. A pending count means no current review event exists; it does not mean the report passed or failed a quality gate. UI summaries use `quality_metadata_missing_reports` for the total evidence gap and this map for review progress; a decided gap must not be labeled as still pending manual review.

`report_quality_audit.selection_basis = latest_per_ticker_pipeline` means the `all_indexed_reports` scope audits the latest indexed row for each ticker/pipeline pair, not every historical artifact version. Use this field with `audited_reports` when describing coverage.

The indexed latest audit also exposes `decision_freshness_summary` as a separate read-only count over the same scope. Its `current_reports`, `needs_rerun_reports`, and `unknown_reports` describe whether conclusions match their snapshots; they do not change `quality_metadata_coverage_pct`, quality gate status, review state, repair queue, or rerun behavior. Only interpret the counts when `scope` and `selection_basis` match the audit envelope.

The same indexed audit exposes `decision_freshness_items` as a bounded navigation sample. Its `items_total` is the full `needs_rerun_reports` count, while `items_returned` is capped by `items_limit` (currently 5); `items_truncated` must be shown when the sample is incomplete. A returned count greater than `items_limit` is contradictory even when it equals the total, so the UI labels the range as needing confirmation instead of presenting it as a complete list. If the returned count is smaller than the total but the truncation flag is missing or contradictory, the UI keeps the target links but labels the range as needing confirmation instead of presenting the total as a complete list. Each item is a read-only target for opening the existing history view and does not create a queue item or enqueue a rerun.

`GET /api/watchlist/current-quality-summary` is a separate read-only projection of the current report-history quality gates over the latest `latest_per_ticker_pipeline` scope. `report_conformance_by_status`, `content_credibility_by_status`, and `evidence_exit_gate_by_verdict` each use the full `audited_reports` denominator; they must not be merged into persisted quality-metadata coverage or freshness counts. The backend loads the full index through pagination and returns an unavailable response rather than publishing a smaller, apparently complete scope when a page is missing, malformed, inconsistent with the declared total, or otherwise incomplete. These maps accept only their contract keys (`passed|warning|blocked|unknown` for status and `approved|caution|rejected|unknown` for verdict); an unknown key is not silently ignored and causes the frontend to reject the projection. `non_passed_reports` is the union count of reports with at least one non-passed current gate and therefore cannot exceed `audited_reports`; the frontend rejects the current-quality projection when that bound is violated. Its `items[]` contains at most 5 non-passed current conformance targets, with `items_total`, `items_returned`, `items_limit`, and `items_truncated` describing the bounded navigation sample. Every returned target must have a non-empty `filename`, explicit normalized conformance/content/evidence statuses, and at least one non-passed gate; otherwise the frontend rejects the whole projection instead of rendering an unqualified report as a review target. A returned count greater than `items_limit` is contradictory even when it equals `items_total`; the UI labels the visible range as needing confirmation rather than rendering the total as a complete list. If `items_returned < items_total` without a consistent `items_truncated=true`, the UI labels the range as needing confirmation rather than rendering the total as a complete list. The bounded process cache is keyed by the projection scope/filter plus the same latest index-row fingerprint used by quality audit (`updated_at`, file mtime, and stored content/data hashes), so an indexed report change invalidates the old current-quality projection immediately without allowing indexed and historical-filter payloads to share a cache entry; if the fingerprint cannot be read, the builder bypasses cache reuse instead of serving an unverified stale summary. The watchlist loads this endpoint after the fast daily dashboard response and updates the board when it arrives. Targets open the existing history view only; they do not write snapshots, reviews, indexes, queue items, or rerun jobs.

The same current-quality projection includes `quality_gate_action_counts` and the additive `quality_gate_action_counts_by_freshness`. The former counts the read-only `quality_gate_repair_item` recommendation once per audited report; the latter partitions those same action counts into `current`, `needs_rerun`, and `unknown` using the report's conclusion freshness. `quality_gate_action_scope.is_daily_queue=false` applies to both fields: they are not daily queue counts and do not imply a review, repair, or rerun was scheduled. Clients may omit the freshness breakdown for legacy payloads and retain the total action wording. When the optional freshness map is present but malformed or does not add back to the total by action, the frontend keeps the independently valid total and omits the freshness breakdown.

The same current-quality projection includes `evidence_failed_count` (the aggregate persisted `failed_count` for sampled numeric mismatches) and `evidence_unverifiable_reason_counts`, an aggregate of the persisted evidence gate's compact unverifiable reason counts over that current scope; each returned `items[]` target also carries its own counts. `evidence_mismatch_claims_by_freshness` counts those mismatch claims by `current`, `needs_rerun`, and `unknown`, while `evidence_mismatch_reports_by_freshness` counts affected reports in the same buckets. A target with `evidence_failed_count > 0` also carries `evidence_mismatch_freshness_status`; these fields describe whether the report text is current against the snapshot, not whether the mismatch is harmless. The watchlist and historical current-quality summary render these as operator-facing labels such as `證據數值不一致`、`資料已更新、本文需完整重跑` and `研究來源非 canonical`; unknown future reason codes remain visible as raw codes. This is read-only diagnostics: it does not copy sampled claim text, change a verdict/status, or create a review, rerun, repair, queue, snapshot, or artifact side effect.

All shared operator-facing evidence, freshness, blocker, and action summaries accept only finite non-negative integer counts; positive-entry distributions require a value greater than zero. Fractional, non-finite, or malformed optional counts are omitted field-by-field, including `evidence_failed_count`, rather than being rounded or floored into a plausible report count. A valid neighboring field remains visible, and a zero affected-report count remains valid when another summary field establishes the bucket context.

`GET /api/watchlist/report-quality-audit/historical` is a separate read-only audit for every indexed report version. Its envelope uses `scope=all_historical_indexed_reports` and `selection_basis=all_indexed_versions`; it is intentionally excluded from the daily decision queue. Optional `q` and `pipeline` filters reuse the report-history search contract and limit the audited version set; `audited_reports` then means all indexed versions matching those filters. `item_offset` and `item_limit` page only the returned manual-review `items[]`; `items_total`, `items_offset`, `items_has_prev`, and `items_has_next` expose the slice boundary while the coverage totals remain unchanged. Use `item_limit=0` when only the filtered coverage counts are needed. This endpoint does not repair artifacts, enqueue reruns, or write the report index.

The same historical endpoint accepts read-only `review_status=all|pending|approved_with_gap|rejected|deferred`. A selected status filters the audited version set before coverage and item pagination, and the response records the applied value in `review_status_filter`; this helps operators revisit one review state without implying that other states were audited in that response. It does not write the review ledger.

The same historical response may include `current_quality_summary` as a separate, read-only current-rule projection. Its `scope=historical_filter_current_latest` and `selection_basis=latest_per_ticker_pipeline` mean that it covers only the latest version for each ticker/pipeline matching the same `q`/`pipeline` filters; `filters` echoes that boundary. Its conformance/content/evidence distributions use their own `audited_reports` denominator and must not be merged into historical persisted metadata coverage. Both the historical version audit and its current projection load their full filtered index scopes through pagination; if either collection is incomplete, the route returns an unavailable audit rather than undercounting the scope. The historical route uses `item_limit=0` for this summary, so it reports counts without adding another target list; if targets are returned by another compatible producer, each must have a non-empty `filename`, explicit normalized gate statuses, and at least one non-passed gate. The client validator also requires `items_returned <= items_total`, `items_returned == len(items)`, and a valid non-passed target shape before rendering, so contradictory bounded metadata or an unqualified target is rejected. It does not reconstruct missing gates or create any artifact, review, index, queue, or rerun side effect.

It also accepts read-only `missing_field=all|report_conformance|evidence_exit_gate|content_credibility`. A selected field keeps only verified reports whose `missing_quality_fields` contains that gate, then applies any selected `review_status`; the response records the normalized value in `missing_quality_field_filter`, and `audited_reports`, coverage, and pagination counts describe only that field-scoped set. The history UI labels this as `缺口範圍` and keeps an `all` navigation entry, including when the selected field has zero rows. When both filters are selected, both scope labels remain visible and the backend applies them as an intersection. This filter is GET-only and does not repair artifacts, write the review ledger, enqueue reruns, or alter the daily queue.

It also accepts read-only `version_status=all|current|historical|unknown`. A selected version status narrows the indexed version scope before coverage and item pagination: `current` is the latest ticker/pipeline row, `historical` is an older row, and `unknown` lacks enough index scope to classify the version. The backend applies this scope to index rows before hydrating snapshot/artifact evidence, so a current-only audit does not read every historical artifact; this changes read cost, not the audited scope or numbers. Complete reports remain in the selected version scope denominator; if `review_status` or `missing_field` is also selected, those gap-only filters are then applied to that scoped set. The response records the normalized value in `report_version_status_filter`, and the history UI labels the active scope as `版本範圍`. This GET-only filter does not repair artifacts, write the review ledger, enqueue reruns, or alter the daily queue.

`missing_quality_fields` describes missing structured quality metadata in the verified snapshot. When present, `artifact_quality_summary.fields` is a separate read-only hint that matching marker text can still be found in the report artifact; it is not a reconstructed gate result and must not be interpreted as automatic approval. Daily and history targets label these layers separately as `結構化缺口` and `artifact 摘要可查`.

The history quality filter state stores only the normalized `reviewStatus`, `missingField`, and `versionStatus` enums in tab-scoped browser `sessionStorage`, so a refresh in the same tab can restore the visible audit scope without storing report content or identifiers. Scoped daily-to-history navigation calls the existing reset boundary and clears those values before loading its filename/pipeline scope.

The surrounding history workspace applies the same tab-scoped persistence to its visible scope: search query, pipeline, recommendation, data-trust, and `include_versions`. A daily scoped navigation uses `history_filters.setValues()` to overwrite that scope with its filename/pipeline and `include_versions=true`; it does not leave the previous search or pipeline in the background request.

The restored history scope does not persist page number, report preview, or decision-tracking stock snapshot content. The workspace resets those transient states to page 1 and hides the preview/snapshot when the scope changes; an in-flight snapshot response is ignored if it belongs to an older scope. This keeps session persistence limited to filters and prevents stale report content from being presented beside a new list.

The response keeps `quality_review_by_status` keys even when a selected status has count `0`; clients should keep the current status and an `all` navigation entry visible so an empty filtered result remains recoverable.

The history UI derives its visible review progress from this map: `approved_with_gap + rejected + deferred` is the decided count, and the sum of all four statuses is the missing-quality denominator for the current response scope. Complete reports are never included in that progress denominator.

The daily watchlist board uses the same derivation for its latest-per-ticker/pipeline audit summary, so the two read-only entry points expose the same review workload semantics; complete latest audit details may add a manual-review presentation item to `decision_queue`, while the historical entry point remains excluded. The frontend evidence helper also exposes `renderTargetContext({ reviewStatus, evidenceContext, warning }, escapeHtml, classNames)`, returning the ordered plain `text` and escaped `html` projection used by history and watchlist targets. `classNames` only supports consumer presentation compatibility; it does not change the underlying evidence text or create a gate verdict.

When `review_status` or `missing_field` is not `all`, `quality_metadata_coverage_pct`, `audited_reports`, and pagination counts describe only the selected scope. Consumers must not present the filtered coverage percentage as whole-library quality; the history UI labels the selected scope as `審核範圍` or `缺口範圍` and reserves `品質 metadata 完整度` for the unfiltered response.

For a filtered response with `audited_reports=0` and `items_total=0`, the correct interpretation is「目前沒有符合該審核狀態或缺口欄位的品質缺口」；it is not evidence that zero reports were complete or that the whole library has zero coverage.

The daily watchlist board reuses the same `artifact_quality_summary` item evidence when it renders report-quality targets. It may expose the marker fields through `data-quality-artifact-fields` and human-readable target context, but this remains a read-only manual-review hint and does not alter the daily decision queue.

Daily report-quality targets also expose the current `quality_review.status` in visible and accessible target context. This is status evidence only; review decisions and notes remain owned by the historical review controls and their mutation-token boundary.

Each daily report-quality target may provide a scoped, read-only navigation into the history workspace. The client passes the target filename as `q`, its pipeline as `pipeline`, and enables historical versions; the workspace resets recommendation/data-trust/review-status filters before issuing the existing GET audit/list requests. This is navigation only and does not create a queue action or review mutation.

When the history workspace has `顯示舊版報告` enabled, it calls the same endpoint with the current search and pipeline filters. The tracking workspace offers a read-only shortcut to this historical scope when its latest-per-ticker/pipeline audit has missing quality metadata; the shortcut only switches views and enables the existing checkbox. The resulting read-only summary and up to five report targets are shown above the existing history list; each target also exposes its missing gate labels, quality provenance, and any visible artifact summary markers in the visible label plus accessible title/aria context. `上一批`/`下一批` loads the remaining targets through `item_offset`, while opening a target reuses the normal report preview callback and does not create a daily queue action. The summary exposes the quality coverage basis (`verified_snapshot_reports`) and flags invalid or unverified snapshots instead of treating them as complete evidence. Rapid filter changes use latest-request-wins for both the audit summary and the report list, so a slower response from an older filter cannot replace the current scope.

When `quality_metadata_by_pipeline` reports missing rows, the historical summary also renders one read-only quick filter per affected pipeline. Selecting it updates the existing history pipeline filter, resets the list page and preview, and re-runs the same GET-based history/audit load; it does not change the audit denominator or create a repair, rerun, or queue action.

Report quality metadata repair accepts mapping-safe top-level report envelopes and nested gate mappings before checking `snapshot_integrity`, `report_conformance`, `evidence_exit_gate`, or `content_credibility`; read-only mapping wrappers must not interrupt the audit.

The quality metadata completeness check recognizes only contract states: `report_conformance` and `content_credibility` use `passed`, `warning`, or blocking states, while `evidence_exit_gate` uses `approved`, `caution`, or `rejected`. Placeholder values such as `not_recorded`, `unknown`, and `N/A` remain missing metadata.

The deterministic `content_credibility` gate also checks canonical long-term scenario targets when they are present: bear must not exceed base, and base must not exceed bull. An inverted pair is `blocked`; an explicitly present but unparseable scenario target is a `warning`. Missing scenario keys are not invented and mode-D reports without long-term scenario targets keep their existing trade-setup checks.

For mode-D trade setup checks, a target or stop-loss field containing multiple non-range scenario prices records `ambiguous_trade_setup_price_inputs` as a non-blocking warning and exposes the parsed `target_price_candidates` or `stop_loss_candidates` in the check details. Percentage adjustments such as `10%` are removed before price extraction and cannot become a price candidate. Valuation multiples such as `28.2x PE band` or `18x PE band` are removed only when the PE/P/E, 本益比, valuation, or band context is explicit; an unqualified `x`/`倍` token is not broadly suppressed. When the same issue is present in persisted metadata and the current projection, the current projection's issue details take precedence so stale candidates do not remain visible; recorded issues that are absent from the current projection are preserved. An explicit two-endpoint price range remains valid, including a range whose second endpoint is labeled as a 52-week high or low. A parenthesized price explicitly labeled as a high, low, pressure, or support reference is not treated as a second scenario price; a real follow-on scenario such as `can rise to 120` remains a candidate. Neutral direction remains neutral; the warning only prevents a multi-scenario string from being presented as a confidently checked single price.

Trade setup price parsing removes explicit calendar tokens before evaluating those fields, including bare month/day forms such as `8/18` as well as full dates and horizon ranges. This prevents a date mentioned in the stop-loss rationale from becoming an extra candidate price; the actual price value remains subject to the same direction check.

Evidence claims that explicitly combine a `P/E River Chart` label, an `x` band/位階 marker, and a price unit use the `data.pe_river_chart.bands` semantic path rather than generic `data.pe_ratio`. This covers legacy wording such as `59.6x 區間：1,379.14 TWD`; when the snapshot has no River Chart band series, the claim remains `unverifiable` and does not borrow a numerically equal generic P/E value.

Table evidence extraction ignores a table value cell that already contains its own numeric currency/unit token when that cell would otherwise be parsed as the next row's label (for example, `NT$464 億 | 18%`). A normal semantic pair such as `營收 | NT$464 億` remains claimable; this is a narrow parser guard and does not alter snapshot values, tolerance, sampling policy, verdicts, or persisted artifacts.

Evidence extraction preserves a numeric horizon prefix in labels such as `3個月目標` and `6個月`, including compact recommendation rows, instead of exposing only the trailing `個月` fragment. Confidence fields such as `資料信心分數` remain unverifiable against evidence paths because they are quality metadata, not source evidence; the gate reports `confidence_metadata_not_evidence` for that boundary and does not upgrade the claim or change the verdict.

For a compact `最終投資建議` row whose `3/6/12個月` values have no persisted `rerun_context.parsed` or `structured_outputs` and no canonical target path, the gate reports `legacy_conclusion_without_snapshot_path`. This includes a currency-prefixed value label such as `NT$209.0；6個月` when the same raw row names `最終投資建議`. This is a more precise routing reason for an old conclusion that cannot be reconstructed; it remains `unverifiable` and does not borrow `content_credibility`, `report_conformance`, `analyst_target`, or another horizon value. When parsed or structured context exists, the same missing target mapping remains `missing_semantic_path`; non-recommendation month labels are not classified as legacy conclusions.

Target evidence matching treats an exact `目標價`/`target price` label separately from a descriptive label such as `航空運輸業，目標價`. The descriptive form does not inherit `valuation` or DCF paths from a nearby sentence, so an unrelated bear intrinsic value cannot become its evidence; without an explicit canonical target source it remains `unverifiable`. Scenario and DCF claims must retain their own explicit scenario/valuation wording.

Numeric claim extraction preserves comma-grouped integers when a sentence follows the value, so `1,177,000. Borrowed short sale today: 21,000.` is checked as `1,177,000` rather than a truncated `1,177`; this is a parsing-boundary fix and does not change tolerance or unit conversion. Derived metrics such as `券資比` and `潛在下行空間` remain `unverifiable` and are classified as `derived_metric_not_canonical` when the snapshot has only component/input values and no canonical ratio or `downside_pct` scalar; stop-loss labels such as `防軋空停損點` and `價格停損條件` use the separate `risk_control_not_canonical` reason when no canonical `risk_price`/stop-loss scalar exists. The gate does not infer a ratio, recompute a percentage, or bind a risk control to an input path; if a canonical field exists, ordinary matched/mismatch evaluation still applies.

Numeric claim extraction also excludes a narrow set of non-evidence tokens: HTTP 4xx/5xx codes immediately following `fallback`/`error`/`不可用` wording, and duration tokens such as `30-day` when they are not a value with a financial unit. A real value such as `target price: 429 TWD` remains claimable; this guard only prevents provider failure metadata and time-span prose from entering evidence counts.

Scenario target labels `熊市情境`、`基本情境`、`牛市情境` and `熊/基/牛情境`, plus a table row whose first cell explicitly says `熊市`、`基本` or `牛市`, are classified as `scenario_target_not_canonical` when no canonical scenario scalar exists. Quality metadata, DCF values, current price, or another target path are not borrowed; the claim remains `unverifiable`. A real canonical scenario field such as `rerun_context.parsed.price_targets.bear` still uses ordinary matched/mismatch evaluation.

Growth-scenario table rows whose first cell says `保守`、`悲觀`、`中性`、`基準` or `樂觀`, and whose nearby context names `情境預測`、`年營收` or `CAGR` (or whose reported unit is `億`), are classified as `analysis_metadata_not_evidence` when no canonical projection path exists. The numeric forecast remains `unverifiable`; the gate does not borrow current revenue, analyst target, or another scenario value.

Exact narrative level labels `心理關卡`、`第二支撐`、`關鍵支撐區`、`近期支撐` and `支撐位` are classified as `technical_level_not_canonical` when no canonical technical-level or `risk_price` scalar exists. The gate does not borrow current price, target candidates, or nearby history; a canonical `risk_price` still uses ordinary matched/mismatch evaluation. A sentence that explicitly names `Agent 3 評分` is classified as `analysis_metadata_not_evidence` even when the score label includes a longer narrative prefix.

For a support or pressure claim that names a dated monthly high/low, the evidence parser binds `price_history[month=YYYY-MM].low|high` only when the reported price is the numeric value immediately associated with that date. A yearless form such as `6 月份高點` is eligible only when the snapshot has one unique year for that month; an explicit `YYYY-MM`/`YYYY 年 M 月` keeps its named year. If a sentence lists an earlier contextual price before the dated monthly extremum, that earlier claim remains `unverifiable` instead of borrowing the later value's path; the secondary dated claim may still be verified independently. News/catalyst wording and cross-year ambiguity remain `unverifiable`. This is a semantic boundary, not a tolerance or verdict change.

For a support, pressure, or prior-high claim that explicitly says `月底收盤價`, `月末收盤價`, or a specific month `收盤價`, the evidence parser binds the associated price to `data.price_history[month-end=YYYY-MM]` when the snapshot has one unambiguous month-end node. The same mapping applies to a separately extracted secondary month-end close value. Wording such as `月底的平台位置`, an unqualified month-end price, news/catalyst price, or a date that does not explicitly identify a close remains `unverifiable`; this does not infer a price-history source, change tolerance, or alter the verdict boundary.

A bottom-boundary label such as `強勁底部分界` may use the dated `price_history[YYYY-MM-DD]` path when the same claim includes an explicit close marker (`收盤價`/`close`), a TWD/元 price, and an unambiguous date whose adjacent value agrees. `平台位置`, an unqualified bottom label, news/catalyst wording, and mismatched values remain `unverifiable` or `mismatch`; the parser does not infer a bottom price from the label alone.

Chinese `催化劑` wording is treated as a news-source boundary for dated support or low-point prices. Even when the date and value happen to equal a `price_history` node, the claim remains `unverifiable` with `news_source_not_canonical`; the gate does not promote a catalyst-mentioned price into canonical market-history evidence.

`盤中速報` wording follows the same news-source boundary for support, pressure, or risk prices. A same-valued target-price candidate, current price, or `risk_price` does not become evidence unless the report has a matching canonical source path.

`FactSet`、`券商研究` 或 `市場研究` 目標／估值若沒有同路徑 canonical snapshot，會以 `research_source_not_canonical` 分類並維持 `unverifiable`；不得改用 `current_price`、DCF、EPS 或其他 provider 的同值欄位。

目前 `short_balance` claim 若已有 canonical field marker，但原文明示 `null`、`N/A`、`not provided` 或不可用，且 snapshot 該欄位沒有數值，evidence gate 會以 `snapshot_field_unavailable` 分類並維持 `unverifiable`；這只改善人工分流，不把缺值當成零，也不借用同一 snapshot 的其他籌碼欄位。

共享品質 helper 會把 `snapshot_field_unavailable` 顯示為「快照欄位不可用」，讓操作員知道這是來源缺值而不是零值或 parser 漏掉的欄位。

`US CPI YoY`、`CPI YoY` 或 `美國 CPI 年增率` 只在同一 snapshot 存在 `data.macro_indicators.indicators.us_cpi_yoy.value` 時核驗；同值的全球市場節點、FRED `summary_text` 或其他宏觀欄位不能替代該 path，缺少該欄位時仍是 `no_matching_snapshot_path`／`unverifiable`。

A numbered, phase-style, or defense-line label such as `波段壓力二` or `長期防線` may use the `data.week_52_high` or `data.week_52_low` semantic path only when the same claim explicitly names `52 週最高價`/`52 週最低價` (or the equivalent high/low wording) and the reported TWD/元 value agrees with that field. A generic numbered pressure/support/defense label without the explicit 52-week marker remains `unverifiable`; the parser does not infer a week-extreme source from the label alone.

An English `Last 5 days Net Buy` label maps only to `data.institutional_trading.last_5_trading_days_net_buy_thousand_shares` when that canonical field exists and the reported `k` value agrees. It does not borrow `total_net_buy_thousand_shares` merely because the number is equal; if the dedicated 5-day field is absent, the claim remains `unverifiable`.

Within the 30-day institutional trading section, exact `Foreign`/`外資` and `Investment Trust`/`投信` labels map only to their matching `data.institutional_trading.net_buy_thousand_shares_by_category.foreign|investment_trust` paths when the values agree. A bare `Total` label maps to `data.institutional_trading.total_net_buy_thousand_shares` only when the preceding claim context contains both category labels; an isolated `Total` remains `unverifiable` instead of borrowing a same-valued field.

Borrowed-short claims map to their own TWSE paths: explicit `Borrowed Short Return Today`/`Today's borrowed short return`, or a compact `return` after `borrowed short sale`, uses `data.chip_data.twse_margin_short_sales.borrowed_short_return_today`; the exact `vs Sale Today` comparison label uses `data.chip_data.twse_margin_short_sales.borrowed_short_sale_today` and converts raw shares to the report's `k` unit. The parser does not reuse the sale path for a return claim, and does not reuse the return path for `vs Sale Today`.

An exact standalone English `Price` label with a reported currency value maps to `data.current_price`; the matcher is exact so `Price Target` remains a separate target-price claim and is not mapped to current price. If the canonical current price exists but differs, the evidence result is `snapshot_value_mismatch` rather than `verified`; this is read-only evidence and does not rewrite the report or snapshot.

Analysis rubric labels such as `品牌影響力`、`網路效應`、`轉換成本`、`成本優勢`、`專利技術`、`FOMO 評分`、`聰明錢派發評分`、`Score` and exact `評分` are classified as `analysis_metadata_not_evidence` when no canonical snapshot path exists. They remain `unverifiable`; the gate does not borrow financial or market values merely because the score is numeric.

When the same international-market narrative explicitly names `S&P 500`, `台股加權指數`, and `Change 1d`, the first reported change maps to `data.global_market_context.items[spy].change_1d_pct`. This narrow parser boundary does not use the Taiwan index or another symbol as a fallback; if the SPY field is absent, the claim remains `unverifiable`.

When a parseable 12-month recommendation target and all three canonical scenario targets are present, content credibility also projects the existing final-audit range check: the recommendation target should stay between `bear * 0.7` and `bull * 1.3`. A target outside that explainable range records `recommendation_target_outside_scenario_range` as a warning with the target, bounds, and scenario values. This is read-only warning evidence for historical/API projections; it does not replace final-audit, scenario-order blocking, or create a rerun/repair action.

When a report has a recommendation field but its normalized label is outside `買入|持有|避免|放空`, content credibility records `unrecognized_recommendation_label` as a warning because directional alignment cannot be evaluated. Final-audit remains responsible for the separate structural contract and may still block the report.

If `evidence_exit_gate` is `not_recorded` (including normalized placeholder values such as `NaN`) and the recommendation confidence is at least `8/10`, content credibility records `high_confidence_unrecorded_evidence` as a warning. This does not upgrade a missing evidence gate to rejected; it prevents high confidence from being presented as fully supported. `approved` evidence and low/unknown confidence retain their existing behavior.

When the evidence gate is not approved, the `non_approved_evidence_gate` content-credibility warning carries compact `evidence_claim_count`, `evidence_sampled_count`, `evidence_verified_count`, `evidence_failed_count`, `evidence_unverifiable_count`, and `evidence_unverifiable_reason_counts` fields from that same read-only gate. `evidence_verified_count` is the number of sampled claims whose gate status is `verified`, so operators can distinguish verified coverage from the remaining failed or unverifiable sample. If a current projection changes the same gate to `approved`, stale recorded evidence-alignment issues are suppressed; `caution` and `rejected` findings remain visible. It does not copy sampled claim text, change the evidence verdict, or create a review, rerun, repair, or queue side effect.

When the current evidence projection sees `decision_validity_status=needs_rerun` or `refreshed_without_analysis_rerun=true`, it adds a compact `freshness_context` to the projected evidence gate and the non-approved content warning adds the same data as `evidence_freshness_context`. The context contains only rerun status, conclusion/snapshot timestamps, and the rerun reason; it does not downgrade a real mismatch, upgrade a verdict, or write snapshot, artifact, index, review, rerun, repair, or queue state.

Content credibility also reuses the shared confidence calibration policy used by final-audit. When `data_trust` or unresolved cross-source conflict lowers the recommended confidence cap and the parsed recommendation exceeds that cap, it records `confidence_exceeds_data_trust_cap` with the raw score, effective score, cap, and calibration reasons. This is warning-level projection only; the shared calibration policy remains authoritative and non-downgraded scores are not escalated.

Final-audit and structured-output confidence downgrade warnings use one shared message formatter, so the same calibration event is not emitted twice merely because it crossed two internal boundaries. When historical/API projection reads older conformance details with equivalent confidence-warning wording, it deduplicates only the stable agent/trust/raw-confidence/cap fingerprint for display; raw `report_conformance` details remain unchanged.

When the recommendation confidence cannot be parsed, the `confidence_data_trust_calibration` check reports `status=unavailable` rather than `passed`, with a message that the cap check could not be completed. This does not create a warning or block the overall `content_credibility` result; it prevents an incomplete calibration from being presented as a successful check.

Trade-setup price extraction removes explicit calendar dates and period expressions before parsing the first price. Period ranges such as `1-2週`, `1至2週`, and `1 to 2 weeks` therefore cannot be mistaken for a target or stop price; the actual price later in the same text remains eligible for the existing parser.

For directional recommendations (`買入`, `避免`, or `放空`) with at least two parseable 3/6/12-month targets, content credibility also projects the existing forward target-sequence rule as `horizon_target_sequence_conflict` warning evidence. It does not replace the final-audit critical contract; it keeps the same deterministic sequence rule visible when a historical/API projection lacks raw final-audit details.

Rendered Markdown and HTML execution summaries expose `Content credibility` as an explicit quality marker. The read-only artifact evidence summary also recognizes the existing `內容一致性` reading-notice line, so historical reports can expose content-credibility evidence without reconstructing or treating artifact text as persisted gate metadata.

The content-credibility evidence-matrix check conditionally covers each structured conclusion that exists: `最終投資建議` when a recommendation map is present, `估值結論` when `price_targets` exists, and `護城河評分` when `moat_scores` exists. Each required row must have a usable status (`success`, `skipped_fresh_cache`, or `degraded_enrichment`) and a non-empty basis; missing rows produce `missing_final_recommendation_evidence`, `missing_valuation_evidence`, or `missing_moat_evidence`, while unusable rows produce the corresponding `unusable_*_evidence` warning. This remains evidence coverage only; numeric evidence approval remains the independent responsibility of `evidence_exit_gate`, and absent mode-D long-term inputs are not invented.

Historical quality targets expose `report_quality_revision` and a revision-scoped `quality_review` state. `GET /api/watchlist/report-quality-audit/review?filename=...&pipeline=v1` reads one current target. `POST /api/watchlist/report-quality-audit/review` requires the current revision, a mutation token, one decision from `approved_with_gap`, `rejected`, or `deferred`, and a non-empty note. The append-only ledger is stored in `operational.sqlite3` as `report_quality_review_events`; `approved_with_gap` means an operator accepted the report while retaining the metadata gap, not that any quality gate passed. The revision fingerprint uses report identity plus content/data hashes; index write time (`updated_at`) and filesystem mtime are refresh signals, not report versions. A changed report-index/artifact content fingerprint makes the old review inapplicable and returns `409` until the operator reviews the new revision. The endpoint never writes artifacts, report index rows, or rerun jobs. Historical audit items may also expose `quality_review_history`, containing the newest 20 events for the same filename/pipeline/revision in descending event order; events from an older revision are excluded.

Before the history UI calls this write endpoint, it asks the operator to confirm the selected decision and note. Cancelling that browser confirmation sends no request and creates no ledger event; the confirmation is only a UX safety gate, while the server-side mutation token, current revision, decision validation, and required note remain authoritative.

Each historical quality-review item exposes its current `report_quality_revision` to the review controls. The UI shows a shortened version identifier for scanning and keeps the full identifier in accessible/title context, so an operator can match the reviewed report version without treating the client display as authorization.

The history UI serializes review submissions per page: the selected decision button is disabled and marked busy until the mutation and read-only reload finish, duplicate clicks do not create extra ledger events, and success or failure is shown through the existing notification center. This is a client-side interaction guard; revision validation and mutation authorization remain server-owned.

Report preview reading boundaries include snapshot integrity mismatch details when `snapshot_integrity.status = invalid`, so operators see the concrete hash evidence before opening the full report.

Report preview reading boundaries derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so preview notices keep hash evidence visible.

Report preview reading boundaries prefer hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report preview reading boundaries treat `snapshot_integrity.valid=false` as blocked even when status text is non-invalid, so contradictory snapshot metadata cannot mark a hash mismatch as ready to use.

Report preview reading boundaries remove default generic snapshot integrity blocker text when the same error list contains specific provider or hash details, so preview notices show the actionable failure reason before opening the full report.

Report preview reading boundaries deduplicate repeated snapshot integrity error details before display, so preview notices show each provider or hash detail once while preserving first-seen order.

Each report `.data.json` snapshot also includes `data_confidence_score`, `conclusion_guardrails.explicit_target_price`, and `reproducibility_packet`. When `data_confidence_score < 60`, explicit target prices are marked disallowed and consumers should treat only ranges or "data insufficient" language as valid. `reproducibility_packet.data_snapshot_hash` matches the final snapshot hash and also records ticker, pipeline, prompt version, full prompt fingerprint, model id, code commit, code dirty state, provider list, generated time, and source data time.

Report artifacts may use partitioned、分層的 `backend/output/YYYY-MM/TICKER/` storage or a legacy flat path. Maintenance commands 會遞迴掃描 both locations, report relative storage keys, and ignore symlink files so snapshot verification and storage counts cover the canonical artifact set without following paths outside the output root.

Report persistence accepts mapping-safe data snapshot payloads before saving `.data.json` and indexing metadata, so immutable snapshots preserve the same report confidence metadata in storage, index handoff, and API return payloads.

Report refresh diffs accept mapping-safe data snapshot payloads before comparing data trust and source audit status, so immutable snapshots still show accurate stale-to-fresh and provider recovery evidence in preview responses.

Report refresh stale-source detection accepts mapping-safe data snapshot payloads and source audit rows, so immutable snapshots with fresh high-frequency source evidence do not incorrectly mark market data or catalysts as stale.

Report refresh source audit sequences treat lookup iterator failures as native-sequence fallbacks before stale-source classification, so malformed `source_audit` list wrappers cannot hide fresh market data or catalyst audit evidence.

Report refresh source audit sequences treat lookup iterator creation failures as native-sequence fallbacks before stale-source classification, so malformed `source_audit` list wrappers cannot hide fresh market data or catalyst audit evidence before iteration starts.

Report refresh source audit rows use Mapping traversal when `.items()` iterables fail lookup before stale-source classification, so readable source audit rows still preserve fresh market data or catalyst evidence.

Report refresh source audit rows skip lookup item unpack failures before stale-source classification, so one malformed `.items()` pair cannot hide later fresh market data or catalyst fields in the same row.

Report refresh source audit rows skip lookup key hash failures before stale-source classification, so one malformed `.items()` key cannot hide later fresh market data or catalyst fields in the same row.

Report refresh source audit rows skip Mapping traversal key hash failures before stale-source classification, so one malformed mapping key cannot hide later fresh market data or catalyst fields when `.items()` access has already fallen back to key traversal.

Report refresh source audit timestamps use safe text conversion instead of truthiness checks, so valid but falsey timestamp wrappers still preserve fresh source evidence.

Report refresh refreshed-data payloads accept mapping-safe provider/cache responses before snapshot rebuild, so read-only data wrappers preserve refreshed prices, source audit rows, and trust metadata instead of being treated as fetch failures.

After a data-only refresh, the response `decision_freshness` is computed from the same refreshed snapshot that was persisted, so `current`/`needs_rerun` remains correct even when the configured report storage is not filesystem-backed; storage paths are not used as a second, weaker source of freshness truth.

Report rerun refreshed-data payloads accept mapping-safe provider/cache responses before full-pipeline reruns, so read-only refreshed data wrappers reach the pipeline runner with prices, source audit rows, and trust metadata intact.

Report rerun source lookup resolves the configured report storage before checking the source HTML, so direct service calls without an injected storage still find partitioned `backend/output/YYYY-MM/TICKER/` artifacts as well as legacy flat files. The resolved storage is reused for the source data snapshot and rerun output persistence; the service does not infer a source from another report, index row, or Markdown text.

The legacy `GET/POST /api/report/{filename}/review` certification record uses the same report storage candidates. New `.review.json` records are written beside the nested HTML/Markdown/data bundle, while reads still accept the legacy flat sidecar; deleting, expiring, or orphan-cleaning a report removes its review sidecar with the bundle. This certification record remains separate from the revision-bound `report_quality_review_events` ledger used by historical quality audit.

Report rerun existing snapshot data payloads use mapping-safe snapshot normalization before full-pipeline reruns, so read-only source audit and trust wrappers become pipeline-safe mutable data.

Report final-recommendation rerun context data uses mapping-safe snapshot normalization before the final agent runs, so read-only source audit and trust wrappers remain editable for final rerun metadata.

Report final-recommendation rerun context accepts mapping-safe rerun context payloads before Markdown fallback, so read-only previous-agent analyses do not force Markdown recovery or block partial reruns.

Report rerun renderer snapshots use mapping-safe snapshot normalization before rerun metadata and integrity hashing, so read-only renderer payloads keep source audit, trust metadata, and valid snapshot hashes when saved.

Report rerun render contexts use mapping-safe top-level normalization before partial-rerun metadata is added, so read-only pipeline contexts can still reach the renderer and saved snapshot with rerun provenance intact.

Report rerun progress events accept mapping-safe payloads before job-store persistence, so read-only progress wrappers preserve phase, message, count, scope, and source filename for the rerun stream.

Report rerun progress event details use snapshot-safe normalization before job-store persistence, so nested read-only source audit or metadata payloads remain serializable in rerun streams.

Report rerun scalar progress fallbacks use integer-safe conversion before job-store persistence, so malformed progress counters cannot interrupt rerun streams or leak boolean counts.

Report rerun progress event scope fields use safe text fallback before job-store persistence, so malformed progress scope payloads cannot interrupt rerun streams.

Report rerun progress event control fields use safe text fallback before job-store persistence, so malformed type, phase, or level payloads cannot leak non-string event metadata into rerun streams.

Report rerun progress event count fields use integer-safe normalization before job-store persistence, so malformed current or total payloads cannot leak boolean or binary progress counters into rerun streams.

Report rerun progress event message fields use safe text fallback before job-store persistence, so malformed boolean, binary, or container messages cannot leak non-text operator copy into rerun streams.

Report rerun progress event name fields use safe text fallback before job-store persistence, so malformed boolean, binary, or container names cannot leak non-text progress labels into rerun streams or logs.

Report rerun progress event detail fields use safe text fallback before job-store persistence, so malformed boolean, binary, or container detail payloads cannot leak non-text runtime log suffixes into rerun streams or logs.

Report rerun progress event agent number fields use integer-safe normalization before job-store persistence, so malformed agent identity payloads cannot leak boolean or binary agent numbers into rerun streams or job observability.

Report rerun progress event pipeline identity fields use safe text fallback before job-store persistence, so malformed pipeline id or label payloads cannot leak boolean, binary, or container pipeline identities into rerun streams or job observability.

Report rerun progress event metadata fields use mapping-safe normalization before job-store persistence, so malformed scalar or sequence metadata cannot leak non-mapping observability payloads into rerun streams or job observability.

Report rerun API key failure events preserve source filenames before job-store persistence, so setup failures remain traceable to the original report in rerun streams.

Report rerun queue enqueue failure events preserve source filenames before job-store persistence, so queue submission failures remain traceable to the original report in rerun streams.

Report rerun queue enqueue failure messages use safe text fallback before job-store persistence, so malformed queue exception strings cannot interrupt rerun enqueue responses or block terminal error events.

Report rerun attached job created flags use explicit boolean selection before enqueue decisions, so malformed created flag truthiness cannot interrupt rerun enqueue responses or trigger queue submissions from untrusted flag values.

Report rerun attached job status checks use safe text fallback before queue recovery, so malformed existing job status rows do not interrupt rerun enqueue responses or trigger recovery from untrusted status values.

Report rerun stream replay payloads use mapping-safe fallback before SSE output, so malformed non-mapping event payloads become warning status events instead of interrupting rerun streams.

Report rerun stream replay payload type fields use safe text fallback before SSE output, so malformed non-string type controls become warning status events instead of interrupting rerun streams.

Report rerun stream replay control fields use safe text fallback before SSE output, so malformed phase or level payloads cannot interrupt rerun streams.

Report rerun stream replay message fields use safe text fallback before SSE output, so malformed boolean, binary, or container messages cannot interrupt rerun streams.

Report rerun stream replay progress text fields use safe text fallback before SSE output, so malformed name or detail payloads cannot interrupt rerun streams.

Report rerun stream replay filename fields use safe text fallback before SSE output, so malformed filename, markdown filename, data filename, or source filename payloads cannot interrupt rerun streams.

Report rerun stream replay context fields use safe text fallback before SSE output, so malformed rerun scope, scope label, pipeline id, or pipeline label payloads cannot interrupt rerun streams.

Report rerun stream replay count fields use integer-safe fallback before SSE output, so malformed current, total, or agent number payloads cannot interrupt rerun streams or leak binary counters.

Report rerun stream replay status code fields use integer-safe fallback before SSE output, so malformed status code payloads cannot interrupt rerun streams or leak binary counters.

Report rerun stream replay structured fields use snapshot-safe normalization before SSE output, so malformed data trust, partial rerun, metadata, or details payloads cannot interrupt rerun streams.

Report rerun stream replay event rows use mapping-safe fallback before SSE output, so malformed non-mapping job-store rows become warning status events and do not interrupt later terminal events.

Report rerun stream replay event id fields use integer-safe fallback before SSE output, so malformed boolean or binary job-store event ids become warning status events and cannot advance rerun stream cursors.

Report rerun stream event collections use sequence-safe fallback before replay and terminal fallback checks, so malformed job-store collection payloads do not interrupt terminal fallback output.

Report rerun stream resume id parsing treats negative `Last-Event-ID` values as malformed, so negative header cursors fall back before reaching job-store event queries.

Report rerun stream missing job rows after SSE setup emit and persist terminal error fallbacks, so operational cleanup or missing job-store rows do not leave rerun streams or reconnects with only the intro event.

Report rerun stream malformed job rows after SSE setup emit terminal error fallbacks, so corrupted job-store rows do not interrupt rerun streams after setup validation has already passed.

Report rerun stream terminal fallback events preserve rerun scope and source filenames before job-store persistence, so synthesized error or cancelled events remain traceable to the original report in rerun streams.

Report rerun stream terminal fallback messages and filenames use safe text normalization before job-store persistence, so malformed job rows cannot interrupt synthesized done, error, or cancelled SSE events.

Report rerun stream terminal polling status checks use safe text fallback before terminal fallback, so malformed job status fields cannot interrupt polling or synthesize terminal events from untrusted status values.

Report rerun stream terminal fallback scopes use safe text fallback before job-store persistence, so empty rerun pipeline scope rows default to final recommendation instead of losing rerun context.

Report rerun stream task validation uses safe text fallback before SSE setup, so malformed rerun pipeline id rows return not found instead of interrupting the API response.

Report rerun stream setup job rows use mapping-safe fallback before task validation, so malformed non-mapping job rows return not found instead of interrupting the API response.

Report rerun stream task ticker validation uses safe text fallback before SSE setup, so malformed rerun job ticker rows return not found instead of interrupting the API response.

Report rerun cancel job rows use mapping-safe fallback before cancellation requests, so malformed non-mapping job rows return not found instead of interrupting the API response.

Report rerun cancel task validation uses safe text fallback before cancellation requests, so malformed rerun pipeline id rows return not found instead of interrupting the API response.

Report rerun cancel task ticker validation uses safe text fallback before cancellation requests, so malformed rerun job ticker rows return not found instead of interrupting the API response.

Report rerun source filename fields use safe text normalization before job-store persistence, so malformed source filename payloads cannot interrupt rerun streams or terminal events.

Report rerun cancellation messages use safe text fallback before job-store persistence, so malformed cancellation exception strings cannot interrupt terminal cancelled events.

Report rerun invalid scope errors are handled inside the job-store terminal event flow, so malformed or unsupported rerun scope payloads still mark the job error and remain visible in rerun streams.

Report rerun HTTP error details use safe text fallback before job-store persistence, so malformed exception detail payloads cannot interrupt terminal error events.

Report rerun HTTP error status codes use integer-safe fallback before job-store persistence, so malformed status code payloads cannot interrupt terminal error events.

Report rerun unexpected exception messages use safe text fallback before job-store persistence, so malformed exception string conversion cannot mask the original error type or block terminal error events.

Report rerun completion results use mapping-safe snapshot normalization before job-store events, so read-only data trust, partial rerun, and metadata payloads remain serializable in report_done and done events.

Report rerun completion structured result fields use mapping-safe normalization before job-store events, so malformed data trust or partial-rerun payloads cannot leak non-mapping result context into report_done and done events.

Report rerun completion identity fields use safe text normalization before job-store events, so malformed filename, markdown/data filename, scope label, or pipeline id values cannot leak boolean or binary identity payloads into rerun streams.

Report refresh rerun checks accept mapping-safe data snapshot payloads before comparing decision-relevant fields, so immutable snapshots with changed prices, valuation inputs, trust reasons, or failure metadata still mark conclusions as needing rerun.

Watchlist rows also include `decision_priority`, `decision_alert`, and `latest_report` when a matching report exists. `decision_priority = high` means the latest data snapshot changed after the conclusion was generated and the report should be rerun.

Watchlist symbol suggestions are local/free and can be used before saving or importing rows:

```bash
curl "http://127.0.0.1:8080/api/watchlist/symbols?q=台積"
```

股票快照 API 提供一般股票頁需要的摘要結構，不需要 mutation token：

```bash
curl http://127.0.0.1:8080/api/stocks/{ticker}/snapshot
```

回傳內容包含 `identity`、`company_profile`、`quote`、`market_session`、`price_trend`、`performance_history`、`technical_summary`、`valuation`、`valuation_range`、`analyst_outlook`、`earnings_forecast`、`share_statistics`、`risk_liquidity`、`profitability_quality`、`dividends`、`dividend_profile`、`event_calendar`、`alert_suggestions`、`financial_health`、`financial_trends`、`peer_comparison`、`ownership_flow`、`events`、`news`、`chip`、`data_quality` 與 `mode_suggestions`。`company_profile` 會整理公司業務摘要、官網、產業、市場/交易所、幣別與員工數；`market_session` 會揭露今日行情、漲跌、日內區間、成交量與均量比較；`price_trend` / `performance_history` / `technical_summary` 會提供近一年趨勢、1M/3M/6M/1Y/3Y/5Y 多週期走勢、均線、52 週位置與動能訊號；`valuation_range` 與 `analyst_outlook` 分別提供 P/E 河流圖估值區間、分析師目標價、共識、Forward P/E 與 EPS 成長；`earnings_forecast` 會整理 Trailing EPS、Forward EPS、Forward EPS 變化、EPS/營收成長、下次財報日期與分析師覆蓋數；`share_statistics` 會整理在外股數、流通股數、內部人/機構持股、空單股數、short ratio 與空單占流通股比例；`risk_liquidity` 會整理 beta、52 週高點回撤、成交量相對均量、負債權益比與流動比率；`profitability_quality` 會整理毛利率、營業利益率、淨利率、ROE、ROA 與 FCF margin；`dividend_profile` 會整理年化股利、殖利率、配息率、近年配息歷史與 FCF 覆蓋；`event_calendar` 會整理財報日、除息日、股利發放日、最近財報季度等關鍵日期，並標出下一事件與距今天數；`alert_suggestions` 會把關鍵日期、分析師目標價、52 週高點與月營收創高等情境轉成可保存到 watchlist 的提醒建議；`financial_health` / `financial_trends` / `peer_comparison` 則把基本面摘要、近年營收/淨利/FCF YoY 與同業比較整理成一般股票頁可讀的摘要；`ownership_flow` 會將法人買賣超、外資/投信/自營商分類、融資券與 TDCC 股權集中度整理成籌碼結構摘要。`mode_suggestions` 則把 `v1` / `v2` / `v3` / `v4` 翻成使用者決策語言，供前端快速切換分析模式。

### Pipeline Mode Catalog

前端模式選項可由唯讀 catalog API 載入：

```bash
curl http://127.0.0.1:8080/api/pipeline-modes
```

回應使用 `schema_version = "pipeline_modes.v1"`，`modes` 會包含 `v1`、`v2`、`v3`、`v4` 與 `both`。每個項目同時提供 canonical id、執行用 label/hint、決策語意、`agentCount`、`optionLabel` 與 CTA 文案。catalog 的 runtime source 是 `backend/pipeline_mode_catalog.py`；首屏 fallback 由 `scripts/generate_pipeline_mode_fallback.py` 產生到 `backend/static/pipeline_mode_fallback.js`，CI 會用 `--check` 阻擋產物漂移。API 成功後由 `pipeline_mode_catalog.js` 合併更新，API 暫時不可用時不阻擋既有分析流程。

## Mutation Token

```bash
TOKEN="$(curl -fsS http://127.0.0.1:8080/api/client-config | python -c 'import json,sys; print(json.load(sys.stdin)["mutation_token"])')"
```

Use it with modifying requests:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/report/<filename>/refresh/data

curl -X DELETE -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/reports/<filename>
```

## Analysis Jobs

新分析請優先使用正式 job API。建立任務是 mutation，必須帶 `X-Mutation-Token`：

```bash
curl -X POST http://127.0.0.1:8080/api/analysis-jobs \
  -H "Content-Type: application/json" \
  -H "X-Mutation-Token: $TOKEN" \
  -d '{"ticker":"2330.TW","pipeline_id":"v1","force":false,"resume":true}'
```

回應包含：

```json
{
  "job_id": "analysis-2330tw-v1-...",
  "ticker": "2330.TW",
  "pipeline_id": "v1",
  "status": "queued",
  "events_url": "/api/analysis-jobs/{job_id}/events",
  "status_url": "/api/analysis-jobs/{job_id}"
}
```

同一個 `ticker + pipeline_id` 在 `queued/running/waiting_retry` 期間只會有一個 active job。重複建立會回傳既有 job；`force=true` 會先把舊 active job 標記 `cancelled`，再建立新 job。

查詢狀態：

```bash
curl http://127.0.0.1:8080/api/analysis-jobs/<job_id>
```

Analysis job status rows use mapping-safe fallback before serialization, so missing or malformed non-mapping job-store rows return not found instead of interrupting the API response.

Analysis job status serializer fields use JSON-safe fallback before response shaping, so malformed status adapter field values do not interrupt public status responses or leak non-JSON payloads.

Analysis job by-id cancellation rows use mapping-safe fallback before cancellation requests, so missing or malformed non-mapping job-store rows return not found instead of reaching the cancel service.

Analysis job by-id cancellation fallback results use bool-safe fallback before response shaping, so malformed fallback cancellation adapter results return not found instead of interrupting cancellation requests.

Analysis job by-id cancellation service results use mapping-safe fallback before response shaping, so malformed service-level cancellation payloads return not found instead of leaking malformed responses.

Analysis job by-id cancellation service fields use JSON-safe fallback before response shaping, so malformed service-level cancellation field values do not interrupt public cancel responses or leak non-JSON payloads.

Analysis job cancellation service rows use mapping-safe fallback before queue cancellation, so malformed service-level job-store rows return not found without cancelling queue tasks or requesting job cancellation.

Analysis job cancellation service request ids use safe text fallback before store lookup and queue cancellation, so malformed requested job ids cannot reach cancellation stores, queue adapters, or public responses as non-JSON payloads.

Analysis job cancellation service status checks use safe text fallback before queue cancellation, so malformed queued status equality cannot interrupt cancellation requests.

Analysis job cancellation queue cancel accessors use safe getattr before queue-side cancellation, so malformed queue adapters cannot block job cancellation requests.

Analysis job serialization rows use mapping-safe fallback before response shaping, so malformed job-store rows produce safe empty payloads without empty job-id event or status URLs.

Analysis job serialization status fields use safe text fallback before response shaping, so malformed status truthiness or string conversion cannot interrupt public job payloads.

Analysis job serialization status fields trim whitespace before public status mapping, so padded internal statuses still map to stable public status values.

Analysis job serialization status fields normalize known status casing before public status mapping, so uppercase or mixed-case internal statuses still map to stable public status values while unknown statuses remain visible.

Analysis job serialization identity fields use safe text fallback before response shaping, so malformed job id truthiness or string conversion cannot interrupt public job payloads or create empty job-id URLs.

Analysis job serialization identity URL helper fields use path-segment fallback before response shaping, so path-like, encoded, or control-character job ids remain visible as text but do not create ambiguous event or status URLs.

Analysis job serialization public URL helper segments reject whitespace before response shaping, so job ids or report filenames with visible or invisible spacing do not create malformed public URLs.

Analysis job serialization public URL helper segments reject encoded percent tokens before response shaping, so double-encoded delimiter or control payloads cannot create ambiguous public URLs.

Analysis job serialization report filename fields use safe text fallback before response shaping, so malformed filename truthiness or string conversion cannot interrupt public job payloads or create invalid report URLs.

Analysis job serialization report filename fields use path-segment fallback before response shaping, so path-like filenames cannot create traversal or absolute public report URLs.

Analysis job serialization report filename fields use URL-delimiter fallback before response shaping, so query, fragment, or encoded separator filenames cannot create ambiguous public report URLs.

Analysis job serialization report filename fields use control-character fallback before response shaping, so invisible filename delimiters cannot create malformed public report URLs.

Analysis job serialization report filename fields use percent-encoded delimiter fallback before response shaping, so encoded query, fragment, separator, or control payloads cannot create ambiguous public report URLs.

Analysis job serialization pipeline fields use safe text fallback before response shaping, so malformed pipeline id truthiness or string conversion cannot interrupt public job payloads and falls back to `v1`.

Analysis job serialization ticker fields use safe text fallback before response shaping, so malformed ticker truthiness or string conversion cannot interrupt public job payloads or leak non-JSON job values.

Analysis job serialization timestamp fields use finite-float fallback before response shaping, so malformed or out-of-range job timestamps become null instead of interrupting public job payloads.

Analysis job serialization timestamp empty checks use type-safe string guards before response shaping, so malformed timestamp equality cannot interrupt public job payloads.

Analysis job serialization error fields use safe sanitizer fallback before response shaping, so malformed error string conversion cannot interrupt public job payloads or leak non-JSON job values.

Analysis job lifecycle result rows use mapping-safe fallback before queue decisions, so malformed create-or-attach rows return safe empty payloads without enqueueing unknown jobs.

Analysis job create handler results use mapping-safe fallback before response shaping, so malformed route-level create adapter payloads return safe empty job payloads instead of leaking malformed responses.

Analysis job create handler fields use serializer-backed JSON-safe fallback before response shaping, so malformed route-level field values do not interrupt public create responses or leak non-JSON payloads.

Analysis job create route normalized pipeline ids use safe text fallback before handler dispatch, so malformed route-level pipeline normalization payloads fall back to `v1` instead of interrupting create responses.

Analysis job id builder input fields use safe text fallback before slug construction, so malformed ticker or pipeline ids fall back to safe slug placeholders instead of interrupting job creation or leaking Python object representations into job ids.

Analysis job id builder force flags use bool-safe fallback before suffix selection, so malformed force truthiness falls back to deterministic non-force job id construction instead of interrupting job creation.

Analysis job lifecycle identity fields use safe text fallback before queue decisions, so malformed create-or-attach job ids return safe payloads without enqueueing unknown jobs.

Analysis job lifecycle status fields use safe text fallback before queue recovery decisions, so malformed create-or-attach statuses return safe payloads without requeueing unknown lifecycle states.

Analysis job input pipeline fields use safe text fallback before lifecycle creation, so malformed input pipeline ids fall back to `v1` without interrupting job creation.

Analysis job input ticker fields use safe text fallback before lifecycle creation, so malformed or empty input tickers return safe payloads without creating or enqueueing unknown jobs.

Analysis job input force flags use bool-safe fallback before lifecycle creation, so malformed force truthiness falls back to non-force job creation without interrupting create responses.

Analysis job input arbitrary object force flags use conservative bool fallback before lifecycle creation, so custom object truthiness cannot trigger forced refresh or append force-refresh queue arguments.

Analysis job input binary or container force flags use conservative bool fallback before lifecycle creation, so malformed binary or collection payloads do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input string force flags use bool-text fallback before lifecycle creation, so string `false`, `0`, `no`, or blank values do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input non-finite numeric force flags use finite-number fallback before lifecycle creation, so `NaN` or infinite values do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input numeric force flags accept only explicit zero or one before lifecycle creation, so fractional or out-of-range numbers do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input Fraction force flags use the same explicit zero-or-one fallback before lifecycle creation, so fractional exact numeric values do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input Decimal force flags use the same explicit zero-or-one fallback before lifecycle creation, so fractional exact numeric values do not trigger forced refresh or append force-refresh queue arguments through float precision loss.

Analysis job input complex force flags use conservative bool fallback before lifecycle creation, so complex numbers do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input resume flags use bool-safe fallback before lifecycle creation, so malformed resume truthiness falls back to active-job attachment without interrupting create responses.

Analysis job lifecycle created flags use explicit boolean selection before queue decisions, so malformed created flag truthiness cannot interrupt create responses or requeue unknown lifecycle states.

Analysis job queue task identity fields use safe text fallback before RQ task id construction, so malformed job ids cannot leak Python object representations into queue task keys.

Analysis job queue task identity fields use path-segment fallback before RQ task id construction, so path-like, encoded, or whitespace job ids cannot create ambiguous queue task keys.

Analysis job queue task lookup ids use safe text fallback before queue adapter lookup, so malformed task ids cannot leak Python object representations into RQ `fetch_job` calls.

Analysis job queue task status fields use safe text fallback before RQ active-state classification, so malformed RQ status values cannot interrupt queue recovery or duplicate-job checks and fall back to inactive.

Analysis job queue task status fetch failures return unknown inspection results before queue recovery or duplicate-job checks, so transient RQ status lookup errors do not interrupt create responses or get misclassified as confirmed missing tasks.

Analysis job queue task status accessors return unknown inspection results before queue recovery or duplicate-job checks, so malformed RQ job status adapters cannot interrupt task lookup.

Analysis job queue task status properties return unknown inspection results before queue recovery or duplicate-job checks, so malformed fallback RQ status fields cannot interrupt task lookup.

Analysis job queue metadata fetch failures return unknown inspection results before queue recovery or duplicate-job checks, so malformed queue adapters cannot interrupt create responses before task lookup starts.

Analysis job child queue fetch-job metadata failures return unknown inspection results before queue recovery or duplicate-job checks, so malformed nested queue adapters cannot interrupt multi-queue task lookup.

Analysis job queue deduplication uses identity-only comparison before multi-queue task lookup, so malformed child queue equality hooks cannot interrupt primary queue inspection.

Analysis job queue enqueue failure messages use safe text fallback before job-store error updates, so malformed queue exception strings cannot interrupt create responses or block error events.

Analysis job legacy create fallback identity fields use safe text fallback before queue enqueue, so malformed fallback job ids return empty job payloads instead of interrupting create responses or enqueueing unknown tasks.

Analysis job legacy create fallback queue enqueue failure messages use safe text fallback before job-store error updates, so malformed fallback queue exception strings cannot interrupt create responses or block terminal error events.

Analysis job legacy create fallback serializer fields use JSON-safe fallback before response shaping, so malformed fallback serializer field values do not interrupt legacy create responses or leak non-JSON payloads.

讀取 SSE：

```bash
curl -N http://127.0.0.1:8080/api/analysis-jobs/<job_id>/events
curl -N "http://127.0.0.1:8080/api/analysis-jobs/<job_id>/events?since_id=42"
```

SSE endpoint 只讀事件，不建立任務。瀏覽器或 client reconnect 時可用 `Last-Event-ID` header、`last_event_id` query，或 `since_id` query 從最後收到的 event id 繼續。沒有新事件時 server 會逐步 backoff polling，並送出 `event: ping` heartbeat：

Analysis SSE setup job rows use mapping-safe fallback before stream creation, so missing or malformed non-mapping job-store rows return not found instead of interrupting the API response.

Analysis SSE intro identity fields use safe text fallback before output, so malformed setup ticker or pipeline values cannot interrupt the initial job event.

Analysis SSE resume id parsing ignores malformed `since_id` values and falls back to `Last-Event-ID` or `last_event_id`, so reconnect setup is not interrupted by malformed resume query values.

Analysis SSE resume id parsing treats negative `since_id`, `Last-Event-ID`, and `last_event_id` values as malformed, so negative cursors fall back instead of reaching job-store event queries.

Analysis SSE resume id parsing treats boolean `since_id`, `Last-Event-ID`, and `last_event_id` values as malformed, so boolean cursors fall back instead of being coerced to event id 0 or 1.

Analysis SSE stream replay payloads use mapping-safe fallback before output, so malformed non-mapping job-store events become warning status events and do not interrupt later terminal events.

Analysis SSE stream replay event rows use mapping-safe fallback before output, so malformed non-mapping job-store rows become warning status events and do not interrupt later terminal events.

Analysis SSE stream replay event id fields use integer-safe fallback before output, so malformed boolean or binary job-store event ids become warning status events and cannot advance analysis stream cursors.

Analysis SSE stream replay payload type fields use safe text fallback before output, so malformed non-string event types become warning status events and cannot interrupt replay output.

Analysis SSE stream replay message fields use safe text fallback before output, so malformed boolean, binary, or container messages cannot interrupt replay output.

Analysis SSE stream replay control fields use safe text fallback before output, so malformed phase or level payloads cannot interrupt replay output.

Analysis SSE stream replay done identity fields use safe text fallback before output, so malformed filename or pipeline identity payloads cannot interrupt replay output.

Analysis SSE stream replay report artifact filename fields use safe text fallback before output, so malformed Markdown or data snapshot filename payloads cannot interrupt report_done replay output.

Analysis SSE stream replay progress text fields use safe text fallback before output, so malformed name, detail, or pipeline label payloads cannot interrupt replay output.

Analysis SSE stream replay telemetry text fields use safe text fallback before output, so malformed node name, model, status, or error payloads cannot interrupt replay output.

Analysis SSE stream replay telemetry metric fields use finite-float, integer-, and bool-safe fallback before output, so malformed latency, retry count, or quality-gate payloads cannot interrupt replay output.

Analysis SSE stream replay metadata fields use snapshot-safe fallback before output, so malformed nested metadata payloads cannot interrupt replay output.

Analysis SSE stream replay structured report fields use snapshot-safe fallback before output, so malformed data trust or audit payloads cannot interrupt report_done or done replay output.

Analysis SSE stream replay done aggregate fields use snapshot-safe fallback before output, so malformed filenames, report collection, or pipeline sequence payloads cannot interrupt done replay output.

Analysis SSE stream replay workflow retry thread ids use safe text fallback before output, so malformed retry checkpoint thread identifiers cannot interrupt workflow retry replay output.

Analysis SSE stream replay count fields use integer-safe fallback before output, so malformed current, total, agent number, or pipeline-local count payloads cannot interrupt replay output.

Analysis SSE stream replay pipeline count fields use integer-safe fallback before output, so malformed pipeline index, agent total, or agent offset payloads cannot interrupt replay output.

Analysis SSE terminal fallback error messages use safe text fallback before output, so malformed job error fields cannot interrupt synthesized error events.

Analysis SSE terminal fallback cancellation messages use safe text fallback before output, so malformed cancelled job error fields cannot interrupt synthesized cancelled events.

Analysis SSE terminal fallback done identity fields use safe text fallback before output, so malformed job filename or pipeline fields cannot interrupt synthesized done events.

Analysis SSE terminal polling status checks use safe text fallback before terminal fallback, so malformed job status fields cannot interrupt polling or synthesize terminal events from untrusted status values.

Analysis SSE terminal fallback persistence checks use mapping-safe event rows before appending synthesized terminal events, so read-only job-store rows do not trigger duplicate fallback persistence.

Analysis SSE event collections use sequence-safe fallback before replay and terminal persistence checks, so malformed job-store collection payloads do not interrupt terminal fallback output.

Analysis SSE missing or empty job rows after stream setup emit terminal error fallbacks, so operational cleanup or empty job-store rows do not leave clients with only the intro event or heartbeat pings.

```text
event: ping
data: {"ts":"2026-06-29T00:00:00Z"}
```

取消任務：

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/analysis-jobs/<job_id>/cancel
```

Queued job 會盡量從 RQ queue 移除並標記 `cancelled`。Running job 會標記 `cancel_requested`，worker 在資料抓取、pipeline segment、report rendering 等安全 checkpoint 檢查後中止。

Node telemetry：

```bash
curl http://127.0.0.1:8080/api/analysis-jobs/<job_id>/telemetry
```

回傳每個 LangGraph node / agent 的 `node_name`、`model`、時間、latency、status、retry count、token 欄位（目前可能為 `null`）、quality gate 結果與已清理過的錯誤摘要。

Analysis job telemetry setup rows use mapping-safe fallback before diagnostics response shaping, so missing or malformed job-store rows return not found instead of exposing telemetry for invalid jobs.

Analysis job telemetry serializer results use mapping-safe fallback before diagnostics response shaping, so malformed telemetry adapter payloads return an empty telemetry list instead of leaking malformed responses.

Analysis job telemetry serializer fields use JSON-safe fallback before diagnostics response shaping, so malformed telemetry adapter field values do not interrupt diagnostics responses or leak non-JSON payloads.

Analysis job telemetry request ids use safe text fallback before diagnostics store lookup and response shaping, so malformed telemetry request ids cannot interrupt diagnostics responses or leak non-JSON payloads.

Analysis node telemetry row collections use iterable-safe fallback before response shaping, so missing or malformed telemetry store result collections become empty telemetry lists instead of interrupting diagnostics.

Analysis node telemetry row collection iterators preserve valid rows before iteration failures, so partial telemetry store result failures do not erase already available diagnostics evidence.

Analysis node telemetry rows use mapping-safe fallback before response shaping, so malformed telemetry store rows become safe empty telemetry rows instead of interrupting diagnostics.

Analysis node telemetry text fields use safe text fallback before diagnostics response shaping, so malformed telemetry job id, ticker, pipeline, node name, model, or status values cannot interrupt diagnostics payloads or leak non-JSON values.

Analysis node telemetry timestamp fields use conservative object fallback before diagnostics response shaping, so arbitrary numeric-like objects cannot synthesize started or finished diagnostics timestamps through conversion methods.

Analysis node telemetry metric fields use integer- and bool-safe fallback before diagnostics response shaping, so malformed telemetry id, latency, retry count, token count, cache hit, or quality gate values cannot interrupt diagnostics payloads or leak non-JSON values.

Analysis node telemetry optional metric fields reject fractional numeric values before diagnostics response shaping, so id, latency, and token count diagnostics cannot be silently truncated from non-integral payloads.

Analysis node telemetry optional metric fields reject fractional exact numeric values before diagnostics response shaping, so Decimal or Fraction id, latency, and token count diagnostics cannot be rounded into synthetic integers through float precision loss.

Analysis node telemetry optional metric fields use conservative object fallback before diagnostics response shaping, so arbitrary numeric-like objects cannot synthesize id, latency, or token count diagnostics through conversion methods.

Analysis node telemetry optional metric fields reject negative values before diagnostics response shaping, so id, latency, and token count diagnostics cannot leak impossible negative counters.

Analysis node telemetry retry count fields reject fractional numeric values before diagnostics response shaping, so retry diagnostics cannot be silently truncated from non-integral payloads.

Analysis node telemetry retry count fields reject negative values before diagnostics response shaping, so retry diagnostics cannot leak impossible negative counters.

Analysis node telemetry bool fields use strict bool fallback before diagnostics response shaping, so binary or container cache-hit and quality-gate values stay false unless they are explicit booleans, accepted truthy strings, or explicit numeric zero or one values.

Analysis node telemetry bool numeric fields accept only explicit zero or one before diagnostics response shaping, so out-of-range cache-hit or quality-gate numbers cannot be misreported as true diagnostics.

Analysis node telemetry bool exact numeric fields use the same explicit zero-or-one contract before diagnostics response shaping, so Decimal or Fraction cache-hit and quality-gate values cannot be misreported through truthiness.

Analysis node telemetry arbitrary object bool fields use conservative fallback before diagnostics response shaping, so custom object truthiness cannot mark cache-hit or quality-gate diagnostics as true.

Report conformance quality gate inputs use dict-native field reads before decision-tree evaluation, so malformed report lint, final audit, evidence exit gate, or content credibility accessors cannot interrupt report quality classification or erase valid blocking and warning evidence.

Report conformance quality gate inputs accept mapping-safe wrappers before decision-tree evaluation, so read-only report lint, final audit, evidence, content credibility, context, or snapshot payloads cannot hide blocker or warning evidence.

Report conformance quality gate issue lists use sequence-safe conversion before decision-tree evaluation, so tuple blocking or warning rows from lint, final audit, or content credibility gates cannot be ignored.

Report conformance visible artifact and gate status text fields use safe text fallback before decision-tree evaluation, so malformed HTML, Markdown, template heading, lint, audit, evidence, content, or data-trust status values cannot interrupt report quality classification.

Report content credibility evidence matrix rows use sequence-safe conversion before coverage checks, so tuple snapshot evidence rows do not trigger false missing-evidence warnings.

Report content credibility evidence matrix row maps use mapping-safe conversion before coverage checks, so read-only evidence rows do not trigger false missing-evidence warnings.

Report content credibility quality gate inputs use mapping-safe conversion before contradiction checks, so read-only context or snapshot wrappers cannot hide recommendation, price, target, evidence, or data-trust blockers.

Report content credibility recommendation and gate text fields use safe text fallback before contradiction checks, so malformed recommendation keys, target values, confidence values, evidence verdicts, or data-trust statuses cannot interrupt content-credibility classification.

Report renderer lint repair result fields use dict-native field reads before structured-key scrubbing, so malformed lint result or issue accessors cannot interrupt automatic repair for structured JSON key leaks.

Report execution summary quality gate fields use dict-native field reads before report rendering, so malformed final audit, evidence gate, report conformance, or report lint accessors cannot interrupt HTML/Markdown execution summary output or erase valid quality status evidence.

Report execution summary quality gate child maps use mapping-safe conversion before report rendering, so read-only data trust, final audit, evidence gate, report conformance, or report lint wrappers cannot be downgraded to unknown or not_recorded.

Report execution summary text fields use shared text conversion before HTML and Markdown output, so malformed final audit, evidence gate, report conformance, report lint, prompt, or model values cannot leak boolean, binary, or memory-view text into runtime trace copy.

Report execution summary Markdown text fields collapse embedded newlines before Markdown output, so model routes, quality gate statuses, prompt versions, model ids, and gate summaries cannot split runtime trace bullet rows.

Report mode template display fields use shared text conversion before HTML and Markdown output, so malformed template id, template name, audience, core question, headings, visual-focus chips, or reading-path items cannot leak boolean, binary, or memory-view text into report template cards.

Report mode template visual focus and reading path fields use shared text-list conversion before HTML and Markdown output, so tuple profile overrides preserve chips and reading paths without leaking malformed binary items.

Report mode template Markdown display fields collapse embedded newlines before Markdown output, so template names, audiences, core questions, headings, visual-focus chips, and reading-path items cannot split reading-path headings or bullet rows.

Report summary and decision discipline display fields use shared text conversion before HTML and Markdown output, so malformed ticker, company name, recommendation, trade setup, metric, or thesis discipline values cannot leak boolean, binary, or memory-view text into report summaries, decision lists, or investment-thesis discipline sections.

Report tear-sheet recent catalyst rows use dict-list safe conversion before HTML and investment-thesis output, so malformed recent_catalysts truthiness cannot interrupt summary or decision-discipline rendering when valid catalyst rows exist.

Report investment-thesis final-audit warning rows use text-list safe conversion before HTML and Markdown output, so malformed warning-list truthiness cannot interrupt decision-discipline data-gap rendering when valid warnings exist.

Report investment-thesis final-audit critical rows use text-list safe conversion before HTML and Markdown output, so malformed critical-list truthiness cannot interrupt decision-discipline downside-risk rendering when valid critical issues exist.

Report investment-thesis agent analysis text uses truthiness-safe fallback before payload and Markdown output, so malformed analysis text truthiness cannot interrupt Mode C thesis mirror rendering when valid agent evidence exists.

Report investment-thesis current price display uses truthiness-safe fallback before payload and Markdown output, so malformed formatted-price truthiness cannot interrupt mirror lines or valuation anchors when valid price text exists.

Report investment-thesis moat score display uses shared text conversion before payload and Markdown output, so malformed moat-score string conversion cannot interrupt mirror lines when valid or fallback moat evidence exists.

Report investment-thesis prebuilt payloads use mapping-safe conversion before HTML and Markdown output, so malformed payload truthiness cannot interrupt report rendering when valid decision-discipline rows already exist.

Report Markdown renderer prebuilt investment-thesis payloads use mapping-safe handoff before Markdown output, so malformed thesis truthiness cannot interrupt Markdown report rendering when valid decision-discipline rows already exist.

Report investment-thesis source audit rows use dict-list safe conversion before HTML and Markdown output, so malformed source_audit truthiness cannot interrupt information-richness grading or erase valid audit row counts.

Report investment-thesis history series use sequence-safe conversion before HTML and Markdown output, so malformed history-series truthiness cannot interrupt information-richness grading or erase valid history evidence.

Report investment-thesis Markdown list fields use text- and dict-list safe conversion before Markdown output, so malformed mirror-test, assumption, red-line, or data-gap list truthiness cannot interrupt decision-discipline Markdown rendering or erase valid thesis evidence.

Report investment-thesis Markdown display fields collapse embedded newlines before Markdown output, so prebuilt thesis headings, score labels, mirror lines, assumptions, red lines, data gaps, and next-review text cannot split decision-discipline headings or bullet rows.

Report investment-thesis recommendation and trade setup mappings use mapping-item safe conversion before payload and Markdown output, so malformed mapping truthiness cannot interrupt recommendation, target-price, confidence, or trade-plan extraction when valid fields exist.

Report investment-thesis structured scenario triggers use dict-list safe conversion before payload and Markdown output, so malformed trigger-list truthiness cannot interrupt Mode C crash-trigger or stop-condition extraction when valid scenario triggers exist.

Report investment-thesis data trust status uses text-safe comparison before payload and Markdown output, so malformed status hash or equality adapters cannot interrupt data-gap or red-line rendering when valid status text exists.

Report HTML sanitizer uses truthiness-safe string conversion before allowlist cleaning, so malformed model or report fragment truthiness cannot interrupt HTML sanitization when the fragment is still stringable.

Report plain-text sanitizer uses truthiness-safe string conversion before HTML output, so malformed report field truthiness cannot interrupt catalyst, summary, discipline, or overlay rendering when the value is still stringable.

Report next catalyst list fields use dict-list safe conversion before HTML output, so malformed catalyst iterators cannot interrupt event trigger rendering when valid rows exist.

Report structured-output child maps use mapping-safe conversion before next-catalyst extraction, so read-only agent payload wrappers cannot hide valid catalyst watchlist triggers.

Report structured-output schema-derived next catalysts accept mapping-safe root payloads before model validation, so read-only structured agent payloads can still derive catalyst watchlists from valid scenario triggers.

Report structured-output schema-derived next catalysts treat null catalyst lists as derivable before model validation, so valid scenario triggers can still produce catalyst watchlists when the model leaves `next_catalysts` empty by null.

Report structured-output schema-derived next catalysts treat non-list catalyst payloads as derivable before model validation, so malformed scalar `next_catalysts` values cannot block catalyst watchlist generation from valid scenario triggers.

Report structured-output schema-derived next catalysts treat non-mapping catalyst rows as derivable before model validation, so malformed catalyst-list contents cannot block catalyst watchlist generation from valid scenario triggers.

Report structured-output schema-derived next catalysts keep valid mapping catalyst rows before model validation, so malformed rows in a mixed `next_catalysts` list cannot discard otherwise valid catalyst watchlist items.

Report structured-output schema-derived next catalysts filter schema-invalid mapping catalyst rows before model validation, so one malformed catalyst mapping cannot discard later valid catalyst watchlist items.

Report structured-output catalyst text fields use safe text fallback before direct model validation, so malformed catalyst event, timeframe, impact, or trigger fields cannot drop otherwise valid catalyst rows.

Report recommendation legacy text uses event metadata fallback for single-character next catalysts, so plain-text catalyst rows show `待確認催化事件 / 待後續資料確認` instead of non-actionable one-character event names or timeframes.

Report structured-output scenario-trigger text fields use safe text fallback before direct model validation, so malformed trigger condition, action, or direction fields cannot drop otherwise valid scenario trigger rows.

Report structured-output schema-derived next catalysts use safe scenario-trigger text before model validation, so malformed trigger rows cannot interrupt automatic catalyst extraction when enough valid triggers exist.

Report structured-output schema-derived next catalysts enforce scenario-trigger minimum lengths before model validation, so too-short trigger rows cannot interrupt automatic catalyst extraction when enough valid triggers exist.

Report structured-output schema-derived scenario triggers use minimum fallback before model validation, so malformed trigger rows cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output schema-derived scenario trigger collections use list-safe fallback before model validation, so malformed scalar trigger collections cannot drop otherwise valid recommendation payloads or catalyst derivation.

Report structured-output scenario-trigger collections use missing-field fallback before model validation, so omitted trigger collections cannot drop otherwise valid recommendation payloads while existing catalyst watchlists remain intact.

Report structured-output missing scenario-trigger fallback drives schema-derived next catalysts before model validation, so payloads that omit both trigger and catalyst collections still keep a neutral catalyst watchlist.

Report structured-output schema-derived next catalysts truncate overlong scenario-trigger lists before model validation, so valid first-five trigger rows can still drive catalyst watchlists when the model emits extra trigger rows.

Report structured-output executive-thesis root payloads use mapping-safe fallback before model validation, so malformed scalar executive synthesis payloads cannot drop the report opening thesis section.

Report structured-output executive-thesis text fields use safe text fallback before model validation, so malformed executive thesis, bull/bear summary, or smoothed markdown fields cannot drop the report opening thesis section.

Report structured-output executive-thesis resolved-contradiction list items use safe text fallback before model validation, so malformed contradiction rows cannot drop otherwise valid executive synthesis payloads.

Report structured-output confidence-basis lists use safe text conversion before model validation, so malformed evidence, risk, or data-gap items cannot drop otherwise valid recommendation payloads when enough valid confidence rows remain.

Report structured-output confidence-basis required lists use minimum fallback before model validation, so malformed evidence or risk items cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output confidence-basis required list collections use list-safe fallback before model validation, so malformed scalar evidence or risk collections cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output confidence-basis root payloads use mapping-safe fallback before direct model validation, so malformed scalar confidence-basis payloads cannot drop the confidence-basis fallback.

Report structured-output confidence-basis objects use missing-field fallback before model validation, so omitted confidence-basis objects cannot drop otherwise valid recommendation payloads.

Report structured-output reasoning steps use safe text conversion before model validation, so malformed reasoning-step items cannot drop otherwise valid recommendation payloads when enough valid reasoning rows remain.

Report structured-output reasoning steps use minimum fallback before model validation, so malformed reasoning-step items cannot drop otherwise valid recommendation payloads below the required reasoning-step count.

Report structured-output reasoning step collections use list-safe fallback before model validation, so malformed scalar reasoning-step collections cannot drop otherwise valid recommendation payloads.

Report structured-output recommendation labels use canonical alias normalization before model validation, so strong-buy or strong-short phrasing cannot drop otherwise valid recommendation payloads while final labels remain in the canonical set.

Report structured-output recommendation labels use missing-field fallback before model validation, so omitted recommendation labels cannot drop otherwise valid investment recommendation payloads.

Report structured-output recommendation text fields use safe text fallback before model validation, so malformed target, potential, or confidence fields cannot drop otherwise valid investment recommendation payloads.

Report structured-output recommendation text fields use missing-field fallback before model validation, so omitted target, potential, or confidence fields cannot drop otherwise valid investment recommendation payloads.

Report structured-output analysis markdown uses safe text fallback before model validation, so malformed report body text cannot drop otherwise valid structured recommendation payloads.

Report structured-output analysis markdown fields use missing-field fallback before model validation, so omitted analysis markdown fields cannot drop otherwise valid structured report payloads.

Report structured-output recommendation root payloads use mapping-safe fallback before model validation, so malformed scalar investment recommendation payloads cannot drop the recommendation section.

Report structured-output recommendation objects use missing-field fallback before model validation, so omitted recommendation objects cannot drop otherwise valid investment recommendation payloads.

Report structured-output recommendation field root payloads use mapping-safe fallback before direct model validation, so malformed scalar recommendation field payloads cannot drop the recommendation field fallback.

Report structured-output bubble-sniper root payloads use mapping-safe fallback before model validation, so malformed scalar bubble-sniper payloads cannot drop the short-bias recommendation section.

Report structured-output bubble-sniper recommendation field root payloads use mapping-safe fallback before direct model validation, so malformed scalar bubble-sniper recommendation fields fall back to avoid instead of dropping the short-bias recommendation fields.

Report structured-output moat analysis markdown uses safe text fallback before model validation, so malformed moat report body text cannot drop otherwise valid moat score payloads.

Report structured-output moat root payloads use mapping-safe fallback before model validation, so malformed scalar moat payloads cannot drop the moat-score section.

Report structured-output moat reasoning steps use minimum fallback before model validation, so malformed moat reasoning-step items cannot drop otherwise valid moat score payloads below the required reasoning-step count.

Report structured-output moat reasoning-step collections use list-safe fallback before model validation, so malformed scalar moat reasoning-step collections cannot drop otherwise valid moat score payloads.

Report structured-output moat-score containers use mapping-safe fallback before model validation, so malformed scalar moat-score containers cannot drop otherwise valid moat reasoning or report body payloads.

Report structured-output moat-score containers use missing-field fallback before model validation, so omitted moat-score containers cannot drop otherwise valid moat reasoning or report body payloads.

Report structured-output moat-score values use safe number fallback before model validation, so malformed moat score values cannot drop otherwise valid moat payloads.

Report structured-output price-target analysis markdown uses safe text fallback before model validation, so malformed valuation report body text cannot drop otherwise valid price-target payloads.

Report structured-output price-target root payloads use mapping-safe fallback before model validation, so malformed scalar price-target payloads cannot drop the valuation section.

Report structured-output price-target containers use mapping-safe fallback before model validation, so malformed scalar price-target containers cannot drop otherwise valid valuation summary or report body payloads.

Report structured-output price-target containers use missing-field fallback before model validation, so omitted price-target objects cannot drop otherwise valid valuation summary or report body payloads.

Report structured-output price-target direct target containers use mapping-safe fallback before direct model validation, so malformed scalar target containers cannot drop the valuation target fallback.

Report structured-output price-target text fields use safe text fallback before model validation, so malformed valuation reasoning, primary method, or double-counting check fields cannot drop otherwise valid price-target payloads.

Report structured-output price-target valuation-summary containers use mapping-safe fallback before model validation, so malformed scalar valuation summaries cannot drop otherwise valid price-target payloads.

Report structured-output price-target valuation-summary containers use missing-field fallback before model validation, so omitted valuation-summary objects cannot drop otherwise valid target-price payloads.

Report structured-output price-target direct valuation-summary containers use mapping-safe fallback before direct model validation, so malformed scalar valuation-summary containers cannot drop the valuation-summary fallback.

Report structured-output price-target valuation-summary boolean fields use bool-safe fallback before model validation, so malformed WACC or normalized-FCF flags cannot drop otherwise valid price-target payloads.

Report structured-output price-target values use safe number fallback before model validation, so malformed bear, base, or bull target values cannot drop otherwise valid price-target payloads.

Report structured-output price-target DCF scenario values use safe number fallback before model validation, so malformed scenario growth, margin, WACC, or intrinsic-value fields cannot drop otherwise valid price-target payloads.

Report structured-output price-target DCF scenario rows use row-safe filtering before model validation, so malformed DCF scenario rows cannot drop otherwise valid price-target payloads or valid DCF scenario rows.

Report structured-output price-target DCF scenario names use enum-safe filtering before model validation, so invalid DCF scenario names cannot drop otherwise valid price-target payloads or valid DCF scenario rows.

Report structured-output price-target direct DCF scenario names use enum-safe fallback before direct model validation, so invalid scalar DCF scenario names cannot drop the direct DCF scenario fallback.

Report structured-output price-target DCF scenario collections use list-safe fallback before model validation, so malformed scalar DCF scenario collections cannot drop otherwise valid price-target payloads.

Report structured-output price-target direct DCF scenario root payloads use mapping-safe fallback before direct model validation, so malformed scalar DCF scenario payloads cannot drop the direct DCF scenario fallback.

Report structured-output management-sentiment analysis markdown uses safe text fallback before model validation, so malformed management report body text cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment root payloads use mapping-safe fallback before model validation, so malformed scalar management sentiment payloads cannot drop the management sentiment section.

Report structured-output management-sentiment text fields use safe text fallback before model validation, so malformed guidance tone, highlight keyword, or highlight quote fields cannot drop otherwise valid management sentiment payloads.

Report structured-output management-highlight root payloads use mapping-safe fallback before direct model validation, so malformed scalar management highlight rows cannot drop otherwise valid highlight content.

Report structured-output management-sentiment highlight rows use row-safe fallback before model validation, so malformed highlight rows cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment highlight collections use list-safe fallback before model validation, so malformed scalar highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment highlight collections use missing-field fallback before model validation, so omitted highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment short highlight collections use minimum-count fallback before model validation, so undersized highlight lists preserve valid rows and pad missing rows instead of dropping otherwise valid management sentiment payloads.

Report structured-output management-sentiment confidence uses safe number fallback before model validation, so malformed confidence values cannot drop otherwise valid management sentiment payloads.

Report structured-output downside-risk analysis markdown uses safe text fallback before model validation, so malformed downside-risk report body text cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk root payloads use mapping-safe fallback before model validation, so malformed scalar downside-risk payloads cannot drop the downside-risk section.

Report structured-output downside-risk root rows use mapping-safe fallback before direct model validation, so malformed scalar downside-risk rows cannot drop otherwise valid downside-risk content.

Report structured-output downside-risk text fields use safe text fallback before model validation, so malformed thesis summary, risk title, evidence, impact, or severity fields cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk rows use row-safe fallback before model validation, so malformed risk rows cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk collections use list-safe fallback before model validation, so malformed scalar downside-risk collections cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk collections use missing-field fallback before model validation, so omitted downside-risk collections cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk short collections use minimum-count fallback before model validation, so undersized downside-risk lists preserve valid rows and pad missing rows instead of dropping otherwise valid downside-risk payloads.

Report structured-output downside-risk confidence uses safe number fallback before model validation, so malformed risk confidence values cannot drop otherwise valid downside-risk payloads.

Report structured-output trade-plan text fields use safe text fallback before model validation, so malformed trade direction, entry, target, stop-loss, catalyst, or risk-level fields cannot drop otherwise valid 1-2 week trade setup payloads.

Report structured-output trade-plan root payloads use mapping-safe fallback before model validation, so malformed scalar trade-plan payloads cannot drop the 1-2 week trade setup section.

Report structured-output trade-plan direct schema preserves enum and required-field strictness, so invalid string trade directions or missing trade-plan fields still fail direct model validation while malformed non-string values can use safe fallbacks.

Report structured-output normalizer payloads use mapping-safe conversion before schema validation and legacy report text rendering, so read-only structured agent payloads and nested recommendation maps cannot be dropped before final recommendation, confidence, catalyst, or trigger output.

Report structured-output normalizer scalar root payloads use schema fallback before final projection, so malformed scalar strict-schema payloads can keep conservative fallback structured sections instead of being rejected before validation.

Report structured-output runtime parsing rejects non-JSON structured responses before schema fallback, so quality gates retry malformed model output instead of accepting conservative `資料不足` report sections as successful structured output.

Report structured-output normalizer rejects incomplete supplied core sections before final projection, so partial moat, valuation, or recommendation JSON cannot be padded into report-contract output when companion core sections were omitted.

Report structured-output normalizer reasoning steps use safe text conversion before schema validation, so malformed reasoning-step values cannot drop otherwise valid recommendation payloads before final report rendering.

Report structured-output normalizer reasoning steps use minimum fallback before schema validation, so malformed reasoning-step values cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer reasoning-step empty lists use minimum fallback before schema validation, so empty reasoning-step collections cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer reasoning-step null values use minimum fallback before schema validation, so null reasoning-step collections cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer reasoning-step scalar objects use minimum fallback before schema validation, so malformed scalar reasoning-step collections cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer scenario trigger rows use dict-list and safe text conversion before schema validation, so malformed trigger rows cannot interrupt next-catalyst derivation or drop otherwise valid recommendation payloads before final report rendering.

Report structured-output normalizer scenario trigger non-mapping rows use sequence-safe fallback before schema validation, so malformed trigger rows cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger mapping fields use minimum fallback before schema validation, so malformed trigger condition or action fields cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger mapping fields enforce schema minimum lengths before validation, so too-short trigger condition or action fragments cannot drop otherwise valid trigger rows or recommendation payloads.

Report structured-output normalizer scenario trigger fallback rows use schema-safe placeholder text, so minimum-count repair cannot reinsert too-short trigger condition or action fragments.

Report structured-output normalizer scenario trigger empty lists use minimum fallback before schema validation, so empty trigger collections cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger null values use minimum fallback before schema validation, so null trigger collections cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger scalar collections use minimum fallback before schema validation, so non-list trigger collections cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger lists use schema-limit truncation before validation, so overlong but otherwise valid recommendation payloads keep the first five trigger rows instead of being dropped.

Report structured-output normalizer scenario trigger fallback rows are deferred until minimum-count repair, so placeholder trigger rows cannot displace valid trigger rows when schema-limit truncation applies.

Report structured-output normalizer confidence-basis lists use safe text conversion before schema validation, so malformed evidence, risk, or data-gap items cannot drop otherwise valid recommendation payloads before final report rendering.

Report structured-output normalizer confidence-basis required lists use minimum fallback before schema validation, so malformed evidence or risk items cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output normalizer confidence-basis required list collections use list-safe fallback before schema validation, so missing, null, or scalar evidence or risk collections cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output normalizer confidence-basis empty required lists use minimum fallback before schema validation, so empty evidence or risk collections cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output normalizer recommendation text fields use safe text conversion before schema validation, so malformed target, potential, or confidence fields cannot drop otherwise valid investment recommendation payloads.

Report structured-output normalizer bubble-sniper recommendation labels use avoid fallback before schema validation, so malformed Agent 19 labels keep the short-bias `避免` default instead of being normalized to generic hold.

Report structured-output normalizer next-catalyst text fields use safe text conversion before schema validation, so malformed catalyst event, timeframe, impact, or trigger fields cannot drop otherwise valid recommendation payloads.

Report structured-output normalizer next-catalyst trigger fields enforce schema minimum length before validation, so too-short trigger fragments cannot drop otherwise valid catalyst rows or recommendation payloads.

Report structured-output normalizer next-catalyst fallback rows use schema-safe trigger text, so minimum-count repair cannot reinsert too-short catalyst trigger fragments.

Report structured-output normalizer next-catalyst rows use sequence-safe fallback before schema validation, so malformed catalyst rows cannot drop otherwise valid recommendation payloads below the required catalyst count.

Report structured-output normalizer next-catalyst empty lists derive from scenario triggers before schema validation, so empty catalyst watchlists cannot drop otherwise valid recommendation payloads below the required catalyst count.

Report structured-output normalizer empty next-catalyst lists derive from missing scenario-trigger fallback before schema validation, so payloads with omitted trigger collections and empty catalyst watchlists still keep neutral catalyst rows.

Report structured-output normalizer next-catalyst fallback rows are deferred until minimum-count repair, so placeholder catalyst rows cannot appear before valid catalysts.

Report structured-output normalizer price-target numbers exclude boolean values after schema validation, so malformed target flags cannot become `NT$1` or `NT$0` valuation rows in legacy report text.

Report structured-output normalizer price-target values use safe number fallback before schema validation, so malformed target values cannot drop otherwise valid bear/base/bull valuation payloads before final target filtering.

Report structured-output normalizer price-target missing objects use validated fallback targets after schema validation, so payloads with valuation context but no valid raw bear/base/bull targets keep a `0.0` fallback valuation section instead of dropping the whole price-target output.

Report structured-output normalizer moat-score numbers exclude boolean values after schema validation, so malformed moat flags cannot become `1.0` or `0.0` score rows in legacy moat reports.

Report structured-output normalizer moat-score fields use safe number fallback before schema validation, so malformed moat score values cannot drop otherwise valid moat payloads before final score filtering.

Report structured-output normalizer moat-score missing objects use validated fallback scores after schema validation, so payloads with moat reasoning but no valid raw moat scores keep a conservative `1.0` fallback moat-score section instead of dropping the whole moat output.

Report structured-output normalizer moat analysis markdown uses safe text conversion before schema validation, so malformed moat body text cannot drop otherwise valid moat score payloads.

Report moat legacy text surfaces reasoning steps from structured outputs, so Agent 3 and Agent 12 plain-text report sections keep the moat scoring rationale before the analysis body.

Report legacy reasoning-step text skips single-character fragments, so moat and recommendation plain-text sections do not present non-actionable one-character model scraps as reasoning bullets.

Report structured-output normalizer management-confidence numbers exclude boolean values after schema validation, so malformed confidence flags cannot become `1.0` max-confidence management sentiment payloads.

Report structured-output normalizer management-confidence numbers use safe fallback before schema validation, so malformed confidence values cannot drop otherwise valid management sentiment payloads.

Report management-sentiment legacy text surfaces confidence from structured outputs, so Agent 20 plain-text report sections keep the certainty score beside management guidance tone.

Report management-sentiment legacy text uses quote fallback for empty highlights, so Agent 20 plain-text highlight rows show `資料不足` instead of leaving a blank quote after malformed highlight text.

Report management-sentiment legacy text uses highlight fallback for single-character fragments, so Agent 20 plain-text highlight rows show `亮點 / 資料不足` instead of presenting non-actionable one-character keyword or quote scraps.

Report management-sentiment legacy text uses fallback row for empty highlights, so Agent 20 plain-text report sections show `亮點 / 資料不足` instead of leaving management guidance without any highlight row when no highlights are displayable.

Report management-sentiment legacy text uses guidance-tone fallback for invalid metadata, so Agent 20 plain-text sections show schema-aligned `資料不足` instead of arbitrary guidance-tone labels outside `樂觀`, `中立`, or `保守`.

Report management-sentiment legacy text uses analysis body fallback for single-character fragments, so Agent 20 plain-text sections end with `資料不足` instead of non-actionable one-character analysis body scraps.

Report structured-output normalizer management-sentiment text fields use safe text conversion before schema validation, so malformed guidance tone, highlight keyword, or highlight quote fields cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment highlight rows use sequence-safe fallback before schema validation, so malformed highlight rows cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment highlight collections use missing-field fallback before schema validation, so omitted highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment empty highlight lists use minimum fallback before schema validation, so empty highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment highlight fallback rows are deferred until fixed-count repair, so placeholder highlight rows cannot displace valid management highlights.

Report structured-output normalizer downside-risk confidence numbers exclude boolean values after schema validation, so malformed risk-confidence flags cannot become `1.0` max-confidence downside risk payloads.

Report structured-output normalizer downside-risk confidence preserves explicit zero values after schema validation, so valid low-confidence risk signals cannot be silently promoted to the default confidence.

Report structured-output normalizer downside-risk confidence numbers use safe fallback before schema validation, so malformed risk-confidence values cannot drop otherwise valid downside risk payloads.

Report structured-output normalizer downside-risk text fields use safe text conversion before schema validation, so malformed risk title, evidence, impact, or severity fields cannot drop otherwise valid downside risk payloads.

Report structured-output normalizer downside-risk rows use sequence-safe fallback before schema validation, so malformed risk rows cannot drop otherwise valid downside risk payloads below the required row count.

Report structured-output normalizer downside-risk collections use missing-field fallback before schema validation, so omitted downside-risk collections cannot drop otherwise valid downside-risk payloads.

Report structured-output normalizer downside-risk empty lists use minimum fallback before schema validation, so empty downside-risk collections cannot drop otherwise valid downside-risk payloads below the required row count.

Report structured-output normalizer downside-risk fallback rows are deferred until minimum-count repair, so placeholder risk rows cannot displace valid downside risks or misalign confidence values.

Report structured-output legacy price-target rendering uses exception-safe number conversion, so malformed target number objects render as `N/A` while other valid valuation scenarios remain visible.

Report structured-output legacy price-target rendering excludes non-finite numbers, so NaN or Infinity target values render as `N/A` instead of `NT$nan` or `NT$inf` in legacy valuation text.

Report structured-output legacy price-target rendering preserves single scientific-notation numeric strings, so `1e3` renders as `NT$1,000` instead of being stripped into a synthetic `NT$13` target.

Report valuation legacy text uses fallback row for empty price targets, so Agent 4/14 plain-text valuation sections show `目標價: N/A` instead of leaving an empty target-price block when no target scenarios are displayable.

Report structured-output normalizer price-target scenario keys use safe text conversion, so malformed extra target keys cannot interrupt valuation normalization or erase valid bear/base/bull targets.

Report structured-output normalizer price-target reasoning fields use safe text conversion before schema validation, so malformed DCF, peer, or scenario reasoning fields cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer valuation-summary text fields use safe text conversion before schema validation, so malformed valuation method or double-counting check text cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer valuation-summary boolean fields use bool-safe conversion before schema validation, so malformed WACC or normalized-FCF flags cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer DCF scenario rows use safe finite-number conversion before schema validation, so malformed DCF scenario rows cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer DCF scenario numeric fields use safe number fallback before schema validation, so DCF rows with valid scenario names keep conservative numeric defaults instead of losing the row.

Report structured-output normalizer trade-plan text fields use safe text conversion before schema validation, so malformed entry, target, stop-loss, or catalyst fields cannot drop otherwise valid 1-2 week trade setup payloads.

Report structured-output normalizer trade-plan enum fields use literal fallback before schema validation, so invalid trade direction or risk level values cannot drop otherwise valid 1-2 week trade setup payloads.

Report structured-output normalizer trade-plan analysis markdown uses safe text projection after schema validation, so Agent 24 normalized payloads keep trade setup body context for legacy report text rendering when callers provide it.

Report Agent 19 required structured sections use dict-list safe scenario triggers before legacy report text rendering, so read-only trigger rows still populate crash-catalyst and stop-loss sections instead of placeholder warnings.

Report Agent 19 required structured trigger rows collapse embedded newlines before legacy report text rendering, so crash-catalyst and stop-loss condition/action text cannot split required-section bullets.

Report Agent 19 required structured trigger rows use action fallback before legacy report text rendering, so crash-catalyst and stop-loss bullets keep an actionable response when malformed or missing action text would otherwise leave only a trigger condition.

Report Agent 19 required structured trigger rows guard single-character fragments before legacy report text rendering, so crash-catalyst and stop-loss bullets skip non-actionable one-character trigger conditions and use actionable fallback text for one-character actions.

Report recommendation block skips mapping-safe nested confidence-basis maps before legacy report text rendering, so read-only confidence-basis payloads do not leak Python mapping representations into final investment recommendation blocks.

Report recommendation block display keys use shared text conversion before legacy report text rendering, so malformed recommendation field names are skipped instead of leaking Python literal text into final investment recommendation blocks.

Report recommendation block skips single-character display keys before legacy report text rendering, so Agent 7/16 plain-text recommendation rows do not present non-actionable one-character field names while preserving compact valid values.

Report recommendation block uses fallback row for empty standard recommendations, so Agent 7/16 plain-text recommendation sections show `建議: N/A` instead of leaving an empty `[投資建議]` block when no recommendation rows are displayable.

Report Agent 19 recommendation ordered values use shared text conversion before legacy report text rendering, so malformed binary or memory-view target fields fall back to `N/A` instead of leaking Python literal text into final investment recommendation blocks.

Report Agent 19 recommendation ordered values guard single-character fragments before legacy report text rendering, so ordered target and recommendation rows fall back to `N/A` for non-numeric one-character scraps while preserving compact numeric confidence values.

Report recommendation block Markdown display rows collapse embedded newlines before legacy report text rendering, so recommendation labels and values cannot split investment recommendation rows.

Report recommendation tail basis and trigger fields use shared text conversion before legacy report text rendering, so malformed confidence-basis items or trigger actions are skipped or blanked instead of leaking Python literal text into final recommendation tail sections.

Report recommendation tail confidence-basis bullets skip single-character fragments in legacy reports, so Agent 7/16/19 confidence-basis sections do not present non-actionable one-character evidence, risk, or data-gap scraps.

Report recommendation legacy analysis bodies use fallback for single-character fragments, so Agent 7/16/19 plain-text recommendation report bodies show `資料不足` instead of non-actionable one-character analysis scraps.

Report recommendation tail trigger actions use fallback text in legacy reports, so Agent 7/16/19 scenario trigger rows keep an actionable `重新檢查投資結論` recommendation when safe conversion drops malformed action values.

Report recommendation tail trigger conditions skip single-character fragments in legacy reports, so Agent 7/16/19 scenario trigger rows do not present non-actionable one-character model scraps while still preserving short readable Chinese trigger conditions.

Report recommendation tail trigger actions use fallback for single-character fragments in legacy reports, so Agent 7/16/19 scenario trigger rows keep `重新檢查投資結論` instead of presenting non-actionable one-character action scraps.

Report recommendation tail omits empty basis and trigger sections in legacy text, so Agent 7/16/19 plain-text reports do not leave orphan `信心依據` or `情境觸發器` headings when safe conversion drops malformed rows.

Report recommendation tail Markdown fields collapse embedded newlines before legacy report text rendering, so confidence-basis items and scenario trigger condition/action text cannot split final recommendation tail bullets.

Report legacy score and valuation fields use shared display conversion before legacy report text rendering, so malformed moat scores, price targets, or valuation summaries fall back to `N/A` instead of interrupting or leaking Python literal text into structured report bodies.

Report moat score legacy text uses semantic key fallback, so Agent 3/12 score rows show `護城河指標` instead of `N/A` when malformed moat-score keys cannot be displayed safely.

Report moat score legacy text uses key fallback for single-character fragments, so Agent 3/12 score rows show `護城河指標` instead of non-actionable one-character moat-score labels while preserving compact numeric score values.

Report moat score legacy text uses value fallback for single-character fragments, so Agent 3/12 score rows show `N/A` instead of non-actionable one-character moat-score values while preserving compact numeric score values.

Report moat score legacy text uses fallback row for empty scores, so Agent 3/12 plain-text score sections show `護城河指標: N/A` instead of leaving an empty moat-score block when no score rows are displayable.

Report valuation summary legacy text uses semantic key fallback, so Agent 4/14 structured valuation checks show `估值檢查項目` instead of `N/A` when malformed summary keys cannot be displayed safely.

Report valuation summary legacy text uses fallback for single-character fragments, so Agent 4/14 structured valuation checks show `估值檢查項目 / N/A` instead of non-actionable one-character summary labels or values.

Report legacy score and valuation Markdown key-value fields collapse embedded newlines before legacy report text rendering, so moat-score and valuation-summary labels or values cannot split score rows or valuation bullets.

Report legacy analysis markdown body uses shared text conversion before escaped-newline normalization, so malformed analysis bodies fall back to safe fallback text instead of leaking Python literal text into structured report bodies.

Report structured-output normalization analysis bodies use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into normalized structured report payloads.

Report structured-output schema analysis bodies use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into structured report analysis bodies.

Report structured-output schema executive thesis fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into executive thesis summaries, resolved contradictions, or smoothed markdown.

Report structured-output normalization display fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into downside thesis summaries, recommendation target rows, or short-term trade-plan fields.

Report structured-output schema display fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into management highlights, downside-risk rows, downside thesis summaries, or short-term trade-plan fields.

Report structured-output schema valuation and recommendation text fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into valuation reasoning, double-counting checks, target rows, or confidence text fields.

Report structured-output schema DCF scenario names use string-only enum fallback before legacy report text rendering, so direct model validation cannot route non-string objects with custom `__str__` methods into bear, base, or bull DCF scenario rows.

Report structured-output schema boolean fields use string-only coercion before legacy report text rendering, so direct model validation cannot let non-string objects with custom `__str__` methods choose valuation boolean flags.

Report structured-output normalization boolean fields use string-only coercion before legacy report text rendering, so normalized payloads cannot let numeric literals choose valuation boolean flags.

Report structured-output schema numeric fields use primitive-only coercion before legacy report text rendering, so direct model validation cannot let non-string objects with custom `__float__` or `__str__` methods choose valuation target or DCF scenario numbers.

Report structured-output normalization numeric fields use primitive-only coercion before legacy report text rendering, so normalized payloads cannot let non-string objects with custom `__float__` methods choose valuation target, DCF scenario, confidence, or score numbers.

Report structured-output schema recommendation keys and labels use string-only routing before legacy report text rendering, so direct model validation cannot let non-string objects with custom `__str__` methods choose recommendation labels or target-row aliases.

Report structured-output normalization recommendation keys and labels use string-only routing before legacy report text rendering, so normalized Agent 7/16/19 payloads cannot let non-string objects with custom `__str__` methods choose recommendation labels or target-row aliases.

Report structured-output schema alias lookups use string-only mapping keys before legacy report text rendering, so direct model validation cannot let non-string keys with custom equality choose valuation reasoning, target aliases, or moat-score aliases.

Report structured-output schema field lookups use string-only mapping keys before legacy report text rendering, so direct model validation cannot let non-string keys with custom equality choose valuation summary methods, boolean flags, double-counting checks, DCF scenario names, DCF scenario numbers, or recommendation trigger/catalyst fields.

Report structured-output normalization alias lookups use string-only mapping keys before legacy report text rendering, so normalized payloads cannot let non-string keys with custom equality choose valuation target aliases.

Report recommendation block legacy text uses primitive-only display fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into standard recommendation rows or Agent 19 ordered recommendation fields.

Report recommendation tail legacy next-catalyst text uses primitive-only display fallback before legacy report text rendering, so direct legacy rendering cannot persist Python-derived literals into next-catalyst event names, timeframes, directions, or trigger conditions.

Report recommendation legacy reasoning steps use primitive-only display fallback before legacy report text rendering, so direct legacy rendering cannot persist Python-derived literals into investment reasoning-step bullets.

Report recommendation legacy confidence basis uses primitive-only display fallback before legacy report text rendering, so direct legacy rendering cannot persist Python-derived literals into evidence, risk, or data-gap bullets.

Report Agent 19 required-section trigger directions use primitive-only enum checks before legacy report text rendering, so non-string objects with custom `__str__` methods cannot route crash or stop-loss trigger rows into required sections.

Report structured-output normalization nested display rows use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into management highlight rows or downside-risk rows.

Report structured-output normalization valuation display fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into valuation reasoning or structured valuation-check rows.

Report structured-output normalization recommendation tail fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into scenario trigger rows or next-catalyst rows.

Report structured-output schema recommendation tail fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into scenario trigger rows or next-catalyst rows.

Report structured-output normalization reasoning steps use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into moat or recommendation reasoning chains.

Report structured-output normalization confidence basis fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into evidence, risk, or data-gap lists.

Report legacy score and valuation analysis bodies use fallback for single-character fragments, so Agent 3/12/4/14 plain-text report bodies show `資料不足` instead of non-actionable one-character analysis scraps.

Report legacy structured display fields use shared text conversion before legacy report text rendering, so malformed management tone, highlight, downside-risk, or short-term trade-plan values fall back to defaults instead of leaking Python literal text into final report bodies.

Report short-term trade-plan legacy text preserves analysis body fallback, so Agent 24 plain-text sections keep the trade setup context after the 1-2 week plan when callers provide fallback or analysis body text.

Report short-term trade-plan legacy text uses enum fallback for invalid metadata, so Agent 24 plain-text sections show schema-aligned `Neutral` / `High` instead of arbitrary trade-direction or risk-level labels outside the structured trade-plan enums.

Report short-term trade-plan legacy text uses field fallback for single-character fragments, so Agent 24 plain-text sections show `N/A` instead of non-actionable one-character entry, target, stop-loss, or catalyst scraps.

Report short-term trade-plan legacy text uses analysis body fallback for single-character fragments, so Agent 24 plain-text sections end with `資料不足` instead of non-actionable one-character trade setup body scraps.

Report legacy structured Markdown display fields collapse embedded newlines before legacy report text rendering, so management tone, highlights, downside risks, and short-term trade-plan values cannot split headings or bullet rows.

Report analysis overlay display fields use shared text conversion before HTML output, so malformed management guidance tone, highlight, downside-risk, peer name, or peer ticker values cannot leak boolean, binary, or memory-view text into management sentiment, downside risk, or peer-comparison sections.

Report analysis overlay display fields collapse embedded newlines before HTML output, so management guidance tone, highlights, downside risks, and peer comparison labels remain single-line overlay fields.

Report analysis overlay list fields use dict-list safe conversion before HTML output, so malformed highlight or downside-risk iterators cannot interrupt management sentiment or downside-risk sections when valid rows exist.

Report analysis overlay structured-output maps use mapping-safe conversion before HTML output, so malformed structured-output accessors cannot interrupt management sentiment or downside-risk sections when valid agent payloads exist.

Report analysis overlay data child maps use mapping-safe conversion before HTML output, so malformed DCF scenario or dynamic peer metric accessors cannot interrupt scenario and peer-comparison overlays when valid data exists.

Report analysis overlay financial history sequences use sequence-safe conversion before peer-comparison target rows, so tuple asset-history payloads preserve target-company asset turnover evidence.

Report key evidence source audit child maps use mapping-safe conversion before HTML and Markdown output, so malformed source audit row accessors cannot interrupt key data evidence tables when valid provider evidence exists.

Report source audit table child maps use mapping-safe conversion before HTML and Markdown output, so malformed source audit row accessors cannot interrupt the source audit table when valid audit rows exist.

Report TWSE official availability banner source audit rows use dict-list safe conversion before HTML output, so tuple or read-only official-source audit rows cannot trigger false TWSE/MOPS unavailable warnings.

Report data trust quant metrics child maps use mapping-safe conversion before HTML and Markdown output, so malformed quant metric accessors cannot interrupt data trust cards when valid fallback warning fields exist.

Report data trust Markdown summary bullets collapse embedded newlines before report output, so market data time, reason labels, notes, and quant warning text cannot split data-confidence bullets.

Report bundle data trust property accepts mapping-safe snapshot maps before persistence or follow-up processing, so immutable data snapshots cannot hide valid report confidence metadata.

Report trust controls data and context maps use mapping-safe conversion before HTML and Markdown output, so malformed data_trust or context data accessors cannot interrupt confidence guardrails or erase valid reproducibility metadata.

Report trust controls generated-at fields use safe text conversion before reproducibility metadata output, so malformed generated time truthiness cannot interrupt confidence guardrails or hide valid provider and model traceability.

Report trust controls Markdown reproducibility fields collapse embedded newlines before report output, so model ids, prompt versions, code status, providers, and source data times cannot split the reproducibility bullet.

Report price target card and chart payload values use JSON-safe numeric conversion before HTML output, so malformed boolean, binary, memory-view, or non-finite target values cannot interrupt report rendering, leak Python literal text, or render boolean values as NT$1 targets.

Report chart payload series fields use JSON-safe text and finite-number conversion before HTML output, so malformed year labels, money series, margin series, price history, moat scores, or P/E river bands cannot interrupt report rendering or leak Python literal text into chart scripts.

Report moat score normalization excludes boolean values before HTML and Markdown output, so malformed flags cannot render as `True`, `False`, or synthetic 1/0 moat scores in visible report sections or chart payloads.

Report price history chart payload accepts mapping-safe chart wrappers before HTML chart JSON output, so immutable price history payloads preserve dates and prices instead of rendering an empty price chart.

Report price history chart series fields use sequence-safe truthiness fallback before HTML chart JSON output, so malformed date or price series truthiness cannot interrupt chart rendering when valid price history rows exist.

Report price history chart date fields use safe text conversion before future-date filtering, so one unstringable date cannot interrupt chart rendering or hide later valid price history rows.

Report price history chart mapping keys use future-date filtering before HTML chart JSON output, so legacy date-to-price payloads cannot leak future close prices into chart scripts.

Report PE river chart payload uses truthiness-safe mapping handoff before HTML chart JSON output, so malformed pe_river_chart truthiness cannot interrupt chart rendering when valid PE river rows exist.

Report PE river chart payload accepts mapping-safe chart wrappers before HTML chart JSON output, so immutable PE river payloads preserve years, bands, and EPS rows instead of rendering an empty river chart.

Report current price chart literals use finite-number conversion before HTML output, so malformed boolean, binary, memory-view, or non-finite current prices cannot render invalid JavaScript literals or distort target-price upside percentages.

Report recommendation banner target and confidence fields use shared text conversion before HTML output, so malformed boolean, binary, or memory-view recommendation values cannot leak Python literal text into verdict banners or final verdict blocks.

Report executive synthesis text fields use shared text conversion before HTML output, so malformed boolean, binary, or memory-view executive thesis or editor-synthesis values cannot leak Python literal text into high-visibility report opening sections.

Report cover metadata uses mapping-safe conversion before HTML output, so malformed report-cover payloads cannot interrupt report rendering or leak Python literal text into cover image styles.

Report cover image URL sanitizer uses truthiness-safe string conversion before HTML output, so malformed report-cover image truthiness cannot interrupt cover metadata handling while URL protocol allowlisting still blocks unsafe image sources.

Report parsed payload and child maps use mapping-safe conversion before HTML output, so malformed parsed, recommendation, price-target, moat-score, or trade-setup payloads cannot interrupt report rendering or leak Python literal text into summary, chart, or verdict sections.

Report data payload and child maps use mapping-safe conversion before HTML output, so malformed data, institutional-trading, or P/E river payloads cannot interrupt report rendering or leak Python literal text into summary, metrics, or chart sections.

Report Markdown renderer data and parsed payload maps use mapping-safe conversion before Markdown output, so malformed data, parsed, recommendation, price-target, or trade-setup payloads cannot interrupt Markdown report rendering or leak Python literal text into summary, metrics, or verdict sections.

Report Markdown renderer reference source table cells escape table separators before Markdown output, so dynamic model-route summary values containing `|` or newlines cannot corrupt the reference source table structure.

Report Markdown renderer single-line fields collapse embedded newlines before Markdown output, so ticker, company, fetch date, metric, target-price, tear-sheet, and investment-thesis display values cannot split headings, summary sentences, or bullet rows.

Report agent output maps use mapping-safe conversion before HTML and Markdown section rendering, so malformed analyses or structured-output payloads cannot interrupt report body rendering or leak Python literal text into agent sections.

Report agent output child maps use mapping-safe conversion before structured tail rendering, so read-only structured recommendation payloads cannot be skipped in HTML or Markdown final sections.

Report agent output maps preserve string-key agent ids before HTML and Markdown section rendering, so JSON-loaded analyses and structured-output maps do not silently fall back to `分析進行中` when valid agent reports exist.

Report agent sequence ids normalize string values before HTML and Markdown section rendering, so JSON-loaded agent sequences keep localized section titles, model labels, and structured tail placement.

Report agent sequence payloads fall back to pipeline defaults when malformed scalar values are loaded, so HTML/Markdown sections and execution traces do not render byte-derived fake agents such as `Agent 98`.

Report tear-sheet target price display avoids duplicate currency prefixes before HTML and Markdown output, so formatted values like `NT$120` are not rendered as `NT$NT$120` in the one-page summary.

Report audit banner final-audit child maps use mapping-safe conversion before HTML and Markdown output, so malformed final audit accessors cannot interrupt top-of-report abnormality notices when valid abnormality evidence exists.

Report audit banner abnormality list fields use list-safe conversion before HTML and Markdown output, so malformed scalar final audit, blocking issue, repair log, correction, or warning values cannot render byte-derived fake abnormality notices.

Report audit banner abnormality list fields use truthiness-safe conversion before HTML and Markdown output, so malformed final audit, blocking issue, repair log, correction, or warning list wrappers cannot interrupt top-of-report abnormality notices when valid issue text exists.

Report audit banner abnormality text fields use shared text conversion before HTML and Markdown output, so malformed final audit, blocking issue, repair log, correction, or warning values cannot leak boolean, binary, or memory-view text into top-of-report abnormality notices.

Report audit banner Markdown abnormality bullets collapse embedded newlines before Markdown output, so final audit, blocking issue, repair log, correction, and warning text cannot split top-of-report abnormality bullets.

Report reading notice quality gate text fields use shared text conversion before HTML and Markdown output, so malformed data trust, evidence gate, content credibility, or conformance values cannot leak boolean, binary, or memory-view text into usage-limit copy.

Report reading notice Markdown gate text collapses embedded newlines before Markdown output, so quality gate values and snapshot integrity details cannot split usage-limit checklist rows or warning blockquotes.

Report reading notice quality gate record detection accepts mapping-safe gate payloads before HTML and Markdown output, so immutable evidence, content credibility, or conformance wrappers cannot downgrade fully recorded passed gates to pending.

Report reading notice snapshot integrity checks treat `valid=false` as blocked before HTML and Markdown output, so contradictory snapshot metadata cannot mark a hash mismatch as ready to quote.

Report reading notice snapshot integrity checks let invalid `data.snapshot_integrity` override a conflicting verified top-level record before HTML and Markdown output, so nested snapshot blockers cannot be hidden by optimistic metadata.

Report reading notice snapshot integrity checks preserve the most specific invalid snapshot integrity detail across top-level and `data.snapshot_integrity` before HTML and Markdown output, so generic top-level blockers cannot hide nested provider or hash mismatch evidence.

Report reading notice snapshot integrity checks accept mapping-safe snapshot integrity payloads before HTML and Markdown output, so immutable integrity wrappers cannot hide invalid snapshot blockers.

Report reading notice snapshot integrity checks downgrade recorded non-verified snapshots to warning before HTML and Markdown output, so unverified legacy or hashless snapshots do not render as passed.

Report reading notice snapshot integrity details deduplicate repeated error entries before HTML and Markdown output, so live/generated report usage notices show each provider or hash detail once while preserving first-seen order.

Report reading notice snapshot integrity details derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so live/generated report usage notices keep hash evidence visible.

Report reading notice snapshot integrity details prefer hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report reading notice snapshot integrity details remove default generic blocker text when the same error list contains specific provider or hash details, so live/generated report usage notices stay focused on the actionable failure reason.

Report view and HTML download paths re-check the current `.data.json` snapshot integrity before returning stored report HTML, so a stale static passed notice is replaced with a blocked notice when the snapshot hash no longer matches.

Report Markdown download paths re-check the current `.data.json` snapshot integrity before returning stored Markdown, so a stale static passed notice is replaced with a blocked Markdown notice when the snapshot hash no longer matches.

Report artifact view and download paths treat malformed or non-object `.data.json` snapshots as blocked before returning stored HTML or Markdown, so corrupted snapshot files cannot leave stale passed notices in reusable report artifacts.

Report artifact view and download paths treat missing `.data.json` snapshots as warning before returning stored HTML or Markdown, so legacy reports without a snapshot cannot leave stale passed notices in reusable artifacts.

Report artifact view and download paths honor invalid `snapshot_integrity` recorded inside `.data.json` before returning stored HTML or Markdown, so hashless snapshots that already failed verification cannot leave stale passed notices in reusable artifacts.

Report artifact view and download paths also honor invalid `data.snapshot_integrity` recorded inside `.data.json`, so nested snapshot integrity metadata follows the same blocked-notice contract as top-level metadata.

Report artifact view and download paths let any recorded invalid snapshot integrity override a conflicting verified record before returning stored HTML or Markdown, so nested blockers cannot be hidden by a top-level green state.

Report artifact view and download paths preserve the most specific invalid snapshot integrity detail before returning stored HTML or Markdown, so a generic top-level blocker cannot hide a nested hash or provider-audit mismatch.

Report artifact view and download paths treat default generic snapshot integrity blocker text as less specific than nested hash or provider-audit mismatch details, so operators see the actionable failure reason first.

Report artifact view and download paths derive a `snapshot_hash mismatch` detail from recorded invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so hash evidence is still visible in stored HTML or Markdown.

Report artifact view and download paths prefer recorded hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report artifact view and download paths remove default generic snapshot integrity errors when the same recorded error list also contains specific details, so stored HTML and Markdown surface the actionable blocker without boilerplate noise.

Report artifact view and download paths deduplicate recorded snapshot integrity error details before repairing stored HTML or Markdown reading notices, so repeated provider or hash details are shown once while preserving first-seen order.

Report quality repair queue quality gate fields use dict-native field reads before action prioritization, so malformed report, content credibility, report conformance, evidence gate, data trust, or decision freshness accessors cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue report identity fields use string-safe conversion before provider-impact handoff and action prioritization, so malformed ticker, filename, or pipeline truthiness cannot interrupt manual-review prioritization or erase valid repair reasons.

Data trust reproducibility packet identity fields use shared text conversion before snapshot provenance projection, so malformed ticker, prompt version, pipeline id, code commit, generated time, model id, provider, or source time fields cannot leak boolean, binary, or memory-view text into report reproducibility metadata.

Report quality repair queue quality gate text fields use string-safe conversion before action prioritization, so malformed status, summary, or message truthiness cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue quality gate text fields treat lookup string conversion failures as blank before action prioritization, so `KeyError` or `IndexError` from malformed summary or message text cannot interrupt manual-review prioritization while later valid fallback text can still describe the repair reason.

Report quality repair queue reason codes use string-safe conversion before action prioritization, so malformed reason-code text cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue stale source lists use string-safe conversion before action prioritization, so malformed stale-source text cannot interrupt refresh-data prioritization or erase valid stale source evidence.

Report quality repair queue text list tuple sequences are evaluated before action prioritization, so immutable reason-code or stale-source batches do not lose repair evidence.

Report quality repair queue reports envelopes use mapping-safe conversion before action prioritization, so immutable report-list wrappers cannot hide stale, blocked, or invalid repair actions.

Report quality repair queue snapshot integrity maps use mapping-safe conversion before action prioritization, so immutable integrity payloads still block automatic reuse when a snapshot hash is invalid.

Report quality repair queue quality gate child maps use mapping-safe conversion before action prioritization, so immutable content credibility, conformance, evidence, data trust, or freshness payloads cannot hide manual-review repair actions.

Report quality repair queue quality gate child maps use Mapping traversal when `.items()` lookup fails before action prioritization, so malformed content credibility or conformance wrappers cannot hide manual-review repair actions if standard key traversal remains readable.

Report quality repair queue quality gate child maps skip lookup item failures during Mapping traversal before action prioritization, so one broken content credibility key cannot hide later valid blocked status or summary fields.

Report quality repair queue snapshot integrity verifier results treat `valid=false` as invalid before action prioritization, so raw verifier payloads still block automatic reuse when a snapshot hash is invalid.

Report quality repair queue snapshot integrity verifier results let `valid=false` override non-invalid status text before action prioritization, so contradictory metadata cannot hide a hash mismatch.

Report quality repair queue snapshot integrity error details use string-safe conversion before action prioritization, so scalar mismatch details still reach manual-review actions instead of falling back to generic repair text.

Report quality repair queue derives a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so manual-review actions keep hash evidence visible.

Report quality repair queue prefers hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report quality repair queue removes default generic snapshot integrity error details when specific provider or hash details exist before action prioritization, so manual-review actions focus on the actionable blocker without boilerplate noise.

Report quality repair queue deduplicates repeated snapshot integrity error details before action prioritization, so manual-review actions show each provider or hash detail once while preserving first-seen order.

Shared mapping list conversions use native list and tuple iterators when iterator accessors fail before item traversal, so report repair and strategy evaluation do not erase valid sequence evidence.

Shared mapping text list conversions use native list and tuple iterators when custom iterators fail before yielding, so report repair reason-code or stale-source evidence is not erased by malformed iterator objects.

Shared mapping text list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed report repair reason-code or stale-source iterators cannot erase underlying list evidence.

Shared mapping dict list conversions use native list and tuple iterators when custom iterators fail before yielding, so report repair provider-alert evidence is not erased by malformed iterator objects.

Shared mapping dict list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed report repair provider-alert iterators cannot erase underlying alert evidence.

Shared mapping traversal falls back to native dict items when custom items iterators fail before yielding, so malformed mapping iterator objects cannot erase underlying snapshot, repair, or provider evidence.

Report quality repair queue provider alert lists preserve valid entries before iterator failures, so malformed provider alert iteration cannot interrupt provider-impact handoff or erase wait-provider-recovery repair evidence.

Report quality repair queue report collections preserve valid reports before iterator failures, so malformed report iteration cannot interrupt action prioritization or erase valid repair reasons.

Report quality repair queue decision freshness detail fields use string-safe conversion before action prioritization, so malformed rerun reason truthiness cannot interrupt rerun-analysis prioritization or erase valid freshness repair context.

Report quality repair queue decision freshness flags use bool-safe conversion before action prioritization, so malformed rerun flag truthiness cannot interrupt rerun-analysis prioritization or erase valid freshness repair context.

Report quality repair queue decision freshness flags treat lookup truthiness failures as false before action prioritization, so `KeyError` or `IndexError` from malformed rerun flags cannot interrupt rerun-analysis prioritization while later valid stale-report flags can still trigger repair.

Report quality repair queue limit uses integer-safe conversion before slicing prioritized actions, so malformed limit truthiness cannot interrupt action prioritization or erase valid repair reasons.

Report quality repair queue limit uses the default cap on lookup integer conversion failures before slicing prioritized actions, so `KeyError` or `IndexError` from malformed limit adapters cannot interrupt action prioritization or hide valid repair items.

Outcome calibration quality signal fields use dict-native field reads before miss attribution, so malformed backtest, report, data trust, content credibility, report conformance, or decision freshness accessors cannot interrupt quality-signal learning or misclassify low-quality misses as thesis failures.

Outcome calibration report identity fields use string-safe conversion before report matching and miss attribution, so malformed report filename, ticker, pipeline, horizon, or reason truthiness cannot interrupt quality-signal learning or disconnect misses from valid report-time evidence.

Outcome calibration data trust score fields use float-safe fallback before miss attribution, so malformed score truthiness cannot interrupt quality-signal learning or replace a valid zero score with fallback confidence.

Outcome calibration row collections use list-safe normalization before report matching and miss attribution, so malformed backtest or report collection truthiness cannot interrupt quality-signal learning or erase valid rows.

Outcome calibration decision freshness flags use bool-safe conversion before miss attribution, so malformed rerun flag truthiness cannot interrupt quality-signal learning or misclassify stale report-time evidence.

Outcome calibration matched reports use dict-safe fallback before miss attribution, so malformed matched report truthiness cannot interrupt quality-signal learning or disconnect misses from valid report-time evidence.

Outcome calibration numeric fields use conversion-safe fallback before miss attribution, so malformed ROI or data trust score conversion cannot interrupt quality-signal learning or erase valid stale report-time evidence.

Strategy evaluator numeric fields use conversion-safe fallback before alpha model comparison, so malformed ROI, excess return, or drawdown conversion cannot interrupt strategy evaluation or erase valid hit-rate evidence.

Strategy evaluator artifact fields use dict-native field reads before alpha model comparison, so malformed artifact, metrics, or quality funnel accessors cannot interrupt strategy evaluation or erase valid model, trigger, quality, or hit-rate evidence.

Strategy evaluator hit flags use bool-safe fallback before alpha model comparison, so malformed hit flag truthiness cannot interrupt strategy evaluation or erase valid outcome-based hit-rate evidence.

Strategy evaluator artifact iterators preserve valid entries before alpha model comparison, so malformed artifact collection iteration cannot erase already parsed model, trigger, quality, or hit-rate evidence.

Strategy evaluator artifact tuple sequences are evaluated before alpha model comparison, so immutable artifact batches do not appear as empty backtest evidence.

Provider impact report fields use dict-native field reads before provider recovery decisions, so malformed report, data trust, or provider alert accessors cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact report, data trust, and alert maps use mapping-safe conversion before provider recovery decisions, so immutable report confidence wrappers cannot hide core-source wait-provider-recovery blocking evidence.

Provider impact report, data trust, and alert maps use Mapping traversal when `.items()` lookup fails before provider recovery decisions, so malformed report confidence wrappers cannot hide core-source wait-provider-recovery evidence if standard key traversal remains readable.

Provider impact report, data trust, and alert maps skip lookup item failures during Mapping traversal before provider recovery decisions, so one broken report, trust, or alert key cannot hide later valid provider recovery evidence.

Provider impact report identity fields use string-safe conversion before provider recovery output, so malformed filename or pipeline truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact ticker identity uses string-safe conversion before provider recovery output, so malformed ticker payload objects cannot interrupt JSON serialization or erase wait-provider-recovery blocking evidence.

Provider impact current fetch fields use bool-, integer-, and string-safe conversion before provider recovery decisions, so malformed current fetch truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact current fetch fields treat lookup integer and bool conversion failures as empty current-fetch evidence, so `KeyError` or `IndexError` from malformed record-count, stale, or healthy-entry adapters cannot interrupt provider recovery impact classification.

Provider impact alert text fields use string-safe conversion before provider recovery decisions, so malformed source, provider, or alert level truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact reason codes use string-safe conversion before provider recovery decisions, so malformed reason-code text cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact reason code iterators preserve valid entries before failures, so malformed reason-code iteration cannot erase already parsed provider recovery blocking evidence.

Provider impact text list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed reason-code iterator objects cannot erase underlying provider recovery blocking evidence.

Provider impact text list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code iterators cannot erase underlying provider recovery blocking evidence.

Provider impact text list conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code `__iter__` access cannot erase underlying provider recovery blocking evidence before iteration starts.

Provider impact alert iterators preserve valid entries before failures, so malformed provider alert iteration cannot erase already parsed core-source provider recovery blocking evidence.

Provider impact ledger report iterators preserve valid reports before failures, so malformed report collection iteration cannot erase already parsed provider recovery impact rows or sampled report counts.

Provider impact ledger reports envelopes use mapping-safe conversion before provider recovery decisions, so immutable report-list wrappers cannot hide wait-provider-recovery blocking evidence or sampled report counts.

Provider impact tuple sequences are evaluated before provider recovery decisions, so immutable reason-code, alert, or ledger report batches do not lose wait-provider-recovery blocking evidence.

Provider impact list conversions use native list and tuple iterators when iterator accessors fail before provider recovery decisions, so underlying reason-code, alert, or ledger report evidence is not erased.

Provider impact dict list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed provider alert iterator objects cannot erase underlying provider recovery evidence.

Provider impact dict list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed provider alert iterators cannot erase underlying provider recovery evidence.

Provider impact dict list conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed provider alert `__iter__` access cannot erase underlying provider recovery evidence before iteration starts.

Provider impact ledger sort keys use string-safe conversion before ordering, so malformed ticker sort-key truthiness cannot interrupt provider recovery impact ledger output.

Daily decision queue action fields use dict-native field reads before priority ordering, so malformed repair, provider impact, notification delivery, backtest, rerun, model route, watchlist, or screener action accessors cannot interrupt daily operating order or erase valid queue context.

Notification plan action fields use dict-native field reads before message and outbox handoff, so malformed decision queue or legacy action accessors cannot interrupt notification planning or erase source, report, CTA, rank, and delivery identity context.

Notification delivery audit context fields use dict-native field reads before persistence and reconciliation, so malformed outbox or audit-record accessors cannot interrupt sender audit writes or erase source, report, CTA, rank, retry, and attention context snapshots.

## Runtime Health And Ops Dashboard

Liveness 只確認 API process 還能回應：

```bash
curl http://127.0.0.1:8080/healthz
```

Readiness 會檢查 runtime storage 與 task queue；若 Redis/RQ 或 SQLite path 不可用，會回 HTTP 503：

```bash
curl http://127.0.0.1:8080/readyz
```

Operator dashboard 是 read-only 聚合端點，不需要 mutation token：

```bash
curl http://127.0.0.1:8080/api/observability/dashboard
curl http://127.0.0.1:8080/api/ops/dashboard
```

`stuck_jobs` 只包含 `running` 與 `waiting_retry` 超過未更新門檻的工作；若同一 task identity 可由 RQ 明確確認為 `queued`、`deferred` 或 `scheduled`，則 `waiting_retry` 視為 queue wait 而不列入 stuck。`started`、unknown 或 RQ 查詢失敗仍保留告警資格；一般 `queued` backlog 應以 RQ queue depth 與 `oldest_queued_seconds` 判斷。

回傳內容包含報告完成耗時 `p50/p95/p99`、active job count、stuck job warning、node/model telemetry summary、`prompt_budget` token 摘要、RQ queue depth/registry counts、provider 24 小時 degradation alerts、API quota ledger 摘要、`notification_delivery` sender audit health，以及 `free_mode` 免費模式合約摘要。`notification_delivery` 會揭露 `failed_count`、`retry_exhausted_count`、`channel_counts`、`failure_reason_counts`、`attention_contexts` 與 `health`；`attention_contexts` 是低量 failed delivery context snapshot，讓 operator 或 repair flow 可定位受影響 source、ticker、report 與 CTA。當 delivery audit 出現 failed 或 retry exhausted 時，dashboard `status` 會升為 `warning`。`status` 可能是 `ok`、`warning` 或 `critical`。

Prometheus `/metrics` 也輸出 notification delivery audit 摘要：`stock_agent_notification_delivery_count{status="failed"}`、`stock_agent_notification_delivery_count{status="retry_exhausted"}`、`stock_agent_notification_delivery_channel_count{channel="..."}`、`stock_agent_notification_delivery_failure_reason_count{reason="timeout|auth|rate_limited|configuration|network|other|unknown"}` 與 `stock_agent_notification_delivery_health{state="ok|warning"}`。這些都是目前 audit rows 的 gauge；health 會固定輸出 `state="ok"` 和 `state="warning"` 兩條 one-hot series，failure reason 只使用低基數分類，不把 raw `last_error` 放進 label，讓外部監控在 in-app 工作台之外也能穩定告警通知通道故障。

Notification delivery summary fetch failures fall back to empty delivery summaries for Prometheus, so notification audit storage or aggregation errors cannot interrupt provider or queue metrics output.

Ops dashboard notification delivery summary fetch failures fall back to empty delivery summaries, so notification audit storage or aggregation errors cannot suppress jobs, queue, provider, or API quota sections.

Ops dashboard API quota payload failures fall back to empty quota services, so local quota ledger or aggregation errors cannot suppress jobs, queue, provider, or notification delivery sections.

Ops dashboard malformed API quota payloads fall back to empty quota services, so quota payload shape errors cannot suppress jobs, queue, provider, or notification delivery sections.

Ops dashboard API quota service lists use list-of-dict safe conversion before payload output, so malformed quota service collections fall back to empty services without suppressing jobs, queue, provider, or notification delivery sections.

Ops dashboard API quota numeric and observation fields use strict string/count conversion before payload output, so boolean, binary, or memory-view quota limits and provider observations cannot become synthetic quota evidence.

Ops dashboard job snapshot failures fall back to empty job sections and mark dashboard status warning, so job telemetry or latency aggregation errors cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard malformed job payloads fall back to empty job sections and mark dashboard status warning, so job payload shape errors cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard nested job sections use dict-safe conversion before payload output, so malformed job telemetry sections fall back to empty maps without suppressing queue, provider, API quota, or notification delivery sections.

Ops dashboard job unavailable status flags use bool-safe conversion, so malformed observability_unavailable truthiness cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard stuck job count status aggregation uses dict- and integer-safe conversion, so malformed stuck job count truthiness cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard stuck job count fields use strict count conversion before status and payload output, so boolean, binary, or memory-view counts cannot be decoded into synthetic stuck-job warnings or non-JSON-safe payload values.

Ops dashboard malformed provider payloads fall back to an empty last_24h provider state, so provider SLA payload shape errors cannot suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider selected windows use string-safe conversion before payload output, so malformed selected-window values cannot leak non-JSON-safe objects or suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard malformed provider alert lists fall back to empty alerts, so provider alert payload shape errors cannot suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert impact classification uses string-safe source conversion, so malformed alert source truthiness cannot interrupt jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert level comparison uses string-safe conversion before status and count aggregation, so malformed alert-level equality cannot interrupt jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert success-rate fields use finite-float conversion before payload output, so NaN or Infinity alert rates fall back to zero instead of leaking non-standard JSON numbers.

Ops dashboard provider alert text and window fields use string- and dict-safe conversion before payload output, so malformed alert source, provider, message, status, basis, selected window, or windows maps cannot leak non-JSON-safe objects.

Provider SLA dashboard alert payload fields use dict-native field reads before impact classification, so malformed provider alert accessors cannot interrupt core/enrichment status projection or erase valid provider, level, message, window, and success-rate evidence.

When a core source has usable provider evidence in the same selected window, the ops dashboard preserves the system-level `critical` impact and exposes `current_source_has_healthy_entry=true`; this is fallback coverage evidence, not a report-level readiness or rerun decision.

The provider summary also exposes `core_critical_covered_count` and `core_critical_uncovered_count`, so operators can scan fallback coverage without changing the system-level status.

Notification delivery observability summaries use dict-safe conversion before rendering dashboard and Prometheus maps, so malformed summary or count-map truthiness cannot interrupt external delivery health metrics.

Notification delivery observability fields use dict-native field reads before attention, dashboard, and Prometheus rendering, so malformed summary accessors cannot interrupt notification health visibility or erase failed, retry-exhausted, channel, and reason evidence.

Notification delivery observability counts use integer-safe conversion before rendering dashboard and Prometheus gauges, so malformed count conversion cannot interrupt external delivery health metrics.

Notification delivery observability counts use strict count conversion before rendering dashboard and Prometheus gauges, so boolean, binary, or memory-view audit counts render as zero instead of decoded delivery-failure evidence.

Notification delivery dashboard count maps use shared text keys and integer-safe values before payload output, so boolean, binary, or memory-view channel/reason keys cannot leak non-JSON-safe map entries into ops dashboard responses.

Notification delivery Prometheus channel and reason labels use shared text conversion with unknown fallback, so malformed, boolean, binary, or memory-view labels cannot leak into external delivery health metrics.

Prometheus label rendering uses shared text conversion with unknown fallback, so malformed, boolean, binary, or memory-view provider, queue, or delivery label values cannot leak into metrics output.

Prometheus provider summary fetch failures fall back to empty provider series, so provider SLA storage or aggregation errors cannot interrupt queue or notification delivery metrics output.

Prometheus provider summary non-iterable payloads fall back to empty provider series, so malformed provider summary payload shape cannot interrupt queue or notification delivery metrics output.

Prometheus provider summary iterator failures preserve provider rows parsed before the failure, so one broken provider summary iterator cannot suppress earlier valid provider series or interrupt queue and notification delivery metrics output.

Prometheus queue snapshot fetch failures fall back to unknown/zero queue gauges, so queue observer or backend errors cannot interrupt provider or notification delivery metrics output.

Ops dashboard queue snapshot fetch failures fall back to an unavailable unknown queue status, so queue observer or backend errors mark the dashboard critical without suppressing jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue availability uses bool-safe conversion before status aggregation and payload output, so malformed queue availability truthiness cannot suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue metadata uses string-, integer-, and dict-safe conversion before payload output, so malformed backend, queue name, depth, or queues maps cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard named queue details use string-key and dict-safe conversion before payload output, so malformed named queue keys or detail rows cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard named queue detail fields use integer-, string-, and registry-map safe conversion before payload output, so malformed named queue depth, registry counts, or supplemental detail fields cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue integer fields use strict count conversion before payload output, so boolean, binary, or memory-view queue depth, registry, active-task, and timeout payloads render as zero instead of decoded backlog values.

Ops dashboard queue supplemental fields use integer-, float-, string-, and registry-map safe conversion before payload output, so malformed registries, active task counts, queue age, timeout, or error values cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue text metadata uses shared text conversion before payload output, so boolean, binary, or memory-view queue labels and error details cannot leak as operator-facing strings.

Ops dashboard queue age fields use finite-float conversion before payload output, so NaN or Infinity queue age values fall back to zero instead of leaking non-standard JSON numbers.

Ops dashboard queue age fields use strict finite-float conversion before payload output, so boolean, binary, or memory-view queue age payloads render as zero instead of decoded wait-time values.

Observability dashboard and Prometheus payload shaping uses payload-safe mapping conversion instead of persistence JSON pruning, so empty job lists, named queue keys, provider SLA numeric fields, notification delivery label maps, and non-finite numeric fields remain present and are normalized to safe output values.

Ops dashboard free mode provider summaries use dict-, list-, bool-, and string-safe conversion before payload output, so malformed free-mode provider tiers or provider lists cannot suppress jobs, queue, provider, API quota, or notification delivery sections.

Ops dashboard free mode violations use string-safe conversion before payload output, so malformed violation entries cannot leak non-JSON-safe objects or suppress jobs, queue, provider, API quota, or notification delivery sections.

Ops dashboard free mode provider tiers and violations use shared text conversion instead of persistence JSON pruning, so boolean, binary, or memory-view values cannot be decoded into trusted cost-tier counts or visible violation text.

Prometheus queue snapshots use dict-safe conversion before rendering queue gauges, so malformed queue snapshot mapping cannot interrupt metrics output and falls back to unknown/zero queue gauges.

Prometheus queue backend and queue name rendering uses string-safe conversion, so malformed queue label truthiness cannot interrupt queue gauges.

Prometheus queue availability rendering uses bool-safe conversion, so malformed queue availability truthiness cannot interrupt queue gauges.

Prometheus named queue depth maps use payload-safe conversion, so malformed queue map or detail truthiness cannot interrupt queue gauges, and named queues with malformed detail rows still emit zero-depth series instead of disappearing.

Prometheus queue depth gauges use strict count conversion, so boolean, binary, or memory-view default and named queue depths render as zero instead of decoded backlog values.

Prometheus integer gauges use integer-safe conversion, so malformed provider or queue count conversion cannot interrupt metrics output.

Prometheus float gauges use float-safe conversion, so malformed provider success-rate conversion cannot interrupt metrics output.

Prometheus provider numeric gauges use strict numeric conversion, so boolean, binary, or memory-view provider success-rate, attempts, and error-count payloads render as zero instead of decoded metric values.

Prometheus provider rows use dict-safe conversion before rendering provider gauges, so malformed provider row mapping cannot interrupt metrics output or create empty-label provider series.

Provider SLA window alert enrichment uses integer-, float-, and string-safe conversion, so malformed provider attempts, success-rate, error count, or status values cannot interrupt dashboard alert recalculation.

Provider SLA alert policy basis selection uses dict-, integer-, float-, and string-safe conversion, so malformed window stats truthiness cannot interrupt upstream provider alert generation.

Data trust provider SLA evidence attempts use truthiness-safe integer and basis text conversion, so malformed provider SLA alert evidence cannot interrupt report trust downgrade decisions.

Data trust provider SLA evidence attempts treat lookup integer conversion failures as zero evidence, so `KeyError` or `IndexError` from malformed attempt adapters cannot interrupt report trust downgrade decisions or create unsupported provider SLA downgrades.

Data trust provider SLA nested window maps use dict-safe conversion before evidence attempts, so malformed nested window accessors cannot interrupt report trust downgrade decisions or suppress alert-level attempts fallback.

Data trust provider SLA row maps fall back to native dict items when copy lookups fail, so `KeyError` or `IndexError` from malformed source-audit or alert row mapping adapters cannot erase provider downgrade evidence.

Data trust provider SLA alert matching uses string-safe source, provider, level, and message conversion, so malformed alert text truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit entries use string-, integer-, and bool-safe conversion, so malformed current source audit truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit entries treat lookup integer and bool conversion failures as empty current-fetch evidence, so `KeyError` or `IndexError` from malformed record-count or stale adapters cannot interrupt report trust downgrade decisions.

Data trust provider SLA trust metadata uses list- and string-safe conversion, so malformed existing trust status, reason codes, or notes cannot interrupt report trust downgrade decisions.

Data trust provider SLA alert collections use iterable-safe conversion, so malformed alert collection truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit collections use iterable-safe conversion, so malformed current source audit iterator failures cannot erase valid source audit rows or interrupt report trust downgrade decisions.

Data trust provider SLA rows use dict-safe conversion before matching current source audit entries and provider alerts, so malformed row accessors cannot interrupt data-trust downgrades or erase provider SLA evidence.

Data trust provider SLA source data uses dict-safe conversion before reading current source audit rows, so malformed source data accessors cannot interrupt data-trust downgrades or erase provider SLA evidence.

Data trust provider SLA alert fetch failures fall back to existing trust, so provider SLA storage or helper failures cannot interrupt report trust downgrade decisions.

Data trust provider SLA policy failures fall back to base trust before final score calculation, so provider SLA policy exceptions cannot interrupt report confidence finalization or erase already computed source audit trust evidence.

Data trust provider SLA policy lookup failures fall back to base trust before final score calculation, so `KeyError` or `IndexError` from provider SLA policy adapters cannot interrupt report confidence finalization or erase already computed source audit trust evidence.

Data trust provider SLA policy failure fallback uses an unmutated base trust snapshot before final score calculation, so partial in-place provider SLA policy mutations cannot pollute report confidence finalization after the policy raises.

Data trust post-SLA status fields use canonical status normalization before final score calculation, so malformed provider SLA status values cannot leak non-canonical report confidence states or drift away from score semantics.

Data trust post-SLA list metadata fields are written back after string-list normalization before final score calculation, so malformed provider SLA critical failures, stale sources, notes, or reason codes cannot leak non-list report confidence metadata while score semantics use normalized evidence.

Data trust post-SLA market timestamp fields use shared text normalization before final score output, so malformed provider SLA last-market timestamps cannot leak non-string report confidence metadata.

Data trust post-SLA provider SLA alert metadata uses dict-list normalization before final score output, so malformed provider SLA alert collections cannot leak non-list report confidence metadata.

Data trust provider SLA trust metadata iterators preserve valid entries before failures, so malformed reason-code or note iterators cannot erase already parsed report trust context.

Data trust provider SLA list conversions use native list and tuple iterators when iterator accessors fail before trust downgrade decisions, so source-audit rows, provider alerts, reason codes, and notes are not erased.

Data trust provider SLA dict row conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed source-audit or provider-alert iterator objects cannot erase trust downgrade evidence.

Data trust provider SLA dict row conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed source-audit or provider-alert iterators cannot erase trust downgrade evidence.

Data trust provider SLA dict row conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed source-audit or provider-alert `__iter__` access cannot erase trust downgrade evidence before iteration starts.

Data trust provider SLA text list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed trust metadata reason-code or note iterator objects cannot erase existing report trust context.

Data trust provider SLA text list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code or note iterators cannot erase existing report trust context.

Data trust provider SLA text list conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code or note `__iter__` access cannot erase existing report trust context before iteration starts.

Data trust normalization note fields use string-list conversion before report trust metadata output, so tuple notes preserve valid report limitation context and malformed binary values are dropped.

Data trust normalization provider SLA alert lists use dict-list safe conversion before report trust metadata output, so tuple or native-backed alert collections preserve valid provider health metadata without interrupting report confidence normalization.

Data trust scoring audit source names use string-safe conversion, so malformed source truthiness cannot interrupt report trust scoring or erase valid source audit decisions.

Data trust audit entry text fields use string-safe conversion, so malformed source, provider, error kind, or message truthiness cannot interrupt source audit evidence creation.

Data trust audit entry text fields use shared text conversion before source audit evidence output, so malformed source, provider, error kind, or message values cannot leak boolean, binary, or memory-view text into source audit rows.

Data trust source audit append preserves tuple audit batches before adding new entries, so immutable upstream source-audit payloads do not lose existing provider evidence during audit enrichment.

Report key evidence source fields use shared text conversion before HTML and Markdown report output, so malformed provider, status, source, or fetched-at values cannot leak boolean, binary, or memory-view text into report evidence tables.

Report key evidence aggregated stale flags use bool-safe conversion before HTML and Markdown report output, so `KeyError` or `IndexError` from malformed source-audit stale adapters cannot interrupt key evidence rendering or mark malformed stale values as true.

Report key evidence data field presence checks ignore malformed scalar values before HTML and Markdown report output, so boolean, binary, or memory-view data fields cannot synthesize source-evidence rows.

Report key evidence data field presence checks use strip-safe shared text conversion before HTML and Markdown report output, so malformed data string `strip()` cannot interrupt key evidence rendering or erase valid source evidence.

Report key evidence Markdown cells escape table separators before Markdown output, so provider or timestamp values containing `|` or newlines cannot corrupt the key evidence table structure.

Report source audit table fields use shared text conversion before HTML and Markdown report output, so malformed source, provider, status, fetched-at, or message values cannot leak boolean, binary, or memory-view text into source audit sections.

Report source audit Markdown cells escape table separators before Markdown output, so provider, fetched-at, or message values containing `|` or newlines cannot corrupt the source audit table structure.

Report source evidence numeric and boolean fields use safe conversion before HTML and Markdown report output, so malformed duration, record count, cache-hit, or stale values cannot leak boolean, binary, or memory-view text into key evidence or source audit tables.

Report data trust summary fields use shared text conversion before HTML and Markdown report output, so malformed trust notes, market timestamps, quant fallback fields, or warning messages cannot leak boolean, binary, or memory-view text into data-trust sections.

Report data trust quant fallback fields use truthiness-safe list conversion before HTML and Markdown report output, so malformed fallback field list wrappers cannot interrupt quant warning rendering and valid fallback field names remain visible.

Report evidence matrix payload source fields use shared text conversion before tooltip JSON output, so malformed provider, status, source, fetched-at, or message values cannot leak boolean, binary, or memory-view text into report evidence data.

Report evidence matrix payload message fallback uses truthiness-safe field selection before tooltip JSON output, so `KeyError` or `IndexError` from malformed source-audit message truthiness cannot interrupt payload generation or overwrite a present message with fallback text.

Report evidence matrix payload message fallback skips text-empty malformed values before tooltip JSON output, so binary or memory-view `message` fields cannot hide a valid `error_kind` fallback in source evidence tooltips.

Report evidence matrix payload message presence checks use length-safe fallback before tooltip JSON output, so malformed source-audit message container length cannot interrupt payload generation or hide a valid `error_kind` fallback.

Report evidence matrix payload message presence checks use strip-safe shared text conversion before tooltip JSON output, so malformed source-audit message string `strip()` cannot interrupt payload generation or overwrite a present message.

Report evidence matrix source audit child maps use mapping-safe conversion before tooltip JSON output, so malformed source audit row accessors cannot interrupt report evidence payload generation when valid provider evidence exists.

Report evidence matrix source row labels use shared text conversion before conclusion matching, so malformed label hash behavior cannot interrupt conclusion evidence rendering when the label text is still valid.

Report evidence matrix Markdown cells use shared text conversion before table output, so malformed cell truthiness cannot interrupt Markdown export and pipe separators are still escaped.

Report evidence matrix HTML cells use shared text conversion before table output, so malformed cell stringification cannot interrupt HTML rendering or leak exception text into visible report evidence.

Report evidence matrix row fetched-at fields use truthiness-safe text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row timestamp truthiness cannot interrupt conclusion evidence rendering.

Report evidence matrix row status fields use truthiness-safe text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row status truthiness cannot interrupt conclusion evidence rendering.

Report evidence matrix row provider fields use truthiness-safe text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row provider truthiness cannot interrupt conclusion evidence rendering.

Report evidence matrix stale-source flags use bool-safe conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row stale truthiness cannot interrupt limitation rendering or synthesize stale-source notes.

Report evidence matrix price-target basis excludes boolean values before HTML, Markdown, snapshot, and tooltip output, so malformed target flags cannot render as `NT$1` or `NT$0` valuation evidence.

Report evidence matrix price-target basis excludes non-finite numeric values before HTML, Markdown, snapshot, and tooltip output, so malformed target numbers cannot render as `NT$nan` or `NT$inf` valuation evidence.

Report evidence matrix price-target scenario keys skip malformed text before HTML, Markdown, snapshot, and tooltip output, so binary or memory-view valuation scenario names cannot render as `N/A: NT$120` evidence.

Report evidence matrix recommendation-basis keys use shared text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed recommendation key stringification cannot interrupt conclusion evidence rendering.

Report evidence matrix recommendation-basis values use equality-safe text checks before HTML, Markdown, snapshot, and tooltip output, so malformed recommendation value comparison cannot interrupt conclusion evidence rendering.

Report evidence matrix recommendation-basis string values use strip-safe shared text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed recommendation value `strip()` cannot interrupt conclusion evidence rendering.

Report evidence matrix moat-score basis skips malformed metric keys before HTML, Markdown, snapshot, and tooltip output, so binary or memory-view moat metric names cannot render as `N/A: 8/10` evidence.

Report evidence matrix limitation notes use shared text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed data-source note values cannot leak boolean, binary, or memory-view text into report limitation copy.

Report evidence matrix limitation notes use text-list safe conversion before HTML, Markdown, snapshot, and tooltip output, so tuple data-source notes preserve valid note text without leaking Python tuple or binary representations.

Data trust audit entry status uses string-safe conversion, so malformed but valid status text cannot be misclassified as unavailable.

Data trust audit entry duration fields ignore boolean millisecond overrides before epoch delta fallback, so true or false duration fields cannot replace valid source fetch timing evidence.

Data trust audit entry duration fields ignore non-finite millisecond overrides before epoch delta fallback, so NaN or Infinity duration fields cannot interrupt source audit creation or replace valid fetch timing evidence.

Data trust audit entry duration fields ignore overflowing millisecond overrides before epoch delta fallback, so oversized duration fields cannot interrupt source audit creation or replace valid fetch timing evidence.

Data trust audit entry duration fields ignore non-finite epoch timestamps before delta calculation, so NaN or Infinity started/finished fields cannot interrupt source audit creation or create synthetic fetch timing evidence.

Data trust audit entry duration fields ignore overflowing epoch timestamps before delta calculation, so oversized started/finished fields cannot interrupt source audit creation or create synthetic fetch timing evidence.

Data trust audit entry duration fields reject out-of-range epoch timestamps before delta calculation, so platform-range-invalid started/finished fields cannot create synthetic fetch timing evidence.

Data trust audit entry fetched-at fields use shared text conversion before epoch fallback, so malformed boolean, binary, or memory-view fetched-at values cannot leak into source audit rows or suppress valid epoch timestamps.

Data trust audit entry fetched-at epoch fallback validates explicit epoch values before finished-at fallback, so malformed boolean or non-finite fetched-at epoch values cannot suppress valid finished timestamps.

Data trust audit entry fetched-at epoch fallback treats out-of-range epoch values as malformed before finished-at fallback, so platform timestamp range errors cannot interrupt source audit creation or suppress valid finished timestamps.

Data trust audit entry finished-at current-time fallback validates epoch values before source audit output, so malformed boolean, non-positive, or non-finite finished timestamps cannot erase source audit fetched-at evidence.

Data trust audit entry record counts use integer-safe conversion, so malformed numeric truthiness cannot erase valid source evidence counts.

Data trust audit entry record counts treat boolean values as malformed counts, so true or false source audit fields cannot inflate source evidence counts.

Data trust audit entry record counts treat fractional numeric values as malformed counts, so non-integer source audit fields cannot be truncated into valid source evidence counts.

Data trust audit entry boolean fields use bool-safe conversion, so malformed cache-hit or stale truthiness cannot interrupt source audit evidence creation.

Data trust audit entry boolean fields treat lookup truthiness failures as false, so `KeyError` or `IndexError` from malformed cache-hit or stale adapters cannot interrupt source audit evidence creation.

Data trust audit entry boolean text fields parse explicit false strings before truthiness fallback, so "false", "0", "no", or "off" cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean binary fields are treated as malformed before truthiness fallback, so byte, bytearray, or memory-view cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean non-finite numeric fields are treated as malformed before truthiness fallback, so NaN or Infinity cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean numeric fields only accept explicit zero or one values before truthiness fallback, so fractional or out-of-range cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean real-number fields apply the same explicit zero or one contract to rational numeric values before truthiness fallback, so Fraction-style cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean overflowing real-number fields are treated as malformed before truthiness fallback, so oversized integer or rational cache-hit and stale values cannot interrupt source audit evidence creation.

Data trust audit entry boolean numeric text fields apply the same finite zero or one contract before truthiness fallback, so numeric-string cache-hit and stale values like "2", "0.5", "NaN", or "Infinity" cannot be misreported as true source audit evidence.

Data trust audit entry boolean free-form text fields are treated as malformed after explicit true, false, and numeric parsing, so unsupported cache-hit and stale labels like "cached", "stale", or "unknown" cannot be misreported as true source audit evidence.

Data trust audit entry boolean complex fields are treated as malformed before truthiness fallback, so complex cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean container fields are treated as malformed before truthiness fallback, so list, tuple, set, or mapping cache-hit and stale values cannot be misreported as true source audit evidence.

Prompt source audit summary fields use string-, integer-, and bool-safe conversion, so malformed audit provider, status, count, cache, stale, or message fields cannot interrupt prompt JSON generation.

Prompt source audit summary text fields use shared text conversion before prompt output, so malformed source, provider, status, or message fields cannot leak boolean, binary, or memory-view text into prompt JSON.

Prompt source audit root source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid source audit summary provider, status, count, cache, stale, mismatch, or message evidence.

Prompt source audit entry fields use dict-native field reads before prompt output, so malformed source audit entry accessors cannot interrupt prompt JSON generation or erase valid source audit provider, status, record count, merged count, mismatch, cache, stale, or message evidence.

Prompt data trust list fields use truthiness- and iterator-safe conversion before prompt output, so malformed data trust critical failures, stale sources, notes, or reason codes cannot interrupt prompt JSON generation and valid trust evidence parsed before iterator failure remains visible.

Prompt data trust source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid data trust evidence.

Prompt data trust fields use dict-native field reads before prompt output, so malformed data trust field accessors cannot interrupt prompt JSON generation or erase valid data trust evidence.

Prompt company identity mapping uses truthiness-safe handoff before prompt output, so malformed identity mapping truthiness cannot interrupt prompt JSON generation or erase valid stock identity and alias constraints.

Prompt company identity fields use dict-native field reads before prompt output, so malformed company identity field accessors cannot erase valid stock identity and alias constraints.

Prompt company identity source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid company identity evidence.

Prompt company metadata source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid schema version, sector, industry, country, employee count, fetch date, or deterministic financial sector context evidence.

Agent runtime identity guard uses truthiness-safe company identity handoff before prompt assembly, so malformed identity mapping truthiness cannot interrupt agent prompt construction or erase the hard identity lock.

Agent runtime identity guard mapping length checks tolerate malformed length access before prompt assembly, so valid company identity evidence remains available even when mapping length cannot be computed.

Agent runtime identity guard mapping access uses dict-native field reads before prompt assembly, so malformed mapping accessor methods cannot interrupt agent prompt construction or erase valid company identity evidence.

Agent runtime identity guard ticker fields use string-safe conversion before prompt assembly, so malformed ticker or stock-id string conversion cannot interrupt agent prompt construction and falls back to the best available identity ticker.

Agent runtime identity guard text fields use string-safe conversion before prompt assembly, so malformed official or legal name truthiness cannot interrupt agent prompt construction or erase valid hard identity evidence.

Agent runtime identity guard alias lists use iterator-safe string conversion before prompt assembly, so malformed English-name or forbidden-alias iterators cannot interrupt agent prompt construction and valid aliases parsed before iterator failure remain visible.

Agent runtime identity guard alias native lists preserve limits before prompt assembly, so malformed list iterator accessors cannot turn bounded English-name aliases into noisy repr strings or leak aliases beyond the configured cap.

Agent runtime identity guard templates use string-safe formatting before prompt assembly, so malformed runtime identity rule templates cannot interrupt hard identity lock construction and valid company identity guidance remains visible.

Agent runtime identity guard runtime rules use dict-native field reads before prompt assembly, so malformed identity guard rule config accessors cannot erase valid company identity constraints.

Agent runtime identity guard values use dict-native field reads before prompt assembly, so malformed identity guard value accessors cannot erase valid legal name, English-name, or forbidden-alias constraints.

Agent runtime identity guard source data uses dict-native field reads before prompt assembly, so malformed source data accessors cannot interrupt hard identity lock construction or erase valid company identity evidence.

Agent runtime RAG context mapping uses truthiness-safe handoff before prompt assembly, so malformed RAG context mapping truthiness cannot interrupt agent prompt construction or erase valid retrieved context for the target agent.

Agent runtime RAG context text uses string-safe conversion before compact prompt truncation, so malformed retrieved-context length or slice behavior cannot interrupt agent prompt construction and valid retrieved context remains visible.

Agent runtime temporal memory reflection prompt uses string-safe conversion before prompt assembly, so malformed reflection prompt truthiness cannot interrupt agent prompt construction and valid reflection evidence remains visible.

Agent runtime temporal memory backtests use iterator- and JSON-safe conversion before prompt assembly, so malformed backtest slices cannot interrupt agent prompt construction and valid backtests parsed before iterator failure remain visible.

Agent runtime prompt safety helpers are split from prompt assembly, so string, bool, iterator, and JSON coercion guards stay reusable without pushing agent prompt construction past backend module size limits.

Agent runtime top-level rule sections use dict-native field reads before prompt assembly, so malformed runtime rules mapping accessors cannot erase valid section configs.

Agent runtime prompt JSON dict items use dict-native field reads before prompt assembly, so malformed mapping item accessors cannot erase valid JSON-safe prompt evidence.

Agent runtime prompt JSON sequence items use native iterators before prompt assembly, so malformed list or tuple iterator accessors cannot erase valid JSON-safe prompt evidence.

Agent runtime prompt JSON collection items use native iterators before prompt assembly, so malformed set or frozenset iterator accessors cannot erase valid JSON-safe prompt evidence.

Agent runtime structured instructions mappings use dict-native traversal before prompt assembly, so malformed structured-agent rule mapping truthiness or item accessors cannot erase valid structured output constraints.

Agent runtime rule section mappings use dict-native lookup before prompt assembly, so malformed runtime rule section truthiness or lookup accessors cannot erase valid agent-specific guidance.

Agent runtime rule block configs use dict-native field reads before prompt assembly, so malformed rule block config truthiness or field accessors cannot erase valid title, intro, schema, or rule guidance.

Agent runtime rule list mappings use dict-native field reads before prompt assembly, so malformed nested rule-list mapping accessors cannot erase valid runtime rule guidance.

Agent runtime state view uses JSON-safe conversion before prompt assembly, so non-serializable AgentState view leaves cannot interrupt agent prompt construction and valid state evidence remains visible.

Agent runtime forensic warning uses string-safe conversion before prompt assembly, so malformed V2 forensic-warning truthiness cannot interrupt agent prompt construction and valid warning evidence remains visible.

Agent runtime retry and audit instruction fields use string-safe conversion before prompt part filtering, so malformed retry or audit instruction truthiness cannot interrupt agent prompt construction and valid runtime guidance remains visible.

Agent runtime final audit mappings use dict-native field reads before preflight rule assembly, so malformed final-audit config, per-agent, or per-pipeline mapping accessors cannot erase valid audit guidance.

Agent runtime final audit pipeline id uses string-safe conversion before preflight rule selection, so malformed pipeline-id truthiness cannot interrupt agent prompt construction and valid mode-specific audit rules remain visible.

Agent runtime final audit rule lists use string-safe conversion before preflight rule assembly, so malformed rule text cannot interrupt agent prompt construction and valid final-audit rules parsed before or after the bad entry remain visible.

Agent runtime prompt rule blocks use string-safe conversion before prompt assembly, so malformed runtime rule titles, intros, schema lines, or rule items cannot interrupt agent prompt construction and valid runtime guidance remains visible.

Agent runtime output cleanliness mappings use dict-native field reads before prompt assembly, so malformed formal-output config accessors cannot erase valid report output contracts.

Agent runtime output cleanliness rules use string-safe conversion before prompt assembly, so malformed formal-output rule text cannot interrupt agent prompt construction and valid report output contracts remain visible.

Agent runtime assistant task prompt mappings use dict-native field reads before background task prompt assembly, so malformed task prompt group or task config accessors cannot erase valid tear sheet, context digest, or repair reflection guidance.

Agent runtime assistant task prompts use string-safe conversion before background task prompt assembly, so malformed task system instructions or instruction lines cannot interrupt tear sheet, context digest, or repair reflection task construction and valid task guidance remains visible.

Agent runtime primary probe flag uses bool-safe conversion before prompt assembly, so malformed compact prompt flag truthiness cannot interrupt agent prompt construction and falls back to the full prompt context.

Prompt freshness mappings use truthiness-safe handoff before prompt output, so malformed data_freshness or source_freshness mapping truthiness cannot interrupt prompt JSON generation or erase valid source recency evidence.

Prompt freshness source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid data_freshness or source_freshness recency evidence.

Prompt market data source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid current price, market cap, and 52-week range evidence.

Prompt valuation metrics source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid valuation multiples, share count, EPS, dividend yield, dividend per share, payout ratio, or deterministic DDM evidence.

Prompt TTM financials source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid trailing revenue, net income, EBITDA, margin, or forward EPS implied revenue evidence.

Prompt cash flow source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid free cash flow, operating cash flow, or deterministic DCF base FCF evidence.

Prompt balance sheet source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid debt, cash, net debt, liquidity, leverage, WACC, or deterministic DCF net debt evidence.

Prompt growth source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid annual, TTM, Yahoo, or 5-year CAGR growth evidence.

Prompt financial history source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid history rows, deterministic revenue CAGR, latest annual revenue growth, or FCF conversion evidence.

Prompt institutional trading mapping uses truthiness-safe handoff before prompt output, so malformed institutional trading mapping truthiness cannot interrupt prompt JSON generation or erase valid chip-flow evidence.

Prompt institutional trading source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid institutional trading chip-flow evidence.

Prompt full market catalyst items use truthiness- and iterator-safe conversion before prompt output, so malformed catalyst lists cannot interrupt default prompt JSON generation and valid news items parsed before iterator failure remain visible.

Prompt market catalyst source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid recent catalyst and news evidence.

Prompt peer context source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid dynamic peer metrics and peer discovery evidence.

Prompt full dynamic peer metrics use truthiness- and iterator-safe conversion before prompt output, so malformed peer metric lists cannot interrupt default prompt JSON generation and valid peer rows parsed before iterator failure remain visible.

Prompt full peer discovery results use truthiness- and iterator-safe conversion before prompt output, so malformed peer discovery lists cannot interrupt default prompt JSON generation and valid discovered peer rows parsed before iterator failure remain visible.

Prompt supplemental source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid data quality notes and monthly revenue evidence.

Prompt full recent monthly revenue text uses truthiness- and iterator-safe conversion before prompt output, so malformed monthly revenue lists cannot interrupt default prompt JSON generation and valid monthly revenue rows parsed before iterator failure remain visible.

Prompt full data quality notes use truthiness- and iterator-safe conversion before prompt output, so malformed data source note lists cannot interrupt default prompt JSON generation and valid notes parsed before iterator failure remain visible.

Prompt PE river chart source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid full or compact PE river chart evidence.

Prompt full PE river chart mapping uses truthiness-safe handoff before prompt output, so malformed valuation chart mapping truthiness cannot interrupt default prompt JSON generation or erase valid local valuation context.

Prompt compact list fields use truthiness- and iterator-safe conversion before compact prompt output, so malformed compact source lists cannot interrupt prompt JSON generation and valid items parsed before iterator failure remain visible.

Prompt compact PE river chart mapping uses truthiness-safe handoff before compact prompt output, so malformed valuation chart mapping truthiness cannot interrupt prompt JSON generation or erase valid local valuation context.

Prompt compact PE river chart fields use dict-native field reads before compact prompt output, so malformed valuation chart field accessors cannot interrupt prompt JSON generation or erase valid PE river chart source, years, multiples, or band labels.

Prompt compact PE river years use truthiness- and iterator-safe tail conversion before compact prompt output, so malformed valuation year lists cannot interrupt prompt JSON generation and valid trailing years parsed before iterator failure remain visible.

Prompt cross-check source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid DuPont identity fallback and WACC capital structure notes.

Prompt history rows use truthiness- and iterator-safe year conversion before prompt output, so malformed history year lists cannot interrupt prompt JSON generation and valid year rows parsed before iterator failure remain visible.

Prompt history value fields use truthiness- and iterator-safe sequence conversion before prompt output, so malformed revenue, net income, and FCF history lists cannot interrupt prompt JSON generation or deterministic financial tool context, and valid values parsed before iterator failure remain visible.

Prompt history source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid financial history rows.

Prompt agent context fields use truthiness-safe presence checks before prompt output, so malformed routed context truthiness cannot interrupt prompt JSON generation or erase valid agent context sections.

Prompt agent context source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt agent context routing or erase valid routed macro, chip, alternative, sentiment, filing, open-data, or earnings-call sections.

Prompt data trust payload accepts mapping-safe trust maps before prompt output, so immutable or read-only `data_trust` wrappers cannot be mistaken for missing report confidence metadata in model instructions.

Data trust string list conversion uses string-safe conversion, so malformed text truthiness cannot interrupt reason-code or score-reason normalization.

Data trust string list conversion uses native list and tuple iterator fallback, so malformed custom iterators cannot erase valid trust notes, reason codes, stale sources, critical failures, or score reasons.

Data trust string list conversion drops non-finite numeric items, so NaN or Infinity values cannot leak into trust notes, reason codes, stale sources, critical failures, or score reasons.

Data trust score normalization uses float-safe conversion, so malformed existing trust score conversion cannot interrupt snapshot generation and falls back to status-derived scoring.

Data trust score normalization treats lookup conversion failures as malformed scores, so `KeyError` or `IndexError` from existing trust score adapters cannot interrupt snapshot generation and falls back to status-derived scoring.

Data trust score normalization treats boolean score values as malformed, so true or false cannot become synthetic 1 or 0 trust scores in report confidence metadata.

Data trust normalization accepts mapping-safe trust payloads before field normalization, so immutable or read-only mapping wrappers cannot be mistaken for missing report confidence metadata.

Data trust normalization uses dict-native trust field reads, so malformed existing trust mapping accessors cannot interrupt score, freshness, reason, note, or provider SLA metadata normalization.

Data trust normalization market timestamp fields use shared text conversion, so malformed boolean, binary, or memory-view last-market-data values cannot leak into report confidence metadata.

Data trust build source payloads accept mapping-safe inputs before scoring, so immutable or read-only source data wrappers cannot be mistaken for missing report confidence evidence.

Data trust build source data uses mapping- and dict-list-safe conversion before scoring, so malformed root payload accessors or tuple/native-backed source audit collections cannot interrupt report confidence scoring or erase valid source audit evidence.

Data trust build source freshness child maps use mapping-safe conversion before scoring, so malformed nested freshness accessors cannot interrupt stale-source scoring or erase valid market-data freshness timestamps.

Data trust build source freshness stale flags use bool-safe conversion before scoring, so malformed stale truthiness cannot interrupt report confidence scoring or misclassify valid source audit evidence.

Data trust build data source notes use string-list conversion before scoring, so malformed note truthiness cannot interrupt report confidence scoring or create synthetic data-source limitation metadata.

Data trust latest audit rows use mapping-safe conversion before scoring, so malformed source audit row accessors cannot interrupt latest-source selection or erase valid source audit status evidence.

Data trust optional source status selection uses mapping-safe row conversion before scoring, so malformed optional audit row accessors cannot interrupt optional-source reason code projection or promote core sources into optional status buckets.

Data trust usable critical data checks use mapping-safe audit conversion before scoring, so malformed critical audit accessors cannot interrupt error-vs-partial trust status selection or erase valid core source availability evidence.

Data trust source audit status comparisons use string-safe conversion before scoring, so malformed but valid status text cannot be misclassified as fresh and hide core source failures from report confidence metadata.

Data trust last-market timestamp fallback uses string-safe conversion before scoring, so malformed timestamp truthiness cannot interrupt report confidence metadata or suppress valid market freshness time evidence.

Data trust post-SLA trust metadata uses mapping-safe conversion before final score calculation, so malformed provider-SLA return accessors cannot interrupt report confidence finalization or erase valid trust status and reason evidence.

Data trust snapshot existing trust selection uses dict-safe conversion, so malformed `data_trust` truthiness cannot interrupt snapshot generation or erase valid trust metadata.

Data trust snapshot existing trust selection accepts mapping-safe payloads, so immutable or read-only `data_trust` wrappers cannot be mistaken for missing report confidence metadata.

Data trust snapshot root context accepts mapping-safe payloads before metadata selection, so immutable or read-only context wrappers cannot interrupt snapshot generation or erase report confidence evidence.

Data trust snapshot source data accepts mapping-safe payloads before trust scoring, so immutable or read-only `data` wrappers cannot erase valid source audit evidence during snapshot generation.

Data trust snapshot refresh flags use bool-safe conversion, so malformed refresh metadata truthiness cannot interrupt snapshot generation.

Data trust snapshot refresh flags treat lookup truthiness failures as false, so `KeyError` or `IndexError` from malformed refresh metadata cannot interrupt snapshot generation.

Data trust snapshot rerun context text uses string-safe conversion, so malformed analysis text truthiness cannot interrupt snapshot generation or rerun context preservation.

Data trust snapshot sanitizer uses string-safe key and value conversion, so malformed snapshot object string conversion cannot interrupt snapshot generation or leak empty keys.

Data trust snapshot sanitizer uses native list and tuple iterators when iterator accessors fail, so malformed snapshot sequence subclasses cannot interrupt snapshot generation or erase underlying list or tuple evidence.

Data trust snapshot sanitizer falls back to native list and tuple iterators when custom sequence iterators fail before yielding, so malformed snapshot iterator objects cannot erase underlying list or tuple evidence.

Data trust snapshot sanitizer uses native dict items when items accessors fail, so malformed snapshot mapping subclasses cannot interrupt snapshot generation or erase underlying mapping evidence.

Data trust snapshot sanitizer falls back to native dict items when custom items iterables fail, so malformed snapshot mapping item views cannot erase underlying mapping evidence.

Data trust snapshot integrity hash lookup uses string-safe conversion, so malformed hash metadata truthiness cannot interrupt snapshot verification.

Snapshot maintenance verify-snapshots uses verifier-derived hash presence, so falsey hash metadata is repaired or reported as mismatch instead of being backfilled as missing.

Data trust snapshot integrity and schema validators use dict-native snapshot field reads, so malformed snapshot accessors cannot interrupt hash or schema verification.

Data trust snapshot integrity and schema validators fall back to item lookup when mapping field accessors fail, so read-only snapshot wrappers with malformed `.get()` or containment accessors still preserve valid hash and required-field evidence.

Data trust snapshot rerun context agent keys use string-safe conversion, so malformed analysis key conversion cannot interrupt snapshot generation or leak malformed rerun context keys.

Data trust snapshot content hash keys use string-safe conversion, so malformed snapshot object keys cannot interrupt integrity verification or leak non-JSON-safe hash inputs.

Data trust snapshot content hashing uses iterator-safe mapping traversal, so malformed snapshot items accessors cannot interrupt integrity generation or verification.

Data trust snapshot content hash accepts mapping snapshot wrappers before integrity verification, so immutable snapshot containers do not lose valid hash evidence.

Data trust snapshot size governance uses snapshot sanitizer input, so malformed snapshot object keys cannot interrupt size governance or leak non-JSON-safe snapshot inputs.

Data trust snapshot size byte calculation uses snapshot sanitizer input, so malformed snapshot object keys cannot interrupt size measurement or leak non-JSON-safe snapshot inputs.

Data trust snapshot builds use dict-native context and data field reads, so malformed mapping accessors cannot interrupt snapshot generation or erase identity, freshness, quality, or rerun metadata.

Data trust snapshot identity fields use string-safe context/data selection, so malformed ticker, company name, or pipeline truthiness cannot interrupt snapshot generation or reproducibility packet identity.

Data trust snapshot identity fields use shared text conversion before artifact output, so malformed ticker, company name, or pipeline values cannot leak boolean, binary, or memory-view text into `.data.json` snapshots and valid data fallback identity remains available.

Data trust reproducibility source audit metadata uses string-safe provider and timestamp extraction, so malformed source audit provider or fetched-at truthiness cannot interrupt snapshot generation or erase valid traceability fields.

Data trust reproducibility source audit metadata uses dict-list safe conversion before provider and timestamp extraction, so malformed source audit iterator lookup failures cannot interrupt snapshot generation or erase valid traceability rows.

Data trust reproducibility source audit helpers accept mapping-safe data wrappers before provider and timestamp extraction, so read-only data payloads cannot erase valid provider or source-time traceability rows.

Data trust reproducibility packets use dict-native context, data, source audit, and metadata field reads, so malformed mapping accessors cannot interrupt provenance generation or erase traceability fields.

Data trust reproducibility packets accept mapping-safe context, data, source audit, and metadata wrappers, so read-only provenance payloads cannot erase ticker, pipeline, model, code, provider, or source-time traceability fields.

Data trust reproducibility packets preserve validated full prompt fingerprints, so report audit can distinguish exact prompt content without exposing arbitrary prompt-like values.

Prompt fingerprints cover agent templates, state-view policy, system prompts, and runtime prompt rules, so report identity follows the effective prompt bundle rather than only `agents.json`.

Prompt identity and prompt injection share one process-stable runtime-rule snapshot, so a report fingerprint cannot drift from the rules injected into the same workflow.

Runtime code provenance records commit and dirty state once per workflow, so uncommitted code cannot be mistaken for a report reproducible from the commit alone. `code_dirty = true` means local changes were present, `false` means the worktree was clean at initialization, and `null` means the state was unknown.

Data trust explicit target price detection uses dict-native root field reads, so malformed parsed or structured output context accessors cannot interrupt target-price guardrail generation or erase underlying evidence.

Data trust explicit target price detection accepts mapping-safe root and nested maps, so read-only parsed or structured output wrappers cannot hide explicit target-price guardrail evidence.

Data trust explicit target price detection uses string-safe key and value conversion, so malformed parsed or structured output target fields cannot interrupt snapshot guardrail generation or erase valid detected target fields.

Data trust explicit target price detection preserves valid list items before iterator failures, so malformed parsed or structured output collections cannot erase already detected target fields.

Data trust explicit target price detection accepts tuple sequences before guardrail output, so immutable parsed or structured output row collections cannot hide target-price evidence.

Data trust explicit target price detection uses native list iterators when iterator accessors fail, so malformed parsed or structured output list subclasses cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native list iterators when custom iterators fail before yielding, so malformed parsed or structured output list iterator objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection treats lookup list iterator failures as native list fallbacks, so `KeyError` or `IndexError` from malformed parsed or structured output list wrappers cannot erase target-price guardrail evidence.

Data trust explicit target price detection preserves valid mapping items before iterator failures, so malformed parsed or structured output objects cannot erase already detected target fields.

Data trust explicit target price detection uses native dict items when items accessors fail, so malformed parsed or structured output mapping subclasses cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native dict items when custom items iterables fail to create iterators, so malformed parsed or structured output mapping items iterable objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native dict items when custom items iterators fail before yielding, so malformed parsed or structured output mapping iterator objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection treats lookup mapping item failures as native dict item fallbacks, so `KeyError` or `IndexError` from malformed parsed or structured output mapping accessors or iterators cannot erase target-price guardrail evidence.

Data trust explicit target price detection ignores non-finite numeric targets, so NaN or Infinity parsed outputs cannot create false explicit target-price evidence.

Data trust source record counting uses string-safe source keys, so malformed source truthiness cannot interrupt merged evidence counts for audit summaries.

Data trust source record counting normalizes root data maps before field reads, so malformed data snapshot accessors cannot interrupt merged evidence counts when valid source values exist.

Data trust source record counting normalizes institutional trading maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid trading rows exist.

Data trust source record counting ignores empty institutional trading daily-only payloads before fallback counting, so blank chip-flow shells cannot inflate merged evidence counts.

Data trust source record counting normalizes global market context maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid market-context rows exist.

Data trust source record counting normalizes international news context maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid news-topic rows exist.

Data trust source record counting normalizes P/E river chart maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid valuation rows exist.

Data trust source record counting normalizes P/E river chart band maps before counting valuation rows, so immutable band payloads keep accurate merged evidence counts.

Data trust source record counting falls back from empty P/E river chart band series to year or EPS rows, so sparse valuation payloads do not lose remaining source evidence.

Data trust source record counting normalizes default source mapping values before counting keys, so malformed mapping length accessors cannot interrupt merged evidence counts for custom source payloads.

Data trust source record counting counts only default source mapping keys with present child values, so custom mapping payloads made only of missing values cannot inflate merged evidence counts.

Data trust source record counting uses sequence-safe tuple value presence checks, so empty tuple history or enrichment payloads cannot be counted as valid source evidence.

Data trust source record counting uses item-aware sequence value presence checks, so non-empty history or enrichment sequences made only of missing values cannot inflate merged evidence counts.

Data trust source record counting uses mapping-safe value presence checks, so empty immutable mapping history or enrichment payloads cannot be counted as valid source evidence.

Data trust source record counting uses child-aware mapping value presence checks, so mapping history or enrichment payloads made only of missing child values cannot inflate merged evidence counts.

Data trust source record counting uses set-aware value presence checks, so empty set or frozenset history payloads cannot inflate merged evidence counts.

Data trust source record counting treats boolean scalar values as missing evidence, so malformed numeric or source fields such as true or false cannot inflate merged evidence counts.

Data trust source record counting treats non-finite numeric scalar values as missing evidence, so NaN or Infinity market fields cannot inflate merged evidence counts.

Data trust source record counting treats overflowing numeric scalar values as missing evidence, so oversized integer or rational market fields cannot interrupt merged evidence counts or inflate source evidence.

Data trust source record counting treats non-finite numeric string values as missing evidence while preserving finite numeric strings, so string NaN or Infinity market fields cannot inflate merged evidence counts.

Data trust source record counting treats placeholder string values as missing evidence while preserving finite numeric strings, so string None, null, or -- market fields cannot inflate merged evidence counts.

Data trust source record counting treats non-finite Decimal scalar values as missing evidence while preserving finite Decimal values, so decimal NaN or Infinity market fields cannot inflate merged evidence counts.

Data trust source record counting treats binary scalar values as missing evidence, so bytes, bytearray, or memory-view market fields cannot inflate merged evidence counts.

Data trust source record counting treats complex scalar values as missing evidence, so complex-number market fields cannot inflate merged evidence counts.

Data trust source record counting uses native list and tuple iterator fallback, so malformed history or enrichment row iterators cannot interrupt merged evidence counts or erase valid source-audit record counts.

Data trust source record counting treats tuple source values as row batches, so immutable custom enrichment rows keep accurate merged evidence counts instead of collapsing to one present scalar.

Data trust source record counting treats set and frozenset source values as row batches, so unordered custom enrichment rows keep accurate merged evidence counts instead of collapsing to one present scalar.

Data trust source record counting uses native set and frozenset iterator fallback, so malformed set row iterators cannot interrupt merged evidence counts or erase valid custom source rows.

Data trust source record counting treats lookup set iterator failures as native set and frozenset fallbacks, so `KeyError` or `IndexError` from malformed custom enrichment set wrappers cannot erase valid source evidence.

Data trust source record counting uses truthiness-safe value presence checks, so malformed list or mapping truthiness cannot interrupt merged evidence counts or hide valid market, financial, or enrichment evidence.

Provider SLA window selection uses string-safe conversion, so malformed selected-window truthiness or string conversion cannot interrupt provider SLA payload generation.

Provider SLA window maps use dict-safe conversion, so malformed provider `windows` or selected-window stats map truthiness cannot interrupt dashboard alert recalculation.

Provider SLA nested window numeric fields use integer- and finite-float-safe conversion, so malformed `windows.*` attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA numeric field shaping uses dict-safe row conversion before provider and window output, so malformed direct-helper row mappings cannot interrupt numeric shaping or leak unnormalized attempts, counts, success rate, duration, and total-record evidence.

Provider SLA numeric field shaping uses strict numeric conversion before provider and window output, so boolean, binary, or memory-view attempts, counts, success rate, duration, and total-record payloads render as zero instead of decoded SLA evidence.

Provider SLA nested window maps keep only canonical `last_1h`, `last_24h`, and `last_7d` buckets before payload output, so experimental or malformed window keys cannot leak into API/UI contracts.

Provider SLA nested window keys use shared text conversion before canonical bucket matching, so binary or memory-view keys cannot be decoded into accepted `last_1h`, `last_24h`, or `last_7d` windows.

Provider SLA selected-window helper output normalizes nested `windows` maps before returning provider rows, so direct helper callers cannot bypass nested window numeric shaping.

Provider SLA selected-window numeric fields use integer- and finite-float-safe conversion, so malformed attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA provider rows use dict-safe conversion before window selection, so malformed provider row mapping conversion cannot interrupt dashboard alert recalculation.

Provider SLA alert projection uses dict-safe row conversion and string-safe alert-level conversion, so malformed alert row mapping or alert level hashing cannot interrupt dashboard alert lists.

Provider SLA alert projection output fields use string-, finite-float-, and dict-safe conversion, so malformed alert source, provider, message, status, basis, selected window, success rate, or windows maps cannot leak non-JSON-safe values.

Provider SLA alert projection text fields use shared text conversion before dashboard alert output, so boolean, binary, or memory-view source, provider, message, status, basis, or selected-window values cannot leak into provider alert payloads.

Provider SLA all-window cumulative alerts reuse the same safe alert projection, so malformed cumulative alert rows cannot bypass the dashboard alert-list guard.

Provider SLA all-window provider summaries use dict-safe row conversion before returning dashboard payloads, so malformed cumulative provider rows cannot bypass the provider-list guard.

Provider SLA all-window provider numeric fields use integer- and finite-float-safe conversion, so malformed cumulative attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA payload summary fetch failures fall back to empty provider lists, so provider SLA storage or aggregation errors cannot interrupt selected-window dashboard payloads.

Provider SLA payload alert fetch failures fall back to empty alert lists, so cumulative alert storage or aggregation errors cannot suppress otherwise available provider summary rows.

Prometheus provider alert level rendering uses string-safe conversion, so malformed alert level truthiness cannot interrupt alert gauges.

Notification delivery failure reason bucketing uses shared text conversion, so malformed `last_error` truthiness cannot interrupt low-cardinality delivery health summaries and binary or memory-view errors fall back to `unknown`.

Notification delivery summary channel counts use string-safe channel conversion, so malformed `channel_id` truthiness cannot interrupt delivery health channel distribution.

Notification delivery summary status counts use string-safe status conversion, so malformed `delivery_status` equality cannot interrupt delivery health status distribution.

Notification delivery reconcile preflight uses string-safe delivery key lookup, so malformed outbox delivery key truthiness cannot interrupt audit reuse or already-sent suppression when the key is stringable.

Notification delivery reconcile preflight treats missing outbox entries as an empty list, so optional sender payloads without delivery work return an empty preflight result instead of raising before audit lookup.

Notification delivery reconcile preflight evaluates tuple outbox entry batches before audit lookup, so immutable sender payloads do not lose pending delivery work.

Notification delivery reconcile preflight evaluates mapping outbox entries before audit lookup, so immutable entry payloads do not lose pending delivery work.

Notification delivery reconcile preflight skips malformed mapping outbox entries before audit lookup, so one broken immutable entry does not erase adjacent pending delivery work.

Notification delivery reconcile attempt counts use string-safe integer conversion, so malformed audit attempt metadata cannot interrupt retry budget or next-attempt calculation.

Notification delivery reconcile retry budgets treat `None` max attempts as the default retry budget, so optional caller configuration does not exhaust failed delivery after the first attempt.

Notification delivery reconcile retry timestamps use string-safe float conversion, so malformed audit last-attempt metadata cannot interrupt retry wait calculation.

Notification delivery reconcile retry backoff treats `None` as the default backoff window, so optional caller configuration does not bypass retry waiting and immediately resend failed delivery.

Notification delivery reconcile statuses use string-safe text conversion, so malformed audit status truthiness cannot interrupt already-sent, retry-exhausted, or retry-wait decisions.

Notification delivery reconcile text metadata uses string-safe conversion, so malformed audit `last_error` or `last_response_id` truthiness cannot interrupt sender preflight result assembly.

Notification delivery response ids are stripped before record and sender preflight output, so repaired or sender-returned response ids with tab, newline, or space padding do not leak padded identifiers into list, API, or sender preflight payloads.

Notification delivery reconcile audit context uses dict-safe conversion, so malformed persisted audit context truthiness cannot interrupt sender preflight context recovery.

Notification delivery audit context maps use JSON-safe dict conversion before reconcile and summary output, so direct or mocked audit context maps with NaN or Infinity values cannot leak non-standard numbers into sender preflight, ops, or daily queue summaries.

Notification delivery audit context preserves mapping metadata values before JSON serialization, so immutable nested context remains structured instead of becoming stringified text.

Notification delivery audit context drops whitespace-only metadata before JSON serialization, so optional ticker, report, CTA, nested, or sequence context fields that contain only formatting whitespace do not become persisted audit history.

Notification delivery audit context drops empty collection metadata after normalization, so optional list or object context fields whose children were all removed do not remain as empty `[]` or `{}` audit history.

Notification delivery audit context partial sequence metadata is normalized before empty collection filtering, so list wrappers that yield valid metadata before stopping are not discarded just because their native backing list is empty.

Notification delivery audit context JSON parsing uses string-safe conversion before loading persisted context, so repaired or mocked context payloads that are stringable JSON still recover source, ticker, report, and CTA context instead of becoming empty audit context.

每日決策儀表板整合近期報告、watchlist、auto-screener、決策回測與免費模式狀態：

```bash
curl http://127.0.0.1:8080/api/watchlist/daily-dashboard
```

The daily dashboard keeps `summary.reports_needing_rerun` and `summary.report_repairs_required` backward-compatible, but those two report counts describe the recent dashboard report sample rather than the full indexed universe. `summary.report_scope` makes that boundary explicit with `scope=daily_report_sample`, `label=近期報告取樣`, and `sampled_reports`; use `report_quality_audit` for the full latest-per-ticker/pipeline quality coverage.

`repair_queue.summary.action_required` is the full actionable count for the sampled reports, while `items_returned` is the number of repair targets included in the bounded `items[]` list. Read `items_limit` and `items_truncated` with those fields before claiming the repair queue has been fully displayed. The operator dashboard and watchlist daily board use the shared scope formatter and show `修復 queue：顯示 N / 共 M` only when all four bounded fields are present and mutually consistent; legacy or contradictory metadata keeps the existing summary wording instead of guessing a scope.

When the daily queue has no work, `decision_queue.items` may contain a UI-compatible `monitor` fallback, but `decision_queue.summary.displayed_count` and `secondary_count` remain `0`; those counts include only real actionable items.

`decision_queue.summary.secondary_count` is the canonical secondary-work count, calculated from the same actionable list and displayed slice as `total_actionable` and `displayed_count`. The top-level `decision_queue.secondary_count` remains as a backward-compatible alias; notification and UI consumers prefer the summary field and fall back to the alias for legacy payloads. Both fields exclude the `monitor` fallback.

`decision_queue.items` keeps the existing priority and source ordering, then applies deterministic identity tie-breakers (`type`, ticker, filename/report filename or route, pipeline, horizon, and warning id). This means equal-priority reports or route warnings do not change rank just because upstream collection order changed. `filename` and `report_filename` are aliases for one report artifact; notification messages and `delivery_outbox` resolve conflicting aliases to the selected canonical filename before exposing either field.

The daily dashboard also returns `notification_plan`. Local UI notifications are always free; SMTP, Telegram, Discord, and Slack are enabled only when the operator supplies the corresponding environment variables/webhook URLs. `decision_queue.summary` exposes `source_labels` and `source_texts` beside raw `sources`, so API consumers can render readable source distribution while preserving raw source keys. Backend source label helpers trim raw source keys before lookup, preventing accidental surrounding whitespace from bypassing canonical labels. Backend source label helpers drop blank raw source keys before outputting display maps, so empty source distribution entries cannot leak into sender or API payloads as empty labels. Backend source display map helpers ignore non-mapping raw source distributions, so `source_labels` and `source_texts` cannot be generated from malformed list or tuple payloads. Backend source key helpers ignore non-string raw source keys before display maps, so numeric, boolean, or bytes payload keys cannot become synthetic source labels. Backend source count normalization ignores non-mapping raw source distributions, so malformed summary payloads do not interrupt source display generation. Backend source count normalization drops non-positive raw source counts before outputting source distribution maps, so zero, negative, or unparseable counts do not appear as active source rows. Backend source count normalization treats boolean and non-finite raw source counts as inactive, so `true`, `NaN`, or infinity cannot become source distribution rows. Backend source count normalization treats fractional raw source counts as inactive, so decimal counts are not silently truncated into active source rows. Backend source count normalization requires non-string numeric raw source counts to equal their integer value, so Decimal or Fraction payload values cannot be truncated into active source rows. Backend source display override helpers normalize active raw source keys before matching upstream overrides, so fallback and override maps use the same canonical source key set. Backend source display override helpers ignore non-mapping active source distributions, so malformed active source inputs cannot generate override maps. Backend source display helpers ignore mapping accessor failures, so broken `keys()` or `items()` accessors cannot interrupt source display generation. Backend source display helpers ignore malformed mapping items, so non-pair mapping entries cannot interrupt source count or override processing. Backend source display helpers ignore mapping item unpack failures, so one broken item entry cannot suppress later valid source rows. Backend source display helpers ignore malformed mapping keys, so string or bytes `keys()` payloads cannot be split into synthetic source labels. Backend source display override helpers ignore non-string override values before fallback labels, so numeric or boolean display overrides cannot replace canonical wording. Frontend source label helpers trim raw source keys before lookup too, so browser-only action details follow the same source display contract. `decision_queue.items` can include `fix_notification_delivery` when notification sender audit health is degraded; that item is an in-app/ops repair action with `suppress_notification = true`, carries low-cardinality `failure_reason_counts` for local triage, and stays out of `notification_plan.messages` and `delivery_outbox`. `notification_plan.messages` uses `decision_queue.items` as the primary source when that contract is present, trims raw action `source` keys before exposing message/outbox source context, drops blank action `source` keys before exposing sender payloads, preserves action metadata such as `route`, `warning_id`, `horizon_months`, `recommended_action`, `blocks_auto_rerun`, `severity`, and `action_label`, preserves action-provided `source_label` / `source_text` before fallback labels, trims source display override values before exposing queue/message/outbox payloads, ignores blank action-provided source display fields before fallback labels, adds `target_panel` / `target_tab` for operator workspace deep links, adds `operator_action` / `operator_action_label` for CTA rendering, adds `queue_rank` / `queue_displayed_count` / `is_top_priority` for displayed-order rendering, adds stable `dedupe_key` / `message_id` fields based on source, type, report, route, horizon, and pipeline identifiers while excluding title/detail/priority changes, adds `delivery_outbox` / `delivery_summary` records for enabled channel/message pairs with stable `delivery_key` and pending delivery status, and `notification_plan.queue_context` exposes the total actionable count, displayed count, secondary count, top priority score, and source distribution for downstream notification channels. When `decision_queue.summary.source_labels` or `source_texts` are present, `notification_plan.queue_context` preserves those upstream maps instead of rebuilding display text from raw source counts; when a partial map omits an active source key, the omitted key is filled from raw `sources` fallback while upstream overrides still win. Blank upstream source display overrides are ignored so fallback labels stay readable, overrides for keys absent from raw `sources` are dropped so display maps match the active source distribution, and raw source distribution keys are trimmed before exposing `sources`, `source_labels`, and `source_texts`. When a sender records a `delivery_outbox` attempt, `notification_delivery_audit` stores a context snapshot from the outbox entry so audit history can still expose source, ticker, report filename, target panel/tab, CTA, and queue rank after the original dashboard response has expired. Audit context snapshots ignore blank `source_label` / `source_text` before deriving fallback labels from raw `source`, preventing empty source wording from becoming persisted operational history. Frontend attention context summaries apply the same blank-display fallback before local source maps, so legacy or external blank snapshot values do not suppress readable source wording.

`decision_queue.items` report repair actions preserve `blocks_auto_rerun` and `reason_codes` from `report_quality_repair_queue`, so API consumers can distinguish a blocked manual review from a safe rerun/refresh action without re-reading the repair queue payload.

For `review_candidate` actions, the shared operator contract uses `operator_action=candidate-snapshot`, `operator_action_label=查看股票快照`, `target_panel=market-screener-panel`, and `target_tab=screener`; `notification_plan.messages` and `delivery_outbox` preserve these fields so candidate notifications do not fall back to the older generic `open-ops` / `查看候選` CTA.

`fix_notification_delivery` is a queue-only repair action with `operator_action=open-ops`, `operator_action_label=查看通知通道`, `target_panel=maintenance-panel`, and `target_tab=ops`; its `suppress_notification=true` policy keeps it out of `notification_plan.messages` and `delivery_outbox`, while the explicit target lets queue API consumers and the operator UI open the same maintenance surface.

Daily decision queue display limits use integer-safe conversion before slicing rendered items, so malformed limit truthiness cannot interrupt daily queue assembly or inflate secondary-count calculations.

Daily decision queue integer conversions ignore malformed conversion failures before priority, horizon, display, and summary calculations, so broken numeric payloads fall back instead of interrupting queue assembly.

Daily decision queue integer conversions treat boolean values as malformed before priority, horizon, display, and summary calculations, so boolean payload drift cannot become synthetic `1` or `0` queue values.

Daily decision queue integer conversions treat fractional float values as malformed before priority, horizon, display, and summary calculations, so decimal payload drift cannot be silently truncated into queue values.

Daily decision queue integer conversions treat fractional exact numeric values as malformed before priority, horizon, display, and summary calculations, so Decimal or Fraction payload drift cannot be silently truncated into queue values.

Shared integer conversion treats boolean values as malformed numeric input before queue, repair, audit, and observability count projection, so boolean payload drift cannot become synthetic `1` or `0` counts.

Shared integer conversion treats fractional float values as malformed numeric input before queue, repair, audit, and observability count projection, so decimal payload drift cannot be silently truncated into synthetic counts.

Shared integer conversion treats fractional exact numeric values as malformed numeric input before queue, repair, audit, and observability count projection, so Decimal or Fraction payload drift cannot be silently truncated into synthetic counts.

Shared text conversion treats boolean values as malformed text input before queue, repair, audit, and notification payload projection, so boolean payload drift cannot become visible `"True"` or `"False"` strings.

Shared text conversion treats binary values as malformed text input before queue, repair, audit, and notification payload projection, so bytes payload drift cannot become visible Python byte-literal strings.

Shared text conversion treats memory view values as malformed text input before queue, repair, audit, and notification payload projection, so buffer-view payload drift cannot become visible nondeterministic memory-address strings.

Report quality repair queue identity fields use shared text conversion before repair action projection, so malformed ticker, filename, report filename, or pipeline fields cannot bypass the shared boolean, binary, and memory-view text guards.

Provider impact identity fields use shared text conversion before provider recovery projection, so malformed ticker, filename, report filename, or pipeline fields cannot bypass the shared boolean, binary, and memory-view text guards.

Data trust scoring audit source names use shared text conversion before trust reason-code projection, so malformed source audit keys cannot become synthetic optional-source errors or leak boolean, binary, or memory-view text into report trust metadata.

Data trust provider SLA trust metadata uses shared text conversion before merging existing status, reason codes, and notes, so malformed boolean, binary, or memory-view values cannot leak into report trust metadata.

Daily decision queue notification delivery summary maps use mapping-safe conversion before repair action projection, so immutable sender audit summary payloads cannot hide a visible notification-channel repair action.

Daily decision queue notification delivery count fields use integer-safe conversion before repair action projection, so malformed sender audit counts cannot interrupt queue assembly or hide a visible notification-channel repair action.

Daily decision queue notification delivery count fields and count maps use strict count conversion before repair action projection, so boolean, binary, or memory-view failed, exhausted, channel, and reason counts cannot become synthetic delivery-failure evidence.

Daily decision queue notification delivery health fields use string-safe conversion before warning-state checks, so malformed sender audit health truthiness cannot interrupt queue assembly or hide a visible notification-channel repair action.

Daily decision queue notification delivery nested count maps use mapping-safe conversion before repair action projection, so immutable sender audit channel and failure-reason maps still preserve triage context.

Daily decision queue notification delivery channel count maps use dict-safe conversion before repair action projection, so malformed sender audit channel-count truthiness cannot interrupt queue assembly or erase visible channel distribution context.

Daily decision queue notification delivery failure reason maps use truthiness-safe detail rendering before repair action projection, so malformed sender audit failure-reason truthiness cannot interrupt queue assembly or erase timeout/auth triage context.

Daily decision queue notification delivery failure reason item access failures fall back to native dict items before repair action projection, so malformed sender audit reason-map accessors cannot interrupt queue assembly or erase valid timeout/auth reason summaries.

Daily decision queue notification delivery failure reason count values fall back to integer-safe rendering before repair action projection, so malformed count text cannot erase valid timeout/auth reason summaries when integer conversion still works.

Daily decision queue notification delivery failure reason unrenderable counts are omitted from reason detail before repair action projection, so malformed count values cannot create misleading `reason=... 0` summaries.

Daily decision queue notification delivery failure reason non-positive counts are omitted from reason detail before repair action projection, so zero or negative sender audit counts cannot appear as active timeout/auth reason summaries.

Daily decision queue notification delivery failure reason boolean counts are omitted from reason detail before repair action projection, so boolean sender audit flags cannot appear as numeric timeout/auth reason summaries.

Daily decision queue notification delivery failure reason fractional counts are omitted from reason detail before repair action projection, so decimal or fractional sender audit counts cannot be truncated into active timeout/auth reason summaries.

Daily decision queue notification delivery failure reason malformed keys are omitted from reason detail before repair action projection, so non-string or blank sender audit reason keys cannot appear as synthetic timeout/auth reason summaries.

Daily decision queue notification delivery failure reason raw keys are omitted from reason detail before repair action projection, so raw exception strings or non-canonical sender audit reason keys cannot bypass low-cardinality timeout/auth/network bucket rendering.

Daily decision queue notification delivery failure reason duplicate buckets are aggregated in reason detail before repair action projection, so casing or whitespace drift cannot duplicate timeout/auth/network summaries.

Daily decision queue notification delivery failure reason partial item failures fall back to native dict items before repair action projection, so sender audit dict subclasses that stop mid-iteration do not erase later valid timeout/auth/network reason summaries.

Daily decision queue notification delivery attention context iterator failures fall back to native sequence items before repair action projection, so malformed sender audit context list wrappers cannot interrupt queue assembly or erase valid affected ticker/report/CTA context.

Daily decision queue notification delivery attention context partial iterator failures fall back to native sequence items before repair action projection, so sender audit context list wrappers that stop mid-iteration do not erase later affected ticker/report/CTA context.

Daily decision queue notification delivery attention context tuple payloads are preserved before repair action projection, so immutable sender audit context batches still reach operator triage.

Daily decision queue notification delivery attention context mapping rows normalize to plain dicts before repair action projection, so immutable sender audit context rows and nested context maps remain JSON-friendly.

Daily decision queue notification delivery attention context dict subclasses normalize to plain dicts before repair action projection, so custom sender audit context wrappers do not leak into queue API payloads.

Daily decision queue notification delivery attention context nested mappings normalize recursively to plain dicts before repair action projection, so nested sender audit metadata remains JSON-friendly.

Daily decision queue notification delivery attention context nested mapping item failures fall back to native dict items before repair action projection, so malformed metadata wrappers cannot interrupt queue assembly or erase valid nested context.

Daily decision queue notification delivery attention context nested sequence iterator failures fall back to native sequence items before repair action projection, so malformed metadata list wrappers cannot erase valid nested triage tags or CTA evidence.

Shared sequence conversion treats lookup iterator failures as native-sequence fallbacks before queue, repair, refresh, and audit payload projection, so `KeyError` or `IndexError` from malformed list or tuple iterators cannot erase underlying sequence evidence.

Shared sequence conversion treats lookup iterator creation failures as native-sequence fallbacks before queue, repair, refresh, and audit payload projection, so `KeyError` or `IndexError` from malformed list or tuple `__iter__` access cannot erase underlying sequence evidence before iteration starts.

Daily decision queue report repair collections use iterator-safe dict-list conversion before repair action projection, so malformed repair collection truthiness cannot interrupt daily queue assembly or suppress later valid report repair rows.

Daily decision queue report repair partial iterator failures fall back to native dict-list items before repair action projection, so repair list wrappers that stop mid-iteration do not erase later valid report repair rows.

Daily decision queue report repair reason code partial iterator failures fall back to native text-list items before repair action projection, so reason-code list wrappers that stop mid-iteration do not erase later blocked-repair causes.

Shared mapping dict conversion normalizes dict subclasses to plain dict copies before queue, repair, and audit payload projection, so custom mapping wrappers do not leak into JSON-facing API responses while native dict fields remain readable.

Shared mapping dict conversion uses mapping-item traversal when mapping key iteration fails before queue, repair, and audit payload projection, so Mapping wrappers with readable `.items()` still preserve fields even when `keys()` or `__iter__()` are unavailable.

Shared mapping dict conversion uses Mapping traversal when `.items()` lookup fails before queue, repair, and audit payload projection, so Mapping wrappers with readable keys and item access still preserve fields when custom `.items()` accessors raise `KeyError` or `IndexError`.

Shared mapping dict conversion uses Mapping traversal when `.items()` iterables fail lookup before queue, repair, refresh, and audit payload projection, so Mapping wrappers with readable keys and item access still preserve fields when custom `.items()` iterable wrappers raise `KeyError` or `IndexError` during iterator creation.

Shared mapping dict conversion skips lookup item failures during Mapping traversal before queue, repair, and audit payload projection, so one broken key lookup cannot erase later valid fields from custom Mapping wrappers.

Shared mapping dict conversion skips lookup key hash failures during Mapping traversal before queue, repair, refresh, and audit payload projection, so one malformed mapping key cannot erase later valid fields after `.items()` fallback.

Shared mapping dict conversion preserves safely empty Mapping wrappers as plain empty dicts before queue, repair, and audit payload projection, so optional empty metadata stays distinct from malformed mapping access failures.

Shared mapping item conversion preserves partial dict-subclass items when native fallback is empty before queue, repair, and audit payload projection, so custom item wrappers that yield valid metadata before stopping do not erase that partial evidence.

Shared mapping item conversion skips lookup item unpack failures before queue, repair, refresh, and audit payload projection, so custom `.items()` wrappers cannot erase later valid fields when one item pair raises `KeyError` or `IndexError` during unpacking.

Shared mapping item conversion skips lookup key hash failures before queue, repair, refresh, and audit payload projection, so custom `.items()` wrappers cannot erase later valid fields when one item key raises `KeyError` or `IndexError` during hash validation.

Shared mapping item conversion skips string-like malformed item pairs before queue, repair, and audit payload projection, so malformed custom item wrappers cannot turn two-character strings into synthetic mapping fields.

Shared mapping item conversion skips unhashable malformed item keys before queue, repair, and audit payload projection, so custom mapping wrappers cannot crash plain-dict normalization with list-like keys while later valid fields remain available.

Daily decision queue ops payloads use type-safe fallback before notification delivery and route warning projection, so malformed ops truthiness cannot interrupt daily queue assembly or suppress later valid ops warning rows.

Daily decision queue route warning projection suppresses `slow_route` latency warnings while preserving `retry_storm`, `quality_gate_failures`, and future actionable route warnings, so p95 latency noise stays out of frontstage actions without hiding retry-failure evidence.

Daily decision queue free-mode violation lists use string-safe conversion before fix-free-mode action output, so direct queue callers cannot leak non-string paid-dependency labels or drop tuple violation evidence.

Daily decision queue free-mode can-run flags use bool-safe fallback before fix-free-mode action projection, so malformed `can_run_without_paid_keys` truthiness cannot interrupt queue assembly or hide paid-dependency repair actions.

Daily decision queue explicit backtest collections use iterator-safe dict-list conversion before due-item projection, so malformed `due_backtests` or `backtest_due` truthiness cannot interrupt daily queue assembly or suppress valid backtest due rows.

Daily decision queue backtest evaluation `details` use iterator-safe dict-list conversion before computed due checks, so malformed evaluation detail truthiness cannot interrupt daily queue assembly or make due reports look already evaluated.

Daily decision queue computed backtest report rows use iterator-safe dict-list conversion before due-date checks, so malformed report collection truthiness cannot interrupt daily queue assembly or hide reports that are due for backtest.

Daily decision queue computed backtest report artifact fields use string-safe conversion before evaluated-key and due-date checks, so malformed filename or report filename truthiness cannot interrupt computed backtest due detection or hide due reports.

Daily decision queue computed backtest report date fields use string- and float-safe conversion before due-date checks, so malformed date or timestamp truthiness cannot interrupt queue assembly or hide later valid due reports.

Daily decision queue backtest due action text fields use string-safe conversion before title, artifact identity, and pipeline projection, so malformed ticker, filename, report filename, or pipeline truthiness cannot interrupt backtest due output or leak non-string display fields.

Daily decision queue rerun report collections use iterator-safe dict-list conversion before stale-report action projection, so malformed rerun collection truthiness cannot interrupt daily queue assembly or suppress valid rerun report rows.

Daily decision queue watchlist collections use iterator-safe dict-list conversion before watchlist action projection, so malformed watchlist collection truthiness cannot interrupt daily queue assembly or suppress valid watchlist rows.

Daily decision queue screener candidate collections use iterator-safe dict-list conversion before candidate action projection, so malformed candidate collection truthiness cannot interrupt daily queue assembly or suppress valid screener candidate rows.

Daily decision queue screener candidate action text fields use string-safe conversion before title and detail projection, so malformed ticker, company name, or reason truthiness cannot interrupt candidate action output or leak non-string display fields.

Daily decision queue report repair action `title` fields use string-safe conversion before priority ordering, so malformed title truthiness cannot interrupt the daily queue or hide which report needs operator attention.

Daily decision queue report repair action `detail` fields use string-safe conversion before priority ordering, so malformed detail truthiness cannot interrupt the daily queue or erase concrete blocked-repair evidence.

Daily decision queue report repair `filename` and `report_filename` aliases use string-safe selection before priority ordering, so malformed filename truthiness cannot interrupt the daily queue or erase artifact identity.

Daily decision queue report repair action `recommended_action` fields use string-safe conversion before action-type mapping, so malformed action truthiness cannot interrupt the daily queue or hide safe refresh, rerun, wait, or manual-review intent.

Daily decision queue report repair action `ticker` fields use string-safe conversion before title and payload output, so malformed ticker truthiness cannot interrupt the daily queue or leak non-string report identity into queue consumers.

Daily decision queue rerun report action `ticker` fields use string-safe conversion before title and payload output, so malformed ticker truthiness cannot interrupt stale-report rerun ordering or leak non-string report identity into queue consumers.

Daily decision queue rerun report action `pipeline_id` fields use string-safe conversion before title and payload output, so malformed pipeline truthiness cannot interrupt stale-report rerun ordering or leak non-string report identity into queue consumers.

Daily decision queue rerun report `filename` and `report_filename` aliases use string-safe selection before dedupe and payload output, so malformed filename truthiness cannot interrupt stale-report rerun ordering or erase artifact identity.

Daily decision queue rerun report action `detail` fields use string-safe fallback before payload output, so malformed rerun reason truthiness cannot interrupt stale-report rerun ordering or erase concrete stale-snapshot evidence.

Daily decision queue report key `ticker` fields use string-safe conversion before dedupe, so malformed ticker truthiness cannot interrupt report repair or stale-report rerun skip-key matching.

Daily decision queue report key `pipeline_id` fields use string-safe conversion before dedupe, so malformed pipeline truthiness cannot interrupt report repair or stale-report rerun skip-key matching.

Daily decision dashboard report envelopes use mapping-safe conversion before row projection, so malformed envelope accessors cannot hide sampled reports, rerun evidence, repair actions, or provider impacts.

Daily decision dashboard report row collections use iterator-safe dict-list conversion before repair, rerun, and provider-impact aggregation, so falsey report-list wrappers cannot hide sampled reports or rerun evidence.

Daily decision dashboard rerun report `filename` and `report_filename` aliases use string-safe selection before rerun dedupe and payload output, so malformed filename truthiness cannot interrupt rerun-bucket aggregation or leak non-string artifact identity.

Daily decision dashboard rerun reason fields use string-safe fallback before `rerun_reports` payload output, so malformed freshness reason truthiness cannot interrupt rerun-bucket aggregation or erase stale-snapshot evidence.

Daily decision dashboard rerun freshness flags use bool-safe fallback before rerun-bucket projection, so malformed flag truthiness cannot interrupt dashboard aggregation or hide fallback stale-report evidence.

Daily decision dashboard performance envelopes use mapping-safe conversion before outcome calibration and queue projection, so malformed performance accessors cannot hide backtest evidence, summary metrics, or due-backtest actions.

Daily decision dashboard watchlist envelopes use mapping-safe conversion before high-priority action projection, so malformed watchlist accessors cannot hide watchlist rerun actions or high-priority counts.

Daily decision dashboard watchlist `decision_priority` fields use string-safe conversion before high-priority action projection, so malformed priority truthiness cannot interrupt dashboard aggregation or hide other valid high-priority watchlist rows.

Daily decision dashboard screener envelopes use mapping-safe conversion before candidate projection, so malformed screener accessors cannot hide review-candidate actions or top-candidate counts.

Daily decision dashboard screener quality-funnel maps use mapping-safe conversion before candidate filtering, so immutable reject outcomes cannot surface rejected candidates as review-candidate actions.

Daily decision dashboard screener quality outcome fields use string-safe conversion before reject filtering and top-candidate output, so malformed outcome truthiness cannot interrupt dashboard aggregation or leak non-string quality labels.

Daily decision dashboard screener candidate text fields use string-safe conversion before top-candidate output, so malformed ticker, company, reason, or category truthiness cannot interrupt dashboard aggregation or leak non-string candidate labels.

Daily decision dashboard screener score fields use conversion-safe fallback before top-candidate payload output, so malformed score objects cannot leak into dashboard or action payloads.

Daily decision dashboard screener score fields use conversion-safe fallback before candidate ordering, so malformed scores cannot interrupt dashboard aggregation or outrank valid candidates.

Daily decision dashboard free-mode envelopes use mapping-safe conversion before dashboard and queue projection, so malformed free-mode accessors cannot hide paid-dependency violations or fix-free-mode actions.

Daily decision dashboard free-mode violation lists use string-safe conversion before dashboard and queue projection, so malformed violation truthiness cannot interrupt aggregation or leak non-string paid-dependency labels.

Daily decision dashboard free-mode boolean flags use bool-safe fallback before dashboard and queue projection, so malformed enabled or can-run flags cannot interrupt aggregation or hide paid-dependency repair actions.

Daily decision dashboard decision freshness maps use mapping-safe conversion before rerun-bucket projection, so immutable report freshness wrappers cannot hide reports that need full reruns from the dashboard summary.

Daily decision queue provider impact ledger objects use type-safe fallback before provider recovery filtering, so malformed ledger truthiness cannot interrupt daily queue assembly or suppress valid provider impact rows.

Daily decision queue provider impact ledger maps use mapping-safe conversion before provider recovery filtering, so immutable provider-impact ledgers cannot hide wait-provider-recovery actions from the daily operating queue.

Daily decision queue provider impact summary maps use mapping-safe conversion before provider recovery filtering, so immutable provider-impact summaries cannot hide blocking wait-provider-recovery flags from the daily operating queue.

Daily decision queue provider impact ledger `items` use iterator-safe dict-list conversion before provider recovery filtering, so malformed ledger item truthiness cannot interrupt provider recovery ordering or suppress later valid provider impact rows.

Daily decision queue provider impact `impacts[].message` fields use string-safe conversion before detail output, so malformed impact-message truthiness cannot interrupt provider recovery ordering or erase concrete provider evidence.

Daily decision queue provider impact `filename` and `report_filename` aliases use string-safe selection before payload output, so malformed filename truthiness cannot interrupt provider recovery ordering or erase artifact identity.

Daily decision queue provider impact `blocks_auto_rerun` fields use bool-safe conversion before provider recovery filtering, so malformed blocking-flag truthiness cannot interrupt daily queue assembly and unparseable flags remain non-blocking.

Daily decision queue provider impact `recommended_action` fields use string-safe fallback before action payload output, so malformed action truthiness cannot interrupt provider recovery ordering or hide wait/retry policy intent.

Daily decision queue provider impact `ticker` fields use string-safe conversion before title and payload output, so malformed ticker truthiness cannot interrupt provider recovery ordering or leak non-string source identity into queue consumers.

Daily decision queue provider impact `pipeline_id` fields use string-safe conversion before payload output, so malformed pipeline truthiness cannot interrupt provider recovery ordering or leak non-string pipeline identity into queue consumers.

Daily decision queue report repair action `pipeline_id` fields use string-safe conversion before title and payload output, so malformed pipeline truthiness cannot interrupt the daily queue or leak non-string report identity into queue consumers.

Daily decision queue report repair action `priority_score` fields use integer-safe conversion before priority ordering, so malformed priority truthiness cannot interrupt the daily queue or hide a valid report repair priority.

Daily decision queue report repair action `severity` fields use string-safe conversion before payload output, so malformed severity truthiness cannot leak non-string repair state into queue consumers.

Daily decision queue report repair action `action_label` fields use string-safe conversion before payload output, so malformed CTA label truthiness cannot leak non-string operator action text into queue consumers.

`notification_plan.messages` and `delivery_outbox` preserve `reason_codes` from report repair queue actions, keeping the blocked-repair cause visible to sender channels and persisted delivery audit context.

`notification_plan.delivery_outbox` also preserves report repair action `detail`, keeping concrete blocked-repair evidence such as snapshot hash mismatch visible to sender channels and persisted delivery audit context.

Backend source count normalization treats raw source count conversion failures as inactive, so malformed count objects cannot interrupt source distribution output or suppress later valid source rows.

Backend source count normalization treats arithmetic raw source count conversion failures as inactive, so divide-by-zero or arithmetic conversion failures cannot interrupt source distribution output.

Backend source count normalization treats arbitrary `__int__` count objects as inactive before outputting source distribution maps, so unknown numeric wrappers cannot synthesize active source rows.

Backend source count normalization accepts only plain string raw source counts, so string subclasses with custom numeric conversion cannot synthesize active source rows.

Backend source display helpers treat arithmetic mapping accessor failures as empty source distributions, so overflow-style source maps cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source display helpers treat mapping attribute lookup failures as empty source distributions, so malformed `keys` or `items` attributes cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source display helpers treat lookup failures as empty or skipped source entries, so `KeyError` or `IndexError` from mapping accessors, iterators, or item unpacking cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source key helpers treat raw source key trim failures as blank keys, so malformed string subclasses cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source key helpers require raw source key trim results to remain strings, so malformed string subclasses cannot inject non-string source keys into labels, texts, counts, or display overrides.

Backend source display override helpers safely trim override values and require trim results to remain strings, so malformed override text cannot interrupt display-map generation or inject non-string display values.

Backend source text normalization requires trim results to be plain strings, so string subclasses with custom hash or equality behavior cannot reach source labels, texts, counts, or display overrides.

Notification messages and `delivery_outbox` entries drop orphan `source_label` and `source_text` fields when an action has no valid raw `source`, so malformed display-only metadata cannot bypass source key normalization.

Notification messages and `delivery_outbox` entries ignore non-string action-provided `source_label` and `source_text` before fallback labels, so numeric or boolean action metadata cannot replace canonical source wording.

`notification_plan.queue_context` maps non-string legacy action source keys to `unknown` before exposing source distribution maps, so numeric or boolean legacy sources cannot create synthetic source rows.

`notification_plan.queue_context` uses a string-safe legacy action type filter before excluding `monitor` fallback actions, so malformed legacy action type truthiness cannot interrupt notification planning or inflate legacy actionable counts.

Notification plan action collections use iterator-safe dict-list conversion before message and `delivery_outbox` assembly, so malformed `decision_queue.items` or legacy `actions` iterators cannot interrupt notification planning or suppress valid native actions.

Notification plan action collections accept list or tuple payloads before message and `delivery_outbox` assembly, so immutable repaired action batches are not silently ignored.

Notification plan decision queue context uses mapping-safe conversion before reading `decision_queue`, `summary`, and `sources`, so immutable repaired queue payloads are not downgraded to empty legacy actions.

Notification plan dashboard payloads use mapping-safe conversion before reading `decision_queue` or legacy `actions`, so immutable repaired dashboard responses do not interrupt notification planning.

`notification_plan.queue_context` treats numeric conversion failures as zero before exposing count and priority fields, so malformed summary counts or priority scores cannot interrupt notification planning.

`notification_plan.queue_context` uses strict count conversion before exposing count and priority fields, so boolean, binary, or memory-view queue summary counts cannot become synthetic notification workload evidence.

Notification plan numeric conversion treats fractional float, Decimal, and Fraction values as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata, so fractional payload drift cannot be silently truncated into synthetic priority, horizon, or workload counts.

Notification plan numeric conversion treats negative values as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata, so impossible negative priority, horizon, or workload counts cannot leak into sender payloads.

Notification plan numeric conversion treats arbitrary `__int__` adapter objects as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata, so unknown numeric wrappers cannot synthesize trusted priority, horizon, or workload counts.

Notification messages treat malformed dedupe identity values as fallback identity parts before exposing `dedupe_key` and `message_id`, so one broken title/report/route identifier cannot interrupt delivery identity generation.

Notification identity branch selection sanitizes report, ticker, pipeline, route, and warning identifiers before choosing fallback identity parts, so malformed truthiness cannot interrupt derived delivery identity generation.

Notification identity parts use shared text conversion before composing `dedupe_key`, `message_id`, and `delivery_key`, so boolean, binary, or memory-view identity payloads fall back instead of leaking Python representations into sender idempotency fields.

Notification identity parts use identity and type-based empty checks before composing `dedupe_key`, `message_id`, and `delivery_key`, so arbitrary identity equality hooks cannot erase valid sender idempotency overrides by comparing equal to blank strings.

Notification messages normalize `filename` and `report_filename` aliases with string-safe selection before exposing message and `delivery_outbox` report context, so malformed filename truthiness cannot interrupt notification planning.

Notification message numeric metadata uses strict count conversion before exposing `priority_score` and `horizon_months` in messages and `delivery_outbox`, so boolean, binary, or memory-view values cannot leak as sender-visible priority or horizon payloads.

Notification message text metadata uses shared text conversion before exposing ticker, filename, report, pipeline, route, warning, recommended action, severity, and action label fields in messages and `delivery_outbox`, so boolean, binary, or memory-view values cannot leak as sender-visible context.

Notification message boolean metadata uses explicit bool-text conversion before exposing `blocks_auto_rerun` in messages and `delivery_outbox`, so string `false` stays false while binary or memory-view values cannot leak as sender-visible blocking flags.

Notification message and `delivery_outbox` context presence checks tolerate malformed equality comparisons before carrying optional metadata, so one broken action metadata value cannot interrupt notification planning.

Notification message and `delivery_outbox` context presence checks use identity and type-based empty checks before carrying optional metadata, so arbitrary metadata equality hooks cannot erase valid sender context by comparing equal to blank strings.

Notification suppression flag checks use explicit bool-text conversion before message filtering, treating malformed or binary `suppress_notification` values as unsuppressed while preserving bool/string true and type-based suppression, so string `false` cannot hide real actions.

Notification plan boolean conversion treats arbitrary string-like objects as malformed before message metadata or suppression checks, so unknown wrappers cannot synthesize blocking flags or suppress notifications through `__str__` tokens.

Notification action type lookups trim raw `type` before suppression, legacy queue context, CTA defaults, target defaults, and message envelope output, so whitespace-padded monitor or provider-recovery actions cannot become sender-visible noise or lose their deep-link defaults.

Notification plan external channel env checks require concrete nonblank string values before enabling SMTP, Telegram, Discord, or Slack, so boolean, binary, memory-view, or arbitrary string-like env payloads stay in `channels[].missing_env` instead of creating external delivery outbox entries.

Notification plan external channel env containers use mapping-safe conversion before missing-env checks, so malformed env payloads keep local notifications enabled while external integrations remain disabled.

Notification messages ignore malformed action-provided `dedupe_key` and `message_id` overrides before falling back to derived delivery identity, so external queue metadata cannot break sender idempotency handoff.

Notification operator CTA metadata selection uses string-safe action/label fallbacks, so malformed custom CTA truthiness cannot interrupt notification planning and stringable custom CTAs remain available to sender payloads.

Notification target metadata selection uses string-safe panel/tab fallbacks, so malformed custom target truthiness cannot interrupt notification planning and stringable custom targets remain available to sender payloads.

Notification custom CTA and target metadata selection trims action-provided values before fallback selection, so whitespace-only custom buttons or deep links cannot leak into visible sender messages or `delivery_outbox` entries.

Notification message envelope selection uses string-safe type/title/detail fallbacks, so malformed message envelope truthiness cannot interrupt notification planning and stringable notification fields remain available to sender payloads.

Notification message envelope selection uses shared text conversion for type/title/detail fields, so boolean, binary, or memory-view envelope payloads cannot leak as visible sender message text.

Notification message envelope selection trims type/title/detail fields before fallback selection, so whitespace-only envelope metadata cannot leak into visible sender messages or `delivery_outbox` entries.

Audit context source display presence checks use string-safe text conversion before deriving fallback labels, so malformed `source_label` or `source_text` truthiness cannot interrupt sender audit persistence.

Audit context source key normalization uses string-safe text conversion before deriving fallback labels, so malformed raw `source` truthiness cannot interrupt sender audit persistence and stringable source keys are trimmed before persistence.

Audit context snapshot presence checks tolerate malformed equality comparisons before preserving optional outbox metadata, so one broken context value cannot interrupt sender audit persistence.

Notification delivery attempt result fields use string-safe status, error, and response id conversion, so malformed sender result truthiness cannot interrupt audit persistence.

Notification delivery outbox identity fields use string-safe required text extraction, so malformed `delivery_key`, `channel_id`, `message_id`, or `dedupe_key` truthiness cannot interrupt audit persistence when the identity value is stringable.

Notification delivery audit persistence evaluates mapping outbox entries before identity and context extraction, so immutable entry payloads can still be written to the delivery audit.

Notification delivery audit persistence rejects malformed mapping outbox entries with required identity errors, so broken entry accessors do not leak low-level iterator failures.

Notification delivery audit listing uses string-safe integer limit conversion, so malformed list limit truthiness cannot interrupt audit record listing or delivery summary generation.

Notification attention context record serialization uses string-safe text, integer, and dict conversion, so malformed failed audit row truthiness cannot interrupt notification delivery summary output.

Notification attention context identity fields are stripped before summary output, so repaired or mocked failed audit rows with padded `delivery_key` or `channel_id` values do not leak formatting whitespace into ops, daily queue, or sender context summaries.

Notification attention context limit handling treats `None` as the default cap before summary output, so optional caller limit values do not erase failed delivery context from ops, daily queue, or sender summaries.

Backend source display helpers preserve valid mapping items before iterator failures, so an iterator error after a valid entry does not erase already parsed source rows or overrides.

Backend source display helpers preserve valid mapping keys before iterator failures, so an iterator error after a valid key does not erase already parsed source labels, source texts, or active override matches.

Auto-screener 候選清單支援商業版前端的篩選與分頁。常用 query 包含 `category`、`min_score`、`fundamental_revenue_growth_yoy_min/max`、`technical_rsi_min/max`、`technical_macd_min`、`technical_macd_histogram_min`、`institutional_total_net_buy_min`、`institutional_foreign_net_buy_min`、`institutional_investment_trust_net_buy_min`、`institutional_dealer_net_buy_min`、`sort_by`、`sort_direction`、`limit` 與 `offset`：

```bash
curl "http://127.0.0.1:8080/api/watchlist/screener?min_score=70&fundamental_revenue_growth_yoy_min=10&technical_rsi_max=70&institutional_total_net_buy_min=1000000&sort_by=score&sort_direction=desc&limit=20"
```

Watchlist paste/CSV import is a mutation endpoint. It accepts `ticker`/`symbol`, optional `pipeline`, `schedule_slots`, `tags`, and `enabled`; four-digit Taiwan symbols are normalized to `.TW`.

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8080/api/watchlist/import \
  -d '{"text":"ticker,pipeline,schedule_slots\n2330.TW,v2,pre_market|post_market\nAAPL,v1,post_market"}'
```

Portfolio CSV 風控是本機研究工具，不接券商、不下單；因使用 POST body，仍需 mutation token：

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8080/api/watchlist/portfolio/risk \
  -d '{"csv":"ticker,weight,sector,country\n2330.TW,55,Semiconductors,TW\nAAPL,45,Technology,US"}'
```

### Deprecated Compatibility Endpoint

`GET /api/analyze/{ticker}` 保留給舊 UI / 舊腳本相容，回應會帶 `Deprecation: true` header，SSE 的 job metadata 也會包含 `deprecated: true`。新整合請改用：

1. `POST /api/analysis-jobs`
2. `GET /api/analysis-jobs/{job_id}/events`
3. `GET /api/analysis-jobs/{job_id}`

Legacy analysis job rows use mapping-safe fallback before stream setup or cancellation, so malformed requested-job or cancel-job rows fall back to the active job or return not found instead of interrupting compatibility endpoints.

Legacy analysis requested-job identity validation uses safe text fallback before stream setup, so malformed requested job ids fall back to the active job instead of interrupting compatibility streams.

Legacy analysis requested-job ticker validation uses safe text fallback before stream setup, so malformed requested ticker values fall back to the active job instead of interrupting compatibility streams.

Legacy analysis requested-job pipeline validation uses safe text fallback before stream setup, so malformed requested pipeline values fall back to the active job instead of interrupting compatibility streams.

Legacy analysis active-job identity validation uses safe text fallback before stream setup, so malformed active job ids fall through to job creation instead of interrupting compatibility streams.

Legacy analysis create handler results use mapping-safe fallback before stream setup, so malformed create adapter payloads fall through to legacy job creation and enqueue instead of interrupting compatibility streams.

Legacy analysis fallback queue enqueue failure messages use safe text fallback before stream setup, so malformed queue exception strings cannot interrupt compatibility streams or block terminal error events.

Legacy analysis API key readiness checks use strict bool fallback before stream setup, so malformed truthy readiness payloads fall back to the missing-key error stream instead of creating analysis jobs.

Legacy analysis missing API key messages use safe text fallback before SSE output, so malformed setup-message payloads cannot interrupt compatibility error streams.

Legacy analysis normalized pipeline ids use safe text fallback before stream setup, so malformed pipeline normalization payloads fall back to `v1` instead of interrupting compatibility streams.

Legacy analysis intro pipeline sequence values use sequence- and text-safe fallback before stream output, so malformed pipeline metadata cannot interrupt compatibility streams.

Legacy analysis intro pipeline label values use safe text fallback before stream output, so malformed pipeline label metadata cannot interrupt compatibility streams.

Legacy analysis intro agent total values use integer-safe fallback before stream output, so malformed binary or boolean agent-count metadata cannot interrupt compatibility streams or become synthetic counts.

Legacy analysis resume id parsing treats negative `Last-Event-ID` values as malformed before stream replay, so negative reconnect cursors fall back instead of reaching job-store event queries.

Legacy analysis cancel normalized pipeline ids use safe text fallback before cancellation requests, so malformed pipeline normalization payloads fall back to `v1` instead of hiding cancellable compatibility jobs.

Legacy analysis cancel ticker validation uses safe text fallback before cancellation requests, so malformed cancel job ticker values return not found instead of interrupting compatibility cancellation.

Legacy analysis cancel pipeline validation uses safe text fallback before cancellation requests, so malformed cancel job pipeline values return not found instead of interrupting compatibility cancellation.

Legacy analysis cancel result handling uses bool-safe fallback before response shaping, so malformed cancellation adapter results return not found instead of interrupting compatibility cancellation.

Report recommendation legacy text surfaces next catalysts from structured outputs, so plain-text agent sections keep the same catalyst watchlist evidence that appears in report sidebars.

Report recommendation legacy text uses trigger fallback for blank next catalysts, so plain-text catalyst rows keep `待後續資料確認` instead of dropping the entire catalyst section when a catalyst event has no displayable trigger condition.

Report recommendation legacy text uses impact-direction fallback for invalid next catalysts, so plain-text catalyst rows show `volatile` instead of arbitrary model text when a catalyst direction is not one of bullish, bearish, or volatile.

Report recommendation legacy text uses trigger-length fallback for too-short next catalysts, so plain-text catalyst rows keep `待後續資料確認` instead of presenting non-actionable trigger fragments.

Report recommendation legacy text surfaces reasoning steps from structured outputs, so Agent 7/16/19 plain-text sections keep the investment reasoning chain near recommendation context while Agent 19 still ends with the final recommendation block.

Report downside-risk legacy text surfaces thesis summaries from structured outputs, so Agent 21 plain-text sections keep the bearish thesis before listing individual downside risks.

Report downside-risk legacy text uses thesis-summary fallback for single-character fragments, so Agent 21 plain-text sections keep the summary block but show `資料不足` instead of non-actionable one-character thesis scraps.

Report downside-risk legacy text uses analysis body fallback for single-character fragments, so Agent 21 plain-text sections end with `資料不足` instead of non-actionable one-character analysis body scraps.

Report downside-risk legacy text uses fallback row for empty risk lists, so Agent 21 plain-text sections show `下行風險 / 資料不足` instead of leaving an empty downside-risk block when no individual risks are displayable.

Report valuation legacy text surfaces valuation reasoning from structured outputs, so Agent 4/14 plain-text sections keep DCF, peer, and scenario reasoning with the target-price table.

Report valuation legacy text skips single-character valuation reasoning fragments, so Agent 4/14 plain-text valuation reasoning sections do not present non-actionable one-character DCF, peer, or scenario scraps.

Report valuation legacy text surfaces DCF scenario assumptions from structured outputs, so Agent 4/14 plain-text sections keep bear/base/bull model sensitivities beside the valuation reasoning.

Report downside-risk legacy text surfaces risk priority metadata from structured outputs, so Agent 21 plain-text risk rows keep impact, severity, and confidence beside each downside risk.

Report downside-risk legacy text separates impact from evidence in risk rows, so Agent 21 plain-text sections do not merge impact labels into evidence text when the evidence sentence has no trailing punctuation.

Report downside-risk legacy text uses evidence fallback for single-character fragments, so Agent 21 plain-text risk rows show `資料不足` instead of presenting non-actionable one-character evidence scraps.

Report downside-risk legacy text uses title fallback for single-character fragments, so Agent 21 plain-text risk rows show `下行風險` instead of presenting non-actionable one-character risk-title scraps.

Report downside-risk legacy text omits impact for single-character fragments, so Agent 21 plain-text risk rows keep the evidence and metadata without presenting non-actionable one-character impact scraps.

Report downside-risk legacy text uses severity fallback for invalid metadata, so Agent 21 plain-text risk rows show schema-aligned `warning` instead of arbitrary severity labels outside `warning`, `high`, or `critical`.

Report downside-risk legacy text uses confidence fallback for invalid metadata, so Agent 21 plain-text risk rows show schema-aligned `0.7` instead of arbitrary confidence labels or non-finite values outside 0 to 1.

## Maintenance Dry Run

Cleanup APIs are dry-run unless `write=true` is explicit:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-analysis-history?retention_days=30"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-analysis-history?retention_days=30&write=true"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-failed-queue?stale_after_seconds=604800"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-failed-queue?stale_after_seconds=604800&write=true"
```

`cleanup-failed-queue` 預設只回報可由 `ended_at` 或 `created_at` 證明已過期的 RQ failed jobs；只有明確傳 `write=true` 才會刪除 stale job 與其資料，近期或無法判定年齡的失敗任務會保留。

SQLite backup/checkpoint/vacuum maintenance is also dry-run by default:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/sqlite-maintenance"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/sqlite-maintenance?write=true"
```

`write=true` creates one daily backup for each runtime SQLite DB under `SQLITE_BACKUP_DIR`, then runs `PRAGMA wal_checkpoint(TRUNCATE)` and `VACUUM`.
