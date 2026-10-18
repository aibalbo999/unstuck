"""Private offline PPTX parser. Never follow links or execute embedded content."""
from io import BytesIO
import hashlib
import json
import posixpath
import re
import stat
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

from source_pdf_worker import _limits, _Failure as _ResourceFailure
from source_pptx_reader import _garbled

INPUT_LIMIT = 8 * 1024 * 1024
ENTRY_LIMIT = 2000
ENTRY_BYTES = 8 * 1024 * 1024
TOTAL_BYTES = 64 * 1024 * 1024
EXPANSION_RATIO = 100
PAGE_LIMIT = 100
CHAR_LIMIT = 200_000
XML_NODES = 200_000
XML_DEPTH = 64
RELATIONSHIP_LIMIT = 20_000
PARSER_VERSION = 'pptx-native-v1'

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
MAIN_TYPE = 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'
SLIDE_TYPE = 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'
XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class _Failure(Exception):
    pass


def _check(deadline):
    if time.monotonic() >= deadline: raise _Failure('timeout')


def _safe_name(name, *, directory=False):
    if (not isinstance(name, str) or not name or name.startswith('/') or
            any(c in name for c in ('\\', ':', '%', '#', '?', '\x00')) or
            any(ord(c) < 32 for c in name)):
        raise _Failure('unsafe_package')
    normalized = name[:-1] if directory and name.endswith('/') else name
    if not normalized or any(p in {'', '.', '..'} for p in normalized.split('/')):
        raise _Failure('unsafe_package')
    return normalized


def _xml(raw, deadline):
    _check(deadline)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        raise _Failure('invalid_xml') from None
    # Decode before checking: UTF-16 / NUL interleaving cannot hide a DTD.
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise _Failure('invalid_xml')
    encoding = re.search(r'<\?xml\s[^>]*encoding=[\'"]([^\'"]+)', text)
    if encoding and encoding[1].lower() not in {'utf-8', 'us-ascii'}:
        raise _Failure('invalid_xml')
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        raise _Failure('invalid_xml') from None
    stack = [(root, 1)]; nodes = 0
    while stack:
        node, depth = stack.pop(); nodes += 1
        if nodes > XML_NODES or depth > XML_DEPTH: raise _Failure('zip_limit')
        stack.extend((child, depth + 1) for child in node)
        _check(deadline)
    return root, nodes


def _content_types(tree, names):
    if tree.tag != '{' + CT + '}Types': raise _Failure('invalid_pptx')
    defaults, overrides = {}, {}
    for item in tree:
        content = item.attrib.get('ContentType', '')
        if not content: raise _Failure('invalid_pptx')
        if any(word in content.lower() for word in ('macroenabled', 'vbaproject', 'oleobject')):
            raise _Failure('active_content')
        if item.tag == '{' + CT + '}Default':
            extension = item.attrib.get('Extension', '')
            if not re.fullmatch(r'[A-Za-z0-9]+', extension) or extension.lower() in defaults:
                raise _Failure('invalid_pptx')
            defaults[extension.lower()] = content
        elif item.tag == '{' + CT + '}Override':
            part = item.attrib.get('PartName', '')
            if not part.startswith('/'): raise _Failure('unsafe_package')
            part = _safe_name(part[1:])
            if part in overrides or part not in names: raise _Failure('invalid_pptx')
            overrides[part] = content
        else:
            raise _Failure('invalid_pptx')
    return {name: overrides.get(name, defaults.get(name.rsplit('.', 1)[-1].lower(), '')) for name in names}


def _relationships(parsed, names, deadline):
    maps, external, count = {}, 0, 0
    for name, root in parsed.items():
        if not name.endswith('.rels'): continue
        if root.tag != '{' + REL + '}Relationships': raise _Failure('invalid_pptx')
        if name == '_rels/.rels':
            base = ''
        else:
            match = re.fullmatch(r'(.+)/_rels/([^/]+)\.rels', name)
            if not match or match[1] + '/' + match[2] not in names:
                raise _Failure('invalid_pptx')
            base = match[1]
        entries = {}
        for item in root:
            _check(deadline); count += 1
            if count > RELATIONSHIP_LIMIT: raise _Failure('zip_limit')
            if item.tag != '{' + REL + '}Relationship': raise _Failure('invalid_pptx')
            key, kind, target = (item.attrib.get(k, '') for k in ('Id', 'Type', 'Target'))
            mode = item.attrib.get('TargetMode', 'Internal')
            if not key or key in entries or not kind or not target or mode not in {'Internal', 'External'}:
                raise _Failure('invalid_pptx')
            if mode == 'External':
                external += 1
                # No URL parsing, file open or invocation, including external OLE.
                entries[key] = {'type': kind, 'external': True, 'target': None}
                continue
            if any(c in target for c in ('\\', ':', '%', '#', '?', '\x00')):
                raise _Failure('unsafe_package')
            resolved = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(base, target))
            _safe_name(resolved)
            if resolved not in names: raise _Failure('invalid_pptx')
            if kind.lower().endswith(('/oleobject', '/vbaproject')):
                raise _Failure('active_content')
            entries[key] = {'type': kind, 'external': False, 'target': resolved}
        maps[name] = entries
    return maps, external


