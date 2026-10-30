"""Offline public checks; original-data replay remains in the local private corpus."""
"""Read-only review probes: real saved originals, isolated public refresh seams."""

import asyncio

from copy import deepcopy

from datetime import datetime, timezone

import hashlib

import json

from pathlib import Path

import shutil

import sys

import time

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'scripts/project_python.sh').exists())

sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'tests')]

from data_fetch.annual_financial_source_provider import HISTORY_FIELDS, SCHEMA, project_source_value

from data_fetch.service import StockDataService

from fastapi import HTTPException

from report_refresh_service import refresh_report_data_snapshot

from report_persistence import report_bundle_keys_for_filename

from storage.report_storage import InMemoryStorage

from test_report_refresh_acquisition_audit import init_db, events

FILENAME = '2308_TW_v1_report_20261009_015945.html'

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def saved_bundle(old, filename=FILENAME):
    storage = InMemoryStorage()
    keys = report_bundle_keys_for_filename(filename)
    for key,body,kind in [(keys.html_key,b'original report unchanged','text/html'),
                           (keys.md_key,b'original markdown unchanged','text/markdown'),
                           (keys.data_key,json.dumps(old,ensure_ascii=False).encode(),'application/json')]:
        storage.save_report(key,body,content_type=kind)
    return storage,keys
