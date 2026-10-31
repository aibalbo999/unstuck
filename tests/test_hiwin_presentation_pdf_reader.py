"""Exact HIWIN raw-original reader; complete native text retains visual limits."""
from hashlib import sha256
import importlib
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261014/hiwin-conference-integration/reader'
RAW=(ROOT/'docs/evidence/source-acquisition/20261014/remaining-originals-after-json/hiwin-new-entry/presentation.body').read_bytes()
DIGEST='ebb6150526e26f75787f30db984ecac363ee95997770c905530491eaf078affb'


def extract(raw=RAW,**kwargs):
    try:module=importlib.import_module('hiwin_presentation_pdf_reader')
    except ModuleNotFoundError as exc:
        if exc.name!='hiwin_presentation_pdf_reader':raise
        from source_pdf_reader import extract_pdf_pages
        return extract_pdf_pages(raw,**kwargs)
    return module.extract_hiwin_presentation_pages(raw,**kwargs)


def test_exact_original_returns_all_thirteen_independent_native_pages():
    value=extract(timeout_seconds=10)
    assert value['page_count']==13 and value['empty_pages']==value['garbled_pages']==[]
    assert value['coverage_status']=='complete' and value['content_sha256']==DIGEST
    assert value['pages']==json.loads((D/'expected-pages.json').read_text())
    assert value['xref_validation_evidence']['in_use_objects']==117
    assert value['xref_validation_evidence']['cursor_delta_bytes']==1
    assert value['hiwin_glyph_evidence']['source_cid']==122
    assert value['hiwin_glyph_evidence']['other_characters_and_native_order_preserved'] is True
    assert sum(p['text'].count('●') for p in value['pages'])==11
    assert '&[頁\n碼]' in value['pages'][6]['text']
    assert value['pages'][12]['text']=='Thank You'
    assert sha256(RAW).hexdigest()==DIGEST


def test_generic_reader_still_rejects_original_warning():
    from source_pdf_reader import extract_pdf_pages,SourcePdfError
    with pytest.raises(SourcePdfError) as exc:extract_pdf_pages(RAW)
    assert exc.value.reason=='parser_warning'


def test_published_xref_evidence_is_exact_original_proof_and_returns_fresh_copy():
    import hiwin_presentation_pdf_reader as module
    evidence=getattr(module,'xref_evidence',lambda:None)()
    assert isinstance(evidence,dict),'source verification needs an exact public xref evidence contract'
    value=extract()
    assert json.dumps(evidence,sort_keys=True)==json.dumps(value['xref_validation_evidence'],sort_keys=True)
    original=json.loads((ROOT/'docs/evidence/source-acquisition/20261014/remaining-originals-after-json/hiwin-new-entry/offline-qualification/xref-proof.json').read_text())
    for field in ('verified_offsets_sha256','trailer_sha256','in_use_objects','xref_size','classic_xref_offset'):
        assert evidence[field]==original[field]
    evidence['cursor_delta_bytes']=9
    assert module.xref_evidence()['cursor_delta_bytes']==1


@pytest.mark.parametrize('raw',[None,False,b'',bytearray(b'%PDF-1.7'),b'x'*(8*1024*1024+1)])
def test_invalid_input_never_starts_worker(monkeypatch,raw):
    import hiwin_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid input started child'))
    with pytest.raises(SourcePdfError) as exc:extract(raw)
    assert exc.value.reason=='invalid_input'


@pytest.mark.parametrize('seconds',[True,False,0,-1,11,float('nan'),float('inf'),'10'])
def test_invalid_deadline_never_starts_worker(monkeypatch,seconds):
    import hiwin_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid timeout started child'))
    with pytest.raises(SourcePdfError) as exc:extract(timeout_seconds=seconds)
    assert exc.value.reason=='invalid_timeout'


@pytest.mark.parametrize('mutation',['append','truncate','header','font_program'])
def test_different_original_is_never_given_source_specific_mapping(monkeypatch,mutation):
    import hiwin_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    raw=RAW+b'\n' if mutation=='append' else RAW[:-30] if mutation=='truncate' else RAW.replace(b'%PDF-1.7',b'%PDF-1.6',1) if mutation=='header' else RAW[:204500]+bytes([RAW[204500]^1])+RAW[204501:]
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('unknown original started child'))
    with pytest.raises(SourcePdfError) as exc:extract(raw)
    assert exc.value.reason=='invalid_pdf'


@pytest.mark.parametrize('case',['other_offset','inside_header','non_lf','duplicate_id','generation','free_state','trailer','trailing','object_end'])
def test_complete_classic_xref_rejects_unqualified_structures(case):
    import time
    from hiwin_presentation_pdf_reader import _qualify_xref
    raw=RAW;entry=975922+len(b'xref\n0 118\r\n')+20
    if case=='other_offset':raw=raw[:entry]+b'0000975531'+raw[entry+10:]
    elif case=='inside_header':raw=raw[:entry]+b'0000975680'+raw[entry+10:]
    elif case=='non_lf':raw=raw[:975679]+b' '+raw[975680:]
    elif case=='duplicate_id':raw=raw[:975680]+b'2'+raw[975681:]
    elif case=='generation':raw=raw[:entry+11]+b'00001'+raw[entry+16:]
    elif case=='free_state':raw=raw[:entry+17]+b'f'+raw[entry+18:]
    elif case=='trailer':raw=raw.replace(b'/Size 118\n>>\nstartxref',b'/Size 119\n>>\nstartxref',1)
    elif case=='trailing':raw+=b'\ntrailer\n<<>>\n'
    else:raw=raw[:2894]+b'X'+raw[2895:]
    with pytest.raises(ValueError):_qualify_xref(raw,time.monotonic()+10)


