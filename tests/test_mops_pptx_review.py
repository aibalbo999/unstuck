"""Independent public-reader adversarial boundaries; no network or formal state."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import source_pptx_reader as reader
from test_source_pptx_reader import package, P, A, R, REL, FIXTURE, track_child

MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'


def shape(text, *, hidden=False, shape_id=2):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Review shape"' +
            (' hidden="1"' if hidden else '') + '/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>' +
            text + '</a:t></a:r></a:p></p:txBody></p:sp>')


def slide(children):
    return (f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:mc="{MC}" '
            'xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">'
            '<p:cSld><p:spTree>' + children + '</p:spTree></p:cSld></p:sld>')


def extract_or_reject(raw):
    try:
        return reader.extract_pptx_pages(raw)
    except reader.SourcePptxError:
        return None  # conservative unsupported-profile rejection is acceptable


def test_hidden_shape_cannot_be_claimed_as_visible_native_text():
    raw = package(replacements={'ppt/slides/slide1.xml': slide(
        shape('Visible earnings 10') + shape('Hidden draft earnings 999', hidden=True, shape_id=3))})
    result = extract_or_reject(raw)
    if result is not None:
        assert 'Visible earnings 10' in result['pages'][0]['text']
        assert 'Hidden draft earnings 999' not in result['pages'][0]['text']


def test_mutually_exclusive_choice_and_fallback_cannot_both_be_source_text():
    branches = ('<mc:AlternateContent><mc:Choice Requires="a14">' +
                shape('Current revenue 10', shape_id=3) + '</mc:Choice><mc:Fallback>' +
                shape('Legacy revenue 999', shape_id=4) + '</mc:Fallback></mc:AlternateContent>')
    raw = package(replacements={'ppt/slides/slide1.xml': slide(shape('Cover') + branches)})
    result = extract_or_reject(raw)
    if result is not None:
        text = result['pages'][0]['text']
        assert not ('Current revenue 10' in text and 'Legacy revenue 999' in text)


def test_presentation_order_not_zip_name_order_drives_visible_numbers():
    raw = package(('First file', 'Second file'))
    with zipfile.ZipFile(BytesIO(raw)) as z:
        document = z.read('ppt/presentation.xml').decode().replace('r:id="rId1"', 'r:id="TEMP"').replace('r:id="rId2"', 'r:id="rId1"').replace('r:id="TEMP"', 'r:id="rId2"')
    result = reader.extract_pptx_pages(package(('First file', 'Second file'), replacements={'ppt/presentation.xml': document}))
    assert result['pages'] == [{'page_number': 1, 'text': 'Second file'}, {'page_number': 2, 'text': 'First file'}]


@pytest.mark.parametrize('show', ['0', 'false'])
def test_hidden_slide_wholly_excluded_even_when_text_garbled(show):
    hidden = slide(shape('\uf075 hidden')).replace('<p:sld ', f'<p:sld show="{show}" ', 1)
    result = reader.extract_pptx_pages(package(('Visible', 'replace'), replacements={'ppt/slides/slide2.xml': hidden}))
    assert result['hidden_pages'] == [2]
    assert result['pages'] == [{'page_number': 1, 'text': 'Visible'}]
    assert result['garbled_pages'] == []


def test_image_only_visible_page_is_retained_as_empty_partial_not_invented_text():
    raw = package(('Cover', ''), extras={'ppt/media/image.png': b'not-rendered-image'})
    result = reader.extract_pptx_pages(raw)
    assert result['pages'][1] == {'page_number': 2, 'text': ''}
    assert result['empty_pages'] == [2] and result['coverage_status'] == 'partial'


def test_notes_are_not_transcript_or_slide_text():
    notes = f'<p:notes xmlns:p="{P}" xmlns:a="{A}"><a:p><a:r><a:t>Private notes</a:t></a:r></a:p></p:notes>'
    result = reader.extract_pptx_pages(package(extras={'ppt/notesSlides/notesSlide1.xml': notes}))
    assert result['pages'] == [{'page_number': 1, 'text': 'Original'}]
    assert 'Private notes' not in json.dumps(result)


@pytest.mark.parametrize('target', ['../../../../secret', '../%2e%2e/secret', 'file:///private/key', 'https://invalid.example/evil'])
def test_internal_relationship_cannot_escape_package_or_fetch(target):
    rels = f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/image" Target="{target}"/></Relationships>'
    with pytest.raises(reader.SourcePptxError):
        reader.extract_pptx_pages(package(extras={'ppt/slides/_rels/slide1.xml.rels': rels}))


def test_case_aliased_parts_are_not_allowed():
    with pytest.raises(reader.SourcePptxError, match='unsafe_package'):
        reader.extract_pptx_pages(package(extras={'PPT/SLIDES/SLIDE1.XML': b'x'}))


def test_symlink_zip_part_is_rejected_without_opening_target():
    raw = BytesIO(package())
    with zipfile.ZipFile(raw, 'a') as z:
        entry = zipfile.ZipInfo('ppt/media/link')
        entry.create_system = 3
        entry.external_attr = 0o120777 << 16
        z.writestr(entry, '/private/never-open')
    with pytest.raises(reader.SourcePptxError, match='unsafe_package'):
        reader.extract_pptx_pages(raw.getvalue())


def test_zip_header_aliasing_is_rejected():
    raw = bytearray(package())
    positions = []
    position = 0
    while True:
        position = raw.find(b'PK\x01\x02', position)
        if position < 0: break
        positions.append(position)
        position += 4
    raw[positions[1]+42:positions[1]+46] = raw[positions[0]+42:positions[0]+46]
    with pytest.raises(reader.SourcePptxError, match='unsafe_package'):
        reader.extract_pptx_pages(bytes(raw))


@pytest.mark.parametrize('channel,size', [('stdout', 3*1024*1024+1), ('stderr', 8193)])
def test_untrusted_child_output_limit_kills_and_reaps(monkeypatch, channel, size):
    processes = track_child(monkeypatch, f'import sys,time; sys.stdin.buffer.read(); sys.{channel}.buffer.write(b"x"*{size}); sys.{channel}.buffer.flush(); time.sleep(30)')
    started = time.monotonic()
    with pytest.raises(reader.SourcePptxError, match=channel + '_limit'):
        reader.extract_pptx_pages(package(), timeout_seconds=2)
    assert time.monotonic() - started < 3
    assert len(processes) == 1 and processes[0].returncode is not None


def test_published_original_matches_frozen_capture_and_byte_hash():
    raw = FIXTURE.read_bytes()
    saved = json.loads((Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261014/mops-material-integration/pptx/public-original-result.json').read_text())
    result = reader.extract_pptx_pages(raw)
    # Capture holds the actual public result, not a seeded runtime cache.
    if 'result' in saved: saved = saved['result']
    assert result == saved
    assert result['content_sha256'] == hashlib.sha256(raw).hexdigest()
