"""A full historical original can retain partial text without admitting images."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

D = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261103/taidoc-mops'


@pytest.fixture(scope='module')
def original():
    from source_pdf_reader import extract_pdf_pages
    raw = (D / 'research-material.pdf').read_bytes()
    return raw, extract_pdf_pages(raw, timeout_seconds=10), json.loads((D / 'research-material.json').read_text())['selected']


def test_exact_original_preserves_image_only_financials_and_trial_qualification(original):
    from data_fetch.market_sources.taidoc_mops_qualification import qualify_native, qualified_projection, NOTE
    raw, native, selected = original; before = deepcopy(native)
    assert qualify_native(raw, native, selected) == '2025Q3'
    projection = qualified_projection(native['pages'])
    assert projection['role_page_allowlist'] == {'3': [1, 3, 11], '5': [1, 3, 8, 9, 11], '12': [1, 3, 11]}
    assert all(n in projection['projection_excluded_pages'] for n in [4, 5, 6, 7, 10, 14, 16, 17, 18, 22])
    assert native == before and native['coverage_status'] == 'partial' and native['garbled_pages'] == [14]
    assert '2025.01~09' in NOTE and 'In Clinical Trials' in NOTE and '影像' in NOTE
    assert '不等於100%' in NOTE and '首次發布日未知' in NOTE


@pytest.mark.parametrize('key,value', [('ticker', '4736.TWO'), ('symbol', '4737'), ('company_name', '豪展'),
    ('event_date', '2026-11-21'), ('event_end_date', '2025-11-22'), ('event_time', '14:00'),
    ('material_file_date', '2025-11-20'), ('filename', '473620251121M001.pdf'), ('language', 'zh'), ('format', 'pptx')])
def test_different_issuer_period_or_attachment_requires_new_qualification(original, key, value):
    from data_fetch.market_sources.taidoc_mops_qualification import qualify_native
    raw, native, selected = original; selected = {**selected, key: value}
    with pytest.raises(ValueError): qualify_native(raw, native, selected)


@pytest.mark.parametrize('damage', ['raw', 'page_count', 'missing_page', 'image_page_text', 'trial_label',
    'garbled_metadata', 'coverage', 'bool_page'])
def test_changed_or_incomplete_material_cannot_reach_roles(original, damage):
    from data_fetch.market_sources.taidoc_mops_qualification import qualify_native
    raw, native, selected = original; native = deepcopy(native)
    if damage == 'raw': raw += b'changed'
    elif damage == 'page_count': native['page_count'] = True
    elif damage == 'missing_page': native['pages'].pop()
    elif damage == 'image_page_text': native['pages'][4]['text'] += '\nAudited EPS 6.43 current TTM'
    elif damage == 'trial_label': native['pages'][10]['text'] = native['pages'][10]['text'].replace('In Clinical Trials', 'FDA Approved')
    elif damage == 'garbled_metadata': native['garbled_pages'] = []
    elif damage == 'coverage': native['coverage_status'] = 'complete'
    else: native['pages'][0]['page_number'] = True
    with pytest.raises(ValueError): qualify_native(raw, native, selected)
