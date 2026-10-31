"""Qualified STI native-text extraction; visual/financial coverage remains partial."""
from pathlib import Path
import importlib
import json
import pytest

R = Path(__file__).resolve().parents[1]
ORIGINAL = R / 'tests/fixtures/source_acquisition/sti2480_presentation_reader.pdf'
RAW = ORIGINAL.read_bytes()
DIGEST = '61a4dececbdb1a30bb4ea6529de24001b4cdf10a26e8a33a85f4feb4378c6e0b'

def extract(raw=RAW, **kwargs):
    try:
        module = importlib.import_module('sti_presentation_pdf_reader')
    except ModuleNotFoundError as exc:
        if exc.name != 'sti_presentation_pdf_reader':
            raise
        from source_pdf_reader import extract_pdf_pages
        return extract_pdf_pages(raw, **kwargs)
    return module.extract_sti_presentation_pages(raw, **kwargs)

def test_exact_original_complete_with_qualified_three_hollow_squares():
    value = extract(timeout_seconds=10)
    assert value['coverage_status'] == 'complete'
    assert value['page_count'] == 44
    assert value['empty_pages'] == value['garbled_pages'] == []
    assert value['content_sha256'] == DIGEST
    assert value['sti_glyph_evidence']['occurrences_by_page'] == {'5': 3}
    assert value['sti_glyph_evidence']['raw_bytes_rewritten'] is False

def test_generic_reader_keeps_same_original_partial():
    from source_pdf_reader import extract_pdf_pages
    value = extract_pdf_pages(RAW, timeout_seconds=10)
    assert value['coverage_status'] == 'partial'
    assert value['garbled_pages'] == [5]
    assert value['pages'][4]['text'].count('\uf070') == 3

@pytest.mark.parametrize('raw',[None,False,b'',bytearray(b'%PDF-1.7'),b'x'*(8*1024*1024+1)])
def test_invalid_input_rejected_before_worker(monkeypatch,raw):
 import sti_presentation_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid input started child'))
 with pytest.raises(SourcePdfError)as error:extract(raw)
 assert error.value.reason=='invalid_input'

@pytest.mark.parametrize('seconds',[True,False,0,-1,11,float('nan'),float('inf'),'10'])
def test_invalid_timeout_rejected_before_worker(monkeypatch,seconds):
 import sti_presentation_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid timeout started child'))
 with pytest.raises(SourcePdfError)as error:extract(timeout_seconds=seconds)
 assert error.value.reason=='invalid_timeout'

@pytest.mark.parametrize('raw',[RAW+b'\n',(R/'docs/evidence/source-acquisition/20261014/free-entrance-next/sti2480/mops-english.body').read_bytes()])
def test_unknown_or_english_original_never_starts_worker(monkeypatch,raw):
 import sti_presentation_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('unqualified digest started child'))
 with pytest.raises(SourcePdfError)as error:extract(raw)
 assert error.value.reason=='invalid_pdf'

def test_every_other_character_digit_and_page_order_held():
 from hashlib import sha256
 before=json.loads((R/'docs/evidence/source-acquisition/20261014/free-entrance-next/sti2480/presentation.extracted.json').read_text())
 result=extract();assert sha256(RAW).hexdigest()==DIGEST
 for old,new in zip(before['pages'],result['pages'],strict=True):
  assert new['page_number']==old['page_number']
  assert new['text']==old['text'].replace('\uf070','\u25a1')
 assert sum(p['text'].count('\uf070')for p in before['pages'])==3
 assert result['sti_glyph_evidence']['visual_semantics_verified'] is False
 assert '\u6566\u967d\u8cc7\u8a0a' in result['pages'][4]['text']
 assert '\u6566\u967d\u79d1\u6280' in result['pages'][0]['text']

