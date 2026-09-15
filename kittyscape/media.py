"""Bounded local JPEG/GIF normalization for Kittyscape's PNG upload path."""

from __future__ import annotations

import os
import select
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from .images import Image, ImageError, inspect_png, load_image, read_image_bytes, validate_png

MAX_FRAMES = 300
MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_SCRATCH_BYTES = 256 * 1024 * 1024
CONVERSION_TIMEOUT = 5
POLICY = """<policymap>
  <policy domain=\"resource\" name=\"memory\" value=\"256MiB\"/>
  <policy domain=\"resource\" name=\"map\" value=\"256MiB\"/>
  <policy domain=\"resource\" name=\"area\" value=\"256MiB\"/>
  <policy domain=\"resource\" name=\"disk\" value=\"0\"/>
  <policy domain=\"delegate\" rights=\"none\" pattern=\"*\"/>
</policymap>
"""


@dataclass(frozen=True)
class Frame:
    image: Image
    duration_ms: int = 100


@dataclass(frozen=True)
class Media:
    frames: tuple[Frame, ...]
    source_format: str
    loop: int | None

    @property
    def bytes(self) -> int:
        return sum(len(frame.image.data) for frame in self.frames)


def source_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    raise ImageError("unsupported-image-format")


def load_media(path: str, *, validate_bytes: bool = True, converter: str | None = None) -> Media:
    """Read once, identify by magic bytes, then normalize non-PNG sources privately."""
    data = read_image_bytes(path)
    kind = source_format(data)
    if kind == "png":
        image = validate_png(data) if validate_bytes else inspect_png(data)
        return Media((Frame(image),), kind, 1)
    executable = converter or shutil.which("magick")
    if not executable:
        raise ImageError("converter-unavailable")
    return _convert(bytes(data), kind, executable)


def _convert(data: bytes, kind: str, executable: str) -> Media:
    suffix = {"jpeg": ".jpg", "gif": ".gif"}[kind]
    with tempfile.TemporaryDirectory(prefix="kittyscape-media-") as temporary:
        root = Path(temporary)
        source = root / ("input" + suffix)
        _write_private(source, data)
        _write_private(root / "policy.xml", POLICY.encode())
        command = [
            executable, f"{kind.upper()}:{source}", "-auto-orient", "-colorspace", "sRGB",
            "-coalesce", "-strip", "PNG32:-",
        ]
        output = _run(command, root)
        durations, loop = _gif_metadata(data) if kind == "gif" else ((), 1)
        frames = _frames(output, durations)
        if not frames:
            raise ImageError("decode-failed")
        return Media(frames, kind, loop)


def _write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _run(command: list[str], root: Path) -> bytes:
    worker = Path(__file__).with_name("media_worker.py")
    try:
        environment = {"MAGICK_CONFIGURE_PATH": str(root), "MAGICK_TEMPORARY_PATH": str(root)}
        process = subprocess.Popen([_worker_python(), str(worker), *command], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=root,
                                   start_new_session=True, env=environment)
        try:
            output = _read_output(process)
        except Exception:
            if process.poll() is None:
                _stop(process)
            raise
        finally:
            process.stdout.close()
    except OSError as error:
        raise ImageError("converter-unavailable") from error
    if process.returncode:
        raise ImageError("decode-failed")
    return output


def _read_output(process: subprocess.Popen) -> bytes:
    deadline, output = time.monotonic() + CONVERSION_TIMEOUT, bytearray()
    while process.poll() is None:
        if time.monotonic() > deadline:
            _stop(process)
            raise ImageError("conversion-timeout")
        readable, _, _ = select.select((process.stdout,), (), (), 0.05)
        if readable:
            output.extend(os.read(process.stdout.fileno(), 65536))
            if len(output) > MAX_MEDIA_BYTES + 65536:
                _stop(process)
                raise ImageError("media-budget-exceeded")
    output.extend(process.stdout.read(MAX_MEDIA_BYTES + 65537))
    if len(output) > MAX_MEDIA_BYTES:
        raise ImageError("media-budget-exceeded")
    return bytes(output)


def _stop(process: subprocess.Popen) -> None:
    os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=1)


def _worker_python() -> str:
    """Kitty embeds Python with the kitty binary as ``sys.executable``."""
    for candidate in ("/usr/bin/python3", "/usr/bin/python", sys.executable):
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK) and "kitty" not in path.name:
            return str(path)
    raise ImageError("converter-unavailable")


def _frames(data: bytes, durations: tuple[int, ...]) -> tuple[Frame, ...]:
    images = _png_sequence(data)
    if not 0 < len(images) <= MAX_FRAMES:
        raise ImageError("media-budget-exceeded")
    frames = tuple(Frame(validate_png(image), durations[index] if index < len(durations) else 100)
                   for index, image in enumerate(images))
    size = sum(len(frame.image.data) for frame in frames)
    if size > MAX_MEDIA_BYTES:
        raise ImageError("media-budget-exceeded")
    return frames


def _png_sequence(data: bytes) -> tuple[bytes, ...]:
    offset, images = 0, []
    while offset < len(data):
        if data[offset:offset + 8] != b"\x89PNG\r\n\x1a\n":
            raise ImageError("decode-failed")
        end = offset + 8
        while end < len(data):
            size = int.from_bytes(data[end:end + 4], "big")
            kind = data[end + 4:end + 8]
            end += size + 12
            if kind == b"IEND":
                images.append(data[offset:end])
                offset = end
                break
        else:
            raise ImageError("decode-failed")
    return tuple(images)


def _gif_metadata(data: bytes) -> tuple[tuple[int, ...], int | None]:
    """Read Netscape loop metadata; ImageMagick coalesces the visual frames."""
    marker = b"NETSCAPE2.0\x03\x01"
    index = data.find(marker)
    loop = 1 if index < 0 or index + len(marker) + 2 > len(data) else int.from_bytes(
        data[index + len(marker):index + len(marker) + 2], "little") + 1
    if loop == 1 and index >= 0:
        loop = None
    return _gif_delays(data), loop


def _gif_delays(data: bytes) -> tuple[int, ...]:
    cursor = 13 + _gif_global_palette_size(data)
    delays, pending = [], 100
    while cursor < len(data):
        marker = data[cursor]
        cursor += 1
        if marker == 0x21:
            cursor, pending = _gif_extension(data, cursor, pending)
        elif marker == 0x2C:
            cursor = _gif_image_data(data, cursor)
            delays.append(pending)
            pending = 100
        else:
            break
    return tuple(delays)


def _gif_global_palette_size(data: bytes) -> int:
    return 3 * (2 ** ((data[10] & 7) + 1)) if len(data) > 10 and data[10] & 0x80 else 0


def _gif_extension(data: bytes, cursor: int, pending: int) -> tuple[int, int]:
    if cursor >= len(data):
        return len(data), pending
    label = data[cursor]
    cursor += 1
    if label == 0xF9 and cursor + 5 <= len(data) and data[cursor] == 4:
        pending = max(10, int.from_bytes(data[cursor + 2:cursor + 4], "little") * 10)
    return _skip_blocks(data, cursor), pending


def _gif_image_data(data: bytes, cursor: int) -> int:
    if cursor + 9 > len(data):
        return len(data)
    packed = data[cursor + 8]
    cursor += 9 + (3 * (2 ** ((packed & 7) + 1)) if packed & 0x80 else 0)
    return _skip_blocks(data, cursor + 1)


def _skip_blocks(data: bytes, cursor: int) -> int:
    while cursor < len(data):
        size = data[cursor]
        cursor += size + 1
        if not size:
            return cursor
    return len(data)
