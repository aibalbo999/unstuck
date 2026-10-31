"""Exact JSON-cache copy, retaining original keys, values, deadlines and source DB.

Call the copy only after all legacy cache writers have stopped. This module
does not stop services, remove old cache rows or refresh any provider data.
"""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

POLICY = 'provider-json-cache-copy:v1'
COLUMNS = ('cache_key', 'value', 'expires_at', 'updated_at')


def _read_only(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
    conn.execute('PRAGMA query_only=ON')
    return conn


def _has_legacy_rows(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cache_entries'").fetchone()
    return bool(exists and conn.execute('SELECT 1 FROM cache_entries LIMIT 1').fetchone())


def ensure_cache_destination(legacy, destination):
    """An absent/unqualified destination cannot discard an existing cooldown."""
    legacy, destination = Path(legacy).resolve(), Path(destination).resolve()
    if legacy == destination or not legacy.exists():
        return
    with closing(_read_only(legacy)) as conn:
        try:
            if not _has_legacy_rows(conn):
                return
        finally:
            conn.close()
    try:
        with closing(_read_only(destination)) as conn:
            try:
                row = conn.execute('SELECT manifest_json FROM provider_json_cache_migrations WHERE id=1').fetchone()
            finally:
                conn.close()
        marker = json.loads(row[0]) if row else None
        if (not isinstance(marker, dict) or marker.get('policy') != POLICY
                or marker.get('source_database') != str(legacy)
                or type(marker.get('row_count')) is not int or marker['row_count'] < 0
                or not re.fullmatch('[0-9a-f]{64}', str(marker.get('row_sha256', '')))):
            raise ValueError('unqualified copy marker')
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        raise RuntimeError('Provider JSON cache migration required; existing guards must be preserved') from exc


def _row_bytes(row):
    def typed(value):
        if value is None:
            return ['null']
        if isinstance(value, bytes):
            return ['blob', base64.b64encode(value).decode('ascii')]
        if isinstance(value, float):
            return ['real', value.hex()]
        return [type(value).__name__, value]
    return json.dumps([typed(value) for value in row], ensure_ascii=True, separators=(',', ':')).encode() + b'\n'


def cache_fingerprint(conn):
    digest, count = hashlib.sha256(), 0
    for row in conn.execute('SELECT cache_key,value,expires_at,updated_at FROM cache_entries ORDER BY cache_key'):
        digest.update(_row_bytes(row)); count += 1
    return {'row_count': count, 'row_sha256': digest.hexdigest()}


def copy_cache_entries(legacy, destination):
    """Create a new verified DB without overwriting any destination or source.

    Failure leaves the original untouched. A partial temporary copy is retained
    for diagnosis; only the verified, closed DB is linked into the final name.
    """
    from cache_backends import _init_schema
    requested = Path(destination)
    legacy, destination = Path(legacy).resolve(), requested.resolve()
    if legacy == destination or requested.exists() or requested.is_symlink():
        raise FileExistsError('Dedicated cache destination must be new')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name('.' + destination.name + '.' + uuid4().hex + '.migrating')
    with closing(_read_only(legacy)) as source:
        try:
            source.execute('BEGIN')
            columns = tuple(row[1] for row in source.execute('PRAGMA table_info(cache_entries)'))
            if columns != COLUMNS:
                raise ValueError('Unsupported legacy cache schema; no data copy performed')
            target = sqlite3.connect(temporary)
            try:
                temporary.chmod(0o600)
                _init_schema(target)
                digest, count = hashlib.sha256(), 0
                for row in source.execute('SELECT cache_key,value,expires_at,updated_at FROM cache_entries ORDER BY cache_key'):
                    target.execute('INSERT INTO cache_entries VALUES(?,?,?,?)', tuple(row))
                    digest.update(_row_bytes(row)); count += 1
                manifest = {'policy': POLICY, 'source_database': str(legacy),
                            'row_count': count, 'row_sha256': digest.hexdigest(), 'copied_at': time.time()}
                if cache_fingerprint(target) != {key: manifest[key] for key in ('row_count', 'row_sha256')}:
                    raise RuntimeError('Copied cache records differ; destination not published')
                target.execute('CREATE TABLE provider_json_cache_migrations (id INTEGER PRIMARY KEY CHECK(id=1), manifest_json TEXT NOT NULL)')
                target.execute('INSERT INTO provider_json_cache_migrations VALUES(1,?)', (json.dumps(manifest),))
                target.commit()
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Copied cache integrity check failed')
            finally:
                target.close()
        finally:
            source.close()
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.link(temporary, destination)  # Atomic no-overwrite publication on the same volume.
    temporary.unlink()
    ensure_cache_destination(legacy, destination)
    return {**manifest, 'destination_database': str(destination), 'original_rows_removed': False,
            'keys_values_and_expiry_preserved': True}
