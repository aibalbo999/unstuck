"""Content-addressed public response evidence; never archive request credentials."""
import gzip
import hashlib
import os
from pathlib import Path
import tempfile

MAX_BYTES = 8 * 1024 * 1024
HARD_MAX_BYTES = 16 * 1024 * 1024


def _byte_limit(value):
    if type(value) is not int or not 0 < value <= HARD_MAX_BYTES:
        raise ValueError('Invalid public evidence byte allowance')
    return value


def archive_response(body, *, source_url, retrieved_at, evidence_kind='raw_http_response_bytes', http_status=200,
                     max_bytes=MAX_BYTES):
    from runtime_paths import current_runtime_paths
    limit = _byte_limit(max_bytes)
    if not isinstance(body, bytes) or not body or len(body) > limit:
        return {'status':'unavailable','reason':'raw_body_missing_or_over_limit'}
    digest = hashlib.sha256(body).hexdigest()
    directory = current_runtime_paths().cache_dir / 'official-response-evidence'
    path = directory / (digest + '.gz')
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
                temporary = handle.name
                handle.write(gzip.compress(body, mtime=0))
            os.replace(temporary, path)
        proof = {'status':'archived','source_url':source_url,'retrieved_at':retrieved_at,'http_status':http_status,
                 'raw_response_sha256':digest,'raw_response_path':str(path),'raw_response_bytes':len(body),
                 'evidence_kind':evidence_kind,'historical_point_in_time_verified':False,'finality_guaranteed':False}
        if read_response(proof, max_bytes=limit) != body:
            raise ValueError('Archived evidence differs')
        return proof
    except (OSError, ValueError, EOFError):
        return {'status':'unavailable','reason':'raw_archive_failed','raw_response_sha256':digest}


def read_response(proof, *, max_bytes=MAX_BYTES):
    from runtime_paths import current_runtime_paths
    limit = _byte_limit(max_bytes)
    digest = proof.get('raw_response_sha256')
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError('Invalid evidence identity')
    try:
        int(digest, 16)
    except ValueError:
        raise ValueError('Invalid evidence identity') from None
    expected = current_runtime_paths().cache_dir / 'official-response-evidence' / (digest + '.gz')
    if Path(proof.get('raw_response_path') or '').resolve() != expected.resolve():
        raise ValueError('Evidence path is outside the public archive')
    with gzip.open(expected, 'rb') as handle:
        body = handle.read(limit + 1)
    if len(body) > limit or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('Archived response hash mismatch')
    return body
