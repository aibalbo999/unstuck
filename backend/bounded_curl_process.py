"""Capped subprocess pipes for bounded public HTTP transports."""
from __future__ import annotations

import os
import selectors
import subprocess
import time

HEADER_LIMIT = METADATA_LIMIT = 65536

def collect_capped_process(argv, deadline, *, body_limit, headers=False):
    """Nonblocking capped pipes; stop/reap our exact child before returning."""
    buffers = {'body': bytearray(), 'headers': bytearray(), 'metadata': bytearray()}
    limits = {'body': body_limit, 'headers': HEADER_LIMIT, 'metadata': METADATA_LIMIT}
    proc = None
    selector = selectors.DefaultSelector()
    header_read = header_write = None
    error = None
    body_bytes_read = 0
    try:
        if time.monotonic() >= deadline:
            raise TimeoutError
        if headers:
            header_read, header_write = os.pipe()
            argv = [part.replace('{HEADER_FD}', str(header_write)) for part in argv]
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                shell=False, close_fds=True, pass_fds=(header_write,) if headers else (),
                                env={key: value for key, value in os.environ.items()
                                     if key in {'PATH', 'LANG', 'LC_ALL', 'CURL_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}})
        if header_write is not None:
            os.close(header_write)
            header_write = None
        streams = [(proc.stdout.fileno(), 'body'), (proc.stderr.fileno(), 'metadata')]
        if header_read is not None:
            streams.append((header_read, 'headers'))
        for fd, name in streams:
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, name)
        while selector.get_map() or proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            # Read available headers first, so refusal identity survives body failures.
            for key, _ in sorted(selector.select(min(remaining, .05)), key=lambda item: item[0].data != 'headers'):
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fd)
                    continue
                name = key.data
                if name == 'body':
                    body_bytes_read += len(chunk)
                space = limits[name] - len(buffers[name])
                buffers[name].extend(chunk[:space])
                if len(chunk) > space:
                    error = {'body': 'response_too_large', 'headers': 'response_headers_too_large',
                             'metadata': 'transport_metadata_too_large'}[name]
                    raise OverflowError
            if not selector.get_map() and proc.poll() is None:
                time.sleep(min(.01, remaining))
    except TimeoutError:
        error = 'timeout'
    except OverflowError:
        pass
    except Exception:
        error = 'transport_error'
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            except Exception:
                error = error or 'transport_cleanup_failed'
            # A complete refusal header can still be queued when body/read fails.
            if header_read is not None:
                try:
                    while len(buffers['headers']) < HEADER_LIMIT:
                        chunk = os.read(header_read, min(16384, HEADER_LIMIT - len(buffers['headers'])))
                        if not chunk:
                            break
                        buffers['headers'].extend(chunk)
                except (BlockingIOError, OSError):
                    pass
            for pipe in (proc.stdout, proc.stderr):
                try:
                    pipe.close()
                except Exception:
                    error = error or 'transport_cleanup_failed'
        for fd in (header_read, header_write):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        try:
            selector.close()
        except Exception:
            error = error or 'transport_cleanup_failed'
    return {**{key: bytes(value) for key, value in buffers.items()}, 'process_started': proc is not None, 'body_bytes_read': body_bytes_read}, proc.returncode if proc else None, error
