"""Lightweight, process-local file locks for concurrent writers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Iterator

_LOCKS: dict[str, Lock] = {}
_LOCKS_GUARD = Lock()


def _lock_for(path: Path) -> Lock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _LOCKS[key] = lock
    return lock


@contextmanager
def locked_path(path: Path) -> Iterator[None]:
    """Serialize access to a single path within this process."""
    lock = _lock_for(path)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
