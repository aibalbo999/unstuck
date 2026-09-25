"""Company-scoped retrieval from shared official daily announcement snapshots."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import time

from official_disclosure_sources import COVERAGE_NOTE, FRESHNESS_SECONDS, MARKETS, TAIPEI, fetch_disclosure_snapshot
from search_provider_runtime import SourceResponseError

from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult


class OfficialDisclosuresProvider(DataProvider):
    source = "official_disclosures"
    name = "TWSE/TPEx official disclosures"
    markets = {"tw"}
    freshness_seconds = FRESHNESS_SECONDS
    capabilities = {"official_announcements", "issuer_matched", "local_document_search"}

    def supports(self, request: FetchRequest) -> bool:
        return bool(re.fullmatch(r"\d{4,6}(?:\.(?:TW|TWO))?", request.ticker))

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        started = time.time()
        ticker = _qualified_ticker(request, context)
        if not ticker:
            return ProviderResult(source=self.source, provider=self.name, status="not_applicable", value={})
        market = "tpex" if ticker.endswith(".TWO") else "twse"
        spec = MARKETS[market]
        meta, snapshot = {}, {"documents": []}
        retrieval = "skipped" if request.options.skip_optional_http else "success"
        if not request.options.skip_optional_http:
            try:
                # force_refresh refers to this report, not the shared market
                # snapshot. Every ticker keeps the same five-minute cadence.
                snapshot, meta = fetch_disclosure_snapshot(market)
                retrieval = "success" if snapshot["documents"] else "valid_empty"
            except SourceResponseError as exc:
                meta, retrieval = dict(exc.diagnostic), "error"
        now = datetime.fromtimestamp(time.time(), TAIPEI)
        since, until = (now - timedelta(days=30)).isoformat(), now.isoformat()
        index_error = False
        try:
            from source_document_index import search_source_documents, upsert_source_documents
            if snapshot["documents"]:
                upsert_source_documents(snapshot["documents"], observed_at_epoch=snapshot.get("retrieved_at_epoch"))
            documents = search_source_documents(ticker, kinds=("official_disclosure",), since=since, until=until, limit=20)
        except Exception:
            # Index availability must not discard evidence acquired this time;
            # only this issuer's observed recent documents can be returned.
            index_error = True
            threshold = now - timedelta(days=30)
            documents = [item for item in snapshot["documents"]
                         if item["ticker"] == ticker and _publication_in_window(item, threshold, now)][:20]
        # An empty daily snapshot is incomplete evidence, not an outage. The
        # common merger interprets unavailable as acquisition failure.
        status = "error" if retrieval == "error" and not documents else "degraded_enrichment"
        latest_publication = max((item.get("published_at") or "" for item in documents), default="") or None
        acquired_at = meta.get("fetched_at_epoch")
        retained = bool(documents) and retrieval in {"error", "skipped"}
        if acquired_at is None and retained:
            acquired_at = max((item.get("last_observed_at_epoch") or item.get("retrieved_at_epoch") or 0
                               for item in documents), default=0) or None
        stale = bool(meta.get("stale")) or bool(documents and retrieval == "error")
        cache_hit = bool(meta.get("cache_hit")) or retained
        fetched_at = datetime.fromtimestamp(acquired_at, timezone.utc).isoformat() if acquired_at is not None else None
        value = {"documents": documents, "status": "partial", "coverage_status": "partial",
                 "coverage_notes": [COVERAGE_NOTE], "actual_provider": spec["provider"],
                 "fetched_at_epoch": acquired_at, "fetched_at": fetched_at,
                 "observed_at": latest_publication, "retrieval_status": retrieval,
                 "stale": stale, "cache_hit": cache_hit, "index_available": not index_error}
        audit = {**meta, "source": self.source, "provider": self.name, "status": status,
                 "actual_provider": spec["provider"], "record_count": len(documents),
                 "fetched_at_epoch": acquired_at, "fetched_at": fetched_at, "observed_at": latest_publication,
                 "retrieval_status": retrieval, "coverage_status": "partial", "cache_hit": cache_hit,
                 "stale": stale, "event_kind": "aggregate", "http_request_sent": False,
                 "duration_ms": max(0, int((time.time() - started) * 1000)), "message": COVERAGE_NOTE,
                 "index_available": not index_error}
        return ProviderResult(source=self.source, provider=self.name, status=status, value=value, audit=audit,
                              duration_ms=audit["duration_ms"], warnings=[COVERAGE_NOTE])


def _publication_in_window(document: dict, start: datetime, end: datetime) -> bool:
    try:
        published = datetime.fromisoformat(document["published_at"])
        if published.tzinfo is None:
            published = published.replace(tzinfo=TAIPEI)
        return start <= published <= end
    except (KeyError, ValueError, TypeError):
        return False


def _qualified_ticker(request: FetchRequest, context: dict | None) -> str:
    """Use an already resolved issuer; never infer a bare ticker's exchange."""
    ticker = str(request.ticker or "").strip().upper()
    if not re.fullmatch(r"\d{4,6}(?:\.(?:TW|TWO))?", ticker):
        return ""
    data = context.get("data") if isinstance(context, dict) else None
    resolved = str(data.get("ticker") or "").strip().upper() if isinstance(data, dict) else ""
    if re.fullmatch(r"\d{4,6}\.(?:TW|TWO)", resolved):
        # Core quote acquisition may correct TW/TWO, but must not change issuer.
        return resolved if resolved.split(".", 1)[0] == ticker.split(".", 1)[0] else ""
    return ticker if re.fullmatch(r"\d{4,6}\.(?:TW|TWO)", ticker) else ""
