"""Real saved presentation remains partial; only exact verified bullets change."""
from hashlib import sha256
import importlib,json
from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261014/free-entry-followup/lienhwa-review'
RAW=(ROOT/'docs/evidence/source-acquisition/20261014/conference-resilience/lienhwa-research/material.body').read_bytes()
DIGEST='a265012e09c64c1e890600fe3fd4151c819b9bf869f7f78dea88ec58ff73e268'

def extract(raw=RAW,**kwargs):
 try:module=importlib.import_module('lienhwa_presentation_pdf_reader')
 except ModuleNotFoundError as exc:
  if exc.name!='lienhwa_presentation_pdf_reader':raise
  from source_pdf_reader import extract_pdf_pages
  return extract_pdf_pages(raw,**kwargs)
 return module.extract_lienhwa_presentation_pages(raw,**kwargs)

def test_exact_original_preserves_partial_pages_and_covered_text():
 value=extract(timeout_seconds=10)
 assert value['garbled_pages']==[]
 assert value['page_count']==30 and value['coverage_status']=='partial'
 assert value['empty_pages']==[2,3,6,11,12,21]
 assert value['pages']==json.loads((D/'prototype-native.json').read_text())['pages']
 assert value['pages'][14]['text'].count('●')==3 and '年底年售電量' in value['pages'][14]['text']
 assert value['lienhwa_glyph_evidence']['raw_bytes_rewritten'] is False
 assert sha256(RAW).hexdigest()==DIGEST

@pytest.fixture
def original_font():
    from io import BytesIO
    from pypdf import PdfReader
    document=PdfReader(BytesIO(RAW),strict=True)
    assert not document.is_encrypted
    return document.pages[14]['/Resources']['/Font']['/F8'].get_object()
@pytest.mark.parametrize('raw',[None,False,b'',bytearray(b'%PDF-1.7'),b'x'*(8*1024*1024+1)])
def test_invalid_input_never_starts_worker(monkeypatch,raw):
    import lienhwa_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid input started child'))
    with pytest.raises(SourcePdfError) as exc:extract(raw)
    assert exc.value.reason=='invalid_input'


@pytest.mark.parametrize('seconds',[True,False,0,-1,11,float('nan'),float('inf'),'10'])
def test_invalid_deadline_never_starts_worker(monkeypatch,seconds):
    import lienhwa_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid timeout started child'))
    with pytest.raises(SourcePdfError) as exc:extract(timeout_seconds=seconds)
    assert exc.value.reason=='invalid_timeout'


@pytest.mark.parametrize('mutation',['append','truncate','header','body_byte'])
def test_different_original_is_never_given_source_specific_mapping(monkeypatch,mutation):
    import lienhwa_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    raw=RAW+b'\n' if mutation=='append' else RAW[:-30] if mutation=='truncate' else RAW.replace(b'%PDF-1.5',b'%PDF-1.6',1) if mutation=='header' else RAW[:204500]+bytes([RAW[204500]^1])+RAW[204501:]
    assert raw!=RAW, 'negative control must actually change original bytes'
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('unknown original started child'))
    with pytest.raises(SourcePdfError) as exc:extract(raw)
    assert exc.value.reason=='invalid_pdf'




@pytest.mark.parametrize('part',['program','encoded_program','cmap','cid','font_name','encoding','registry','ordering','supplement','children','cmap_filter','program_filter','descriptor'])
def test_changed_embedded_font_does_not_map_by_name_or_codepoint(original_font,part):
    from pypdf.generic import NameObject,DecodedStreamObject,TextStringObject,BooleanObject,ArrayObject
    from lienhwa_presentation_pdf_worker import _verified_font
    font=original_font;assert _verified_font(font);child=font['/DescendantFonts'][0].get_object()
    if part in ('program','cmap'):
        stream=DecodedStreamObject();stream.set_data(b'unqualified original program')
        if part=='program':child['/FontDescriptor'][NameObject('/FontFile2')]=stream
        else:font[NameObject('/ToUnicode')]=stream
    elif part=='encoded_program':
        stream=child['/FontDescriptor']['/FontFile2'];stream._data=bytes([stream._data[0]^1])+stream._data[1:]
    elif part=='cid':child[NameObject('/CIDToGIDMap')]=NameObject('/Unknown')
    elif part=='font_name':font[NameObject('/BaseFont')]=NameObject('/UnknownFont')
    elif part=='encoding':font[NameObject('/Encoding')]=NameObject('/Identity-V')
    elif part in ('registry','ordering'):child['/CIDSystemInfo'][NameObject('/'+part.title())]=TextStringObject('Unknown')
    elif part=='supplement':child['/CIDSystemInfo'][NameObject('/Supplement')]=BooleanObject(False)
    elif part=='cmap_filter':font['/ToUnicode'][NameObject('/Filter')]=NameObject('/Unknown')
    elif part=='program_filter':child['/FontDescriptor']['/FontFile2'][NameObject('/Filter')]=NameObject('/Unknown')
    elif part=='descriptor':child['/FontDescriptor'][NameObject('/FontName')]=NameObject('/Unknown')
    else:font[NameObject('/DescendantFonts')]=ArrayObject([font['/DescendantFonts'][0],font['/DescendantFonts'][0]])
    assert not _verified_font(font)




