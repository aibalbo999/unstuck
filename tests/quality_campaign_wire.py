"""Capture public wire text/explicit usage without storing thoughts or errors.

HTTP dispatch is an attempted request, not proof that the server received it.
Every AFC HTTP response has its own identity and cumulative usage snapshot.
"""
import json
import time
import re

import httpx

# Pinned to the installed SDK's documented terminal enum, not arbitrary strings.
# Termination is usage evidence only, never proof of a qualified research report.
TERMINAL_REASONS = frozenset(('STOP', 'MAX_TOKENS', 'SAFETY', 'RECITATION', 'LANGUAGE',
    'OTHER', 'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII', 'MALFORMED_FUNCTION_CALL',
    'IMAGE_SAFETY', 'UNEXPECTED_TOOL_CALL', 'IMAGE_PROHIBITED_CONTENT', 'NO_IMAGE',
    'IMAGE_RECITATION', 'IMAGE_OTHER'))

class ReplayAbort(BaseException):
    """A campaign stop must not be retried by the application SDK."""


def _safe_model_identity(value):
    from security_sanitizer import sanitize_error_message
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}',value):
        return None
    return value if sanitize_error_message(value)==value else None


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON member')
        value[key] = item
    return value


class WireReader:
    def __init__(self, observer, row, content_type, *, encoding=''):
        from httpx._decoders import SUPPORTED_DECODERS, IdentityDecoder, MultiDecoder
        self.observer, self.row = observer, row
        encodings = [value.strip().lower() for value in encoding.split(',') if value.strip()]
        if any(value not in SUPPORTED_DECODERS for value in encodings):
            raise ReplayAbort('Unsupported HTTP content encoding; no fabricated wire observations')
        self.decoder = MultiDecoder([SUPPORTED_DECODERS[value]() for value in encodings]) if encodings else IdentityDecoder()
        self.sse = 'text/event-stream' in content_type
        self.buffer = b''
        self.closed = False

    def feed(self, chunk):
        # Own decoder: the unchanged raw bytes are still yielded to HTTPX/SDK,
        # whose independent decoder must see the original compressed stream.
        self._decoded(self.decoder.decode(chunk))

    def _decoded(self, chunk):
        self.observer.check_stream()
        self.buffer += chunk
        if len(self.buffer) > 4 * 1024 * 1024:
            raise ReplayAbort('Wire frame budget exceeded; retained partial only')
        if self.sse:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line.startswith(b'data:'):
                    self._json(line[5:].strip())

    def _json(self, raw):
        if not raw or raw == b'[DONE]':
            return
        try:
            payload = json.loads(raw, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError):
            self.row['unparsed_frames'] = self.row.get('unparsed_frames', 0) + 1
            return
        if isinstance(payload, list):
            for item in payload:
                self._observe(item, _safe_model_identity)
        elif isinstance(payload, dict):
            self._observe(payload, _safe_model_identity)

    def _observe(self, payload, identity):
        if not isinstance(payload, dict):
            return
        usage = payload.get('usageMetadata')
        candidates = payload.get('candidates')
        terminal = (isinstance(candidates, list) and bool(candidates) and all(isinstance(candidate, dict)
            and isinstance(candidate.get('finishReason'), str)
            and candidate['finishReason'] in TERMINAL_REASONS for candidate in candidates))
        if isinstance(usage, dict) or isinstance(candidates, list):
            self.row['usage_terminal'] = bool(terminal and isinstance(usage, dict)
                and type(usage.get('totalTokenCount')) is int and usage['totalTokenCount'] >= 0)
        if isinstance(usage, dict):
            fields = {'promptTokenCount': 'input_tokens', 'candidatesTokenCount': 'output_tokens',
                      'totalTokenCount': 'total_tokens', 'thoughtsTokenCount': 'reasoning_tokens',
                      'cachedContentTokenCount': 'cached_input_tokens', 'toolUsePromptTokenCount': 'tool_prompt_tokens'}
            if any(key in usage and (type(usage[key]) is not int or usage[key] < 0) for key in fields):
                self.row['usage_integrity_failed'] = True
            explicit = {dest: usage[key] for key, dest in fields.items() if type(usage.get(key)) is int and usage[key] >= 0}
            if explicit:
                self.row['usage'] = {**(self.row.get('usage') or {}), **explicit}
                counts = self.row['usage']
                if ('cached_input_tokens' in counts and 'input_tokens' in counts
                        and counts['cached_input_tokens'] > counts['input_tokens']):
                    self.row['usage_integrity_failed'] = True
        elif 'usageMetadata' in payload:
            self.row['usage_integrity_failed'] = True
        version = identity(payload.get('modelVersion'))
        if version:
            self.row['provider_model_version'] = version
        parts = []
        for candidate in payload.get('candidates', []) if isinstance(payload.get('candidates'), list) else []:
            content = candidate.get('content') if isinstance(candidate, dict) else None
            if not isinstance(content, dict):
                continue
            for part in content.get('parts', []) if isinstance(content.get('parts'), list) else []:
                if isinstance(part, dict) and not part.get('thought') and isinstance(part.get('text'), str):
                    parts.append(part['text'])
        self.observer.evidence.append('wire.jsonl', {'http_id': self.row['http_id'], 'attempt_id': self.row.get('attempt_id'),
            'at': time.time(), 'public_text': ''.join(parts), 'usage': self.row.get('usage'),
            'provider_model_version': self.row.get('provider_model_version')})

    def finish(self, complete):
        if self.closed:
            return
        self.closed = True
        if complete:
            self._decoded(self.decoder.flush())
        if not self.sse and complete:
            self._json(self.buffer)
        elif self.sse and complete and self.buffer.startswith(b'data:'):
            self._json(self.buffer[5:].strip())
        self.row.update(response_complete=complete, finished_at=time.time(),
                        status='response_complete' if complete else 'response_interrupted')
        self.observer.evidence.append('http.jsonl', dict(self.row))


