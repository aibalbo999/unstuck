"""An existing MOPS link must become verified prepared content through the workflow."""
from copy import deepcopy
from types import SimpleNamespace
import sys

import pytest
from data_fetch import earnings_call_fetcher as earnings


def test_nanya_public_workflow_reads_published_content_instead_of_only_link(monkeypatch):
    metadata={'ticker':'2408','date':'2026-09-21','source':'MOPS investor conference','materials':[{'url':'https://mopsov.twse.com.tw/nas/STR/240820260819E001.pdf'}]}
    enriched={**metadata,'documents':[{'document_kind':'presentation','page_count':14}], 'transcript_available':False}
    calls=[]
    def enrich(ticker,context,**kwargs):
        calls.append((ticker,deepcopy(context)));return enriched
    monkeypatch.setitem(sys.modules,'data_fetch.market_sources.nanya_mops_presentation',SimpleNamespace(supports_nanya=lambda t:t=='2408.TW',enrich_nanya_context=enrich))
    monkeypatch.setattr(earnings,'_fetch_official_index_context',lambda *args,**kwargs:deepcopy(metadata))
    result=earnings.fetch_free_earnings_call_context('2408.TW')
    assert result==enriched and calls==[('2408.TW',metadata)]
    assert metadata.get('documents') is None