def _visible_paragraphs(node, deadline):
    """Keep native XML order without treating hidden or alternate text as shown."""
    _check(deadline)
    properties = {'sp': 'nvSpPr', 'grpSp': 'nvGrpSpPr', 'graphicFrame': 'nvGraphicFramePr',
                  'pic': 'nvPicPr', 'cxnSp': 'nvCxnSpPr'}
    for kind, container in properties.items():
        if node.tag != '{' + P + '}' + kind:
            continue
        flags = node.findall('{' + P + '}' + container + '/{' + P + '}cNvPr')
        if len(flags) > 1:
            raise _Failure('invalid_pptx')
        if flags:
            hidden = flags[0].attrib.get('hidden', '0')
            if hidden not in {'0', '1', 'true', 'false'}:
                raise _Failure('invalid_pptx')
            if hidden in {'1', 'true'}:
                return  # A hidden group also hides all of its child shapes.
        break
    if node.tag == '{' + MC + '}AlternateContent':
        # Selecting an Office feature branch requires a capability profile.
        # Neither mutually exclusive branch may become native source text.
        if any(part.tag in {'{' + A + '}' + local for local in ('p', 't', 'br', 'tab')}
               for part in node.iter()):
            raise _Failure('invalid_pptx')
        return  # Image/OLE alternatives remain counted, omitted visual content.
    if node.tag == '{' + A + '}p':
        # AlternateContent may also replace runs inside a single paragraph.
        for alternate in node.iter('{' + MC + '}AlternateContent'):
            if any(part.tag in {'{' + A + '}' + local for local in ('p', 't', 'br', 'tab')}
                   for part in alternate.iter()):
                raise _Failure('invalid_pptx')
        yield node
        return
    for child in node:
        yield from _visible_paragraphs(child, deadline)


