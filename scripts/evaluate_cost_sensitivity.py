"""Offline explicitly hypothetical cost scenarios; does not write operational results."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from cost_sensitivity import cost_sensitivity

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots",required=True,type=Path)
    scenarios=parser.add_mutually_exclusive_group(required=True)
    scenarios.add_argument("--round-trip-cost-bps",nargs="+",type=float)
    scenarios.add_argument("--profiles",type=Path,help="Explicit hypothetical component/tax-class policy JSON")
    args=parser.parse_args()
    slots=json.loads(args.slots.read_text())
    if not isinstance(slots,list):
        parser.error("slots must be a JSON list")
    if args.profiles:
        from cost_profile_sensitivity import evaluate_profiles
        result=evaluate_profiles(slots,json.loads(args.profiles.read_text()))
    else:
        result=cost_sensitivity(slots,args.round_trip_cost_bps)
    print(json.dumps(result,ensure_ascii=False,indent=2))
