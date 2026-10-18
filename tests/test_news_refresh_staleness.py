"""Changed news invalidates old conclusions even when numeric inputs stay fresh."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from report_refresh_diff import refresh_data_diff, refresh_requires_analysis_rerun


def snapshot():
    forum = json.loads((Path(__file__).parent / 'fixtures' / 'finmind-forum-only-news-20261012.json').read_bytes())['data'][0]
    rows = [{"title": f"百一營運新聞 {i}", "link": f"https://publisher{i % 3}.example/news/{i}",
             "date": "2026-10-11T01:00:00+00:00", "source": f"publisher{i % 3}", "summary": "已公布的營運說明"}
            for i in range(7)]
    return {'data': {'current_price': 10., 'revenue_ttm_raw': 1000., 'recent_catalysts': [forum, *rows],
                     'additional_recent_catalysts': []},
            'data_trust': {'status': 'fresh', 'critical_failures': [], 'stale_sources': [],
                           'reason_codes': ['fresh_core_sources']}, 'source_audit': []}


def needs_rerun(old, new):
    return refresh_requires_analysis_rerun(old, new, refresh_data_diff(old, new))


def test_replacing_saved_forum_with_news_invalidates_unchanged_fresh_core():
    old = snapshot(); new = deepcopy(old)
    new['data']['recent_catalysts'][0] = {**new['data']['recent_catalysts'][1],
                                        'title': '百一新的營運說明', 'link': 'https://publisher0.example/news/new'}
    new['data']['unverified_catalysts'] = [old['data']['recent_catalysts'][0]]
    assert needs_rerun(old, new) is True


@pytest.mark.parametrize('field,value', [('title', '百一更正公告'), ('summary', '已撤回先前公布的數值'),
                                       ('date', '2026-10-10T01:00:00+00:00'), ('source', '更正後發布者')])
def test_material_news_revisions_invalidate_same_url(field, value):
    old = snapshot(); new = deepcopy(old)
    new['data']['recent_catalysts'][1][field] = value
    assert needs_rerun(old, new) is True


def test_receipt_refresh_and_same_news_order_do_not_require_extra_models():
    old = snapshot(); new = deepcopy(old)
    new['data']['recent_catalysts'].reverse()
    for row in new['data']['recent_catalysts']:
        row.update(fetched_at_epoch=999999, fetch_id='new-receipt', raw_http_receipt={'new_observation': True})
    row = new['data']['recent_catalysts'][0]
    row['published_date'] = row.pop('date')
    assert needs_rerun(old, new) is False


def test_changed_additional_news_is_material_and_history_archive_is_preserved():
    old = snapshot(); new = deepcopy(old)
    new['data']['additional_recent_catalysts'] = [deepcopy(new['data']['recent_catalysts'][1])]
    assert needs_rerun(old, new) is True


def test_excluded_record_archiving_alone_does_not_require_extra_models():
    old = snapshot(); new = deepcopy(old)
    new['data']['source_record_archive'] = [{'reason': 'original preserved'}]
    new['data']['unverified_catalysts'] = [{'title': 'unverified archived sample'}]
    assert needs_rerun(old, new) is False


def test_new_native_presentation_content_invalidates_old_metadata_only_conclusion():
    old=snapshot();old['data']['earnings_call']={'date':'2026-08-26','summary':'法說會資料連結','transcript_available':False}
    new=deepcopy(old);new['data']['earnings_call']['documents']=[{'document_kind':'presentation','pages':[{'page_number':5,'text':'公司公布本季营运說明'}]}]
    assert needs_rerun(old,new) is True


def test_same_call_evidence_with_new_receipt_only_does_not_require_extra_models():
    old=snapshot();old['data']['earnings_call']={'date':'2026-08-26','summary':'法說會說明','fetched_at_epoch':1,'psc_conference_receipt':{'old':True}}
    new=deepcopy(old);new['data']['earnings_call'].update(fetched_at_epoch=2,psc_conference_receipt={'new':True})
    assert needs_rerun(old,new) is False
