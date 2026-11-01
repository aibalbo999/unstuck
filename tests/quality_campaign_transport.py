"""HTTPX campaign accounting, not a launcher, billing verifier or OS sandbox.

The integration owner must supply reviewed per-model conservative ceilings and
an actual frozen-file verifier, force all SDK calls through these wrappers and
HTTPX, preserve the shared quota/socket boundary, and enforce outer cleanup.
Imports never read credentials, install patches, open databases or call I/O.
"""
import copy
from contextvars import ContextVar
import fcntl
import functools
import hashlib
import json
import math
import os
import re
import stat
import threading
import time
import uuid

from quality_campaign_budget import BudgetDenied
from quality_campaign_wire import ReplayAbort, instrument_http, unique_object


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _positive(value):
    if type(value) is not int or value <= 0:
        raise ReplayAbort('A reviewed positive integer reservation ceiling is required')
    return value


class _Journal:
    """Persist only safe request hashes, explicit usage and dispatch state."""
    def __init__(self, owner):
        self.owner = owner
        self.path = owner.ledger.path.with_suffix('.http.jsonl')
        self.lock = threading.RLock()

    def record(self, row):
        encoded = (_json(row) + '\n').encode()
        with self.lock:
            fd = os.open(self.path, os.O_APPEND | os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'ab') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                    raise ReplayAbort('Campaign HTTP journal must be a private regular file')
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        return hashlib.sha256(encoded).hexdigest()

    def append(self, name, value):
        # WireReader can expose public answer text. It is NOT duplicated here;
        # the original replay recorder remains responsible for report evidence.
        http_id = value['http_id']
        row = self.owner.http_rows[http_id]
        if name == 'wire.jsonl':
            if row.get('usage') is not None:
                self.owner._settle(row, final=False)
        elif name == 'http.jsonl':
            receipt = {'type': 'http_state', 'job_id': self.owner.job_id, **value}
            self.record(receipt)
            if value.get('status') in ('response_complete', 'response_interrupted', 'transport_error'):
                self.owner._settle(row, final=value.get('response_complete') is True
                    and 200 <= value.get('http_status', 0) < 300)


