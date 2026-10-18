"""Qualified originals' observed xref-to-LF defects, never generic warning suppression.

The bytes and their xref remain untouched. Every visited object header must bind
its number/generation to the original offset; all recorded observations must
match before any recovery evidence is returned. All other diagnostics are fatal.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import re

CONTENT_SHA256 = 'df2e5df2eed796be2286edeb8566b1a5b84615e9b675ef2f123e12977a024e6b'
OBSERVATIONS_SHA256 = '9c05eaeb25e2f42a0a8036acc1fac72bbf203bfa4385f8f55aba298e45597764'
WARNING_COUNT = 217
POLICY = 'exact-original-xref-leading-LF-v1'
QUALIFIED_ORIGINALS = {
    CONTENT_SHA256: (WARNING_COUNT, OBSERVATIONS_SHA256),
    'b58d8c9416118f949518e963600d7e9897670345af42e9006e4529c4b518fe7f':
        (99, 'dbc039eea6e8165fd12fa91bc5d18f09d20365d6ba34c9b056c03d586f97d3a2'),
}

def _evidence(digest=CONTENT_SHA256):
    count, observations = QUALIFIED_ORIGINALS[digest]
    return {'policy': POLICY, 'content_sha256': digest,
            'warning_count': count, 'observations_sha256': observations,
            'raw_bytes_modified': False, 'generic_warning_suppression': False}

def valid_evidence(value, digest):
    try:
        return (digest in QUALIFIED_ORIGINALS and isinstance(value, dict)
                and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(_evidence(digest),sort_keys=True,allow_nan=False))
    except (TypeError,ValueError):
        return False

class HeaderWhitespaceQualification:
    def __init__(self, raw):
        self.raw = raw
        self.digest = sha256(raw).hexdigest()
        self.enabled = self.digest in QUALIFIED_ORIGINALS
        self.count, self.observations_sha = QUALIFIED_ORIGINALS.get(self.digest, (0, None))
        self.active = None
        self.observations = []

    @contextmanager
    def header(self, stream):
        previous = self.active
        self.active = None
        if self.enabled:
            offset = stream.tell()
            prefix = stream.read(64)
            stream.seek(offset)
            match = re.match(rb'\n([1-9][0-9]{0,5}) (0) obj\n', prefix)
            if match and prefix == self.raw[offset:offset+64]:
                self.active = (offset, int(match[1]), int(match[2]))
        try:
            yield
        finally:
            self.active = previous

    def accepts(self, record):
        if not self.enabled or self.active is None or record.name != 'pypdf._reader':
            return False
        offset, number, generation = self.active
        expected = f'Superfluous whitespace found in object header {str(number).encode()!r} {str(generation).encode()!r}'
        observation = [offset, number, generation]
        if (record.getMessage() != expected or len(self.observations) >= self.count
                or observation in self.observations):
            return False
        self.observations.append(observation)
        return True

    def evidence(self):
        if not self.enabled:
            return None
        encoded = json.dumps(sorted(self.observations),separators=(',',':')).encode()
        if len(self.observations) != self.count or sha256(encoded).hexdigest() != self.observations_sha:
            raise ValueError('PDF original object-boundary observations differ')
        return _evidence(self.digest)
