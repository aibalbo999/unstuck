"""Public native PPTX behavior and bounded child/ZIP trust boundaries."""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
import zipfile
from xml.sax.saxutils import escape

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import source_pptx_reader as reader

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/lienhwa_pptx_20261014/122920260930E001.pptx'
SHA = '4ab60e7e57d57255e9d93ffcf25e54bab12db5e3718086000ae956a057ba160c'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'

def package(texts=('Original',), *, hidden=(), extras=None, replacements=None, compression=zipfile.ZIP_STORED):
    parts = {
        '[Content_Types].xml': f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>' + ''.join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1, len(texts)+1)) + '</Types>',
        '_rels/.rels': f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        'ppt/presentation.xml': f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>' + ''.join(f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in range(1, len(texts)+1)) + '</p:sldIdLst></p:presentation>',
        'ppt/_rels/presentation.xml.rels': f'<Relationships xmlns="{REL}">' + ''.join(f'<Relationship Id="rId{i}" Type="{R}/slide" Target="slides/slide{i}.xml"/>' for i in range(1, len(texts)+1)) + '</Relationships>',
    }
    for i, text in enumerate(texts, 1):
        h = ' show="0"' if i in hidden else ''
        parts[f'ppt/slides/slide{i}.xml'] = f'<p:sld xmlns:p="{P}" xmlns:a="{A}"{h}><p:cSld><p:spTree><p:sp><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{escape(text)}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    parts.update(extras or {}); parts.update(replacements or {})
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=compression) as z:
        for name, body in parts.items(): z.writestr(name, body)
    return stream.getvalue()

def test_complete_published_original_preserves_visible_numbering_and_partial_text():
    raw = FIXTURE.read_bytes()
    assert len(raw) == 3883370 and hashlib.sha256(raw).hexdigest() == SHA
    result = reader.extract_pptx_pages(raw)
    assert result['content_sha256'] == SHA
    assert result['parser_version'] == 'pptx-native-v1'
    assert result['page_count'] == 30 and result['total_slide_count'] == 32
    assert result['hidden_pages'] == [31, 32]
    assert [p['page_number'] for p in result['pages']] == list(range(1, 31))
    assert result['empty_pages'] == [2, 3, 21, 29]
    assert result['garbled_pages'] == [] and result['coverage_status'] == 'partial'
    assert result['external_relationship_count'] == 11 and result['embedded_object_count'] == 1
    assert 'Lien Hwa Industrial Holdings Corporation' in result['pages'][0]['text']
    assert 'Dividend Policy' not in '\n'.join(p['text'] for p in result['pages'])
    assert 'Forward-Looking Information' not in result['pages'][1]['text']  # raster disclaimer must not be fabricated

def test_hidden_middle_page_excluded_but_image_only_and_garbled_pages_preserved():
    raw = package(('Revenue 0', 'Hidden 99', '', '\uf075 raw'), hidden=(2,))
    result = reader.extract_pptx_pages(raw)
    assert result['pages'] == [{'page_number': 1, 'text': 'Revenue 0'}, {'page_number': 3, 'text': ''}, {'page_number': 4, 'text': '\uf075 raw'}]
    assert result['hidden_pages'] == [2] and result['empty_pages'] == [3]
    assert result['garbled_pages'] == [4] and result['coverage_status'] == 'partial'

@pytest.mark.parametrize('raw', [b'', 'not bytes', b'x' * (8 * 1024**2 + 1)])
def test_input_rejected(raw):
    with pytest.raises(reader.SourcePptxError, match='invalid_input'): reader.extract_pptx_pages(raw)

@pytest.mark.parametrize('timeout', [True, 0, -1, 11, float('nan'), float('inf'), '2', 10**1000])
def test_invalid_deadline_rejected(timeout):
    with pytest.raises(reader.SourcePptxError, match='invalid_timeout'):
        reader.extract_pptx_pages(package(), timeout_seconds=timeout)

