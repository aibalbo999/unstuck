"""Fubon official presentation with distinct event and document dates."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import csv
import io
import json
import re
import time
import zlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
from .official_issuer_master import JSON_URL
from .fubon_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2881.TW'
LEGAL = '富邦金融控股股份有限公司'
UBN = '03374805'
POLICY = 'fubon-original-presentation-v1'
PROJECTION_POLICY = 'fubon-presentation-role-v1'
KNOWN_SHA = '1d5c9d3b81ba65e5c089910da6261735d4032d33c7de9ed03fc541f706a1594c'
PAGE_TEXT_SHA256 = ('b55f4fefc431452bba2597cf9c21a04ad8d2884777d461208f06734578745a4c', 'e8609aa8ad057d1deaa1ce21a1c1ac51b2e771ef7c3070f20d74e41c87526509', 'b1b4d8e48684693efedb9a96f947d7047cc10295c5cb7d64afedd437e8158201', '4838fcbd19c8b97b05b5e120dc25aeb0f71f29574a5b12fa5fdaa4de866de181', '7c08ad61db1ddeace397c728b0612e7221d53d16db6d294245364c971fe95e0d', '5c0a350389cc0591eb72e1a5a93886b8afad9cd31124cf89847309ff9ca86cdb', 'c2bd4f18012c93d045762fa3e0f43ca37eefd8471684f106929c228828ffd37c', 'b48090d0b00ee9c3a91f73a285b63366e65eb0ec4b25c5e476cd215e56d7b4b4', '9cdc1c7aeaf3fc458d68fef1711cd369941e41ec78c0e5cb2a52fced9f4dcc6d', 'a3e5ae9a21aa56b3f09ae2c5739e6e539d516798ff8d9f0c882a937985aacdb3', 'db976382bc1e2e1c2dc78dccd37fcccb5bb84fbd49ca448ba6fd0130553e054c', '260aa02645d7d1d4211d27616aee9d047f22185822a3feffed51132e5598c102', '868e4d94ef9d86a75d924a25c32022bbfb0e27fc87b775b6cca935f43534566b', 'a7e662cbc444d81733f235496cba3af1740a4e23f1bfb524f5633a1ab879d76c', 'ce41480b8907048a87fb11f6ff98431595574eda16bb93fb5a78682fd8e8e2ec', '925bd450a8f6ca984de6b09e2a46cd0f15ebdd270378ae80e1d66fd9f2b7236e', '9ba87339d6bd4c4fe01f5dcd4fba5fb5df9ea8318abd3ea19f2bd691ce7c1e2f', 'c2397d70dc8c08bf899aea475650cc31f866b64c0251c97c256a8b9e34005766', 'e645f0bf08903e6fe191a46473cf47ebdd60e4fcd2c2706b570b5b42fc12cfcd', '738c7c8638dcc45f1cd7e9d8a786da4a3776c7186e373e768e31382bb07f685d', '7bb01661fc7ee22a30bb1e1de5d2acf54cbe86cbd72bb422ca9c4a0c754b0aaf', '8900c9c3ec7247ac2c6db16123bbb3aa80c97634b4d1d53a498eb2df87005260', '9022c58c4fb12a0bded96d7da2ef01909f3d12eae2da1b8280feea0aa269ad80', '5e0559c35edbba0345e9f70dcba4a45c1da08322a15495840fab453d45677d75', 'adbcd7a1bc2d160d2e1bfe13fcafbcb3dee517a10b0f641bd9c536d3ed0d71da', 'b56434ab6c082b4079176d47d05c76110ba77ca81c3c09a38a9674649efeac2e', '977da02730c84dcb1c0e164de05ab70518c89bab2f053d4e887028b9f8df3787', '8f7a466e31d28d2bca1c78bf4115b1ec14c621340067a73781de1d3371d58004', '00e5274656a4b7628f3bed722f30c3a34b1a3599cee3d474921e582e396e202a', '2a3ae3bc40fc92ae8fcb6fdb17e33d67d28c445cc7df1a7e7d6a72baae0ac5ec', '4389d1057f966664ef00c3d5d0ecd88c07afb7c9b1aec89d5910d101c79dbdda', '8d168bf304e019b4a138f7acb45698242acf1cd5b9387338e4f3dab40b74d2be', '355e4dd564fa49c0785a7095217a5fe581aef4992b1720d7e9b309467e917576', 'c7984ab5ab14a77195b13db408a353026c879cad352bd079685f181c81a2f6c4', '37ed24a8382f0f1ce675989bc64bacd0c391354bb3b6b6ff93525c549898f386', 'ca929fa35c3a2c1d873117b497ebbce28c715a1795b923ec3ee801d63b2ed76e', '587261a8919a1d583fec87fb32a64df6aa5d437062dc3e3bfa03f0ad2cfa455d', '08d3b2a0258166af65ff85f0a1eb24f55bbb600f9a2625be02dab23ef9a3cd77', 'd0dfcf270bc34766defac350aa616adf00036708279879ef8dacdbca5d25f80e', 'fd5248db40a96b8fd5fcb65d9e6db816ebc17f3be048221569e4d8726fce36b1', 'cd88a195a06d44da2e051cc39ba3b98f3ba71aba72bd913ab4b6cd6a5341bbe5', 'ff8de08594f1d423b89f7990d2e4ecbdd14b9bfcb9619f6f3d2d4933f8b222cd', '1996a1530a995e879aa1e85a3035da107b446dee4e5f65f12cd66389029e3d38', '5fd96ba4689924978f4545ea0bf9c5a40438a81cb31b20da80836f57223726c0', '5cbadfa4dcab2447c264baa8f969b23b698628eb2ee93613741582972938c406', '831ba8f9919f85aae37d6c7a0936db4f48075e487f7aafca989b672ab6cf47fc', '6c9d23460b96624ab0f1542db1dfaa56c23951bb8156ef54946a25bb55c6f2f6', '7311c9dd7b26d1e22cc7f3d1457d6ff63492a639d780cc076dcb5d40444c7575', '9ce8561bd11971ee3619eef88559c913a3de54969288555e84bbd215cbc8dab4', '1708b894ac6d24e7d94457c73e49a13bc63500139116ef7a76d1eaf73bbf42cb', '271b1bed07902d3e747b000aec9f4f4252fb31d5a8935befdb01fc223acc8301', '8f07375a8ad15237d5a522bf24dc0f7919b16e61a169bbe3b12922ef58770d52', 'f2d81b5ef1d2955fe50d6badd5df42b17b2e98691a68537fd4db3acd7a44c39d', '424b7019194271107912db3255734bdc90ff35f90d94a4ee80df3c073c70b3aa', 'd3ddb7d111592ef7781f0fe763d7c4dedc26d9c9384aa226cc9a4f351ffc69c0', '7bbadb736cd1c379cf4e50eb7fbd8a98d16fccd658e108e2796a05d423c380b5', 'c0e0ee18e0b3595ecc2a59ce56ded48d39c49fb1c9b4619db536ec384fb4974a', 'f3c492e11f0a1dddd1484e4fb1c28f2719896d8d4a357ffb93c49286e9f32ccf', '37301eadc6d70098189f99ba7fe09a32214d73d68f0ede08682d2b2d437f1dc1', 'd29f00c805e89ec73b7a026f14eccf50c70edeb138dd0e0e36c24e9300bf4eb2', 'f599b55917be3e960a76c5b88baad7512ca8110a6b672486635db49d1bf363f9', 'd518a2405f29cacf4af5800cc181fb601faf0ccb1b805c8e9d6e866fbcb45746', 'bbabd0c3fc963b839c77e3d3608443d8935bdc993c3b7903150cf439a7150dd7', '25b5505b494cb54cae60829d3430a5121dcc949363ceabed48e962390172feed', 'e92c659923aedc7f0e7d7e39bb6073b649db1a72010ce4f3bea341c97a0575ee', 'e23d1a55c84c64da6609f0d15de8cd33a82bd0391d01d931f5eeef086a4d0920', '07d6db2c65bb70671956b54a25817e46c0b0a309e6c54ff29bd25b0954995983', '56291e7265a92d54c6a092564d148426b7dd37434a27dae432906cec46d1c26e', '04566d7f6ff6fc035d66b378604920a8bdc1d18dc4ab6be03240b6f6addadbe2', '8b2f2b931715ae4125d260b6ed68874e4f53f1cc6f8d7caf908b54dc04fd1600', 'eafd8ff5075a530d102252f8380a858884969ee36dd9437a482c14435a8da66f', '80bfbc249ad77a9899820b8c21de73cd26c765f7674161d39a1c0f9ef7942d45', 'd2342c1c35c4534feb790846e8996c739746c6b599fe9ec4e641b4413df867e6', '450b4bb3bcedc1cf93bd7704573be246a061923cfd7a30c5c9b52141389efc99', '5615ce88348755ebcb2b4b6882207c611cd5059458598c29f4bcb65d6b73b27f', 'e84a33997483ac8715962e3e3bde55a064f60f97b1a26ad69ce294727b46c5c0', '44859de6f07d9029ba4e7aa06cc8b5d136d9a86f3260d2f54faa65067e849ba1', '86a8e551911966a287cda1cec3943bb2faac08f75b8c99714c3668b47eb384dd', '0ad0f7c5162d7b3819c47b5d46d2dd46ebf31296f3ae64964cbffecf0d3493d4', '1bea46b0d602c91150e312406091bb66f3424162ece0eed4878eb20a0d2304d1', '74ec1d2acc25fb607ecac3ec2de1af3f035e8db07568787a3a6c5c607a86dabe', 'd0a03fd8ca9ee1a6373ee5f2888abe6717af834936eb764ac06d56a86fea9c72', '5c0632bbde8742de8e3c58d83a604a5641bf5fdfa758bf60bb5f54def9935ce2', 'f92ce41c8a67ac6b6b6eb9124bda2fd249b3a90a4165fadedaf6cc1dfc5d55dd', 'a49e1cd6edf5f5fec0b4718a0da8752916f8f9c25c2aaaa6a77c1f9d837731dd', 'ab4e7e025e36b01e5ecf9110c69f5ec8f5095cb0520ff6207452f81a46207db9', 'f115886e868198316b06c74febc44fd3de50925700efaadab8da82ec4722f4fe', '926d58dc535fc92adc963777de5b469c2c615c5e06c973d5451285df48e4c5fd', '90f662e786e8b4c150466552dc6a3276e575cf644f5233c1322df7bb7ecb0e1f', 'f11b355543e14370cc205bcb17875bd075cca199b029b8f9001f1887d137cc77', 'd35d08d26be6d42075d9ec489a0a8818ccf69184c8465f2c6003d8dccb86c433', '5c330ab670d0005babf3e090cefd9462336ddb0ac15ae6dda11bd8d1b5627b9c', 'f9218e6d49e6f04e087a9dd1b808afa9e561491efe348841c91b128a8bd0cfd3', '604643964d339548f39c9240fe30b041c006ba5f72f8e4e1264d639d8d729ed8')
ROLE_PAGES = (1, 2, 3, 17, 18, 25, 26, 34)
NOTE = '富邦金9/22至9/23場次之9/2檔名英文94頁原件；主題1H26，附錄封面8/24。原生文字94頁完整，整體語意coverage仍partial；角色限1/2/3/17/18/25/26/34完整頁及免責聲明。金控、壽險、銀行單獨及產險範圍不可混用；不當作完整年度財報或逐字稿。'

def supports_fubon(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2881', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_fubon_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Fubon master size invalid')
    if source_url == JSON_URL:
        from .official_issuer_master_json import parse_rows
        rows = parse_rows(raw, epoch); fields = list(rows[0])
    elif source_url == MASTER_URL:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
        rows = list(reader); fields = reader.fieldnames
    else:
        raise ValueError('unqualified master URL')
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('Fubon complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2881']
    if len(matched) != 1:
        raise ValueError('Fubon master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '富邦金融控股股份有限公司', '公司簡稱': '富邦金', '營利事業統一編號': '03374805', '網址': 'www.fubon.com'}
    # Accept official master padding without changing the issuer name.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'Fubon Financial'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Fubon master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Fubon master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '富邦金', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '富邦金2026年9月22日至23日法人說明會英文簡報', 'pdf_url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'event_date': '2026-09-22', 'document_date': '2026-09-02', 'cover_month': None, 'period_label': '2026H1', 'filename': '288120260902E001.pdf', 'language': 'en', 'selection_policy': 'latest_exact_MOPS_published_english_attachment', 'history_scope': 'Current2026 index is fully parsed; newer event or changed attachment requires qualification; Chinese and English originals stay separate'}
CURRENT_DESCRIPTOR = {'ticker': '2881.TW', 'symbol': '2881', 'company_name': '富邦金', 'event_date': '2026-09-22', 'event_end_date': '2026-09-23', 'event_time': '13:00', 'event_location': '香港', 'event_summary': '討論富邦金控財務及業務相關資訊', 'material_file_date': '2026-09-02', 'filename': '288120260902E001.pdf', 'format': 'pdf', 'language': 'en', 'row_sha256': 'fd074dff5847141bc301ca3f1ee572fffbcbf8cfd5c1ceb1890306c8d9025722', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'method': 'POST', 'request_body': 'step=9&filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&fileName=288120260902E001.pdf&functionName=t100sb02_1', 'request_sha256': '3e24563ba1de175f127c90e2fdb49cec15d3c9a2e38a2e6d357741b1d46d1264'}

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from mops_published_materials import select_published_material
    selected=select_published_material(raw,TICKER,as_of_epoch=epoch,company_name='富邦金')
    current=select_published_material(raw,TICKER,as_of_epoch=time.time()if as_of_epoch is None else as_of_epoch,company_name='富邦金')
    if not selected or current!=selected or {k:v for k,v in selected.items()if k!='index_sha256'}!=CURRENT_DESCRIPTOR:
        raise ValueError('latest published event or attachment changed')
    day=date.fromisoformat(selected['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch)or not 0<=(_today(as_of_epoch)-day).days<=370:
        raise ValueError('published event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 94
DOCUMENT_METADATA = {'document_id': '2881:2026-09-22:1d5c9d3b81ba65e5', 'ticker': '2881.TW', 'source': 'Fubon published conference presentation', 'source_type': 'regulated_issuer_presentation', 'document_kind': 'presentation', 'projection_policy': 'fubon-presentation-role-v1', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'language': 'en', 'event_date': '2026-09-22', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': '13:00', 'event_timezone': None, 'published_at': None, 'material_file_date': '2026-09-02', 'presentation_cover_month': None, 'content_period': '2026H1', 'content_periods': ['Main deck: 1H26 financial results', 'Taipei Fubon Bank: standalone as of 2Q26', 'Appendix pages43-94: 1H26 interim results; cover2026.08.24', 'Prior-period comparisons retain original IFRS4/IFRS17 accounting bases'], 'content_sha256': '1d5c9d3b81ba65e5c089910da6261735d4032d33c7de9ed03fc541f706a1594c', 'page_count': 94, 'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [], 'role_page_allowlist': [1, 2, 3, 17, 18, 25, 26, 34], 'excluded_native_text_pages': [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94], 'native_editorial_caution': 'All94 pages of the current published English original are retained unchanged. All pages have native text, but this does not verify every visual or table relationship. Roles receive only eight whole pages1/2/3/17/18/25/26/34; original callout order and disclaimer are preserved.', 'index_reuse_caution': 'Latest complete MOPS2026 index selects English288120260902E001.pdf for September22-23event in Hong Kong. Event time13:00 is as published; timezone is unspecified. September2 filename date is not an independently verified first-publication timestamp. Appendix coverAugust24 differs from event date; do not replace this94page original with the older52page issuer-host original.', 'forward_looking_caution': 'Preserve complete page2 disclaimer. Unaudited figures, rounding, forward-looking statements, strategies, ESG and market rankings remain issuer claims, not independently verified facts or realized forecasts.', 'period_scope_caution': '1H26 main results, Taipei Fubon Bank standalone as of2Q26, prior periods and September22-23event remain distinct. Appended results cover2026.08.24 is not the current event date. IFRS17 and IFRS4 amounts and ratios are not interchangeable.', 'unit_scope_caution': 'Keep NT$ billions, percent, YoY, card counts and numbered strategy labels distinct. Callout numbers on18/26/34 label items, not financial values or an inferred native-text ordering. Do not infer FX conversion, denominators, or omitted values.', 'visual_semantics_caution': 'Eight visually checked whole native-text pages feed roles. Other86 pages remain in the original only. Chart/pie/table cross-column, multi-year and IFRS4/17 relationships are not role-qualified; all94native pages do not mean complete visual coverage.', 'financial_scope_caution': 'Financial holding company, Fubon Life, Taipei Fubon Bank and Fubon Insurance are distinct scopes. Pages17/18 are Life,25/26 Bank standalone,34 Insurance. Never assign subsidiary metrics to the holding company. Prepared presentation is not complete audited five-year statements, and cannot fill missing annual cash-flow or intangible purchase values.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native MOPS index and published POST attachment; immutable private evidence, no response cache reuse', 'publisher_notice': 'Copyright notices preserved verbatim per page; public download does not prove commercial reuse permission.', 'filename': '288120260902E001.pdf', 'request_method': 'POST', 'event_end_date': '2026-09-23', 'appended_results_cover_date': '2026-08-24'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_fubon_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete'or native['empty_pages']!=[]or native['garbled_pages']
            or native['page_count']!=PAGE_COUNT or len(native['pages'])!=PAGE_COUNT
            or [p['page_number']for p in native['pages']]!=list(range(1,PAGE_COUNT+1))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected!=QUALIFIED_SELECTED):
        raise ValueError('complete original projection invalid')
    return native

def _context(selected,native,proof):
    doc=deepcopy(DOCUMENT_METADATA)
    doc.update(title=selected['title'],retrieved_at_epoch=proof['pdf']['retrieved_at'],pages=deepcopy(native['pages']),
               parser_version=native['parser_version'])
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026H1','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'en','filename':QUALIFIED_SELECTED['filename'],'request_method':'POST'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'fubon_conference_receipt':proof}

def role_pages(document):
    if not isinstance(document,dict):return []
    try:
        native={k:document[k]for k in ('pages','parser_version')}
        expected=_context(QUALIFIED_SELECTED,native,{'pdf':{'retrieved_at':document['retrieved_at_epoch']}})['documents'][0]
        if json.dumps(document,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return []
    except (KeyError,TypeError,ValueError):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=PAGE_COUNT:return []
    for n,p in enumerate(pages,1):
        if not isinstance(p,dict)or type(p.get('page_number'))is not int or p['page_number']!=n or not isinstance(p.get('text'),str)or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]:return []
    return deepcopy([p for p in pages if p['page_number']in ROLE_PAGES])


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_fubon(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['fubon_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        identity_url=proof['identity']['source_url']
        parse_master(original_bytes(proof['identity'],identity_url,max_age=max_age),proof['identity']['retrieved_at'],identity_url)
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_fubon_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_fubon(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'fubon_presentation_workflow':True}
    try:
        http.check_index_guard()
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        selected,index = http.get_receipt(INDEX_URL,parser=lambda raw,r:select_presentation(raw,r['retrieved_at']));_check(deadline)
        native,pdf = http.get_receipt(PDF_URL,parser=lambda raw,r:native_presentation(raw,selected,deadline))
        proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(fubon_originals_verified=True,coverage_status='qualified_partial_presentation',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
        if diagnostics is not None:diagnostics.update(details)
        # Diagnostic delivery and scheduler delay belong to the same budget.
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        _check(deadline)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        for key in ('coverage_status','cache_hit','stale','fetched_at_epoch'):
            details.pop(key,None)
            exc.diagnostic.pop(key,None)
            if diagnostics is not None:diagnostics.pop(key,None)
        details.update(fubon_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity = data.get('company_identity')
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','2881'),('official_name','富邦金'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'富邦金', LEGAL, 'Fubon Financial Holding Co., Ltd.', 'Fubon Financial Holding Co.,Ltd.', 'FUBON FINANCIAL HLDG CO LTD', 'Fubon Financial'}
    names = {name.casefold() for name in names}
    aliases = names | {'2881','2881.tw'}
    def good_name(name, allowed):
        return isinstance(name,str) and all(s.strip().casefold() in allowed for s in name.split(' / '))
    for key in ('company_name','raw_company_name'):
        if data.get(key) is not None and not good_name(data[key],names):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key,[])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows):return False
        if key != 'forbidden_aliases' and any(not good_name(s,aliases if key=='allowed_aliases' else names) for s in rows):return False
    for key in ('display_name','company_name'):
        if identity.get(key) not in (None,'') and not good_name(identity[key],names):return False
    forbidden = {part.strip('* ').strip().casefold() for s in identity.get('forbidden_aliases',[]) for part in s.split(' / ')}
    return not (aliases & forbidden)


def is_marked(value):
    return isinstance(value,dict) and ('fubon_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL and value.get('ticker') == TICKER or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL and d.get('filename') == QUALIFIED_SELECTED['filename']
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
