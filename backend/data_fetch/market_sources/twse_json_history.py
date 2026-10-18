"""Issuer/month index exposed by the public MOPS frontend; originals stay checked."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import datetime, timedelta
import re
import time
import hashlib

from .twse_company_history import TAIPEI, _detail_identity, _roc_day, _text
from .twse_history_transport import JSON_URL

MAX_CANDIDATES = 64
TITLES = ["公司代號", "公司名稱", "發言日期", "發言時間", "主旨", "詳細資料"]


def fetch_monthly_candidates(stock_id, *, now, post, deadline):
    """At most three exact monthly ranges, 64 candidates, within one shared deadline."""
    lower = now - timedelta(days=30)
    current = lower.replace(day=1)
    candidates, seen, rejected = [], set(), Counter()
    audit = {"index_url": JSON_URL, "coverage_status": "partial", "status": "unavailable",
             "candidate_limit": MAX_CANDIDATES, "month_count": 0, "rejected_reason_counts": {}, "requests": []}
    while current.date() <= now.date() and audit["month_count"] < 3:
        month_end = current.replace(day=calendar.monthrange(current.year, current.month)[1])
        first, last = max(current.date(), lower.date()), min(month_end.date(), now.date())
        form = {"companyId": stock_id, "year": str(current.year - 1911), "month": str(current.month),
                "firstDay": str(first.day), "lastDay": str(last.day)}
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError("history deadline")
            response = post(JSON_URL, json=form, timeout=(2, 4), provider="TWSE monthly company history")
            audit["month_count"] += 1
            response.raise_for_status()
            audit["requests"].append({"query": form, "response_sha256": hashlib.sha256(response.content).hexdigest(),
                                      "response_bytes": len(response.content)})
            if len(response.content) > 256_000:
                raise ValueError("oversized monthly index")
            payload = response.json()
            result = payload.get("result") if isinstance(payload, dict) and payload.get("code") == 200 and payload.get("message") == "查詢成功" else None
            if (not isinstance(result, dict) or result.get("marketName") != "上市公司"
                    or result.get("companyId") != stock_id or not _text(result.get("companyAbbreviation"))
                    or [r.get("main") for r in result.get("titles", []) if isinstance(r, dict)] != TITLES
                    or not isinstance(result.get("data"), list) or len(result["data"]) >= 1000):
                raise ValueError("monthly index envelope mismatch")
            for row in result["data"]:
                try:
                    if not isinstance(row, list) or len(row) != 6:
                        raise ValueError("invalid row")
                    code, company, day, clock, title, action = row
                    if code != stock_id or company != result["companyAbbreviation"] or not _text(title):
                        raise ValueError("issuer or title mismatch")
                    published_day = _roc_day(day)
                    if not isinstance(clock, str) or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", clock):
                        raise ValueError("invalid time")
                    published = datetime.fromisoformat(f"{published_day.date().isoformat()}T{clock}").replace(tzinfo=TAIPEI)
                    if not first <= published.date() <= last:
                        raise ValueError("index month mismatch")
                    if not lower <= published <= now:
                        continue
                    params = action.get("parameters") if isinstance(action, dict) and action.get("apiName") == "t05st01_detail" else None
                    if (not isinstance(params, dict) or params.get("companyId") != stock_id
                            or params.get("marketKind") != "sii"
                            or params.get("enterDate") != f"{published.year - 1911:03d}{published:%m%d}"
                            or not isinstance(params.get("serialNumber"), str)
                            or not re.fullmatch(r"[1-9]\d{0,5}", params["serialNumber"])):
                        raise ValueError("detail identity mismatch")
                    link = ("https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?firstin=true&stp=1&step=1"
                            f"&SEQ_NO={params['serialNumber']}&SPOKE_TIME={published:%H%M%S}"
                            f"&SPOKE_DATE={published:%Y%m%d}&COMPANY_ID={stock_id}")
                    if not _detail_identity(link, stock_id, published) or link in seen:
                        raise ValueError("duplicate or invalid detail")
                    seen.add(link)
                    candidates.append((published, _text(title), _text(company), link))
                except (ValueError, TypeError, KeyError):
                    rejected["invalid_row"] += 1
        except Exception as exc:
            audit.update(error_kind=getattr(exc, "error_kind", type(exc).__name__),
                         http_status=getattr(getattr(exc, "response", None), "status_code", None),
                         rejected_reason_counts=dict(rejected))
            return [], audit
        current = month_end + timedelta(days=1)
    complete = not rejected and current.date() > now.date() and len(candidates) <= MAX_CANDIDATES
    audit.update(status="success" if complete else "degraded_enrichment", candidate_count=len(candidates),
                 coverage_status="window_complete" if complete else "partial", rejected_reason_counts=dict(rejected))
    return candidates[:MAX_CANDIDATES], audit