def test_high_compression_zip_bomb_rejected():
    with pytest.raises(reader.SourcePptxError, match='zip_limit'):
        reader.extract_pptx_pages(package(extras={'huge.xml': b'0' * 1000000}, compression=zipfile.ZIP_DEFLATED))

@pytest.mark.parametrize('name', ['../outside.xml', '/absolute.xml', 'ppt/../outside.xml', 'ppt\\evil.xml'])
def test_unsafe_member_path_rejected(name):
    with pytest.raises(reader.SourcePptxError, match='unsafe_package'):
        reader.extract_pptx_pages(package(extras={name: b'x'}))


@pytest.mark.parametrize('body', [b'<!DOCTYPE x [<!ENTITY y "hidden">]><x>&y;</x>',
                                '<!DOCTYPE x [<!ENTITY y "hidden">]><x>&y;</x>'.encode('utf-16'),
                                b'<x>' * 65 + b'</x>' * 65])
def test_unsafe_xml_is_refused_without_entity_or_external_fetch(body):
    with pytest.raises(reader.SourcePptxError) as error:
        reader.extract_pptx_pages(package(extras={'danger.xml': body}))
    assert error.value.reason in {'invalid_xml', 'zip_limit'}


@pytest.mark.parametrize('name,content', [('ppt/vbaProject.bin', b'evil'),
                                        ('ppt/embeddings/oleObject1.bin', b'\xd0\xcf\x11\xe0'),
                                        ('ppt/embeddings/fake.xlsx', b'\xd0\xcf\x11\xe0'),
                                        ('script.js', b'evil')])
def test_active_content_is_rejected_without_execution(name, content):
    with pytest.raises(reader.SourcePptxError, match='active_content'):
        reader.extract_pptx_pages(package(extras={name: content}))


def test_macro_enabled_content_type_is_rejected():
    raw = package()
    with zipfile.ZipFile(BytesIO(raw)) as z:
        types = z.read('[Content_Types].xml').decode().replace(
            'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml',
            'application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml')
    with pytest.raises(reader.SourcePptxError, match='active_content'):
        reader.extract_pptx_pages(package(replacements={'[Content_Types].xml': types}))


def test_external_links_are_inert_counted_and_do_not_enter_text():
    relationships = f'<Relationships xmlns="{REL}"><Relationship Id="rId3" Type="{R}/hyperlink" Target="https://invalid.example/never" TargetMode="External"/><Relationship Id="rId4" Type="{R}/oleObject" Target="file:///never-open-secret.xlsx" TargetMode="External"/></Relationships>'
    result = reader.extract_pptx_pages(package(extras={'ppt/slides/_rels/slide1.xml.rels': relationships}))
    assert result['external_relationship_count'] == 2
    assert result['pages'] == [{'page_number': 1, 'text': 'Original'}]
    assert 'never' not in json.dumps(result)


def test_external_slide_is_rejected_instead_of_treated_as_empty_success():
    relations = f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/slide" Target="https://invalid.example/slide.xml" TargetMode="External"/></Relationships>'
    with pytest.raises(reader.SourcePptxError, match='invalid_pptx'):
        reader.extract_pptx_pages(package(replacements={'ppt/_rels/presentation.xml.rels': relations}))


def test_duplicate_encrypted_and_corrupt_zip_members_rejected():
    raw = package()
    stream = BytesIO(raw)
    with zipfile.ZipFile(stream, 'a') as z:
        with pytest.warns(UserWarning, match='Duplicate name'):
            z.writestr('ppt/slides/slide1.xml', b'other')
    with pytest.raises(reader.SourcePptxError, match='unsafe_package'):
        reader.extract_pptx_pages(stream.getvalue())
    altered = bytearray(raw)
    central = altered.index(b'PK\x01\x02')
    altered[central+8:central+10] = (1).to_bytes(2, 'little')
    with pytest.raises(reader.SourcePptxError, match='encrypted_package'):
        reader.extract_pptx_pages(bytes(altered))
    with zipfile.ZipFile(BytesIO(raw)) as z:
        target = z.getinfo('ppt/slides/slide1.xml')
        offset = target.header_offset + 30 + len(target.filename.encode()) + len(target.extra)
    corrupt = bytearray(raw); corrupt[offset] ^= 1
    with pytest.raises(reader.SourcePptxError, match='invalid_pptx'):
        reader.extract_pptx_pages(bytes(corrupt))


