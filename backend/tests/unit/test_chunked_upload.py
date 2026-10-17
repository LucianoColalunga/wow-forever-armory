"""Sesiones de subida por partes (sin base de datos)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.importer import chunked
from app.importer.validation import InvalidUpload

MB = 1024 * 1024


def test_chunks_are_appended_in_order_and_retries_are_idempotent(tmp_path: Path) -> None:
    sess = chunked.start(tmp_path, "user:1", "WoWCombatLog.txt", 10, MB)
    sess = chunked.append_chunk(tmp_path, sess, 0, b"hola ")
    # Reintento de red de la misma parte: no se duplica.
    sess = chunked.append_chunk(tmp_path, sess, 0, b"hola ")
    assert (sess.received, sess.next_index) == (5, 1)
    with pytest.raises(chunked.ChunkOutOfOrder):
        chunked.append_chunk(tmp_path, sess, 2, b"mundo")
    sess = chunked.append_chunk(tmp_path, sess, 1, b"mundo")
    assert sess.complete
    with chunked.open_data(tmp_path, sess) as fh:
        assert fh.read() == b"hola mundo"
    chunked.discard(tmp_path, sess.id)
    with pytest.raises(chunked.UploadNotFound):
        chunked.load(tmp_path, sess.id, "user:1")


def test_sessions_belong_to_their_owner(tmp_path: Path) -> None:
    sess = chunked.start(tmp_path, "user:1", "log.zip", 10, MB)
    assert chunked.load(tmp_path, sess.id, "user:1").id == sess.id
    with pytest.raises(chunked.UploadNotFound):
        chunked.load(tmp_path, sess.id, "user:2")
    with pytest.raises(chunked.UploadNotFound):
        chunked.load(tmp_path, "../../etc", "user:1")


@pytest.mark.parametrize(
    ("name", "size", "message"),
    [
        ("virus.exe", 10, "Extensión"),
        ("log.txt", 0, "vacío"),
        ("log.txt", 2 * MB, "máximo"),
    ],
)
def test_start_rejects_bad_files(tmp_path: Path, name: str, size: int, message: str) -> None:
    with pytest.raises(InvalidUpload, match=message):
        chunked.start(tmp_path, "user:1", name, size, MB)


def test_more_bytes_than_declared_are_rejected(tmp_path: Path) -> None:
    sess = chunked.start(tmp_path, "user:1", "log.txt", 3, MB)
    with pytest.raises(InvalidUpload, match="tamaño declarado"):
        chunked.append_chunk(tmp_path, sess, 0, b"demasiado")


def test_active_sessions_per_owner_are_limited(tmp_path: Path) -> None:
    for _ in range(chunked.MAX_ACTIVE_PER_OWNER):
        chunked.start(tmp_path, "user:1", "log.txt", 10, MB)
    with pytest.raises(InvalidUpload, match="subidas en curso"):
        chunked.start(tmp_path, "user:1", "log.txt", 10, MB)
    # Otra cuenta no se ve afectada.
    chunked.start(tmp_path, "user:2", "log.txt", 10, MB)


def test_expired_sessions_are_cleaned(tmp_path: Path) -> None:
    sess = chunked.start(tmp_path, "user:1", "log.txt", 10, MB)
    assert chunked.cleanup_expired(tmp_path, now=time.time() + chunked.SESSION_TTL_S + 1) == 1
    with pytest.raises(chunked.UploadNotFound):
        chunked.load(tmp_path, sess.id, "user:1")
