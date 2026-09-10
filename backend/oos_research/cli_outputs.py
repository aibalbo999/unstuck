"""Safe multi-output reservations for the offline OOS CLI."""

from __future__ import annotations

import os
from pathlib import Path


Reservation = tuple[Path, int, int]


def validate_new_outputs(*path_values: str | None) -> tuple[Path, ...]:
    paths: list[Path] = []
    for value in path_values:
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or path.is_symlink():
            raise ValueError("OOS output paths must be normalized and distinct")
        cursor = path.parent
        while cursor != cursor.parent:
            if cursor.is_symlink():
                raise ValueError("OOS output paths must be normalized and distinct")
            cursor = cursor.parent
        try:
            parent = path.parent.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError("OOS output paths must be normalized and distinct") from None
        normalized = parent / path.name
        if normalized != path or not parent.is_dir():
            raise ValueError("OOS output paths must be normalized and distinct")
        if normalized.exists():
            raise FileExistsError(f"OOS output already exists: {normalized}")
        paths.append(normalized)
    if len(set(paths)) != len(paths):
        raise ValueError("OOS output paths must be normalized and distinct")
    return tuple(paths)


def reserve_outputs(paths: tuple[Path, ...]) -> list[Reservation]:
    reservations: list[Reservation] = []
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        for path in paths:
            directory_fd = os.open(path.parent, directory_flags)
            try:
                file_fd = os.open(path.name, file_flags, 0o600, dir_fd=directory_fd)
            except BaseException:
                os.close(directory_fd)
                raise
            reservations.append((path, directory_fd, file_fd))
    except BaseException:
        close_reservations(reservations, remove=True)
        raise
    return reservations


def write_reserved(descriptor: int, data: str) -> None:
    view = memoryview(data.encode("utf-8"))
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short OOS output write")
        view = view[written:]
    os.fsync(descriptor)


def close_reservations(reservations: list[Reservation], *, remove: bool) -> None:
    for path, directory_fd, file_fd in reservations:
        try:
            os.close(file_fd)
        finally:
            if remove:
                try:
                    os.unlink(path.name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
            os.close(directory_fd)