def instrument_http(observer):
    """Process-local patch: all HTTP clients must match the exact provider route."""
    sync_send, async_send = httpx.Client.send, httpx.AsyncClient.send
    sync_single, async_single = httpx.Client._send_single_request, httpx.AsyncClient._send_single_request
    if any(getattr(method, '_campaign_budget_hook', False) for method in
           (sync_send, async_send, sync_single, async_single)):
        raise ReplayAbort('Campaign HTTP instrumentation is already installed')

    class SyncStream(httpx.SyncByteStream):
        def __init__(self, original, reader):
            self.original, self.reader = original, reader
        def __iter__(self):
            completed = False
            try:
                for chunk in self.original:
                    self.reader.feed(chunk)
                    yield chunk
                completed = True
            finally:
                self.reader.finish(completed)
        def close(self):
            try:
                self.original.close()
            finally:
                self.reader.finish(False)

    class AsyncStream(httpx.AsyncByteStream):
        def __init__(self, original, reader):
            self.original, self.reader = original, reader
        async def __aiter__(self):
            completed = False
            try:
                async for chunk in self.original:
                    self.reader.feed(chunk)
                    yield chunk
                completed = True
            finally:
                self.reader.finish(completed)
        async def aclose(self):
            try:
                await self.original.aclose()
            finally:
                self.reader.finish(False)

    def receive(row, response, stream_type):
        row.update(http_status=response.status_code, headers_received_at=time.time())
        observer.evidence.append('http.jsonl', dict(row))
        reader = WireReader(observer, row, response.headers.get('content-type', ''),
            encoding='' if response.is_stream_consumed else response.headers.get('content-encoding', ''))
        if response.is_stream_consumed:
            reader.feed(response.content)
            reader.finish(True)
        else:
            response.stream = stream_type(response.stream, reader)
        return response

    def fail(row, error):
        row.update(error_type=type(error).__name__, finished_at=time.time(), status='transport_error')
        observer.evidence.append('http.jsonl', dict(row))

    def sync_physical(client, request):
        row = observer.before_http(request)
        response = None
        try:
            observer.before_send(row)
            response = sync_single(client, request)
            return receive(row, response, SyncStream)
        except BaseException as exc:
            if response is not None:
                try:
                    response.close()
                except BaseException as cleanup_error:
                    row['cleanup_error_type'] = type(cleanup_error).__name__
            fail(row, exc)
            raise

    async def async_physical(client, request):
        row = observer.before_http(request)
        response = None
        try:
            observer.before_send(row)
            response = await async_single(client, request)
            return receive(row, response, AsyncStream)
        except BaseException as exc:
            if response is not None:
                try:
                    await response.aclose()
                except BaseException as cleanup_error:
                    row['cleanup_error_type'] = type(cleanup_error).__name__
            fail(row, exc)
            raise
    # Request hooks and auth flows run INSIDE Client.send. Reserve after those
    # hooks, at each single physical request, including a DigestAuth resend.
    def sync(client, request, **options):
        return sync_send(client, request, **{**options, 'follow_redirects': False})

    async def asynchronous(client, request, **options):
        return await async_send(client, request, **{**options, 'follow_redirects': False})

    for method in (sync, asynchronous, sync_physical, async_physical):
        method._campaign_budget_hook = True
    httpx.Client.send, httpx.AsyncClient.send = sync, asynchronous
    httpx.Client._send_single_request, httpx.AsyncClient._send_single_request = sync_physical, async_physical

    def restore():
        if (httpx.Client.send is not sync or httpx.AsyncClient.send is not asynchronous
                or httpx.Client._send_single_request is not sync_physical
                or httpx.AsyncClient._send_single_request is not async_physical):
            raise ReplayAbort('Campaign HTTP hooks changed; cannot safely restore another owner')
        httpx.Client.send, httpx.AsyncClient.send = sync_send, async_send
        httpx.Client._send_single_request, httpx.AsyncClient._send_single_request = sync_single, async_single
    return restore