def test_entry_slide_and_character_limits_are_enforced_without_truncation():
    with pytest.raises(reader.SourcePptxError, match='zip_limit'):
        reader.extract_pptx_pages(package(extras={f'empty{i}': b'' for i in range(2000)}))
    with pytest.raises(reader.SourcePptxError, match='slide_limit'):
        reader.extract_pptx_pages(package(('A',) * 101))
    with pytest.raises(reader.SourcePptxError, match='character_limit'):
        reader.extract_pptx_pages(package(('A' * 100001, 'B' * 100000)))
    boundary = reader.extract_pptx_pages(package(('A' * 100000, 'B' * 100000)))
    assert sum(len(p['text']) for p in boundary['pages']) == 200000


@pytest.mark.parametrize('texts,hidden', [(('', ''), ()), (('Original',), (1,))])
def test_no_visible_native_content_is_not_success(texts, hidden):
    with pytest.raises(reader.SourcePptxError, match='empty_document'):
        reader.extract_pptx_pages(package(texts, hidden=hidden))


def test_original_native_visible_text_matches_qualified_xml_paragraph_order():
    import xml.etree.ElementTree as ET
    raw = FIXTURE.read_bytes(); result = reader.extract_pptx_pages(raw)
    with zipfile.ZipFile(BytesIO(raw)) as z:
        for page in result['pages']:
            root = ET.fromstring(z.read(f'ppt/slides/slide{page["page_number"]}.xml'))
            paragraphs = [''.join(n.text or '' for n in p.iter('{' + A + '}t')) for p in root.iter('{' + A + '}p')]
            assert page['text'] == '\n'.join(paragraphs)


def track_child(monkeypatch, code):
    import source_pdf_reader as engine
    original = engine.subprocess.Popen; processes = []
    def spawn(*args, **kwargs):
        process = original(*args, **kwargs); processes.append(process); return process
    monkeypatch.setattr(engine.subprocess, 'Popen', spawn)
    monkeypatch.setattr(reader, '_worker_command', lambda deadline: [sys.executable, '-B', '-c', code])
    return processes


def test_actual_timeout_kills_and_reaps_private_child(monkeypatch):
    processes = track_child(monkeypatch, 'import time; time.sleep(30)')
    started = time.monotonic()
    with pytest.raises(reader.SourcePptxError, match='timeout') as error:
        reader.extract_pptx_pages(package(), timeout_seconds=.15)
    assert time.monotonic() - started < 2
    assert error.value.retryable is False
    assert len(processes) == 1 and processes[0].returncode is not None
    with pytest.raises(ChildProcessError): os.waitpid(processes[0].pid, os.WNOHANG)


@pytest.mark.parametrize('stage', ['worker_return', 'validator_return'])
def test_final_handoff_cannot_outlive_original_deadline(monkeypatch, stage):
    raw = package(); result = reader.extract_pptx_pages(raw)
    def slow_worker(*args, **kwargs):
        if stage == 'worker_return': time.sleep(.04)
        return json.dumps(result).encode()
    monkeypatch.setattr(reader, '_run_worker', slow_worker)
    if stage == 'validator_return':
        original = reader._validate_result
        def validate(*args):
            value = original(*args); time.sleep(.04); return value
        monkeypatch.setattr(reader, '_validate_result', validate)
    with pytest.raises(reader.SourcePptxError, match='timeout'):
        reader.extract_pptx_pages(raw, timeout_seconds=.02)