@pytest.fixture(scope='module')
def qualified_font():
 from pypdf import PdfReader
 from io import BytesIO
 reader=PdfReader(BytesIO(RAW),strict=True);fonts=[]
 def visitor(text,cm,tm,font,size):
  if '\uf070' in text:fonts.append(font)
 reader.pages[4].extract_text(visitor_text=visitor);font=fonts[0];child=font['/DescendantFonts'][0].get_object()
 class Stream:
  def __init__(self,data):self.data=data
  def get_data(self):return self.data
 descriptor=child['/FontDescriptor'];desc={'/FontName':str(descriptor['/FontName']),'/FontFile2':Stream(descriptor['/FontFile2'].get_data())}
 basic={k:str(font[k])for k in ['/Type','/Subtype','/BaseFont','/Encoding']}
 descendant={k:str(child[k])for k in ['/Type','/Subtype','/BaseFont','/CIDToGIDMap']};descendant['/CIDSystemInfo']={k:(int(v)if k=='/Supplement'else str(v))for k,v in child['/CIDSystemInfo'].items()};descendant['/FontDescriptor']=desc
 basic['/DescendantFonts']=[descendant];basic['/ToUnicode']=Stream(font['/ToUnicode'].get_data());return basic

@pytest.mark.parametrize('change',['font_name','type','subtype','encoding','children','child_subtype','child_name','CIDToGIDMap','registry','ordering','supplement_bool','supplement_float','descriptor','program','cmap'])
def test_mutated_font_profile_never_normalizes(qualified_font,change):
 import copy
 import sti_presentation_pdf_worker as worker
 font=copy.deepcopy(qualified_font);child=font['/DescendantFonts'][0]
 if change=='font_name':font['/BaseFont']='/Arial'
 elif change=='type':font['/Type']='/Other'
 elif change=='subtype':font['/Subtype']='/Type1'
 elif change=='encoding':font['/Encoding']='/Identity-V'
 elif change=='children':font['/DescendantFonts']*=2
 elif change=='child_subtype':child['/Subtype']='/CIDFontType0'
 elif change=='child_name':child['/BaseFont']='/ABCDEE+Other'
 elif change=='CIDToGIDMap':child['/CIDToGIDMap']='/Other'
 elif change=='registry':child['/CIDSystemInfo']['/Registry']='Other'
 elif change=='ordering':child['/CIDSystemInfo']['/Ordering']='Other'
 elif change=='supplement_bool':child['/CIDSystemInfo']['/Supplement']=False
 elif change=='supplement_float':child['/CIDSystemInfo']['/Supplement']=0.0
 elif change=='descriptor':child['/FontDescriptor']['/FontName']='/Other'
 elif change=='program':child['/FontDescriptor']['/FontFile2'].data+=b'x'
 else:font['/ToUnicode'].data=font['/ToUnicode'].data.replace(b'<0087>',b'<0088>')
 assert worker._verified_font(font) is False
 assert worker._normalize('\uf070',[('\uf070',font)],5,{})==('\uf070',0)

@pytest.mark.parametrize('text,fragments',[('amount\uf070',[('amount\uf070','FONT')]),('\uf076',[('\uf076','FONT')]),('\uf070',None),('\uf070',[('different','FONT')])])
def test_unknown_mixed_and_inconsistent_fragments_remain_unknown(qualified_font,text,fragments):
 import sti_presentation_pdf_worker as worker
 if fragments is not None:fragments=[(t,qualified_font)for t,f in fragments]
 assert worker._normalize(text,fragments,5,{})==(text,0)

def test_exact_standalone_glyph_changes_only_itself(qualified_font):
 import sti_presentation_pdf_worker as worker
 assert worker._verified_font(qualified_font)
 assert worker._normalize(' \uf070\n12.3',[(' \uf070\n',qualified_font),('12.3',None)],5,{})==(' \u25a1\n12.3',1)