@pytest.mark.parametrize('damage',['warning','unknown_glyph','invalid_font'])
def test_private_worker_keeps_other_warnings_and_unknown_glyphs_fatal(monkeypatch,tmp_path,damage):
    import lienhwa_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    backend=str(Path(module.__file__).parent);worker=tmp_path/'negative_worker.py'
    prefix='import sys,logging\nsys.path.insert(0,'+repr(backend)+')\nimport pypdf\nimport source_pdf_worker as common\nimport lienhwa_presentation_pdf_worker as specific\n'
    if damage=='warning':
        inject='original=pypdf.PdfReader.read_object_header\ndef noisy(self,stream):\n logging.getLogger("pypdf").warning("unexpected independent warning")\n return original(self,stream)\npypdf.PdfReader.read_object_header=noisy\n'
    elif damage=='invalid_font':inject='specific._verified_font=lambda font:False\n'
    else:inject='original=specific._normalize\ndef unknown(*args):\n text,counts=original(*args)\n return text.replace("●","\\uf06d"),counts\nspecific._normalize=unknown\n'
    worker.write_text(prefix+inject+'common._extract=specific._extract\ncommon.main()\n')
    run=module._run_worker
    def altered(raw,deadline,*,worker_command):
        command=list(worker_command);command[2]=str(worker)
        return run(raw,deadline,worker_command=command)
    monkeypatch.setattr(module,'_run_worker',altered)
    with pytest.raises(SourcePdfError) as exc:extract()
    assert exc.value.reason in ({'parser_warning','invalid_pdf'} if damage=='warning' else {'invalid_pdf'})




@pytest.fixture(scope='module')
def good_result():
    return extract()


@pytest.mark.parametrize('change',['missing_proof','bool_for_int','int_for_bool','mapping','period','duplicate_table','page_order','p18_invented_text'])
def test_public_parent_rejects_forged_proof_or_modified_native_text(monkeypatch,good_result,change):
    from copy import deepcopy
    import lienhwa_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    value=deepcopy(good_result)
    if change=='missing_proof':value.pop('lienhwa_glyph_evidence')
    elif change=='bool_for_int':value['lienhwa_glyph_evidence']['source_cids']['U+F06C']=True
    elif change=='int_for_bool':value['lienhwa_glyph_evidence']['raw_bytes_rewritten']=0
    elif change=='mapping':value['lienhwa_glyph_evidence']['mapping'][0]['replacement_character']='U+25CB'
    elif change=='period':value['pages'][21]['text']=value['pages'][21]['text'].replace('2026 H1','2026 Q2')
    elif change=='duplicate_table':value['pages'][4]['text']+='Accounting Period Income'
    elif change=='page_order':value['pages'][0],value['pages'][1]=value['pages'][1],value['pages'][0]
    else:value['pages'][1]['text']='invented disclaimer'
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
    with pytest.raises(SourcePdfError) as exc:extract()
    assert exc.value.reason=='invalid_worker_result'


def test_final_deadline_includes_parent_evidence_validation(monkeypatch,good_result):
    from copy import deepcopy
    import lienhwa_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    clock=[0.]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(deepcopy(good_result)).encode())
    validate=module._validate_result
    def slow(*args):
        result=validate(*args);clock[0]=10.;return result
    monkeypatch.setattr(module,'_validate_result',slow)
    with pytest.raises(SourcePdfError) as exc:extract()
    assert exc.value.reason=='timeout'

