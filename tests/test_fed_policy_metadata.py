from datetime import datetime, timezone
from pathlib import Path
import sys
from fed_policy_metadata import parse_policy_feed
NOW=datetime(2026,10,31,12,tzinfo=timezone.utc)
RAW=(Path(__file__).parent/'fixtures/fed_monetary_20261031.xml').read_bytes()
def test_actual_original_has_one_recent_policy_release():
    rows=parse_policy_feed(RAW,tag='macro',now=NOW)
    assert len(rows)==1
    assert rows[0]['url'].endswith('monetary20261028a.htm')
    assert rows[0]['article_body_verified'] is False
    assert rows[0]['event_date_verified'] is False
    assert rows[0]['evidence_coverage']=='headline_metadata_only'
def test_semiconductor_and_issuer_context_not_substituted():
    assert parse_policy_feed(RAW,tag='semiconductors_ai',now=NOW)==[]
    assert parse_policy_feed(RAW,tag='supply_chain',now=NOW)==[]
def test_future_and_stale_releases_not_accepted():
    assert parse_policy_feed(RAW,tag='macro',now=datetime(2026,10,27,tzinfo=timezone.utc))==[]
    assert parse_policy_feed(RAW,tag='macro',now=datetime(2026,11,10,tzinfo=timezone.utc))==[]
def test_wrong_host_and_nonpolicy_links_rejected():
    assert parse_policy_feed(RAW.replace(b'www.federalreserve.gov',b'evil.example'),tag='macro',now=NOW)==[]
    assert parse_policy_feed(RAW.replace(b'/pressreleases/monetary',b'/pressreleases/other'),tag='macro',now=NOW)==[]
def test_malformed_oversized_dtd_and_naive_clock_rejected():
    for raw in [b'<rss>',b'x'*1000001,b'<!DOCTYPE rss><rss/>']:
        assert parse_policy_feed(raw,tag='macro',now=NOW)==[]
    assert parse_policy_feed(RAW,tag='macro',now=NOW.replace(tzinfo=None))==[]
def test_window_not_widened():
    assert parse_policy_feed(RAW,tag='macro',now=NOW,lookback_days=8)==[]
    assert parse_policy_feed(RAW,tag='macro',now=NOW,lookback_days=0)==[]
