"""Create-only local bundles. Partial attempts are retained, never rolled back.

The root lock serializes cooperating local storage users. Exclusive file opens
and a plain SQLite INSERT also reject collisions after preflight. This is not a
cross-filesystem/SQLite transaction or protection from a noncooperating writer;
the campaign controller must still establish sole-writer ownership.
"""

from contextlib import contextmanager
import hashlib
import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile

from ._local_file_operations import exclusive_storage_lock, fsync_directory, metadata_path
from .report_storage import LocalFileStorage
from .capacity import reserve_write


_RECEIPTS = ".onstock-storage-publications.tmp"  # Reserved by normal local storage.
_COMPLETE = b"complete\n"


def _receipt_paths(root, filename):
    directory = Path(root) / _RECEIPTS
    identity = hashlib.sha256(filename.encode("utf-8")).hexdigest()
    return directory, directory / f"{identity}.attempt", directory / f"{identity}.complete"


def publication_is_pending(root, filename):
    """Legacy reports have no receipt; incomplete new attempts stay hidden."""
    directory, attempt, complete = _receipt_paths(root, filename)
    if not os.path.lexists(directory):
        return False
    if (directory.is_symlink() or not directory.is_dir()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700):
        return True
    if not os.path.lexists(attempt) and not os.path.lexists(complete):
        return False
    if (attempt.is_symlink() or not attempt.is_file()
            or complete.is_symlink() or not complete.is_file()):
        return True
    try:
        with complete.open("rb") as handle:
            return handle.read(len(_COMPLETE) + 1) != _COMPLETE
    except OSError:
        return True


def _complete_attempt(path):
    # The complete marker becomes visible only after its bytes are durable.
    # A crash/uncertain INSERT never reaches here. A directory fsync failure
    # after rename remains uncertain to the caller, but cannot expose a partial
    # bundle: files and INSERT were already confirmed before this operation.
    with NamedTemporaryFile(dir=path.parent, prefix=".ready-", delete=False) as handle:
        pending = Path(handle.name)
        handle.write(_COMPLETE)
        handle.flush()
        os.fsync(handle.fileno())
    # Called only while holding the root lock through the INSERT. Cooperating
    # writers cannot race this check. Unlike a hard link, rename also keeps each
    # file single-linked under the campaign write guard. Noncooperating writers
    # remain outside this contract; the controller must own this private root.
    if os.path.lexists(path):
        raise FileExistsError("publication completion receipt already exists")
    os.rename(pending, path)
    fsync_directory(path.parent)


def _create_file(path, payload):
    # O_EXCL rejects existing files, directories and dangling symlinks. Never
    # unlink on a failed write/fsync: those bytes are evidence of an attempt.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(path.parent)


@contextmanager
def create_only_bundle(storage, *, output_dir, filename, candidates, contents):
    """Hold a local bundle boundary through index insertion by the caller."""
    if type(storage) is not LocalFileStorage or not output_dir:
        raise ValueError("create-only publication requires explicit LocalFileStorage")
    root = Path(output_dir)
    if (not root.is_absolute() or root.is_symlink() or root.resolve(strict=True) != storage._root):
        raise ValueError("create-only output directory does not match storage")
    contents = list(contents)
    admission_payloads = [value for _, payload, content_type in contents for value in (
        payload, json.dumps({"content_type": content_type, "sha256": hashlib.sha256(payload).hexdigest()},
                            separators=(",", ":")).encode())]
    known = sum(len(payload) for payload in admission_payloads) + (len(contents) + 2) * 4096
    with reserve_write(storage._root, known, 'Create-only bundle exact bodies/metadata and publication markers'), exclusive_storage_lock(storage._root):
        directory, attempt, complete = _receipt_paths(storage._root, filename)
        if (os.path.lexists(directory) and (directory.is_symlink() or not directory.is_dir())):
            raise ValueError("invalid private publication receipt directory")
        if os.path.lexists(attempt) or os.path.lexists(complete):
            raise FileExistsError("report identity already has a retained publication attempt")
        targets = []
        for key in candidates:
            _, target = storage._target(key)
            for path in (target, metadata_path(target)):
                if os.path.lexists(path):
                    raise FileExistsError("report identity already has retained artifacts")
        for key, payload, content_type in contents:
            normalized, target = storage._target(key)
            targets.append((normalized, target, payload, content_type))

        def write_contents():
            directory.mkdir(mode=0o700, exist_ok=True)
            fsync_directory(directory.parent)
            _create_file(attempt, b"attempt\n")
            for normalized, target, payload, content_type in targets:
                missing = []
                parent = target.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for created_parent in reversed(missing):
                    created_parent.mkdir(mode=0o700, exist_ok=True)
                    fsync_directory(created_parent.parent)
                storage._assert_no_symlink_components(normalized)
                _create_file(metadata_path(target), json.dumps({
                    "content_type": content_type, "sha256": hashlib.sha256(payload).hexdigest(),
                }, separators=(",", ":")).encode())
                _create_file(target, payload)

        yield write_contents
        _complete_attempt(complete)
