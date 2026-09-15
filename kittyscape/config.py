"""Bounded, data-only JSON configuration with privacy-safe validation errors."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass

from .rules import Rule, _comparison_key, normalize_directory

MAX_CONFIG_BYTES = 1024 * 1024
MAX_RULES = 10000


class ConfigError(ValueError):
    """A configuration error identified by schema location, without path values."""


@dataclass(frozen=True)
class Config:
    """Validated configuration; image readability belongs to the runtime layer."""

    version: int = 1
    enabled: bool = True
    rules: tuple[Rule, ...] = ()
    fallback: str | None = None


def _read(path: str | os.PathLike[str]) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ConfigError("config: expected a regular file")
            content = stream.read(MAX_CONFIG_BYTES + 1)
    except (OSError, ValueError, TypeError):
        raise ConfigError("config: cannot read a regular configuration file") from None
    if len(content) > MAX_CONFIG_BYTES:
        raise ConfigError("config: exceeds the 1 MiB size limit")
    return content


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("config: duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ConfigError("config: non-finite numbers are not valid JSON")


def _decode(content: bytes) -> object:
    try:
        return json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as error:
        raise ConfigError(f"config: invalid JSON at line {error.lineno}, column {error.colno}") from None
    except ConfigError:
        raise
    except (ValueError, RecursionError):
        raise ConfigError("config: expected bounded UTF-8 JSON") from None


def _fields(value: object, allowed: set[str], location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigError(f"{location}: expected an object")
    if value.keys() - allowed:
        raise ConfigError(f"{location}: unknown field")
    return value


def _path_string(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{location}: expected a non-empty local path")
    if not value or "\0" in value:
        raise ConfigError(f"{location}: expected a non-empty local path")
    try:
        os.fsencode(value)
    except UnicodeError:
        raise ConfigError(f"{location}: invalid path encoding") from None
    return value


def _image(value: object, config_directory: str, location: str) -> str:
    path = _path_string(value, location)
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", path):
        raise ConfigError(f"{location}: expected a local path, not a URL")
    expanded = os.path.expanduser(path) if path.startswith("~/") else path
    return os.path.abspath(os.path.join(config_directory, expanded))


def _rule(value: object, index: int, config_directory: str) -> Rule:
    location = f"rules[{index}]"
    data = _fields(value, {"directory", "image"}, location)
    directory = _path_string(data.get("directory"), f"{location}.directory")
    try:
        directory = normalize_directory(directory)
    except ValueError:
        raise ConfigError(f"{location}.directory: expected an existing absolute local directory") from None
    image = _image(data.get("image"), config_directory, f"{location}.image")
    return Rule(directory, image)


def _rules(value: object, config_directory: str) -> tuple[Rule, ...]:
    if not isinstance(value, list):
        raise ConfigError("rules: expected an array")
    if len(value) > MAX_RULES:
        raise ConfigError("rules: exceeds the 10000 rule limit")
    rules = []
    seen: dict[str, list[str]] = {}
    for index, item in enumerate(value):
        rule = _rule(item, index, config_directory)
        aliases = seen.setdefault(_comparison_key(rule.directory), [])
        try:
            duplicate = any(previous == rule.directory or os.path.samefile(previous, rule.directory) for previous in aliases)
        except OSError:
            raise ConfigError(f"rules[{index}].directory: directory became unavailable") from None
        if duplicate:
            raise ConfigError(f"rules[{index}].directory: duplicate normalized root")
        aliases.append(rule.directory)
        rules.append(rule)
    return tuple(rules)


def _config_path(path: str | os.PathLike[str]) -> str:
    try:
        selected = os.fspath(path)
    except TypeError:
        raise ConfigError("config: expected a text file path") from None
    selected = _path_string(selected, "config")
    expanded = os.path.expanduser(selected) if selected.startswith("~/") else selected
    return os.path.abspath(expanded)


def load_config(path: str | os.PathLike[str]) -> Config:
    """Load strict schema version 1 JSON; errors leave callers' existing data intact.

    Version is required. Enabled defaults to true, rules to an empty array, and
    fallback to null. Relative images use the directory of the selected config
    path, including when that file is a symlink. This function never reads images.
    """
    selected_path = _config_path(path)
    data = _fields(_decode(_read(selected_path)), {"version", "enabled", "rules", "fallback"}, "config")
    version = data.get("version")
    if type(version) is not int or version != 1:
        raise ConfigError("version: expected integer schema version 1")
    enabled = data.get("enabled", True)
    if type(enabled) is not bool:
        raise ConfigError("enabled: expected a boolean")
    config_directory = os.path.dirname(selected_path)
    rules = _rules(data.get("rules", []), config_directory)
    fallback = data.get("fallback")
    fallback_image = None if fallback is None else _image(fallback, config_directory, "fallback")
    return Config(version=version, enabled=enabled, rules=rules, fallback=fallback_image)
