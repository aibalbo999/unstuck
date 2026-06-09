# ADR: Runtime Observability and Watchlist Scheduling

Date: 2026-06-09

## Status

Accepted

## Context

The system exposes operator dashboards for API quota usage, scheduled watchlist runs, report history, and local maintenance. These surfaces are useful only if they preserve the distinction between planned work and work that actually reached an external provider.

Watchlist scheduling also runs in both background and manual contexts. Without an explicit claim step, two scheduler checks can observe the same due slot and enqueue duplicate analysis jobs.

## Decision

- Scheduled watchlist runs must atomically claim due slots before enqueueing jobs. The claim updates `last_run_dates` inside a SQLite `BEGIN IMMEDIATE` transaction, so another scheduler pass sees the slot as already handled.
- `llm_model_call` means the runtime is preparing a model call. It does not count as quota usage.
- `llm_provider_request` means an API key has been selected and the provider request is being sent. The API usage ledger counts this event as one observed Gemini / Google AI call.
- Provider audit entries count toward API usage only when they represent an actual provider attempt. Fresh-cache skips and explicit fallback skips do not consume local observed quota.
- FMP quota summaries include both the historical `FMP quote` provider name and the current `FMP stable quote` provider name.
- Operator-only panels under the "報告與維運" tab should lazy-load on first activation, not during initial analysis-page load.

## Consequences

- The quota dashboard is a local observation ledger, not the source of truth for remaining provider quota.
- A scheduled watchlist slot may be marked claimed even if enqueue later fails; this favors duplicate prevention over automatic retry. Failed enqueue paths should emit job or scheduler logs so an operator can rerun manually.
- Historical `llm_model_call` rows with nonzero units remain compatible because summaries include both `llm_model_call` and `llm_provider_request` operations.
- UI startup work is lighter for the common analysis workflow; maintenance data is loaded only when the operator opens the maintenance tab.