@pytest.mark.parametrize('mutation', ['extra_key', 'wrong_hash', 'bool_count', 'hidden_overlap', 'bool_empty', 'missing_garbled', 'false_complete', 'unknown_error'])
def test_parent_refuses_forged_or_inconsistent_child_schema(monkeypatch, mutation):
    raw = package(('Original', '', '\uf075'))
    result = reader.extract_pptx_pages(raw)
    if mutation == 'extra_key': result['native_urls'] = ['https://unsafe.example']
    elif mutation == 'wrong_hash': result['content_sha256'] = '0' * 64
    elif mutation == 'bool_count': result['page_count'] = True
    elif mutation == 'hidden_overlap': result['hidden_pages'] = [1]
    elif mutation == 'bool_empty': result['empty_pages'] = [True]
    elif mutation == 'missing_garbled': result['garbled_pages'] = []
    elif mutation == 'false_complete': result['coverage_status'] = 'complete'
    else: result = {'error': 'unrecognized'}
    monkeypatch.setattr(reader, '_run_worker', lambda *a, **k: json.dumps(result).encode())
    with pytest.raises(reader.SourcePptxError) as error:
        reader.extract_pptx_pages(raw)
    assert error.value.reason in {'invalid_worker_result', 'worker_failed'}
    assert error.value.content_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('hidden,expected', [('1', 'Visible'), ('true', 'Visible'), ('0', 'Visible\nDraft'), ('false', 'Visible\nDraft')])
def test_native_shape_visibility_is_honored(hidden, expected):
    xml = (f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
           '<p:sp><p:txBody><a:p><a:r><a:t>Visible</a:t></a:r></a:p></p:txBody></p:sp>'
           f'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Draft" hidden="{hidden}"/></p:nvSpPr>'
           '<p:txBody><a:p><a:r><a:t>Draft</a:t></a:r></a:p></p:txBody></p:sp>'
           '</p:spTree></p:cSld></p:sld>')
    result = reader.extract_pptx_pages(package(replacements={'ppt/slides/slide1.xml': xml}))
    assert result['pages'] == [{'page_number': 1, 'text': expected}]


def test_hidden_group_cannot_be_unhidden_by_visible_child():
    xml = (f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
           '<p:sp><p:txBody><a:p><a:r><a:t>Visible</a:t></a:r></a:p></p:txBody></p:sp>'
           '<p:grpSp><p:nvGrpSpPr><p:cNvPr id="4" name="Hidden group" hidden="1"/></p:nvGrpSpPr>'
           '<p:sp><p:nvSpPr><p:cNvPr id="5" name="Visible child" hidden="0"/></p:nvSpPr>'
           '<p:txBody><a:p><a:r><a:t>Private draft</a:t></a:r></a:p></p:txBody></p:sp></p:grpSp>'
           '</p:spTree></p:cSld></p:sld>')
    result = reader.extract_pptx_pages(package(replacements={'ppt/slides/slide1.xml': xml}))
    assert result['pages'] == [{'page_number': 1, 'text': 'Visible'}]


def test_ambiguous_shape_visibility_is_not_claimed_as_visible_text():
    xml = (f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
           '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Ambiguous" hidden="perhaps"/></p:nvSpPr>'
           '<p:txBody><a:p><a:r><a:t>Unverified</a:t></a:r></a:p></p:txBody></p:sp>'
           '</p:spTree></p:cSld></p:sld>')
    with pytest.raises(reader.SourcePptxError):
        reader.extract_pptx_pages(package(replacements={'ppt/slides/slide1.xml': xml}))


def test_inline_alternate_runs_are_not_concatenated_as_one_source_statement():
    mc = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
    xml = (f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:mc="{mc}" xmlns:new="urn:unsupported-office-feature">'
           '<p:cSld><p:spTree><p:sp><p:txBody><a:p>'
           '<a:r><a:t>Revenue </a:t></a:r><mc:AlternateContent>'
           '<mc:Choice Requires="new"><a:r><a:t>10</a:t></a:r></mc:Choice>'
           '<mc:Fallback><a:r><a:t>999</a:t></a:r></mc:Fallback>'
           '</mc:AlternateContent></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
    with pytest.raises(reader.SourcePptxError):
        reader.extract_pptx_pages(package(replacements={'ppt/slides/slide1.xml': xml}))