class CampaignTransport:
    def __init__(self, ledger, job_id, policies, *, actual_hashes, verify_frozen, secrets=()):
        if not callable(verify_frozen) or not isinstance(policies, dict):
            raise ReplayAbort('Explicit frozen verifier and reviewed route policies required')
        self.ledger, self.job_id = ledger, job_id
        self.policies, self.actual_hashes = copy.deepcopy(policies), copy.deepcopy(actual_hashes)
        self.policy_hashes = {model: _digest(policy) for model, policy in self.policies.items()}
        self.verify_frozen, self.secrets = verify_frozen, tuple(secret for secret in secrets if secret)
        self.active = ContextVar('campaign_transport', default=None)
        self._restore = None
        self.http_rows, self._usage_receipts = {}, {}
        self._deadline_ms = self._monotonic_deadline = None
        self._last_wall = self._last_monotonic = self._last_shared_check = None
        self.evidence = _Journal(self)

    def __enter__(self):
        if self._restore is not None:
            raise ReplayAbort('Campaign transport context already active')
        self._restore = instrument_http(self)
        return self

    def __exit__(self, *args):
        self._restore()
        self._restore = None
        return False

    def _budget(self, method, *args, **kwargs):
        try:
            return getattr(self.ledger, method)(*args, **kwargs)
        except BudgetDenied as error:
            raise ReplayAbort(str(error)) from None

    def check(self):
        if self._restore is None:
            raise ReplayAbort('Campaign transport context is not installed')
        self._budget('check')
        self._last_shared_check = self._check_local_time()

    def _check_local_time(self):
        wall, monotonic = self.ledger.clock(), time.monotonic()
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in (wall, monotonic)):
            raise ReplayAbort('Invalid campaign stream clock')
        if self._last_wall is not None and wall < self._last_wall:
            self._budget('check')  # Persist the shared wall-clock stop when applicable.
            raise ReplayAbort('Campaign stream wall clock rollback')
        if self._last_monotonic is not None and monotonic < self._last_monotonic:
            raise ReplayAbort('Campaign stream monotonic clock rollback')
        self._last_wall, self._last_monotonic = wall, monotonic
        if ((self._deadline_ms is not None and wall * 1000 >= self._deadline_ms)
                or (self._monotonic_deadline is not None and monotonic >= self._monotonic_deadline)):
            self._budget('check')
            raise ReplayAbort('Campaign stream deadline exceeded')
        return monotonic

    def check_stream(self):
        if self._restore is None:
            raise ReplayAbort('Campaign transport context is not installed')
        monotonic = self._check_local_time()
        # Each HTTP and explicit usage settlement still checks immediately.
        # Coalesce only pure chunk polling: a cross-process stop is observed at
        # the first chunk at/after 250 ms, or sooner on the next HTTP/usage.
        if self._last_shared_check is None or monotonic - self._last_shared_check >= 0.25:
            self.check()

    def _verify(self):
        if self.verify_frozen() != self.actual_hashes:
            raise ReplayAbort('Frozen code/source/route hashes changed')

    def before_send(self, row):
        self._verify()
        self.check()

    def _policy(self, model):
        policy = self.policies.get(model)
        if not isinstance(policy, dict) or _digest(policy) != self.policy_hashes.get(model):
            raise ReplayAbort('Model route has no unchanged reviewed reservation policy')
        for field in ('maximum_total_tokens', 'maximum_output_tokens', 'maximum_request_bytes'):
            _positive(policy.get(field))
        rate = policy.get('maximum_microusd_per_million_tokens')
        if type(rate) is not int or rate < 0 or policy['maximum_output_tokens'] > policy['maximum_total_tokens']:
            raise ReplayAbort('Invalid conservative token/cost policy')
        if (policy.get('billing_status') not in ('verified_paid', 'verified_free')
                or (policy['billing_status'] == 'verified_paid' and rate == 0)
                or (policy['billing_status'] == 'verified_free' and rate != 0)):
            raise ReplayAbort('Unverified or contradictory billing policy')
        return policy

    def _reservation(self, policy, tokens):
        # This is a conservative ESTIMATE using the reviewed maximum rate for
        # every observed token, including cached/thinking tokens, not an invoice.
        return {'tokens': tokens,
                'cost_microusd': (tokens * policy['maximum_microusd_per_million_tokens'] + 999999) // 1000000,
                'billing_status': policy['billing_status'],
                'billing_identity_sha256': policy.get('billing_identity_sha256'),
                'reservation_basis_sha256': policy.get('reservation_basis_sha256'),
                'actual_hashes': self.actual_hashes}

    def _start(self, args, options):
        self._verify()
        self.check()
        model = args[1] if len(args) > 1 else options.get('model_id')
        policy = self._policy(model)
        current = self.active.get()
        if current is not None:
            if current['model'] != model:
                raise ReplayAbort('Nested transport changed model without a new reservation')
            return None
        identifier = 'transport-' + uuid.uuid4().hex
        self._budget('reserve_attempt', identifier, self.job_id, transport=1, http=0,
                     **self._reservation(policy, 0))
        return {'id': identifier, 'model': model}

    def before_http(self, request):
        current = self.active.get()
        if current is None:
            raise ReplayAbort('HTTP requires an enclosing reserved transport')
        self.check()
        url = request.url
        match = re.fullmatch(r'/v1(?:beta)?/models/([^/:]+):(generateContent|streamGenerateContent)', url.path)
        if (url.scheme != 'https' or url.host != 'generativelanguage.googleapis.com'
                or url.port not in (None, 443) or url.username or url.password or url.fragment
                or request.method != 'POST' or not match or match[1] != current['model']
                or any(key != 'alt' for key in url.params)):
            raise ReplayAbort('HTTP endpoint/model is outside the reserved Gemini route')
        policy = self._policy(match[1])
        if len(request.content) > policy['maximum_request_bytes']:
            raise ReplayAbort('Actual HTTP body exceeds reviewed byte ceiling')
        try:
            payload = json.loads(request.content, object_pairs_hook=unique_object)
            body = request.content.decode('utf-8') + '\n' + _json(payload)
        except (ValueError, UnicodeError):
            raise ReplayAbort('HTTP body must be complete unambiguous JSON') from None
        if any(secret in body for secret in self.secrets) or re.search(r'AIza[\w-]{20,}', body):
            raise ReplayAbort('Credential found in HTTP body; no dispatch')
        if not isinstance(payload, dict) or payload.get('cachedContent'):
            raise ReplayAbort('Unsupported externally cached request input')
        config = payload.get('generationConfig')
        if not isinstance(config, dict) or _positive(config.get('maxOutputTokens')) > policy['maximum_output_tokens']:
            raise ReplayAbort('Actual output configuration exceeds reviewed ceiling')
        for content in [*(payload.get('contents') or []), payload.get('systemInstruction', {})]:
            if not isinstance(content, dict):
                raise ReplayAbort('Unsupported request content shape')
            for part in content.get('parts') or []:
                if not isinstance(part, dict) or set(part) - {'text', 'thought', 'thoughtSignature',
                        'thought_signature', 'functionCall', 'function_call', 'functionResponse', 'function_response'}:
                    raise ReplayAbort('Non-text remote/modality input has no reviewed token bound')
                for key in ('functionResponse', 'function_response'):
                    if key in part and (not isinstance(part[key], dict) or part[key].get('parts')):
                        # FunctionResponse.parts is a separate multimodal SDK
                        # surface (including snake_case inline_data), not the
                        # bounded JSON response of our frozen local functions.
                        raise ReplayAbort('Nested tool response modality has no frozen input bound')
        for tool in payload.get('tools') or []:
            if not isinstance(tool, dict) or set(tool) - {'functionDeclarations'}:
                raise ReplayAbort('Hosted retrieval or execution tools are outside frozen input scope')
        identifier = 'http-' + uuid.uuid4().hex
        self._budget('reserve_attempt', identifier, self.job_id, transport=0, http=1,
                     **self._reservation(policy, policy['maximum_total_tokens']))
        row = {'http_id': identifier, 'attempt_id': current['id'], 'model': match[1],
               'job_id': self.job_id, 'request_sha256': hashlib.sha256(request.content).hexdigest(),
               'started_at': time.time(), 'policy_sha256': self.policy_hashes[match[1]],
               'status': 'reserved_not_confirmed_dispatched', 'response_complete': False,
               'usage': None, 'provider_model_version': None}
        self.http_rows[identifier] = row
        self.evidence.record({'type': 'http_reserved', **row})
        # Durable reservation/logging can consume the remaining time. Check
        # again before the underlying HTTPX send; a denial never refunds it.
        self.check()
        job = self.ledger.snapshot()['jobs'][self.job_id]
        left = (job['deadline_ms'] - self.ledger.clock() * 1000) / 1000
        if left <= 0:
            raise ReplayAbort('Campaign deadline reached before HTTP dispatch')
        self._deadline_ms = job['deadline_ms']
        deadline = time.monotonic() + left
        self._monotonic_deadline = deadline if self._monotonic_deadline is None else min(self._monotonic_deadline, deadline)
        previous = request.extensions.get('timeout') or {}
        request.extensions['timeout'] = {name: min(left, value) if type(value) in (int, float) and value > 0 else left
            for name in ('connect', 'read', 'write', 'pool') for value in [previous.get(name)]}
        return row

    def _settle(self, row, *, final):
        usage = row.get('usage') or {}
        explicit = {key: value for key, value in usage.items() if type(value) is int and value >= 0}
        if not explicit:
            return  # Missing usage is not zero and never releases a reservation.
        total = explicit.get('total_tokens')
        # Installed Google SDK documents total as prompt + candidates + tool
        # prompt + thoughts. Cached input is already part of prompt, not extra.
        components = sum(explicit.get(key, 0) for key in
                         ('input_tokens', 'output_tokens', 'tool_prompt_tokens', 'reasoning_tokens'))
        minimum = max(components, max(explicit.values(), default=0))
        if total is None:
            observed = minimum
        else:
            observed = max(total, minimum)
        final = bool(final and row.get('usage_terminal') and total is not None
                     and total >= minimum and total >= explicit.get('input_tokens', 0) + explicit.get('output_tokens', 0)
                     and not row.get('unparsed_frames') and not row.get('usage_integrity_failed'))
        policy = self._policy(row['model'])
        amount = self._reservation(policy, observed)
        observation = {'type': 'usage_observation', 'http_id': row['http_id'], 'job_id': self.job_id,
            'usage': explicit, 'usage_final': final, 'observed_total_tokens': observed,
            'estimated_cost_microusd_upper_bound': amount['cost_microusd'],
            'cost_basis': 'reviewed_max_rate_all_tokens_not_provider_invoice',
            'response_complete': row.get('response_complete', False),
            'http_status': row.get('http_status'), 'usage_terminal': row.get('usage_terminal', False)}
        observation['usage_integrity_failed'] = bool(row.get('usage_integrity_failed'))
        signature = _digest(observation)
        if self._usage_receipts.get(row['http_id']) == signature:
            return
        receipt_sha = self.evidence.record(observation)
        self._budget('settle_attempt', row['http_id'], actual_tokens=observed,
            actual_cost_microusd=amount['cost_microusd'], cached_input_tokens=explicit.get('cached_input_tokens'),
            usage_evidence_sha256=receipt_sha, usage_final=final)
        self._usage_receipts[row['http_id']] = signature
        # Settlement records true overruns instead of refusing the evidence.
        # Stop this call immediately after that durable record, not only when
        # a later request happens to check the shared campaign ledger.
        self.check()

    def wrap_sync(self, original):
        @functools.wraps(original)
        def run(*args, **options):
            current = self._start(args, options)
            if current is None:
                return original(*args, **options)
            token = self.active.set(current)
            try:
                return original(*args, **options)
            finally:
                self.active.reset(token)
        return run

    def wrap_async(self, original):
        @functools.wraps(original)
        async def run(*args, **options):
            current = self._start(args, options)
            if current is None:
                return await original(*args, **options)
            token = self.active.set(current)
            try:
                return await original(*args, **options)
            finally:
                self.active.reset(token)
        return run
