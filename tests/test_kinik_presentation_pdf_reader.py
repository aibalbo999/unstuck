"""Exact saved KINIK native text, keeping every visual and period limitation."""
from hashlib import sha256
import importlib,json
from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261014/kinik-conference-integration/reader'
RAW=(ROOT/'docs/evidence/source-acquisition/20261014/remaining-originals-after-json/kinik-new-conference-entry/presentation.body').read_bytes()
DIGEST='4490a76682ab9655cbe78c30736ede3749c31577c35eaa95ef187f7af8511d4c'


def extract(raw=RAW,**kwargs):
    try:module=importlib.import_module('kinik_presentation_pdf_reader')
    except ModuleNotFoundError as exc:
        if exc.name!='kinik_presentation_pdf_reader':raise
        from source_pdf_reader import extract_pdf_pages
        return extract_pdf_pages(raw,**kwargs)
    return module.extract_kinik_presentation_pages(raw,**kwargs)


def test_exact_original_returns_thirty_six_native_pages_without_duplicating_tables():
    value=extract(timeout_seconds=10)
    assert value['page_count']==36 and value['coverage_status']=='complete'
    assert value['empty_pages']==value['garbled_pages']==[]
    assert value['content_sha256']==DIGEST and sha256(RAW).hexdigest()==DIGEST
    assert value['pages']==json.loads((D/'expected-pages.json').read_text())
    assert value['pages'][17]['text']=='18\n'
    assert '2Q26  1Q25 QoQ' in value['pages'][4]['text']
    assert value['pages'][4]['text'].count('Accounting Period Income')==1
    assert value['pages'][5]['text'].count('Business Unit')==1
    assert value['pages'][6]['text'].count('Business Unit')==1
    assert sum(p['text'].count('●') for p in value['pages'])==25
    assert sum(p['text'].count('◆') for p in value['pages'])==7
    proof=value['kinik_glyph_evidence']
    assert proof['raw_bytes_rewritten'] is False
    assert proof['visual_semantics_verified'] is False
    assert proof['other_characters_and_native_order_preserved'] is True


def test_generic_reader_remains_partial_for_thirteen_unqualified_symbol_pages():
    from source_pdf_reader import extract_pdf_pages
    value=extract_pdf_pages(RAW)
    assert value['coverage_status']=='partial'
    assert value['garbled_pages']==[4,5,6,7,10,11,12,13,15,28,29,30,31]


@pytest.fixture
def original_font():
    from io import BytesIO
    from pypdf import PdfReader
    document=PdfReader(BytesIO(RAW),strict=True)
    assert not document.is_encrypted
    return document.get_object(127)
@pytest.mark.parametrize('raw',[None,False,b'',bytearray(b'%PDF-1.7'),b'x'*(8*1024*1024+1)])
def test_invalid_input_never_starts_worker(monkeypatch,raw):
    import kinik_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid input started child'))
    with pytest.raises(SourcePdfError) as exc:extract(raw)
    assert exc.value.reason=='invalid_input'


@pytest.mark.parametrize('seconds',[True,False,0,-1,11,float('nan'),float('inf'),'10'])
def test_invalid_deadline_never_starts_worker(monkeypatch,seconds):
    import kinik_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid timeout started child'))
    with pytest.raises(SourcePdfError) as exc:extract(timeout_seconds=seconds)
    assert exc.value.reason=='invalid_timeout'


@pytest.mark.parametrize('mutation',['append','truncate','header','body_byte'])
def test_different_original_is_never_given_source_specific_mapping(monkeypatch,mutation):
    import kinik_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    raw=RAW+b'\n' if mutation=='append' else RAW[:-30] if mutation=='truncate' else RAW.replace(b'%PDF-1.5',b'%PDF-1.6',1) if mutation=='header' else RAW[:204500]+bytes([RAW[204500]^1])+RAW[204501:]
    assert raw!=RAW, 'negative control must actually change original bytes'
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('unknown original started child'))
    with pytest.raises(SourcePdfError) as exc:extract(raw)
    assert exc.value.reason=='invalid_pdf'




@pytest.mark.parametrize('part',['program','encoded_program','cmap','cid','font_name','encoding','registry','ordering','supplement','children','cmap_filter','program_filter','descriptor'])
def test_changed_embedded_font_does_not_map_by_name_or_codepoint(original_font,part):
    from pypdf.generic import NameObject,DecodedStreamObject,TextStringObject,BooleanObject,ArrayObject
    from kinik_presentation_pdf_worker import _verified_font
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
    import kinik_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    backend=str(Path(module.__file__).parent);worker=tmp_path/'negative_worker.py'
    prefix='import sys,logging\nsys.path.insert(0,'+repr(backend)+')\nimport pypdf\nimport source_pdf_worker as common\nimport kinik_presentation_pdf_worker as specific\n'
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
    assert exc.value.reason==('parser_warning' if damage=='warning' else 'invalid_pdf')




