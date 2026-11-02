"""Issuer-linked current job samples never become recruitment/headcount totals."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import time

import pytest

from data_fetch.market_sources.psc_careers_literals import PREFIX, SUFFIX


def literal(value):
    return (PREFIX + json.dumps({'code': 11, 'data': value}, ensure_ascii=True) + SUFFIX).encode()


def fixtures():
    from data_fetch.market_sources import thsrc_careers as s
    now = time.time()
    number = '964508496998000936'
    row = {'id': number, 'custId': s.CUST_ID, 'enable': True,
           'cleanI18nName': '車輛維修技師（燕巢總機廠）'}
    detail = {'id': number, 'custId': s.CUST_ID, 'custNo': s.UBN + '000',
              'coName': s.LEGAL, 'enable': True, 'deleteDate': None, 'closeDate': None,
              'formattedCloseDate': '無', 'job': '車輛維修技師(燕巢總機廠)',
              'formattedCreateDate': '2023/08/30 15:32:03', 'formattedInputDate': '2023/08/30',
              'formattedUpdateDate': '2026/10/28 08:42:29', 'roleString': '全職',
              'needEmpString': '', 'salaryString': '月薪: NT$38,000 ~ NT$40,500',
              'i18nAddressRegion': '高雄市燕巢區',
              'peer': {'i18nDescription': '執行車輛維修工作。', 'i18nOthers': ''}}
    def receipt(raw, key):
        url, method, identity = s.request_identity(key)
        return {'url': url, 'method': method, 'request_identity': identity,
                'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'fetched_at_epoch': now, 'http_status': 200, 'response_complete': True,
                'response_bytes': len(raw)}
    index = ('<html><title>甄選流程 – 台灣高鐵</title><a href="' + s.LISTING_URL + '">我要應徵</a></html>').encode()
    tenant = ('<html><title>職務訊息 - '+s.LEGAL+' - 招募管理系統</title>'
              '<script>var Job = {custId: '+s.CUST_ID+', init: function(){}};</script></html>').encode()
    receipts = [receipt(index, 'index'), receipt(tenant, 'tenant'),
                receipt(literal([1, [row]]), 'listing'), receipt(literal(detail), number)]
    return receipts, detail, now


def change_body(receipt, value):
    raw = literal(value)
    receipt.update(body_b64=base64.b64encode(raw).decode(), sha256=sha256(raw).hexdigest(), response_bytes=len(raw))


def test_linked_individual_job_preserves_dates_and_unknown_headcount():
    from data_fetch.market_sources import thsrc_careers as s
    receipts, _, now = fixtures()
    value = s.parse_jobs(receipts, now=now)
    assert s.verified_job_count(value, s.TICKER, s.LEGAL, s.UBN, now=now) == 1
    assert value['job_count'] is None and value['recent_company_job_count'] is None
    job = value['job_postings'][0]
    assert job['published_date'] is None and job['headcount_text'] is None
    assert job['source_created_at'].startswith('2023/')
    assert job['source_updated_at'].startswith('2026/10/28')
    assert job['title'] == '車輛維修技師(燕巢總機廠)'
    assert job['listing_title'] == '車輛維修技師（燕巢總機廠）'


@pytest.mark.parametrize('field,value', [
    ('custId', '9900000736'), ('custNo', '16446275000'), ('coName', '高鐵工業股份有限公司'),
    ('enable', False), ('deleteDate', '2026/10/30'), ('closeDate', '2026/10/30'),
    ('formattedCloseDate', '2026/10/30'), ('job', '列車駕駛'),
    ('formattedUpdateDate', '2099/01/01 00:00:00'), ('formattedInputDate', '2025/01/01'),
])
def test_wrong_employer_closed_future_and_conflicting_jobs_are_rejected(field, value):
    from data_fetch.market_sources import thsrc_careers as s
    receipts, detail, now = fixtures()
    detail[field] = value
    change_body(receipts[-1], detail)
    with pytest.raises(ValueError):
        s.parse_jobs(receipts, now=now)


@pytest.mark.parametrize('index', range(4))
def test_every_original_must_be_current_complete_and_unchanged(index):
    from data_fetch.market_sources import thsrc_careers as s
    receipts, _, now = fixtures()
    receipts[index]['fetched_at_epoch'] = now - 1800.01
    with pytest.raises(ValueError):
        s.parse_jobs(receipts, now=now)
    receipts, _, now = fixtures()
    receipts[index]['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        s.parse_jobs(receipts, now=now)


@pytest.mark.parametrize('mutation', [
    lambda v: v.update(job_count=36),
    lambda v: v.update(current_open_job_count=36),
    lambda v: v.update(recent_company_job_count=1),
    lambda v: v['job_postings'][0].update(published_date='2026-10-28'),
    lambda v: v['job_postings'][0].update(employer='台灣高鐵子公司'),
    lambda v: v['job_postings'][0].update(headcount_text='36'),
    lambda v: v.update(message='近日新增36人'),
])
def test_projection_is_recomputed_from_originals(mutation):
    from data_fetch.market_sources import thsrc_careers as s
    receipts, _, now = fixtures()
    value = s.parse_jobs(receipts, now=now)
    mutation(value)
    assert s.verified_job_count(value, s.TICKER, s.LEGAL, s.UBN, now=now) == 0


def test_official_link_tenant_and_listing_membership_are_required():
    from data_fetch.market_sources import thsrc_careers as s
    receipts, detail, now = fixtures()
    wrong = deepcopy(receipts)
    raw = base64.b64decode(wrong[0]['body_b64']).replace(b'16446274', b'23218183')
    wrong[0].update(body_b64=base64.b64encode(raw).decode(), sha256=sha256(raw).hexdigest())
    with pytest.raises(ValueError): s.parse_jobs(wrong, now=now)
    wrong = deepcopy(receipts)
    raw = base64.b64decode(wrong[1]['body_b64']).replace(b'1900000134', b'9900000736')
    wrong[1].update(body_b64=base64.b64encode(raw).decode(), sha256=sha256(raw).hexdigest())
    with pytest.raises(ValueError): s.parse_jobs(wrong, now=now)
    wrong = deepcopy(receipts)
    change_body(wrong[2], [1, [{'id': '964508496998000937', 'custId': s.CUST_ID,
                               'enable': True, 'cleanI18nName': detail['job']}]])
    with pytest.raises(ValueError): s.parse_jobs(wrong, now=now)


def test_partial_or_duplicate_listing_never_infers_complete_total():
    from data_fetch.market_sources import thsrc_careers as s
    receipts, detail, now = fixtures()
    row = {'id': detail['id'], 'custId': s.CUST_ID, 'enable': True, 'cleanI18nName': detail['job']}
    for listing in ([36, [row]], [2, [row, row]]):
        altered = deepcopy(receipts); change_body(altered[2], listing)
        with pytest.raises(ValueError): s.parse_jobs(altered, now=now)
