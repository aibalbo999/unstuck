"""Activate explicitly approved 76-row version scope or reversibly deactivate."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from legacy_evidence_revisions import activate_scope,deactivate_batch,revision_summary
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);a=p.add_mutually_exclusive_group(required=True)
 a.add_argument('--activate-manifest',type=Path);a.add_argument('--deactivate-batch');a.add_argument('--summary',action='store_true');args=p.parse_args()
 if args.activate_manifest: activate_scope(json.loads(args.activate_manifest.read_text()))
 elif args.deactivate_batch: deactivate_batch(args.deactivate_batch)
 print(json.dumps(revision_summary(),ensure_ascii=False,indent=2))
