"""Validación de archivos subidos.

Se acepta sólo texto UTF-8 con formato de combat log (.txt / .log) o un .zip con exactamente
un archivo de log adentro. Se rechazan ejecutables y binarios por firma (magic bytes), archivos
con bytes NUL, zips cifrados, con varias entradas, con rutas raras o con descompresión abusiva
(zip bomb). Nunca se confía en la extensión ni en el Content-Type del cliente.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ALLOWED_TEXT_EXT = {".txt", ".log"}
ALLOWED_ZIP_EXT = {".zip"}
CHUNK = 1024 * 1024

# Firmas de formatos que nunca son un combat log.
_FORBIDDEN_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "ejecutable de Windows (PE)"),
    (b"\x7fELF", "ejecutable ELF"),
    (b"\xfe\xed\xfa\xce", "ejecutable Mach-O"),
    (b"\xfe\xed\xfa\xcf", "ejecutable Mach-O"),
    (b"\xce\xfa\xed\xfe", "ejecutable Mach-O"),
    (b"\xcf\xfa\xed\xfe", "ejecutable Mach-O"),
    (b"\xca\xfe\xba\xbe", "binario universal / clase Java"),
    (b"#!", "script con shebang"),
    (b"%PDF", "PDF"),
    (b"\xd0\xcf\x11\xe0", "documento OLE"),
    (b"Rar!", "RAR"),
    (b"7z\xbc\xaf", "7-Zip"),
    (b"\x1f\x8b", "gzip (no soportado)"),
    (b"\x00asm", "WebAssembly"),
    (b"<?php", "script PHP"),
    (b"<script", "HTML/script"),
    (b"<!DOCTYPE", "HTML"),
    (b"<html", "HTML"),
)

_FIRST_LINE_RE = re.compile(rb"^\d{1,2}/\d{1,2}(?:/\d{4})?\s\d{1,2}:\d{2}:\d{2}\.\d{3}(?:-?\d{1,2})?(?:\s\s|\t)[A-Z_]+")


class InvalidUpload(ValueError):
    """El archivo no es un combat log aceptable. El mensaje es seguro para mostrar al usuario."""


@dataclass(slots=True)
class SavedUpload:
    path: Path
    size: int


@dataclass(slots=True)
class ValidatedLog:
    text_path: Path  # archivo de texto normalizado listo para parsear
    sha256: str
    size: int
    content_kind: str  # text | zip
    header: str | None  # primera línea (para detectar demo / dialecto)


def safe_filename(name: str | None) -> str:
    base = (name or "combatlog.txt").replace("\\", "/").split("/")[-1]
    base = unicodedata.normalize("NFKC", base)
    base = "".join(c for c in base if c.isprintable() and c not in '<>:"|?*')
    base = base.strip(" .") or "combatlog.txt"
    return base[:120]


def save_stream(stream: BinaryIO, dest_dir: Path, max_bytes: int) -> SavedUpload:
    """Copia el stream a un archivo temporal cortando apenas supera el máximo."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="upload-", suffix=".bin", dir=dest_dir)
    size = 0
    with open(fd, "wb") as out:
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                out.close()
                Path(tmp).unlink(missing_ok=True)
                raise InvalidUpload(f"El archivo supera el máximo permitido ({max_bytes // (1024 * 1024)} MB).")
            out.write(chunk)
    if size == 0:
        Path(tmp).unlink(missing_ok=True)
        raise InvalidUpload("El archivo está vacío.")
    return SavedUpload(Path(tmp), size)


def _check_magic(head: bytes, allow_zip: bool) -> None:
    text_head = head.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    for magic, label in _FORBIDDEN_MAGIC:
        if head.startswith(magic) or (magic[:1] == b"<" and text_head.startswith(magic.lower())):
            raise InvalidUpload(f"Formato no permitido: {label}.")
    if head.startswith(b"PK") and not allow_zip:
        raise InvalidUpload("Es un archivo comprimido: subilo con extensión .zip.")


