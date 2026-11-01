"""Read-only necessary source checks; never a certificate of research quality."""

import hashlib
import json
import os
import stat
from collections import Counter
from datetime import date
from pathlib import Path
import re


def observation_period(data):
    """Exact source date only; never substitute generation time or today's date."""
    value = data.get('fetch_date')
    if not isinstance(value, str):
        return None
    value = value.strip()
    match = re.fullmatch(r'(20\d{2})年(\d{2})月(\d{2})日', value)
    if match:
        value = '-'.join(match.groups())
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return 'OBS:' + value


def text_value(value):
    return value.strip() if isinstance(value, str) else ''


def source_screen(snapshot):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    data = snapshot.get('data')
    data = data if isinstance(data, dict) else {}
    mode, ticker, data_ticker = (text_value(snapshot.get('pipeline')),
                               text_value(snapshot.get('ticker')), text_value(data.get('ticker')))
    period = observation_period(data)
    call = data.get('earnings_call')
    call = call if isinstance(call, dict) else {}
    transcript_texts = [text_value(call.get(key)) for key in ('transcript_excerpt', 'transcript', 'content')]
    transcript = any(transcript_texts)
    identity = data.get('company_identity')
    identity = identity if isinstance(identity, dict) else {}
    categories = identity.get('industry_categories')
    categories = categories if isinstance(categories, list) else []
    is_fund = any(text_value(category).upper() == 'ETF' for category in categories)
    source_flags = ['fund_identity_requires_separate_qualification'] if is_fund else []
    blockers = []
    if mode not in ('v1', 'v2', 'v3', 'v4'):
        blockers.append('invalid_pipeline_identity')
    if not ticker or not data_ticker:
        blockers.append('missing_ticker_identity')
    elif ticker != data_ticker:
        blockers.append('conflicting_ticker_identity')
    if period is None:
        blockers.append('invalid_source_cutoff')
    if mode in ('v1', 'v2', 'v3') and not transcript:
        blockers.append('missing_earnings_call_transcript')
    if mode in ('v1', 'v2', 'v3') and any('\ufffd' in text for text in transcript_texts):
        blockers.append('transcript_text_contains_replacement_character')
    return {'status': 'excluded_from_full_research' if blockers else 'needs_source_review',
            'qualified_for_live': False, 'blockers': blockers, 'pipeline': mode, 'ticker': ticker,
            'cutoff': period.removeprefix('OBS:') if period else None, 'transcript_present': transcript,
            'sector': text_value(data.get('sector')), 'industry': text_value(data.get('industry')),
            'source_flags': source_flags,
            'industry_quota_status': 'not_a_company_industry_sample' if is_fund else 'unverified',
            'basis': 'necessary_source_checks_only_not_integrity_provenance_or_research_certification'}


def _unique_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_member')
        result[key] = value
    return result


def _read_regular_source(root, relative, limit=50 * 1024 * 1024):
    """Open every component without following links, then bound the held file."""
    relative = Path(relative)
    if relative.is_absolute() or any(part in ('', '.', '..') for part in relative.parts):
        raise ValueError('invalid_relative_source_path')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open('/', flags)
    descriptor = None
    try:
        for part in (*root.parts[1:], *relative.parts[:-1]):
            following = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = following
        descriptor = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('source_must_be_bounded_regular_file')
        chunks, length = [], 0
        while chunk := os.read(descriptor, min(65536, limit + 1 - length)):
            chunks.append(chunk)
            length += len(chunk)
            if length > limit:
                raise ValueError('source_grew_beyond_read_limit')
        return b''.join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def inventory_sources(root):
    """Scan only the given artifact root, retaining failures and file identities.

    No DB, environment, generated analysis, provider or current time is used to
    supply missing source facts. A second full digest pass detects source drift.
    """
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('source_root_must_be_directory')
    paths = sorted(root.rglob('*.data.json'))
    rows = []
    for path in paths:
        row = {'path': str(path.relative_to(root)), 'qualified_for_live': False}
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                row.update(status='unreadable', blockers=['symlink_source_not_read'])
            elif path.stat().st_size > 50 * 1024 * 1024:
                row.update(status='unreadable', blockers=['source_exceeds_read_limit'])
            else:
                raw = _read_regular_source(root, path.relative_to(root))
                row['file_sha256'] = hashlib.sha256(raw).hexdigest()
                payload = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_members)
                if not isinstance(payload, dict):
                    raise ValueError('source_root_not_object')
                row.update(source_screen(payload))
                data = payload.get('data')
                if isinstance(data, dict):
                    row['data_sha256'] = hashlib.sha256(json.dumps(
                        data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
                    ).encode()).hexdigest()
        except (OSError, ValueError, UnicodeError, RecursionError):
            row.update(status='unreadable', blockers=['source_read_or_json_error'])
        rows.append(row)
    changed = []
    for row in rows:
        if row.get('file_sha256'):
            path = root / row['path']
            try:
                same = (not path.is_symlink() and path.resolve().is_relative_to(root)
                        and hashlib.sha256(_read_regular_source(root, path.relative_to(root))).hexdigest()
                        == row['file_sha256'])
            except (OSError, ValueError):
                same = False
            if not same:
                changed.append(row['path'])
    current_paths = sorted(str(path.relative_to(root)) for path in root.rglob('*.data.json'))
    path_list_changed = current_paths != [row['path'] for row in rows]
    summaries = {}
    for mode in ('v1', 'v2', 'v3', 'v4'):
        selected = [row for row in rows if row.get('pipeline') == mode]
        remaining = [row for row in selected if row['status'] == 'needs_source_review']
        pairs = {(row['ticker'], row['cutoff']) for row in remaining}
        summaries[mode] = {'artifact_files': len(selected),
            'excluded_files': sum(row['status'] == 'excluded_from_full_research' for row in selected),
            'necessary_check_remaining_unique_pairs': len(pairs), 'qualified_for_live': 0,
            'full_research_sample_minimum': 30,
            'impossible_with_this_same_mode_pool': len(pairs) < 30,
            'blocker_counts': dict(Counter(code for row in selected for code in row['blockers']))}
    return {'schema_version': 1, 'scope': 'existing_report_artifact_sources_only', 'root': str(root),
            'artifact_files': len(rows), 'unreadable_files': sum(row['status'] == 'unreadable' for row in rows),
            'source_unchanged': not changed and not path_list_changed, 'changed_paths': changed,
            'path_list_changed': path_list_changed, 'by_mode': summaries, 'rows': rows,
            'provider_calls': 0, 'market_refreshes': 0,
            'limitations': ['Necessary exclusion only; remaining v4 sources still require provenance review.',
                           'No DB, cached job, or cross-mode source substitution was inspected or approved here.',
                           'No report output, hash presence, or nonempty transcript certifies source truth.']}
