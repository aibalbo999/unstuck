"""Offline replay of four captured TWSE responses; no provider or operational writes."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from market_screener_sources import (TwseFreeScreenerDataSource, TWSE_FOREIGN_INVESTOR_URL,
    TWSE_INVESTMENT_TRUST_URL, TWSE_STOCK_DAY_ALL_URL, TWSE_STOCK_DAY_AVG_ALL_URL)
from market_screener_candidates import build_screener_candidates


def replay(directory, scan_date):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    names = {TWSE_FOREIGN_INVESTOR_URL:"foreign",TWSE_INVESTMENT_TRUST_URL:"trust",
             TWSE_STOCK_DAY_ALL_URL:"daily",TWSE_STOCK_DAY_AVG_ALL_URL:"average"}
    captures = {}
    for name in names.values():
        raw = (directory / (name + ".json")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest[name].get("raw_sha256"):
            raise ValueError("capture hash mismatch: " + name)
        captures[name] = json.loads(raw)
    class Response:
        def __init__(self, value): self.value = value
        def raise_for_status(self): pass
        def json(self): return self.value
    class CapturedSession:
        def get(self, url, **kwargs):
            if url not in names:
                raise ValueError("unexpected endpoint; network disabled")
            params = kwargs.get("params")
            if params and params.get("date") != scan_date.strftime("%Y%m%d"):
                raise ValueError("capture cannot supply a different requested date")
            return Response(captures[names[url]])
    source = TwseFreeScreenerDataSource(session=CapturedSession())
    inst, daily = source.fetch_institutional_frame(scan_date), source.fetch_daily_frame(scan_date)
    candidates = build_screener_candidates(inst, daily, scan_date=scan_date, top_n=10)
    return {"scope":"offline captured-source replay;no operational write",
            "capture_manifest":manifest,"institutional_rows":len(inst),"daily_rows":len(daily),
            "candidate_count":len(candidates),"candidates":candidates,
            "same_date_normalized_flow_count":sum(c["metrics"].get("normalized_flow_pct") is not None for c in candidates),
            "historical_point_in_time_verified":False,"validated_net_results":0,
            "limitation":"Capture acquisition cannot restore historical availability, corporate actions, fills or actual costs."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True)
    parser.add_argument("--scan-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    print(json.dumps(replay(args.capture_dir, args.scan_date), ensure_ascii=False, indent=2))
