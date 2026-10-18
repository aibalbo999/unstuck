"""Recheck saved cash-flow, volume and institutional originals without network."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from report_artifacts import ReportArtifactLocator
from report_evidence_gap_details import evidence_gap_details
from report_evidence_review import load_review
from storage.report_storage import LocalFileStorage


def audit(index, output):
    storage = LocalFileStorage(output)
    locator = ReportArtifactLocator(storage)
    with sqlite3.connect(f'{index.resolve().as_uri()}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        indexed = [dict(row) for row in connection.execute(
            'SELECT * FROM reports WHERE output_dir=? ORDER BY timestamp DESC,filename', (str(storage._root),))]
    seen, reports, errors = set(), [], []
    for row in indexed:
        key = (row['ticker'], row['pipeline_id'])
        if key in seen:
            continue
        seen.add(key)
        try:
            snapshot = locator.require_bundle(row['filename'], require_markdown=False).read_data_snapshot()
            data = snapshot['data']
            bundle = locator.require_bundle(row['filename'], require_markdown=False)
            review, _ = load_review(storage, row['filename'], bundle.read_data_item().content)
            details = evidence_gap_details(data, review.get('institutional_reports', ()), review.get('volume_observation'), review.get('cash_flow_period_review'), review.get('annual_cash_flow_review'))
            warnings = [item['id'] for item in snapshot.get('content_credibility', {}).get('warnings', [])
                        if isinstance(item, dict) and isinstance(item.get('id'), str)]
            annual = [row.get('provider') for row in data.get('source_audit', [])
                      if row.get('source') == 'financial_statements' and row.get('status') == 'success'
                      and row.get('raw_twd_by_year')]
            reports.append({'filename': row['filename'], 'ticker': row['ticker'], 'mode': row['pipeline_id'],
                            'original_warning_ids': warnings, 'annual_providers': annual, **details})
        except (KeyError, ValueError, TypeError, OSError) as exc:
            errors.append({'filename': row['filename'], 'error': str(exc)})
    summary = {key: dict(Counter(item[key]['status'] for item in reports))
               for key in ('cash_flow', 'volume', 'institutional')}
    summary['annual_cash_flow_reference'] = dict(Counter(
        item['cash_flow'].get('annual_reference', {}).get('status', 'not_provided') for item in reports))
    return {'reports_checked': len(reports), 'errors': errors, 'reports': reports, 'summary': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--result', required=True, type=Path)
    args = parser.parse_args()
    if not args.index.is_file() or not args.output.is_dir() or args.result.exists():
        parser.error('Existing index/output and a new result path are required')
    result = audit(args.index, args.output)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('reports_checked', 'summary', 'errors')}, ensure_ascii=False))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