@pytest.fixture
def original_font():
    from io import BytesIO
    import time
    from pypdf import PdfReader
    from hiwin_presentation_pdf_reader import _qualify_xref
    offsets,_=_qualify_xref(RAW,time.monotonic()+10)
    class ProvenCursor(PdfReader):
        def read_object_header(self,stream):
            offset=stream.tell();assert offset in offsets and stream.read(1)==b'\n'
            result=super().read_object_header(stream);assert result==offsets[offset];return result
    document=ProvenCursor(BytesIO(RAW),strict=True)
    return document.get_object(44)


@pytest.mark.parametrize('part',['program','encoded_program','cmap','cid','font_name','encoding','registry','ordering','supplement','children'])
def test_changed_embedded_font_does_not_map_by_name_or_codepoint(original_font,part):
    from pypdf.generic import NameObject,DecodedStreamObject,TextStringObject,BooleanObject,ArrayObject
    from hiwin_presentation_pdf_worker import _verified_font
    font=original_font;assert _verified_font(font);child=font['/DescendantFonts'][0].get_object()
    if part in ('program','cmap'):
        stream=DecodedStreamObject();stream.set_data(b'unqualified original program')
        if part=='program':child['/FontDescriptor'][NameObject('/FontFile2')]=stream
        else:font[NameObject('/ToUnicode')]=stream
    elif part=='encoded_program':
        stream=child['/FontDescriptor']['/FontFile2'];stream._data=bytes([stream._data[0]^1])+stream._data[1:]
    elif part=='cid':child[NameObject('/CIDToGIDMap')]=NameObject('/Unknown')
    elif part=='font_name':font[NameObject('/BaseFont')]=NameObject('/Wingdings')
    elif part=='encoding':font[NameObject('/Encoding')]=NameObject('/Identity-V')
    elif part in ('registry','ordering'):child['/CIDSystemInfo'][NameObject('/'+part.title())]=TextStringObject('Unknown')
    elif part=='supplement':child['/CIDSystemInfo'][NameObject('/Supplement')]=BooleanObject(False)
    else:font[NameObject('/DescendantFonts')]=ArrayObject([font['/DescendantFonts'][0],font['/DescendantFonts'][0]])
    assert not _verified_font(font)


@pytest.mark.parametrize('text,page,mode',[('\uf06c 123',2,'mixed'),('\uf06d',2,'unknown'),('\uf06c',1,'wrong_page'),('\uf06c',2,'no_font'),('\uf06c',2,'missing'),('\uf06c',2,'mismatch')])
def test_unknown_or_mixed_glyphs_are_never_guessed(original_font,text,page,mode):
    from hiwin_presentation_pdf_worker import _normalize
    fragments=None if mode=='missing' else [('wrong' if mode=='mismatch' else text,None if mode=='no_font' else original_font)]
    result,count=_normalize(text,fragments,page,{})
    assert result==text and count=={}


def test_only_proven_standalone_glyph_changes_and_all_other_positions_remain(original_font):
    from hiwin_presentation_pdf_worker import _normalize
    result,count=_normalize('x\n \uf06c\n123',[('x\n',None),(' \uf06c\n',original_font),('123',None)],2,{})
    assert result=='x\n ●\n123' and count=={'U+F06C':1}


@pytest.mark.parametrize('change',['missing_glyph','missing_xref','glyph_bool','glyph_cid','xref_cursor','xref_bool','text','page_order'])
def test_parent_rejects_forged_worker_proofs_or_changed_text(monkeypatch,change):
    import hiwin_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    value=extract()
    if change=='missing_glyph':value.pop('hiwin_glyph_evidence')
    elif change=='missing_xref':value.pop('xref_validation_evidence')
    elif change=='glyph_bool':value['hiwin_glyph_evidence']['raw_bytes_rewritten']=0
    elif change=='glyph_cid':value['hiwin_glyph_evidence']['source_cid']=122.0
    elif change=='xref_cursor':value['xref_validation_evidence']['cursor_delta_bytes']=2
    elif change=='xref_bool':value['xref_validation_evidence']['other_parser_warnings_fatal']=1
    elif change=='text':value['pages'][6]['text']=value['pages'][6]['text'].replace('&[頁\n碼]','')
    else:value['pages'][0],value['pages'][1]=value['pages'][1],value['pages'][0]
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
    with pytest.raises(SourcePdfError) as exc:extract()
    assert exc.value.reason=='invalid_worker_result'


@pytest.mark.parametrize('damage',['warning','unknown_glyph','invalid_font'])
def test_private_worker_keeps_other_warnings_and_unknown_glyphs_fatal(monkeypatch,tmp_path,damage):
    import hiwin_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    backend=str(Path(module.__file__).parent);worker=tmp_path/'negative_worker.py'
    prefix='import sys,logging\nsys.path.insert(0,'+repr(backend)+')\nimport pypdf\nimport source_pdf_worker as common\nimport hiwin_presentation_pdf_worker as specific\n'
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


def test_final_deadline_includes_parent_evidence_validation(monkeypatch):
    import hiwin_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    value=extract();clock=[0.]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
    qualify=module._qualify_xref
    def slow(*args):
        result=qualify(*args);clock[0]=10.;return result
    monkeypatch.setattr(module,'_qualify_xref',slow)
    with pytest.raises(SourcePdfError) as exc:extract()
    assert exc.value.reason=='timeout'
