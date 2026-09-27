"""Offline behavior checks for the private killable PDF parser."""
import hashlib
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import time
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import source_pdf_reader as reader


@pytest.fixture(autouse=True)
def evidence_only_dependency(monkeypatch):
    """Local dependency injection is test-only; no production import override."""
    dependency = os.environ.get('SOURCE_PDF_TEST_DEPENDENCY_PATH')
    if dependency:
        worker = Path(reader.__file__).with_name('source_pdf_worker.py')
        code = f'import sys,runpy;sys.path.insert(0,{dependency!r});runpy.run_path({str(worker)!r},run_name="__main__")'
        monkeypatch.setattr(reader, '_worker_command', lambda deadline: [sys.executable, '-B', '-c', code, str(deadline)])


def make_pdf(texts, *, compressed=False, stream_override=None, replacement_mapping=False):
    """Small valid PDF, generated without production/provider dependencies."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for text in texts:
        page = len(objects) + 1
        kids.append(f'{page} 0 R'.encode())
        stream = b'BT /F1 12 Tf 10 100 Td (' + text + b') Tj ET' if text else b''
        if stream_override is not None:
            stream = stream_override
        if compressed:
            stream = zlib.compress(stream)
        objects.extend([
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 3 0 R >> >> /Contents {page+1} 0 R >>'.encode(),
            b'<< /Length ' + str(len(stream)).encode() + (b' /Filter /FlateDecode' if compressed else b'') + b' >>\nstream\n' + stream + b'\nendstream',
        ])
    if replacement_mapping:
        mapping = b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n1 begincodespacerange <00> <FF> endcodespacerange\n1 beginbfchar <41> <FFFD> endbfchar\nendcmap CMapName currentdict /CMap defineresource pop end end'
        objects[2] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode ' + str(len(objects)+1).encode() + b' 0 R >>'
        objects.append(b'<< /Length ' + str(len(mapping)).encode() + b' >>\nstream\n' + mapping + b'\nendstream')
    objects[1] = b'<< /Type /Pages /Count ' + str(len(kids)).encode() + b' /Kids [' + b' '.join(kids) + b'] >>'
    data = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(data)
    data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        data.extend(f'{offset:010} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(data)


def test_native_pages_preserve_original_text_and_hash():
    raw = make_pdf([b'2026-04-15 Revenue 123.450', b'Page two'])
    result = reader.extract_pdf_pages(raw)
    assert result['pages'] == [{'page_number': 1, 'text': '2026-04-15 Revenue 123.450'},
                               {'page_number': 2, 'text': 'Page two'}]
    assert result['page_count'] == 2
    assert result['empty_pages'] == []
    assert result['coverage_status'] == 'complete'
    assert result['parser_version'] == '6.19.0'
    assert result['content_sha256'] == hashlib.sha256(raw).hexdigest()


def test_empty_page_preserved_as_partial_and_all_empty_fails():
    raw = make_pdf([b'Original', b'', b'Last'])
    result = reader.extract_pdf_pages(raw)
    assert result['page_count'] == 3 and result['empty_pages'] == [2]
    assert result['pages'][1] == {'page_number': 2, 'text': ''}
    assert result['coverage_status'] == 'partial'
    with pytest.raises(reader.SourcePdfError, match='empty_document'):
        reader.extract_pdf_pages(make_pdf([b'', b'']))


def test_garbled_page_retains_raw_text_and_marks_partial():
    result = reader.extract_pdf_pages(make_pdf([b'A'], replacement_mapping=True))
    assert result['pages'][0]['text'] == '\ufffd'
    assert result['garbled_pages'] == [1]
    assert result['empty_pages'] == [] and result['coverage_status'] == 'partial'


@pytest.mark.parametrize('value', [b'', 'not bytes', b'X' * (reader.INPUT_LIMIT + 1)])
def test_input_bounds_refuse_before_spawning(value, monkeypatch):
    monkeypatch.setattr(reader.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spawn'))
    with pytest.raises(reader.SourcePdfError, match='invalid_input'):
        reader.extract_pdf_pages(value)


@pytest.mark.parametrize('timeout', [0, -1, 11, float('nan'), float('inf'), True, '1', 10**1000])
def test_invalid_deadline_is_refused_before_spawning(timeout, monkeypatch):
    monkeypatch.setattr(reader.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spawn'))
    with pytest.raises(reader.SourcePdfError, match='invalid_timeout'):
        reader.extract_pdf_pages(make_pdf([b'Valid']), timeout_seconds=timeout)


def test_page_and_text_limits_fail_without_truncated_success():
    with pytest.raises(reader.SourcePdfError, match='page_limit'):
        reader.extract_pdf_pages(make_pdf([b'A'] * 101))
    with pytest.raises(reader.SourcePdfError, match='character_limit'):
        reader.extract_pdf_pages(make_pdf([b'A' * 100_001, b'B' * 100_000]))
    boundary = reader.extract_pdf_pages(make_pdf([b'A' * 100_000, b'B' * 100_000]))
    assert sum(len(page['text']) for page in boundary['pages']) == 200_000
    assert boundary['coverage_status'] == 'complete'


def test_compressed_stream_bomb_fails_closed():
    raw = make_pdf([b''], compressed=True, stream_override=b' ' * (8 * 1024 * 1024 + 1))
    assert len(raw) < 20000
    with pytest.raises(reader.SourcePdfError, match='stream_limit'):
        reader.extract_pdf_pages(raw)


def test_malformed_pdf_is_not_empty_success():
    raw = b'%PDF-1.4\nnot a valid document\n%%EOF'
    with pytest.raises(reader.SourcePdfError) as caught:
        reader.extract_pdf_pages(raw)
    assert caught.value.error_kind in {'invalid_pdf', 'parser_warning'}
    assert caught.value.content_sha256 == hashlib.sha256(raw).hexdigest()
    assert caught.value.retryable is False


def track_child(monkeypatch, code):
    processes = []
    original = subprocess.Popen
    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(reader.subprocess, 'Popen', spawn)
    monkeypatch.setattr(reader, '_worker_command', lambda _deadline: [sys.executable, '-B', '-c', code])
    return processes


def assert_reaped(processes):
    assert len(processes) == 1
    assert processes[0].returncode is not None
    with pytest.raises(ChildProcessError):
        os.waitpid(processes[0].pid, os.WNOHANG)


def test_timeout_kills_and_reaps_child_even_when_stdin_is_not_consumed(monkeypatch):
    processes = track_child(monkeypatch, 'import time; time.sleep(30)')
    started = time.monotonic()
    with pytest.raises(reader.SourcePdfError, match='timeout'):
        reader.extract_pdf_pages(b'%PDF-' + b' ' * 1_000_000, timeout_seconds=.15)
    assert time.monotonic() - started < 2
    assert_reaped(processes)


@pytest.mark.parametrize('stream,expected', [('stdout', 'stdout_limit'), ('stderr', 'stderr_limit')])
def test_unbounded_child_output_is_capped_killed_and_reaped(monkeypatch, stream, expected):
    code = f'import os; data=b"X"*65536\nwhile True: os.write({1 if stream == "stdout" else 2}, data)'
    processes = track_child(monkeypatch, code)
    with pytest.raises(reader.SourcePdfError, match=expected):
        reader.extract_pdf_pages(make_pdf([b'A']))
    assert_reaped(processes)


def test_resident_memory_limit_kills_and_reaps_child(monkeypatch):
    monkeypatch.setattr(reader, 'MEMORY_LIMIT', 24 * 1024 * 1024)
    processes = track_child(monkeypatch, 'import time; data=bytearray(40*1024*1024); time.sleep(30)')
    with pytest.raises(reader.SourcePdfError, match='memory_limit'):
        reader.extract_pdf_pages(make_pdf([b'A']))
    assert_reaped(processes)


def test_unavailable_memory_accounting_fails_closed_before_spawn(monkeypatch):
    monkeypatch.setattr(reader, '_memory_sampler', lambda: (_ for _ in ()).throw(reader.SourcePdfError('memory_accounting_unavailable')))
    monkeypatch.setattr(reader.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not spawn'))
    with pytest.raises(reader.SourcePdfError, match='memory_accounting_unavailable'):
        reader.extract_pdf_pages(make_pdf([b'A']))


def test_interrupt_kills_and_reaps_child(monkeypatch):
    processes = track_child(monkeypatch, 'import time; time.sleep(30)')
    def interrupt(_pid):
        raise KeyboardInterrupt
    monkeypatch.setattr(reader, '_memory_sampler', lambda: interrupt)
    with pytest.raises(KeyboardInterrupt):
        reader.extract_pdf_pages(make_pdf([b'A']))
    assert_reaped(processes)


@pytest.mark.parametrize('payload', [b'{}', b'not json', b'{"error":"SECRET source content"}'])
def test_invalid_protocol_does_not_publish_partial_data_or_child_text(monkeypatch, payload):
    processes = track_child(monkeypatch, f'import sys;sys.stdin.buffer.read();sys.stdout.buffer.write({payload!r})')
    with pytest.raises(reader.SourcePdfError) as caught:
        reader.extract_pdf_pages(make_pdf([b'A']))
    assert 'SECRET' not in str(caught.value)
    assert_reaped(processes)


def test_worker_resource_limits_fail_closed(monkeypatch):
    import resource
    import source_pdf_worker as worker
    monkeypatch.setattr(resource, 'setrlimit', lambda *a: (_ for _ in ()).throw(ValueError('unsupported')))
    with pytest.raises(worker._Failure, match='resource_limits_unavailable'):
        worker._limits(time.monotonic() + 2)


def test_encrypted_document_is_explicitly_refused(monkeypatch):
    dependency = os.environ.get('SOURCE_PDF_TEST_DEPENDENCY_PATH')
    if dependency:
        monkeypatch.syspath_prepend(dependency)
    from pypdf import PdfReader, PdfWriter
    output = BytesIO()
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(make_pdf([b'Secret']))))
    writer.encrypt('password')
    writer.write(output)
    with pytest.raises(reader.SourcePdfError, match='encrypted_pdf'):
        reader.extract_pdf_pages(output.getvalue())


def test_cpu_limit_stops_worker_independently_of_parent_timeout(monkeypatch):
    backend = str(Path(reader.__file__).parent)
    code = f'import sys,time;sys.path.insert(0,{backend!r});from source_pdf_worker import _limits;_limits(time.monotonic()+.2)\nwhile True: pass'
    processes = track_child(monkeypatch, code)
    started = time.monotonic()
    with pytest.raises(reader.SourcePdfError, match='worker_failed'):
        reader.extract_pdf_pages(make_pdf([b'A']), timeout_seconds=4)
    assert time.monotonic() - started < 3
    assert processes[0].returncode < 0
    assert_reaped(processes)


def test_parser_warning_is_not_silent_full_coverage(monkeypatch):
    import source_pdf_worker as worker
    import logging
    handler = worker._FailOnWarning()
    with pytest.raises(worker._Failure, match='parser_warning'):
        handler.handle(logging.LogRecord('pypdf', logging.WARNING, '', 0, 'source text', (), None))
