"""Bounded local PNG loading, executed outside kitty's UI callbacks."""

from __future__ import annotations

import hashlib
import os
import stat
import struct
import zlib
from dataclasses import dataclass

MAX_BYTES = 16 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_000_000
MAX_DECODED_BYTES = 64 * 1024 * 1024


class ImageError(ValueError):
    """An image is unavailable or outside the supported PNG limits."""


@dataclass(frozen=True)
class Image:
    data: bytes
    digest: str
    width: int
    height: int


def validate_png(data: bytes) -> Image:
    """Reject truncated, corrupt, animated, and oversized PNG containers."""
    if len(data) > MAX_BYTES or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ImageError("image-format-or-size")
    chunks = _chunks(data)
    header = _header(chunks)
    width, height = struct.unpack("!II", header[:8])
    if not 0 < width <= MAX_DIMENSION or not 0 < height <= MAX_DIMENSION or width * height > MAX_PIXELS:
        raise ImageError("image-dimensions")
    _structure(chunks)
    rows = _scanlines(header)
    compressed = b"".join(body for kind, body in chunks if kind == b"IDAT")
    _decoded(compressed, rows)
    return Image(data, hashlib.sha256(data).hexdigest(), width, height)


def _header(chunks: list[tuple[bytes, bytes]]) -> bytes:
    if not chunks or chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
        raise ImageError("image-header")
    return chunks[0][1]


def _structure(chunks: list[tuple[bytes, bytes]]) -> None:
    kinds = [kind for kind, _ in chunks]
    if kinds.count(b"IHDR") != 1 or kinds.count(b"IEND") != 1 or chunks[-1] != (b"IEND", b""):
        raise ImageError("image-structure")
    if b"acTL" in kinds or b"IDAT" not in kinds:
        raise ImageError("image-structure")
    first = kinds.index(b"IDAT")
    if kinds[first:first + kinds.count(b"IDAT")] != [b"IDAT"] * kinds.count(b"IDAT"):
        raise ImageError("image-structure")
    _critical_chunks(kinds)
    _palette(chunks, kinds)


def _critical_chunks(kinds: list[bytes]) -> None:
    allowed = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
    if any(kind[:1].isupper() and kind not in allowed for kind in kinds):
        raise ImageError("image-critical-chunk")


def _palette(chunks: list[tuple[bytes, bytes]], kinds: list[bytes]) -> None:
    depth, color = chunks[0][1][8:10]
    palettes = [body for kind, body in chunks if kind == b"PLTE"]
    if len(palettes) > 1 or (color == 3 and not palettes):
        raise ImageError("image-palette")
    if not palettes:
        return
    _palette_size(palettes[0], depth, color)
    if kinds.index(b"PLTE") > kinds.index(b"IDAT"):
        raise ImageError("image-palette")


def _palette_size(palette: bytes, depth: int, color: int) -> None:
    """Validate palette entries against the image's color encoding."""
    size = len(palette)
    if not size or size % 3 or size > 768 or color in (0, 4):
        raise ImageError("image-palette")
    if color == 3 and size // 3 > 2 ** depth:
        raise ImageError("image-palette")


def _scanlines(header: bytes) -> list[int]:
    width, height, depth, color, compression, filtering, interlace = struct.unpack("!2I5B", header)
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if depth not in depths.get(color, ()) or compression or filtering or interlace not in (0, 1):
        raise ImageError("image-encoding")
    bits = depth * {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    # Adam7 pass geometry from the PNG specification, section 8.1.
    passes = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
              (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)) if interlace else ((0, 0, 1, 1),)
    rows = []
    for x, y, dx, dy in passes:
        columns = max(0, (width - x + dx - 1) // dx)
        count = max(0, (height - y + dy - 1) // dy)
        if columns:
            rows.extend([1 + (columns * bits + 7) // 8] * count)
    return rows


def _decoded(compressed: bytes, rows: list[int]) -> None:
    expected = sum(rows)
    if expected > MAX_DECODED_BYTES:
        raise ImageError("image-decoded-size")
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(compressed, expected + 1)
    except zlib.error as error:
        raise ImageError("image-compression") from error
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ImageError("image-scanlines")
    _filters(raw, rows)


def _filters(raw: bytes, rows: list[int]) -> None:
    offset = 0
    for size in rows:
        if raw[offset] > 4:
            raise ImageError("image-filter")
        offset += size


def _chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    offset = 8
    chunks = []
    while offset < len(data):
        if len(data) - offset < 12:
            raise ImageError("image-truncated")
        length = struct.unpack_from("!I", data, offset)[0]
        end = offset + 12 + length
        if end > len(data):
            raise ImageError("image-truncated")
        kind, body = data[offset + 4:offset + 8], data[offset + 8:end - 4]
        checksum = struct.unpack_from("!I", data, end - 4)[0]
        if zlib.crc32(kind + body) & 0xFFFFFFFF != checksum:
            raise ImageError("image-checksum")
        chunks.append((kind, body))
        offset = end
    return chunks


def load_image(path: str) -> Image:
    """Read one regular local file with a strict byte limit and no conversion."""
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                raise ImageError("image-file-or-size")
            data = stream.read(MAX_BYTES + 1)
    except OSError as error:
        raise ImageError("image-unreadable") from error
    return validate_png(data)
