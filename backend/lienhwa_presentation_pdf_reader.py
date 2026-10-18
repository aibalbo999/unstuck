"""One exact Lien Hwa PDF: all native pages retained, image/covered text incomplete."""
from __future__ import annotations
import copy,hashlib,json,math
from pathlib import Path
import sys,time
from source_pdf_reader import SourcePdfError,_run_worker,_validate_result

ORIGINAL_SHA256 = 'a265012e09c64c1e890600fe3fd4151c819b9bf869f7f78dea88ec58ff73e268'
INPUT_LIMIT = 8*1024*1024
PAGE_TEXT_SHA256 = ('8e27187c37f0f2165cbc93c58d9c5f0b38d3951fe1fb860b0d5f83c92e522a7b', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', '576264b840134cac3fb6cb9ebde04866e2c6aa37e39ea82a49a4c690a5908544', 'bf5ebcb9014c602cae689972c0e69c0ae525310a9e262fe5d05f76c2ee934ddb', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'c1c86505a54be95993a36f4623ad590964826ea51ef794abe466ad33875b729a', 'a2f5d0e909e3a9797fb1360da06dcc90f8d008c1123f00c5ab190b93dd104ec8', '6b345ea2c75ccd3be34de86041eed9a43a735709f60304f256ec6a493f455b34', '4f4008397e076a5048652469ce286de5cc5cffb0491e5a02b43cf459d83b62e6', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', '67336f5651978d8293692361d2b7de14ec9d624ee5b9443df64a40ef6c1b511b', 'a636a6f0878f4684080962e48f0a887c9166a04af45c7acfeaaf709b939be4c8', '3cdbefe45f3f6eb7345bd7c738f71527173ec663d9d92e117785ddeb35018930', '021b8453e3affcadb8d4f594acd742ef47bf6879e16e63f3e9654767da1e080c', '25acf01cb470c15552db51af7aca10f198a4e8250ecac6906e754262cdc4fe11', 'b49f81c3d79e5bfae22bea4e18cfffb87480fffb532e4c0210295d9ead37c093', '46aad741c29f3ba6991ad198f358268f9f3185b4a3ec5ddee9fc6d6ee63c1f7d', '4cf828de752b40580b85b6db50d4111907270a5b4844534c4662d305d336d9d3', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', '9f736b3f1d116fa0955fdb99debe45e913a3743227381ff808cd6da0ef87b6d0', 'fef9a192e1c06a3a009f7167f984e7c42e9c7741a86f088e9be9fdda209afad7', '176140f6118b57f543f6f3e36a6aeb0ba8905ab56c0b18fa73ff668047766fdc', '87c3f17560a0c87d999c6eae74e344ac189c146e18b1bbed7b1ce3aa43e29627', '03c60135b23693df856710208052f98a99ea7460fac0bcbfe54cab76d30a088f', '64a12bf011477fdbf6d47a9879ee81f608591b1029543f72ccf0e6594b5f29c7', '3dcf40e9ff9a3c778241c357907793f877c7d048805175c068d00369530e3b86', '35135aaa6cc23891b40cb3f378c53a17a1127210ce60e125ccf03efcfdaec458', 'f4ccd05b3271c386ee55d9876c7450012a3b361e5065c09dc22075e38b3cc35c')
_GLYPH_EVIDENCE = {'policy': 'lienhwa-2026q2-exact-native-symbols.v1', 'complete_original_sha256': 'a265012e09c64c1e890600fe3fd4151c819b9bf869f7f78dea88ec58ff73e268', 'font_program_sha256': '491b9e161d940202f958dd86f18ac4ecce3ac18f9ab3bd3a2823e4692642fb6c', 'font_program_bytes': 5108, 'font_program_encoded_sha256': 'c815ac49c88ab503af923325718b62e83b30465f423400e2ac42fc9e05698fad', 'font_program_encoded_bytes': 2746, 'cmap_sha256': 'afe870fbb2a96e0710fe717e1b0b0367b5d81aae87d2b680b7efb7e2f0c00e63', 'cmap_bytes': 337, 'cmap_encoded_sha256': '2b5567a1e5bc094f60b2b9a5fd27a6e8b1f83a6612bbb9530667dd53ce272786', 'cmap_encoded_bytes': 225, 'source_font': 'ASJHEV+Wingdings-Regular', 'encoding': 'Identity-H', 'cid_to_gid_map': 'Identity', 'source_cids': {'U+F06C': 122}, 'mapping': [{'source_character': 'U+F06C', 'replacement_character': 'U+25CF'}], 'decomposed_outline_sha256': {'U+F06C': 'f2e0c2f4c354ef96ce6662965f1ca3c46103504bafafb94dfd1afdcbb321931b'}, 'occurrences_by_page': {'15': {'U+F06C': 3}}, 'raw_bytes_rewritten': False, 'other_characters_and_native_order_preserved': True, 'other_parser_warnings_fatal': True, 'visual_semantics_verified': False, 'covered_native_page_retained': 15}

def glyph_evidence():
    return copy.deepcopy(_GLYPH_EVIDENCE)

def _deadline(deadline):
    if time.monotonic()>=deadline:raise SourcePdfError('timeout')

def extract_lienhwa_presentation_pages(raw,*,timeout_seconds=10):
    if not isinstance(raw,bytes) or not raw or len(raw)>INPUT_LIMIT:raise SourcePdfError('invalid_input')
    if type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0<timeout_seconds<=10:raise SourcePdfError('invalid_timeout')
    deadline=time.monotonic()+float(timeout_seconds);digest=hashlib.sha256(raw).hexdigest()
    try:
        _deadline(deadline)
        if digest!=ORIGINAL_SHA256:raise SourcePdfError('invalid_pdf')
        command=[sys.executable,'-B',str(Path(__file__).with_name('lienhwa_presentation_pdf_worker.py')),str(deadline)]
        output=_run_worker(raw,deadline,worker_command=command);_deadline(deadline)
        value=json.loads(output)
        if isinstance(value,dict) and set(value)=={'error'}:_validate_result(value,digest)
        if not isinstance(value,dict):raise SourcePdfError('invalid_worker_result')
        proof=value.pop('lienhwa_glyph_evidence',None);expected=glyph_evidence()
        if json.dumps(proof,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True):raise SourcePdfError('invalid_worker_result')
        result=_validate_result(value,digest)
        if (result['page_count']!=30 or result['coverage_status']!='partial'
                or result['empty_pages']!=[2,3,6,11,12,21] or result['garbled_pages']
                or tuple(hashlib.sha256(p['text'].encode()).hexdigest() for p in result['pages'])!=PAGE_TEXT_SHA256):
            raise SourcePdfError('invalid_worker_result')
        result['lienhwa_glyph_evidence']=expected;_deadline(deadline);return result
    except SourcePdfError as exc:
        exc.content_sha256=digest;raise
    except (OSError,ValueError,TypeError,OverflowError):
        raise SourcePdfError('invalid_worker_result',content_sha256=digest) from None
