"""Physical local-directory normalization and deterministic image selection."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


@dataclass(frozen=True)
class BackgroundOptions:
    """Explicit native background fields; ``None`` inherits the prior layer."""

    layout: str | None = None
    linear: bool | None = None
    tint: float | None = None
    tint_gaps: float | None = None
    opacity: float | None = None

    def overlay(self, override: "BackgroundOptions") -> "BackgroundOptions":
        return BackgroundOptions(**{
            field: getattr(override, field) if getattr(override, field) is not None else getattr(self, field)
            for field in self.__dataclass_fields__
        })


@dataclass(frozen=True)
class AnimationOptions:
    """GIF playback fields; rule objects use ``None`` to inherit global values."""

    enabled: bool | None = None
    fps_limit: int | None = None
    speed: float | None = None
    loop: str | int | None = None

    def overlay(self, override: "AnimationOptions") -> "AnimationOptions":
        return AnimationOptions(**{
            field: getattr(override, field) if getattr(override, field) is not None else getattr(self, field)
            for field in self.__dataclass_fields__
        })


@dataclass(frozen=True)
class Rule:
    """An absolute normalized directory root and its resolved local image path."""

    directory: str
    image: str
    background: BackgroundOptions = BackgroundOptions()
    animation: AnimationOptions = AnimationOptions()


@dataclass(frozen=True)
class Selection:
    """One fully resolved image and its inherited rendering/playback policy."""

    image: str
    rule: Rule | None
    background: BackgroundOptions
    animation: AnimationOptions

    @property
    def fallback(self) -> bool:
        return self.rule is None


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


def _matching_rule(config: Config, cwd: str | None) -> Rule | None:
    if cwd is None:
        return None
    try:
        directory = normalize_directory(cwd)
    except ValueError:
        return None
    folded_directory = _comparison_key(directory)
    matches = (rule for rule in config.rules if _contains(rule.directory, directory, folded_directory))
    return max(matches, key=lambda rule: rule.directory.rstrip(os.sep).count(os.sep), default=None)


def resolve(config: Config, cwd: str | None) -> Selection | None:
    """Select the deepest rule and resolve its inherited option values.

    Disabled configuration returns None, requesting baseline restoration. Rule
    roots must already be normalized, as guaranteed by load_config().
    """
    if not config.enabled:
        return None
    selected = _matching_rule(config, cwd)
    image = config.fallback if selected is None else selected.image
    if image is None:
        return None
    return Selection(
        image=image,
        rule=selected,
        background=config.background if selected is None else config.background.overlay(selected.background),
        animation=config.animation if selected is None else config.animation.overlay(selected.animation),
    )
