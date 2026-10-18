"""Read-only inventory of saved report gaps; never calls a data/model provider."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from report_artifacts import ReportArtifactLocator
from report_reader_assets import reader_observations
from storage.report_storage import LocalFileStorage


def missing(value):
    return value is None or isinstance(value, str) and value.strip().lower() in {
        '', 'n/a', 'na', '資料不足', '未評估', '未驗證', '未估計', '--'}


def audit(index: Path, output: Path, *, all_versions=False):
    storage = LocalFileStorage(output)
    locator = ReportArtifactLocator(storage)
    with sqlite3.connect(f'{index.resolve().as_uri()}?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute('SELECT * FROM reports WHERE output_dir=? ORDER BY timestamp DESC,filename', (str(storage._root),))]
    seen, reports, errors = set(), [], []
    for row in rows:
        identity = (row['ticker'], row['pipeline_id'])
        if not all_versions and identity in seen:
            continue
        seen.add(identity)
        try:
            snapshot = locator.require_bundle(row['filename'], require_markdown=False).read_data_snapshot()
            context = snapshot.get('rerun_context') or {}
            parsed = context.get('parsed') or {}
            if not isinstance(context, dict) or not isinstance(parsed, dict):
                raise ValueError('Saved analysis context must be an object')
            observed = reader_observations(snapshot)
            latest = {}
            for entry in observed['source_audit']:
                latest[(entry['source'], entry['provider'])] = entry
            gaps = []
            for field in {'v1': ('moat_scores', 'price_targets'), 'v2': ('position_plan',),
                          'v3': ('short_setup',), 'v4': ('trade_setup',)}.get(row['pipeline_id'], ()):
                values = parsed.get(field)
                if not isinstance(values, dict) or not values:
                    gaps.append({'output': field, 'field': 'entire_output'})
                else:
                    gaps.extend({'output': field, 'field': key} for key, value in values.items() if missing(value))
            reports.append({'filename': row['filename'], 'ticker': row['ticker'], 'mode': row['pipeline_id'],
                'missing_fields': gaps,
                'source_issues': [entry for entry in latest.values() if entry['status'] not in {'success', 'skipped_fresh_cache', 'not_applicable'}],
                'calendar_status': observed['event_calendar']['status'] or 'not_saved',
                'analysis_not_rerun': observed['analysis_not_rerun'],
                'quality_statuses': {key: snapshot.get(key, {}).get('status') for key in
                    ('final_audit', 'content_credibility', 'report_conformance', 'evidence_exit_gate')},
                'interpretation': 'Missing fields are not automatically acquisition failures; Neutral/waiting may intentionally omit execution fields.'})
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            errors.append({'filename': row['filename'], 'error': str(exc)})
    causes = Counter((entry['source'], entry['provider'], entry['status'], entry['error_kind'])
                     for report in reports for entry in report['source_issues'])
    return {'indexed_reports': len(rows), 'selection': 'all_versions' if all_versions else 'latest_stock_mode',
        'reports_checked': len(reports), 'modes': dict(Counter(report['mode'] for report in reports)),
        'source_causes': [{'source': key[0], 'provider': key[1], 'status': key[2], 'error_kind': key[3], 'count': count}
                          for key, count in causes.most_common()], 'errors': errors, 'reports': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--all-versions', action='store_true')
    args = parser.parse_args()
    if not args.index.is_file() or not args.output.is_dir() or args.result.exists():
        parser.error('Existing index/output and a new result path are required')
    result = audit(args.index, args.output, all_versions=args.all_versions)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('indexed_reports', 'selection', 'reports_checked', 'modes', 'errors')}, ensure_ascii=False))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
