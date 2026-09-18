"""Data-only validation for Kitty process profile overlays."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .config import ConfigError


MAX_PROFILE_BYTES = 1024 * 1024
ALLOWED = {
    "font_size", "window_padding_width", "window_margin_width",
}


def read_process_overlay(path: str, root: str | os.PathLike[str] | None = None) -> tuple[str, ...]:
    """Read a bounded, confined data-only overlay before kitty sees it."""
    content = _read_profile(path, root)
    lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or parts[0] not in ALLOWED or not parts[1].strip():
            raise ConfigError("process profile: unsupported configuration field")
        lines.append(line)
    return tuple(lines)


def _read_profile(path: str, root: str | os.PathLike[str] | None) -> str:
    try:
        selected = Path(path).resolve(strict=True)
        boundary = Path(root if root is not None else selected.parent).resolve(strict=True)
        selected.relative_to(boundary)
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(selected, flags)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ConfigError("process profile: expected a regular file")
            raw = stream.read(MAX_PROFILE_BYTES + 1)
    except ConfigError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise ConfigError("process profile: cannot read UTF-8 regular file") from None
    if len(raw) > MAX_PROFILE_BYTES:
        raise ConfigError("process profile: exceeds the 1 MiB size limit")
    try:
        return raw.decode("utf-8")
    except UnicodeError:
        raise ConfigError("process profile: cannot read UTF-8 regular file") from None
