"""Deduplicate identical evidence work only within one read request.

Every lookup rehashes the actual snapshot/text and referenced archive bytes.
There is no TTL, cross-request result store, index-only key, or persisted state.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime
from functools import wraps
import hashlib
import json
from pathlib import Path
from threading import RLock
from zoneinfo import ZoneInfo

_SCOPE=ContextVar('request_evidence_projection_reuse',default=None)

@contextmanager
def projection_reuse_scope():
    token=_SCOPE.set(({},RLock()))
    try:yield
    finally:_SCOPE.reset(token)

def with_projection_reuse(function):
    @wraps(function)
    async def wrapped(*args,**kwargs):
        with projection_reuse_scope():
            return await function(*args,**kwargs)
    return wrapped

def _proof_paths(value):
    if isinstance(value,dict):
        if value.get('raw_response_path') and value.get('raw_response_sha256'):
            yield value
        for child in value.values():yield from _proof_paths(child)
    elif isinstance(value,list):
        for child in value:yield from _proof_paths(child)

def reuse_projection(snapshot,markdown,compute):
    scope=_SCOPE.get()
    if scope is None:return compute()
    try:
        digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
        digest.update(markdown.encode())
        # A missing/corrupt/changed archive must never inherit an earlier gate.
        from runtime_paths import current_runtime_paths
        directory=current_runtime_paths().cache_dir/'official-response-evidence'
        archives={}
        for proof in _proof_paths(snapshot):
            identity=proof['raw_response_sha256']
            if not isinstance(identity,str) or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
                return compute()
            expected=directory/(identity+'.gz')
            if Path(proof['raw_response_path']).resolve()!=expected.resolve():
                return compute()
            archives[str(expected)]=expected
        for path,expected in sorted(archives.items()):
            digest.update(path.encode());digest.update(expected.read_bytes())
        digest.update(datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='minutes').encode())
        key=digest.hexdigest()
    except (OSError,ValueError,TypeError):return compute()
    cache,lock=scope
    with lock:
        future=cache.get(key);owner=future is None
        if owner:future=cache[key]=Future()
    if owner:
        try:future.set_result(deepcopy(compute()))
        except BaseException as exc:
            future.set_exception(exc)
            with lock:cache.pop(key,None)
            raise
    return deepcopy(future.result())
