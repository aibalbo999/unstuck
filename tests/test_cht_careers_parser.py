from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from data_fetch.market_sources.cht_careers import parse_index,parse_listing,parse_detail,assemble,INDEX_URL,LIST_URL,canonical_detail_url
NOW=datetime(2026,10,30,13,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()

def index():
 return '''<title>所有職缺 | 中華電信 CHT.com.tw</title><div class="card" data-recruit-details>
 <div class="card-title">中華電信公司115年第27次從業人員(具工作經驗)遴選簡章</div>
 <div class="card-content"><div class="row"><div class="col">用人機構：中華電信股份有限公司</div>
 <div class="col">徵才日期：2026/10/16 12:00 - 2026/11/13 17:00</div><div class="col">總錄取名額：11</div><div class="col">狀態：報名中</div>
 <button onclick="openLink('/home/cht/-/media/web/pdf/recruit-and-training/recruit/2026/11527.pdf?sc_lang=zh-tw','_blank')">完整簡章</button></div></div></div>'''.encode()

def listing():
 text='<title>中華電信 人才招募網</title><h6>115年第27次從業人員（具工作經驗）遴選</h6><div class="cht-col-date"><span>徵才時間：2026/10/16 12:00～2026/11/13 17:00</span></div>'
 for i in range(1,5):
  text+=f'<div class="card cht-Bjob-jobcard"><div class="cht-jobcard-code">代碼：AD0{i}</div><h5>職務{i}</h5><a class="cht-jobcard-action-detail" href="jobdetail.jsp?verno=11510&amp;idno=AD0{i}">詳情</a><a class="cht-jobcard-action-apply" href="login.jsp?verno=11510&amp;dutyno=AD0{i}">應徵</a></div>'
 return (text+'<span>中華電信股份有限公司版權所有 Chunghwa Telecom Co., Ltd. All Rights Reserved</span>').encode('cp950')

def detail(i):
 return f'<title>中華電信 人才招募網</title><h2>職務{i}</h2><div class="cht-jobcard-code">代碼：AD0{i}</div><div class="cht-job-detail-row" name="工作內容"><div class="cht-article-col">本職務負責相關專業工作及專案協調，並依職務條件執行各項業務。</div></div><a id="idBtnJobApply" href="login.jsp?verno=11510&amp;dutyno=AD0{i}">應徵</a><span>中華電信股份有限公司版權所有 Chunghwa Telecom Co., Ltd. All Rights Reserved</span>'.encode('cp950')

def bodies():return {f'https://rmis.cht.com.tw/portal/jobs/jobdetail.jsp?idno=AD0{i}&verno=11510':detail(i)for i in range(1,4)}

def test_exact_live_batch_and_three_individual_jobs_are_a_bounded_sample():
 out=assemble(index(),listing(),bodies(),now=NOW)
 assert out['status']=='success'and out['verified_sample_job_count']==3
 assert out['current_open_job_count'] is None and out['job_count'] is None
 assert out['coverage_status']=='partial'and out['first_publication_verified'] is False
 assert [j['job_id']for j in out['job_postings']]==['AD01','AD02','AD03']
 assert all(j['employer']=='中華電信股份有限公司' and j['application_start']=='2026-10-16T12:00:00+08:00'and j['application_end']=='2026-11-13T17:00:00+08:00'for j in out['job_postings'])

@pytest.mark.parametrize('old,new',[
 ('用人機構：中華電信股份有限公司','用人機構：中華電信子公司'),
 ('狀態：報名中','狀態：已截止'),('2026/11/13 17:00','2026/10/20 17:00'),
 ('2026/10/16 12:00','2026/11/01 12:00'),('11527.pdf','11528.pdf'),
 ('中華電信公司115年第27次','中華電信公司114年第27次')])
def test_index_rejects_incompatible_employer_state_period_and_document(old,new):
 raw=index().decode().replace(old,new).encode()
 with pytest.raises(ValueError):assemble(raw,listing(),bodies(),now=NOW)

@pytest.mark.parametrize('old,new',[
 ('115年第27次','115年第26次'),('2026/10/16 12:00','2026/10/17 12:00'),
 ('版權所有','代理徵才'),('verno=11510','verno=11410'),('idno=AD01','idno=AD02')])
def test_listing_cannot_change_the_source_owned_batch_or_job_identity(old,new):
 raw=listing().decode('cp950').replace(old,new).encode('cp950')
 with pytest.raises(ValueError):assemble(index(),raw,bodies(),now=NOW)

@pytest.mark.parametrize('kind',['wrong_title','wrong_job','missing_apply','missing_body','invalid_encoding'])
def test_detail_requires_the_exact_posting_and_complete_body(kind):
 bs=bodies();url=next(iter(bs));raw=bs[url]
 if kind=='invalid_encoding':raw=b'\x81'
 else:
  s=raw.decode('cp950');s=s.replace('職務1','其他職務')if kind=='wrong_title'else s.replace('代碼：AD01','代碼：AD09')if kind=='wrong_job'else s.replace('id="idBtnJobApply"','id="unbound"')if kind=='missing_apply'else s.replace('本職務負責相關專業工作及專案協調，並依職務條件執行各項業務。','')
  raw=s.encode('cp950')
 bs[url]=raw
 with pytest.raises((ValueError,UnicodeError)):assemble(index(),listing(),bs,now=NOW)

@pytest.mark.parametrize('url',[
 'http://rmis.cht.com.tw/portal/jobs/jobdetail.jsp?idno=AD01&verno=11510',
 'https://example.com/portal/jobs/jobdetail.jsp?idno=AD01&verno=11510',
 'https://rmis.cht.com.tw/portal/jobs/jobdetail.jsp?idno=AD01&idno=AD02&verno=11510',
 'https://rmis.cht.com.tw/portal/jobs/jobdetail.jsp?idno=AD01&verno=11510&token=secret'])
def test_detail_url_cannot_escape_the_published_public_contract(url):
 with pytest.raises(ValueError):canonical_detail_url(url)

def test_future_published_batch_is_discovered_without_code_or_id_changes():
 def future(b,enc):return b.decode(enc).replace('2026','2027').replace('115','116').encode(enc)
 out=assemble(future(index(),'utf-8'),future(listing(),'cp950'),{u.replace('11510','11610'):future(b,'cp950')for u,b in bodies().items()},now=datetime(2027,10,30,13,tzinfo=ZoneInfo('Asia/Taipei')).timestamp())
 assert out['verified_sample_job_count']==3 and out['batch_id']=='11627'

def test_application_closes_at_the_published_deadline():
 end=datetime(2026,11,13,17,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
 assert assemble(index(),listing(),bodies(),now=end-1)['verified_sample_job_count']==3
 with pytest.raises(ValueError):assemble(index(),listing(),bodies(),now=end)
