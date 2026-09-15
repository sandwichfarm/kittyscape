"""Physical local-directory normalization and deterministic image selection."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


@dataclass(frozen=True)
class Rule:
    """An absolute normalized directory root and its resolved local image path."""

    directory: str
    image: str


def normalize_directory(path: str) -> str:
    """Resolve a physical local directory; invalid paths raise a private ValueError."""
    try:
        if not isinstance(path, str):
            raise ValueError
        if not path or "\0" in path:
            raise ValueError
        expanded = os.path.expanduser(path) if path.startswith("~/") else path
        if not os.path.isabs(expanded):
            raise ValueError
        normalized = os.path.realpath(expanded, strict=True)
        if not os.path.isdir(normalized):
            raise ValueError
        return normalized
    except (OSError, ValueError, RuntimeError):
        raise ValueError("directory: expected an existing absolute local directory") from None


def _comparison_key(path: str) -> str:
    """Filter possible spelling aliases; only filesystem identity confirms them."""
    return unicodedata.normalize("NFC", path).casefold()


def _contains(root: str, directory: str, folded_directory: str) -> bool:
    if directory == root or directory.startswith(root.rstrip(os.sep) + os.sep):
        return True
    folded_root = _comparison_key(root)
    if folded_directory != folded_root and not folded_directory.startswith(folded_root.rstrip(os.sep) + os.sep):
        return False
    candidate = directory
    levels = directory.rstrip(os.sep).count(os.sep) - root.rstrip(os.sep).count(os.sep)
    for _ in range(levels):
        candidate = os.path.dirname(candidate)
    try:
        return os.path.samefile(root, candidate)
    except OSError:
        return False


def resolve(config: Config, cwd: str) -> str | None:
    """Select the deepest rule, or fallback for unmatched/unavailable directories.

    Disabled configuration returns None, requesting baseline restoration. Rule
    roots must already be normalized, as guaranteed by load_config().
    """
    if not config.enabled:
        return None
    try:
        directory = normalize_directory(cwd)
    except ValueError:
        return config.fallback
    folded_directory = _comparison_key(directory)
    matches = (rule for rule in config.rules if _contains(rule.directory, directory, folded_directory))
    selected = max(matches, key=lambda rule: rule.directory.rstrip(os.sep).count(os.sep), default=None)
    return config.fallback if selected is None else selected.image