def _saved_native_and_fragments(page, font, *, repeated=True):
    cap=json.loads((D/'font-capture.json').read_text())
    old=json.loads((ROOT/'docs/evidence/source-acquisition/20261014/remaining-originals-after-json/kinik-new-conference-entry/native-reader.json').read_text())['result']
    text=old['pages'][page-1]['text']
    record=cap['pages'][page-1]
    joined=record['fragment_join'] if repeated and record['fragment_join'] is not None else text
    import re
    fragments=[(part,font if part in {'\uf06c','\uf075'} else None) for part in re.split('([\uf06c\uf075])',joined)]
    return text,fragments


@pytest.mark.parametrize('page',[4,5,6,7,13,15])
def test_exact_known_fragment_behavior_preserves_native_order_and_every_other_character(original_font,page):
    import kinik_presentation_pdf_reader as reader
    from kinik_presentation_pdf_worker import _normalize
    text,fragments=_saved_native_and_fragments(page,original_font)
    result,counts=_normalize(text,fragments,page,{})
    expected=json.loads((D/'expected-pages.json').read_text())[page-1]['text']
    assert result==expected and len(result)==len(text)
    assert counts==reader.OCCURRENCES[str(page)]
    assert [(a,b) for a,b in zip(text,result) if a!=b]==[(c,reader.MAPPING[c]) for c in text if c in reader.MAPPING]


@pytest.mark.parametrize('change',['extra_table','changed_table_value','unknown_glyph','mixed_symbol_fragment','wrong_font','missing_symbol','wrong_page'])
def test_exact_form_exception_does_not_admit_unknown_fragments_or_numbers(original_font,change):
    from kinik_presentation_pdf_worker import _normalize
    text,fragments=_saved_native_and_fragments(5,original_font)
    page=5
    if change=='extra_table':fragments.append(('Accounting Period Income',None))
    elif change=='changed_table_value':fragments=[(p.replace('2,492,667','9,492,667'),f) for p,f in fragments]
    elif change=='unknown_glyph':fragments.append(('\uf076',original_font))
    elif change=='mixed_symbol_fragment':fragments=[(p+' 1' if p=='\uf06c' else p,f) for p,f in fragments]
    elif change=='wrong_font':fragments=[(p,None) for p,f in fragments]
    elif change=='missing_symbol':fragments=[(p.replace('\uf06c',''),f) for p,f in fragments]
    else:page=8
    result,count=_normalize(text,fragments,page,{})
    assert result==text and count=={}


@pytest.fixture(scope='module')
def good_result():
    return extract()


@pytest.mark.parametrize('change',['missing_proof','bool_for_int','int_for_bool','mapping','join_sha','period','duplicate_table','page_order','p18_invented_text'])
def test_public_parent_rejects_forged_proof_or_modified_native_text(monkeypatch,good_result,change):
    from copy import deepcopy
    import kinik_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    value=deepcopy(good_result)
    if change=='missing_proof':value.pop('kinik_glyph_evidence')
    elif change=='bool_for_int':value['kinik_glyph_evidence']['source_cids']['U+F06C']=True
    elif change=='int_for_bool':value['kinik_glyph_evidence']['raw_bytes_rewritten']=0
    elif change=='mapping':value['kinik_glyph_evidence']['mapping'][0]['replacement_character']='U+25CB'
    elif change=='join_sha':value['kinik_glyph_evidence']['qualified_fragment_join_sha256']['5']='0'*64
    elif change=='period':value['pages'][4]['text']=value['pages'][4]['text'].replace('1Q25','1Q26')
    elif change=='duplicate_table':value['pages'][4]['text']+='Accounting Period Income'
    elif change=='page_order':value['pages'][0],value['pages'][1]=value['pages'][1],value['pages'][0]
    else:value['pages'][17]['text']='18 complete company history'
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
    with pytest.raises(SourcePdfError) as exc:extract()
    assert exc.value.reason=='invalid_worker_result'


def test_final_deadline_includes_parent_evidence_validation(monkeypatch,good_result):
    from copy import deepcopy
    import kinik_presentation_pdf_reader as module
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


def test_glyph_contract_is_fresh_and_not_shared_mutable_state():
    import kinik_presentation_pdf_reader as module
    value=module.glyph_evidence();value['source_cids']['U+F06C']=0
    value['occurrences_by_page']['4']['U+F06C']=999
    assert module.glyph_evidence()['source_cids']['U+F06C']==122
    assert module.glyph_evidence()['occurrences_by_page']['4']['U+F06C']==5
