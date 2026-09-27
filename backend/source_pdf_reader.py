"""Bounded native PDF text extraction in one private, killable child.

Coverage describes native text only, not images, transcripts or source truth.
Darwin has no usable address-space rlimit here: the parent samples resident
memory, so short overshoots between checks remain possible.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

INPUT_LIMIT = 16 * 1024 * 1024
PAGE_LIMIT = 100
CHAR_LIMIT = 200_000
MEMORY_LIMIT = 512 * 1024 * 1024
# JSON ASCII escapes need up to 12 bytes per non-BMP code point.
STDOUT_LIMIT = 3 * 1024 * 1024
STDERR_LIMIT = 8192
TIMEOUT_LIMIT = 10.0
PARSER_VERSION = '6.19.0'


class SourcePdfError(RuntimeError):
    """Fixed diagnostics; no source text or child stderr is exposed."""
    retryable = False

    def __init__(self, reason, *, content_sha256=None):
        super().__init__(f'PDF extraction: {reason}')
        self.reason = self.error_kind = reason
        self.content_sha256 = content_sha256


class _DarwinTaskInfo(ctypes.Structure):
    # proc_taskinfo from the platform SDK's sys/proc_info.h.
    _fields_ = [('virtual_size', ctypes.c_uint64), ('resident_size', ctypes.c_uint64),
                ('times', ctypes.c_uint64 * 4), ('counters', ctypes.c_int32 * 12)]


def _memory_sampler():
    if sys.platform == 'darwin':
        library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        call = library.proc_pidinfo
        call.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        call.restype = ctypes.c_int

        def sample(pid):
            info = _DarwinTaskInfo()
            if call(pid, 4, 0, ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info):
                raise SourcePdfError('memory_accounting_unavailable')
            return info.resident_size
        return sample
    if sys.platform.startswith('linux'):
        page_size = os.sysconf('SC_PAGE_SIZE')

        def sample(pid):
            try:
                with open(f'/proc/{pid}/statm', 'rb') as stream:
                    fields = stream.read(256).split()
                return int(fields[1]) * page_size
            except (OSError, ValueError, IndexError):
                raise SourcePdfError('memory_accounting_unavailable') from None
        return sample
    raise SourcePdfError('resource_limits_unavailable')


def _worker_command(deadline):
    return [sys.executable, '-B', str(Path(__file__).with_name('source_pdf_worker.py')), str(deadline)]


def _run_worker(raw, deadline):
    sample = _memory_sampler()
    proc = None
    selector = selectors.DefaultSelector()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    limits = {'stdout': STDOUT_LIMIT, 'stderr': STDERR_LIMIT}
    sent = 0
    try:
        if time.monotonic() >= deadline:
            raise SourcePdfError('timeout')
        proc = subprocess.Popen(
            _worker_command(deadline), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, shell=False,
            cwd=str(Path(__file__).parent),
            env={name: value for name, value in os.environ.items()
                 if name in {'LANG', 'LC_ALL', 'SYSTEMROOT', 'STOCK_AGENT_TEST_NO_NETWORK'}},
        )
        for pipe, mode, name in [(proc.stdin, selectors.EVENT_WRITE, 'stdin'),
                                 (proc.stdout, selectors.EVENT_READ, 'stdout'),
                                 (proc.stderr, selectors.EVENT_READ, 'stderr')]:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, mode, name)
        while selector.get_map() or proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourcePdfError('timeout')
            if proc.poll() is None:
                try:
                    resident = sample(proc.pid)
                except SourcePdfError:
                    if proc.poll() is None:
                        raise
                    resident = 0  # The child exited before its process info was read.
                if resident > MEMORY_LIMIT:
                    raise SourcePdfError('memory_limit')
            for key, _ in selector.select(min(remaining, .02)):
                if key.data == 'stdin':
                    try:
                        sent += os.write(key.fd, raw[sent:sent + 16384])
                    except BrokenPipeError:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    if sent == len(raw):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer = buffers[key.data]
                if len(buffer) + len(chunk) > limits[key.data]:
                    raise SourcePdfError(f'{key.data}_limit')
                buffer.extend(chunk)
            if not selector.get_map() and proc.poll() is None:
                time.sleep(min(.01, max(0, deadline - time.monotonic())))
        if proc.returncode != 0:
            raise SourcePdfError('worker_failed')
        if buffers['stderr']:
            raise SourcePdfError('worker_diagnostic')
        return bytes(buffers['stdout'])
    finally:
        selector.close()
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                raise SourcePdfError('worker_cleanup_failed') from None
            finally:
                for pipe in (proc.stdin, proc.stdout, proc.stderr):
                    pipe.close()


def _validate_result(value, digest):
    if not isinstance(value, dict):
        raise SourcePdfError('invalid_worker_result')
    if set(value) == {'error'}:
        reason = value['error']
        if reason not in {'invalid_pdf', 'encrypted_pdf', 'page_limit', 'character_limit',
                          'empty_document', 'parser_unavailable', 'parser_version_mismatch',
                          'parser_warning', 'stream_limit', 'resource_limits_unavailable',
                          'timeout', 'invalid_input', 'memory_limit'}:
            reason = 'worker_failed'
        raise SourcePdfError(reason)
    expected = {'page_count', 'pages', 'empty_pages', 'garbled_pages', 'coverage_status',
                'parser_version', 'content_sha256'}
    if set(value) != expected or value['content_sha256'] != digest or value['parser_version'] != PARSER_VERSION:
        raise SourcePdfError('invalid_worker_result')
    pages = value['pages']
    count = value['page_count']
    if type(count) is not int or not 1 <= count <= PAGE_LIMIT or not isinstance(pages, list) or len(pages) != count:
        raise SourcePdfError('invalid_worker_result')
    total = 0
    empty = []
    for number, page in enumerate(pages, 1):
        if (not isinstance(page, dict) or set(page) != {'page_number', 'text'} or
                type(page['page_number']) is not int or page['page_number'] != number or
                not isinstance(page['text'], str)):
            raise SourcePdfError('invalid_worker_result')
        total += len(page['text'])
        if not page['text'].strip():
            empty.append(number)
    garbled = value['garbled_pages']
    if (total > CHAR_LIMIT or len(empty) == count or value['empty_pages'] != empty or
            not isinstance(garbled, list) or any(type(n) is not int or not 1 <= n <= count for n in garbled) or
            garbled != sorted(set(garbled)) or
            value['coverage_status'] != ('partial' if empty or garbled else 'complete')):
        raise SourcePdfError('invalid_worker_result')
    return value


def extract_pdf_pages(raw: bytes, *, timeout_seconds=10) -> dict:
    """Return every native text page or fail; never OCR, summarize or truncate.

    ``complete`` means no empty/obviously garbled native text page was found.
    It does not certify image coverage, reading order or a conference transcript.
    The deadline includes child startup/I/O; mandatory kill/reap adds cleanup time.
    """
    if not isinstance(raw, bytes) or not raw or len(raw) > INPUT_LIMIT:
        raise SourcePdfError('invalid_input')
    digest = hashlib.sha256(raw).hexdigest()
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or
            not 0 < timeout_seconds <= TIMEOUT_LIMIT or not math.isfinite(timeout_seconds)):
        raise SourcePdfError('invalid_timeout', content_sha256=digest)
    deadline = time.monotonic() + float(timeout_seconds)
    try:
        output = _run_worker(raw, deadline)
        if time.monotonic() >= deadline:
            raise SourcePdfError('timeout')
        result = _validate_result(json.loads(output), digest)
        if time.monotonic() >= deadline:
            raise SourcePdfError('timeout')
        return result
    except SourcePdfError as exc:
        exc.content_sha256 = digest
        raise
    except (OSError, ValueError, TypeError, OverflowError):
        raise SourcePdfError('invalid_worker_result', content_sha256=digest) from None
