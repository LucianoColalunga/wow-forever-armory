"""Subidas por partes.

Los combat logs reales pesan decenas o cientos de MB y el proxy web (funciones de Vercel) acepta como
máximo 4,5 MB por pedido. El navegador parte el archivo en trozos de ``CHUNK_BYTES``, la API los
concatena en disco y, al completar, el archivo entra por el mismo camino que una subida directa
(validación, deduplicación, cola). Las sesiones viven en ``STORAGE_DIR/uploads`` y vencen solas.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO

from app.importer.validation import ALLOWED_TEXT_EXT, ALLOWED_ZIP_EXT, InvalidUpload, safe_filename

CHUNK_BYTES = 4 * 1024 * 1024  # entra con margen en el límite de 4,5 MB por pedido de Vercel
SESSION_TTL_S = 2 * 3600
MAX_ACTIVE_PER_OWNER = 3
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{24,64}$")
_lock = threading.Lock()


class UploadNotFound(LookupError):
    """La subida no existe, venció o pertenece a otra cuenta (no se distingue a propósito)."""


class ChunkOutOfOrder(ValueError):
    """La parte recibida no es la siguiente esperada."""


@dataclass(slots=True)
class UploadSession:
    id: str
    owner: str
    file_name: str
    size: int
    received: int
    next_index: int
    last_chunk_size: int
    created_at: float

    @property
    def complete(self) -> bool:
        return self.received == self.size


def _root(storage_dir: Path) -> Path:
    return storage_dir / "uploads"


def _dir(storage_dir: Path, upload_id: str) -> Path:
    return _root(storage_dir) / upload_id


def _write_meta(storage_dir: Path, sess: UploadSession) -> None:
    path = _dir(storage_dir, sess.id) / "meta.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(sess)), encoding="utf-8")
    os.replace(tmp, path)


def _read_meta(path: Path) -> UploadSession | None:
    try:
        return UploadSession(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def cleanup_expired(storage_dir: Path, now: float | None = None) -> int:
    """Borra sesiones vencidas o ilegibles. Devuelve cuántas eliminó."""
    root = _root(storage_dir)
    if not root.is_dir():
        return 0
    now = now if now is not None else time.time()
    removed = 0
    for d in root.iterdir():
        if not d.is_dir():
            continue
        sess = _read_meta(d / "meta.json")
        created = sess.created_at if sess else d.stat().st_mtime
        if now - created > SESSION_TTL_S:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed


def _active_for(storage_dir: Path, owner: str) -> int:
    root = _root(storage_dir)
    if not root.is_dir():
        return 0
    return sum(1 for d in root.iterdir() if (s := _read_meta(d / "meta.json")) is not None and s.owner == owner)


def start(storage_dir: Path, owner: str, file_name: str, size: int, max_bytes: int) -> UploadSession:
    name = safe_filename(file_name)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_TEXT_EXT | ALLOWED_ZIP_EXT:
        raise InvalidUpload("Extensión no permitida: usá .txt, .log o .zip.")
    if size <= 0:
        raise InvalidUpload("El archivo está vacío.")
    if size > max_bytes:
        raise InvalidUpload(f"El archivo supera el máximo permitido ({max_bytes // (1024 * 1024)} MB).")
    with _lock:
        cleanup_expired(storage_dir)
        if _active_for(storage_dir, owner) >= MAX_ACTIVE_PER_OWNER:
            raise InvalidUpload("Tenés demasiadas subidas en curso: terminá o cancelá alguna.")
        sess = UploadSession(secrets.token_urlsafe(24), owner, name, size, 0, 0, 0, time.time())
        d = _dir(storage_dir, sess.id)
        d.mkdir(parents=True)
        (d / "data.bin").touch()
        _write_meta(storage_dir, sess)
    return sess


def load(storage_dir: Path, upload_id: str, owner: str) -> UploadSession:
    if not _ID_RE.fullmatch(upload_id):
        raise UploadNotFound(upload_id)
    sess = _read_meta(_dir(storage_dir, upload_id) / "meta.json")
    if sess is None or sess.owner != owner or time.time() - sess.created_at > SESSION_TTL_S:
        raise UploadNotFound(upload_id)
    return sess


def append_chunk(storage_dir: Path, sess: UploadSession, index: int, data: bytes) -> UploadSession:
    """Agrega una parte. Reenviar la última parte ya recibida (reintento de red) no la duplica."""
    with _lock:
        current = _read_meta(_dir(storage_dir, sess.id) / "meta.json")
        if current is None:
            raise UploadNotFound(sess.id)
        if index == current.next_index - 1 and len(data) == current.last_chunk_size:
            return current
        if index != current.next_index:
            raise ChunkOutOfOrder(f"Se esperaba la parte {current.next_index} y llegó la {index}.")
        if not data:
            raise InvalidUpload("La parte llegó vacía.")
        if len(data) > CHUNK_BYTES:
            raise InvalidUpload(f"Cada parte puede tener como máximo {CHUNK_BYTES // (1024 * 1024)} MB.")
        if current.received + len(data) > current.size:
            raise InvalidUpload("Se recibieron más bytes que el tamaño declarado del archivo.")
        with (_dir(storage_dir, sess.id) / "data.bin").open("ab") as fh:
            fh.write(data)
        current.received += len(data)
        current.next_index += 1
        current.last_chunk_size = len(data)
        _write_meta(storage_dir, current)
        return current


def open_data(storage_dir: Path, sess: UploadSession) -> BinaryIO:
    return (_dir(storage_dir, sess.id) / "data.bin").open("rb")


def discard(storage_dir: Path, upload_id: str) -> None:
    if _ID_RE.fullmatch(upload_id):
        shutil.rmtree(_dir(storage_dir, upload_id), ignore_errors=True)