def _validate_text(path: Path) -> tuple[str, str | None]:
    """Valida texto UTF-8 sin NUL y con primera línea de combat log. Devuelve (sha256, cabecera)."""
    digest = hashlib.sha256()
    first_line: bytes | None = None
    pending = b""
    with path.open("rb") as fh:
        head = fh.read(64)
        _check_magic(head, allow_zip=False)
        fh.seek(0)
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            if b"\x00" in chunk:
                raise InvalidUpload("El archivo contiene datos binarios (bytes NUL).")
            digest.update(chunk)
            if first_line is None:
                pending += chunk
                for raw in pending.splitlines():
                    if raw.strip():
                        first_line = raw.lstrip(b"\xef\xbb\xbf")
                        break
                if first_line is None and len(pending) > 65536:
                    raise InvalidUpload("No se encontró ninguna línea de combat log al inicio del archivo.")
    if first_line is None:
        raise InvalidUpload("El archivo no tiene líneas de texto.")
    try:
        header = first_line.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidUpload("El archivo no está codificado en UTF-8.") from exc
    if not _FIRST_LINE_RE.match(first_line):
        raise InvalidUpload("El archivo no parece un combat log de World of Warcraft (formato de línea inválido).")
    return digest.hexdigest(), header


def _extract_zip(path: Path, dest_dir: Path, max_uncompressed: int, max_ratio: int) -> Path:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise InvalidUpload("El .zip está dañado o no es un zip válido.") from exc
    with zf:
        entries = [
            i
            for i in zf.infolist()
            if not i.is_dir() and not i.filename.startswith("__MACOSX/") and not i.filename.endswith(".DS_Store")
        ]
        if len(entries) != 1:
            raise InvalidUpload("El .zip debe contener exactamente un archivo de combat log.")
        info = entries[0]
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise InvalidUpload("El .zip contiene rutas no permitidas.")
        if Path(name).suffix.lower() not in ALLOWED_TEXT_EXT:
            raise InvalidUpload("El archivo dentro del .zip debe ser .txt o .log.")
        if info.flag_bits & 0x1:
            raise InvalidUpload("No se aceptan zips cifrados.")
        if info.file_size > max_uncompressed:
            raise InvalidUpload("El contenido descomprimido supera el máximo permitido.")
        if info.compress_size and info.file_size / max(info.compress_size, 1) > max_ratio:
            raise InvalidUpload("Relación de compresión sospechosa (posible zip bomb).")
        fd, tmp = tempfile.mkstemp(prefix="unzip-", suffix=".txt", dir=dest_dir)
        written = 0
        # No se confía en file_size: se cuenta lo que realmente se descomprime.
        with zf.open(info) as src, open(fd, "wb") as out:
            while True:
                chunk = src.read(CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_uncompressed or written > max_ratio * max(path.stat().st_size, 1):
                    out.close()
                    Path(tmp).unlink(missing_ok=True)
                    raise InvalidUpload("El contenido descomprimido supera el máximo permitido.")
                out.write(chunk)
        return Path(tmp)


def validate_saved(
    saved: SavedUpload, original_name: str, work_dir: Path, *, max_uncompressed: int, max_ratio: int
) -> ValidatedLog:
    ext = Path(original_name).suffix.lower()
    with saved.path.open("rb") as fh:
        head = fh.read(64)
    is_zip_magic = head.startswith(b"PK\x03\x04")
    if ext in ALLOWED_ZIP_EXT:
        if not is_zip_magic:
            raise InvalidUpload("La extensión es .zip pero el contenido no es un zip.")
        text_path = _extract_zip(saved.path, work_dir, max_uncompressed, max_ratio)
        try:
            sha, header = _validate_text(text_path)
        except InvalidUpload:
            text_path.unlink(missing_ok=True)
            raise
        return ValidatedLog(text_path, sha, text_path.stat().st_size, "zip", header)
    if ext not in ALLOWED_TEXT_EXT:
        raise InvalidUpload("Extensión no permitida: usá .txt, .log o .zip.")
    _check_magic(head, allow_zip=False)
    sha, header = _validate_text(saved.path)
    return ValidatedLog(saved.path, sha, saved.size, "text", header)


def store_validated(validated: ValidatedLog, storage_dir: Path) -> Path:
    """Mueve el log normalizado a su ubicación definitiva (nombre = hash, sin datos del usuario)."""
    dest = storage_dir / "logs" / validated.sha256[:2] / f"{validated.sha256}.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        validated.text_path.unlink(missing_ok=True)
    else:
        shutil.move(str(validated.text_path), dest)
    return dest