@pytest.mark.parametrize('change',['missing','cid','program','count_bool','raw_flag_integer','text','page_number'])
def test_parent_rejects_worker_proof_or_text_tampering(monkeypatch,change):
 import sti_presentation_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 value=extract();proof=value['sti_glyph_evidence']
 if change=='missing':value.pop('sti_glyph_evidence')
 elif change=='cid':proof['source_cid']=136
 elif change=='program':proof['font_program_sha256']='0'*64
 elif change=='count_bool':proof['occurrences_by_page']['5']=True
 elif change=='raw_flag_integer':proof['raw_bytes_rewritten']=0
 elif change=='text':value['pages'][23]['text']=value['pages'][23]['text']+'1'
 else:value['pages'][5]['page_number']=7
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
 with pytest.raises(SourcePdfError)as error:extract()
 assert error.value.reason=='invalid_worker_result'

@pytest.mark.parametrize('injection',['warning','unqualified_font'])
def test_private_child_other_warning_or_unqualified_font_fails_closed(monkeypatch,tmp_path,injection):
 import sti_presentation_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 private=tmp_path/'injected.py';code='import sys,logging\nsys.path.insert(0,'+repr(str(R/'backend'))+')\nimport pypdf\nimport source_pdf_worker as common\nimport sti_presentation_pdf_worker as specific\n'
 if injection=='warning':code+='original=pypdf.PdfReader.read_object_header\ndef noisy(self,stream):\n logging.getLogger("pypdf").warning("independent warning")\n return original(self,stream)\npypdf.PdfReader.read_object_header=noisy\n'
 else:code+='specific._verified_font=lambda font:False\n'
 private.write_text(code+'common._extract=specific._extract\ncommon.main()\n');run=module._run_worker
 def injected(raw,deadline,*,worker_command):
  command=list(worker_command);command[2]=str(private);return run(raw,deadline,worker_command=command)
 monkeypatch.setattr(module,'_run_worker',injected)
 with pytest.raises(SourcePdfError)as error:extract()
 assert error.value.reason==('parser_warning'if injection=='warning'else'invalid_pdf')

def test_parent_final_validation_does_not_restart_deadline(monkeypatch):
 import sti_presentation_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 value=extract();clock=[0.];monkeypatch.setattr(module.time,'monotonic',lambda:clock[0]);monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode());validate=module._validate_result
 def late(*args):
  result=validate(*args);clock[0]=10.;return result
 monkeypatch.setattr(module,'_validate_result',late)
 with pytest.raises(SourcePdfError)as error:extract()
 assert error.value.reason=='timeout'

def test_qualified_font_is_not_applied_on_a_different_page(qualified_font):
    import sti_presentation_pdf_worker as worker
    assert worker._normalize('\uf070', [('\uf070', qualified_font)], 6, {}) == ('\uf070', 0)

def test_wrong_occurrence_count_fails_closed_in_actual_private_child(monkeypatch, tmp_path):
    import sti_presentation_pdf_reader as module
    from source_pdf_reader import SourcePdfError
    private = tmp_path / 'wrong_count.py'
    private.write_text(
        'import sys\nsys.path.insert(0,' + repr(str(R / 'backend')) + ')\n'
        'import source_pdf_worker as common\n'
        'import sti_presentation_pdf_worker as specific\n'
        'old=specific._normalize\n'
        'def fewer(*args):\n text,count=old(*args)\n return text,0\n'
        'specific._normalize=fewer\ncommon._extract=specific._extract\ncommon.main()\n'
    )
    run = module._run_worker
    def injected(raw, deadline, *, worker_command):
        command = list(worker_command)
        command[2] = str(private)
        return run(raw, deadline, worker_command=command)
    monkeypatch.setattr(module, '_run_worker', injected)
    with pytest.raises(SourcePdfError) as error:
        extract()
    assert error.value.reason == 'invalid_pdf'

def test_tiny_deadline_is_terminal_without_returning_native_text():
    from source_pdf_reader import SourcePdfError
    with pytest.raises(SourcePdfError) as error:
        extract(timeout_seconds=0.000001)
    assert error.value.reason == 'timeout'
