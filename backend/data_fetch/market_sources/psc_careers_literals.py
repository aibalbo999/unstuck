"""Decode one public DWR data callback without evaluating JavaScript."""
from __future__ import annotations

import json
import math
import re

MAX_BYTES = 500_000
PREFIX = ('//#DWR-INSERT\n//#DWR-REPLY\n//#DWR-START#\n(function(){\n'
          'if(!window.dwr)return;\nvar dwr=window.dwr._[0];\n'
          'dwr.engine.remote.handleCallback("0","0",')
SUFFIX = ');\n})();\n//#DWR-END#\n'
IDENTIFIER = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*')
NUMBER = re.compile(r'-?(?:0|[1-9]\d{0,20})(?:\.\d{1,20})?(?:[eE][+-]?\d{1,3})?')


class _Reader:
    def __init__(self, text):
        self.text, self.i, self.nodes = text, 0, 0
        self.json = json.JSONDecoder()

    def ws(self):
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def take(self, token):
        self.ws()
        if not self.text.startswith(token, self.i):
            raise ValueError('unexpected DWR literal token')
        self.i += len(token)

    def value(self, depth=0):
        self.nodes += 1
        if depth > 20 or self.nodes > 50_000:
            raise ValueError('DWR literal bounds exceeded')
        self.ws()
        if self.i >= len(self.text):
            raise ValueError('truncated DWR literal')
        c = self.text[self.i]
        if c == '"':
            value, self.i = self.json.raw_decode(self.text, self.i)
            return value
        if c == '{':
            self.i += 1
            out = {}
            self.ws()
            if self.text.startswith('}', self.i):
                self.i += 1
                return out
            while True:
                self.ws()
                if self.i >= len(self.text):
                    raise ValueError('truncated DWR object')
                if self.text[self.i] == '"':
                    key = self.value(depth + 1)
                else:
                    match = IDENTIFIER.match(self.text, self.i)
                    if not match:
                        raise ValueError('invalid DWR literal key')
                    key, self.i = match.group(), match.end()
                if key in out:
                    raise ValueError('duplicate DWR literal key')
                self.take(':')
                out[key] = self.value(depth + 1)
                self.ws()
                if self.text.startswith('}', self.i):
                    self.i += 1
                    return out
                self.take(',')
        if c == '[':
            self.i += 1
            out = []
            self.ws()
            if self.text.startswith(']', self.i):
                self.i += 1
                return out
            while True:
                out.append(self.value(depth + 1))
                self.ws()
                if self.text.startswith(']', self.i):
                    self.i += 1
                    return out
                self.take(',')
        for literal, value in (('true', True), ('false', False), ('null', None)):
            if self.text.startswith(literal, self.i):
                self.i += len(literal)
                return value
        # Date is a serialized DWR data literal, not a permitted JS call.
        if self.text.startswith('new Date(', self.i):
            self.i += len('new Date(')
            millis = self.value(depth + 1)
            if type(millis) is not int or abs(millis) > 8_640_000_000_000_000:
                raise ValueError('invalid DWR Date literal')
            self.take(')')
            return {'dwr_date_epoch_ms': millis}
        match = NUMBER.match(self.text, self.i)
        if not match:
            raise ValueError('executable or unsupported DWR literal rejected')
        value, end = self.json.raw_decode(self.text, self.i)
        if end != match.end() or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('non-finite DWR number')
        self.i = match.end()
        return value


def decode_public_callback(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('DWR response size invalid')
    text = raw.decode('utf-8').replace('\r\n', '\n')
    if not text.startswith(PREFIX) or not text.endswith(SUFFIX):
        raise ValueError('unknown DWR wrapper')
    reader = _Reader(text[len(PREFIX):-len(SUFFIX)])
    value = reader.value()
    reader.ws()
    if (reader.i != len(reader.text) or not isinstance(value, dict)
            or type(value.get('code')) is not int or value['code'] != 11 or 'data' not in value):
        raise ValueError('DWR callback result invalid')
    return value
