"""Full-ledger summaries with explicit denominators and nulls."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Iterable, Mapping

from .evaluation import select_latest_revisions


def _metric(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row.get("outcome") in {"hit", "miss"}]
    rois = [row["strategy_roi_pct"] for row in rows if isinstance(row.get("strategy_roi_pct"), (int, float))]
    net = [row["net_strategy_roi_pct"] for row in rows if isinstance(row.get("net_strategy_roi_pct"), (int, float))]
    benchmark = [row["excess_return_pct"] for row in rows if isinstance(row.get("excess_return_pct"), (int, float))]
    return {
        "total": len(rows), "scored": len(scored), "hit_count": sum(r.get("outcome") == "hit" for r in scored),
        "miss_count": sum(r.get("outcome") == "miss" for r in scored),
        "hit_rate_pct": round(sum(r.get("outcome") == "hit" for r in scored) / len(scored) * 100, 4) if scored else None,
        "average_gross_roi_pct": round(mean(rois), 4) if rois else None,
        "gross_roi_n": len(rois), "average_net_roi_pct": round(mean(net), 4) if net else None,
        "net_roi_n": len(net), "average_excess_return_pct": round(mean(benchmark), 4) if benchmark else None,
        "benchmark_n": len(benchmark),
        "status_counts": dict(Counter(r.get("status", "unknown") for r in rows)),
    }


def summarize(*, candidates: Iterable[Mapping[str, Any]], evaluations: Iterable[Mapping[str, Any]],
              cutoff: str | None = None, page_total: int | None = None, page_returned: int | None = None) -> dict[str, Any]:
    candidates = list(candidates)
    selected = select_latest_revisions(evaluations, cutoff=cutoff)
    by_group: defaultdict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for evaluation in selected:
        result = evaluation["result"]
        by_group[(str(result.get("pipeline_id", "unknown")), str(evaluation["horizon_unit"]), str(evaluation["horizon_value"]))].append(result)
    report_ids = {str(c.get("report_bundle_hash")) for c in candidates if c.get("report_bundle_hash")}
    tickers = {str(c.get("ticker")) for c in candidates if c.get("ticker")}
    summary = {
        "schema_version": "oos.summary.v1", "cutoff": cutoff, "candidate_total": len(candidates),
        "admission_counts": dict(Counter(str(c.get("admission_status", "unknown")) for c in candidates)),
        "report_identity_count": len(report_ids), "ticker_count": len(tickers),
        "evaluation_total": len(selected),
        "groups": {f"{mode}:{unit}:{value}": _metric(rows) for (mode, unit, value), rows in sorted(by_group.items())},
        "pagination": {"total": page_total if page_total is not None else len(candidates),
                        "returned": page_returned if page_returned is not None else len(candidates),
                        "truncated": (page_returned if page_returned is not None else len(candidates)) < (page_total if page_total is not None else len(candidates))},
    }
    return summary


def summary_markdown(summary: Mapping[str, Any]) -> str:
    """Stable human-readable projection; JSON remains the source of truth."""
    lines = [
        "# Offline OOS summary",
        "",
        f"- Candidates: {summary.get('candidate_total', 0)}",
        f"- Evaluations: {summary.get('evaluation_total', 0)}",
        f"- Cutoff: {summary.get('cutoff') or 'not specified'}",
        "",
        "| Group | Total | Scored | Hit rate % | Gross ROI % | Statuses |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for group, metric in sorted((summary.get("groups") or {}).items()):
        hit = metric.get("hit_rate_pct")
        gross = metric.get("average_gross_roi_pct")
        lines.append(f"| {group} | {metric.get('total', 0)} | {metric.get('scored', 0)} | {hit if hit is not None else 'null'} | {gross if gross is not None else 'null'} | {metric.get('status_counts', {})} |")
    return "\n".join(lines) + "\n"