def _extract(raw, deadline):
    _check(deadline)
    if not isinstance(raw, bytes) or not raw.startswith(b'PK\x03\x04') or len(raw) > INPUT_LIMIT:
        raise _Failure('invalid_input')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        infos = archive.infolist()
        if not 1 <= len(infos) <= ENTRY_LIMIT: raise _Failure('zip_limit')
        names = [i.filename for i in infos]
        if len(set(n.casefold() for n in names)) != len(names): raise _Failure('unsafe_package')
        if sum(i.file_size for i in infos) > TOTAL_BYTES: raise _Failure('zip_limit')
        offsets = set()
        for info in infos:
            _check(deadline); _safe_name(info.filename, directory=info.is_dir())
            if info.header_offset in offsets or not 0 <= info.header_offset < archive.start_dir:
                raise _Failure('unsafe_package')
            offsets.add(info.header_offset)
            if info.flag_bits & 1: raise _Failure('encrypted_package')
            if stat.S_ISLNK(info.external_attr >> 16): raise _Failure('unsafe_package')
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise _Failure('unsafe_package')
            if info.file_size > ENTRY_BYTES or info.file_size / max(1, info.compress_size) > EXPANSION_RATIO:
                raise _Failure('zip_limit')
            lower = info.filename.lower()
            if 'vbaproject' in lower or lower.endswith(('.vba', '.bin', '.exe', '.dll', '.js')):
                raise _Failure('active_content')
        parsed, total_nodes, embedded = {}, 0, []
        for info in infos:
            _check(deadline)
            if info.is_dir():
                if info.file_size: raise _Failure('unsafe_package')
                continue
            lower = info.filename.lower()
            is_xml = lower.endswith(('.xml', '.rels'))
            is_embedded = '/embeddings/' in lower
            if is_embedded and not lower.endswith('.xlsx'): raise _Failure('active_content')
            chunks, actual, prefix = [], 0, b''
            # Read only for CRC and actual length, discard images/embedded bytes.
            # Nothing is extracted to disk or passed to an application.
            with archive.open(info) as member:
                while chunk := member.read(65536):
                    _check(deadline); actual += len(chunk)
                    if actual > info.file_size or actual > ENTRY_BYTES: raise _Failure('zip_limit')
                    if not prefix: prefix = chunk[:8]
                    if is_xml: chunks.append(chunk)
            if actual != info.file_size: raise _Failure('invalid_pptx')
            if is_embedded:
                if not prefix.startswith(b'PK\x03\x04'): raise _Failure('active_content')
                embedded.append(info.filename)
            if is_xml:
                tree, nodes = _xml(b''.join(chunks), deadline)
                parsed[info.filename] = tree; total_nodes += nodes
                if total_nodes > XML_NODES: raise _Failure('zip_limit')
        _check(deadline)
        required = {'[Content_Types].xml', '_rels/.rels', 'ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels'}
        if not required <= parsed.keys(): raise _Failure('invalid_pptx')
        types = _content_types(parsed['[Content_Types].xml'], set(names))
        if types['ppt/presentation.xml'] != MAIN_TYPE or any(types[p] != XLSX_TYPE for p in embedded):
            raise _Failure('invalid_pptx')
        maps, external = _relationships(parsed, set(names), deadline)
        office = [r for r in maps['_rels/.rels'].values() if r['type'] == R + '/officeDocument']
        if len(office) != 1 or office[0]['external'] or office[0]['target'] != 'ppt/presentation.xml':
            raise _Failure('invalid_pptx')
        document = parsed['ppt/presentation.xml']
        if document.tag != '{' + P + '}presentation': raise _Failure('invalid_pptx')
        lists = document.findall('{' + P + '}sldIdLst')
        if len(lists) != 1: raise _Failure('invalid_pptx')
        entries = list(lists[0])
        if not 1 <= len(entries) <= PAGE_LIMIT: raise _Failure('slide_limit')
        pages, hidden, seen_targets, seen_ids, chars = [], [], set(), set(), 0
        for number, entry in enumerate(entries, 1):
            _check(deadline)
            if entry.tag != '{' + P + '}sldId': raise _Failure('invalid_pptx')
            slide_id = entry.attrib.get('id', '')
            if not re.fullmatch(r'[0-9]+', slide_id) or slide_id in seen_ids: raise _Failure('invalid_pptx')
            seen_ids.add(slide_id)
            ref = entry.attrib.get('{' + R + '}id')
            link = maps['ppt/_rels/presentation.xml.rels'].get(ref)
            if not link or link['external'] or link['type'] != R + '/slide': raise _Failure('invalid_pptx')
            path = link['target']
            if path in seen_targets or types.get(path) != SLIDE_TYPE or path not in parsed:
                raise _Failure('invalid_pptx')
            seen_targets.add(path); slide = parsed[path]
            if slide.tag != '{' + P + '}sld': raise _Failure('invalid_pptx')
            show = slide.attrib.get('show', '1')
            if show not in {'0', '1', 'true', 'false'}: raise _Failure('invalid_pptx')
            if show in {'0', 'false'}:
                hidden.append(number)
                continue
            paragraphs = []
            for paragraph in _visible_paragraphs(slide, deadline):
                fragments = []
                for node in paragraph.iter():
                    if node.tag == '{' + A + '}t': fragments.append(node.text or '')
                    elif node.tag == '{' + A + '}br': fragments.append('\n')
                    elif node.tag == '{' + A + '}tab': fragments.append('\t')
                paragraphs.append(''.join(fragments))
            text = '\n'.join(paragraphs); chars += len(text)
            if chars > CHAR_LIMIT: raise _Failure('character_limit')
            pages.append({'page_number': number, 'text': text})
        empty = [p['page_number'] for p in pages if not p['text'].strip()]
        if not pages or len(empty) == len(pages): raise _Failure('empty_document')
        garbled = [p['page_number'] for p in pages if _garbled(p['text'])]
        _check(deadline)
        return {'pages': pages, 'page_count': len(pages), 'total_slide_count': len(entries),
                'hidden_pages': hidden, 'empty_pages': empty, 'garbled_pages': garbled,
                'coverage_status': 'partial' if empty or garbled else 'complete',
                'content_sha256': hashlib.sha256(raw).hexdigest(), 'parser_version': PARSER_VERSION,
                'external_relationship_count': external, 'embedded_object_count': len(embedded)}


def main():
    try:
        deadline = float(sys.argv[1]); _limits(deadline)
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        result = _extract(raw, deadline)
        _check(deadline)
    except (_Failure, _ResourceFailure) as exc:
        result = {'error': str(exc)}
    except MemoryError:
        result = {'error': 'memory_limit'}
    except Exception:
        result = {'error': 'invalid_pptx'}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True, separators=(',', ':')).encode('ascii'))
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
