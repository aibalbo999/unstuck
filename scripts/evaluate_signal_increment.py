"""Run a fixed-policy offline comparison on explicitly supplied historical JSON."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from signal_increment_evaluation import evaluate_increment
parser = argparse.ArgumentParser()
parser.add_argument("dataset", type=Path)
parser.add_argument("--cutoff", required=True)
args = parser.parse_args()
rows = json.loads(args.dataset.read_text())
if not isinstance(rows, list): raise SystemExit("dataset must be a JSON array")
print(json.dumps(evaluate_increment(rows, cutoff=args.cutoff), ensure_ascii=False, indent=2))
