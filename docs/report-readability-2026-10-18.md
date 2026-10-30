# Four-mode HTML readability

## Approved Scope

Improve all four HTML report modes and existing reports without changing saved
analysis, numeric evidence, Markdown, snapshots, source provenance, or quality
decisions. No model calls, data refresh, commit, or push is required. The formal
HTML response's fixed-script CSP must allow the exact trusted reader hash;
runtime reload requires a preservation preflight, not an unscoped dirty reload.

## Delivery

- [x] Shared reader presentation: conclusions first, visible material warnings,
  mode-specific headings, readable references and terminology, expandable audit.
- [x] New HTML templates use the same self-contained assets as existing reports.
- [x] Isolated tests cover original-content preservation, mode semantics,
  unknown values, quality markers, migration failure recovery and idempotence.
- [x] Desktop, mobile and print checks on saved reports from all four modes.
- [x] Inventory and dry-run all existing HTML; apply only verified byte-preserving
  additions with compare-and-swap guards and matching HTML checksums.
- [x] Verify unchanged Markdown, snapshots, quality decisions and index fields
  other than HTML fingerprint. HTML mtime remains unchanged. Record exceptions.

## Invariants

The HTML source keeps its original content. A self-contained reader script
projects that content into a readable DOM and retains exact original passages
inside accessible disclosures. It does not generate investment judgments or
recalculate evidence. Missing values remain unknown unless an explicit source
states they are not applicable. Blocked/warning/freshness notices stay visible.
Source links and original technical identifiers remain available for checking.
Charts, their inputs, and the report's analysis date remain unchanged.

The migration adds one versioned asset block; removing it must reproduce the
original HTML bytes exactly. Existing checksum sidecars and index HTML hashes
are updated together with rollback on failure. No full report re-render or
quality-gate recomputation is part of a layout migration.

## Progress

2026-10-18: Initial read-only inventory: 859 indexed reports (A 28, B 21,
C 67, D 743). Existing checkout has unrelated modifications; edits are scoped
to new reader assets, template integration, migration utility, and tests.

Final offline browser inventory: 859/859 passed at mobile width. Four saved
mode samples also passed desktop/mobile, chart-pixel and print checks under the
formal CSP, including rejection of injected scripts and inline event handlers.
One A-mode moat chart correctly reports unavailable data; no values were filled.

Focused isolated tests: 15 passed, 2 optional browser tests skipped (the separate
browser harness above ran). Broader regression: 314 passed, 2 skipped, 2 existing
failures, both reproduced without the reader include: mapping-safe conversion
in memo_output_completion, and a persistence rollback expectation. These are
not counted as passing and were not changed by this presentation task.

Runtime reload completed after idle-queue and deployed-code comparison. Only
the three reader-related Python files differed from the prior deployed baseline;
environment and launcher were unchanged. Health/readiness both returned 200.

Final migration and API acceptance completed: all 859 HTML files updated, with
byte-identical original HTML after removal of the added block; original mtimes,
859 Markdown files, 859 data snapshots, and all non-HTML index fields unchanged.
Four-mode view/download endpoints returned 200 with the fixed reader CSP hash.
The final served-response browser run passed all 16 checks and four print checks.
Jobs, tracking and scheduled work were preserved. New runtime audit rows were
verified as cached data reads only, with zero model or external HTTP requests.
See [evidence](evidence/report-readability/20261018/README.md). No commit or push.

Contrast follow-up: corrected legacy light-on-light stop-loss/risk/catalyst
styles, muted labels, ratings, price-scenario values and tracking buttons.
Saved charts are repainted with darker labels and series colors while keeping
their data and axes. All 859 HTML files received the final assets; original
content, mtimes, snapshots and quality fields were verified unchanged. The
four-mode desktop/mobile sample and risk/status matrix passed contrast checks;
all 27 valid sample charts painted with identical data/axis fingerprints.
