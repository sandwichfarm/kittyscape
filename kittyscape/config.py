"""Bounded, data-only JSON configuration with privacy-safe validation errors."""

from __future__ import annotations

import json
import math
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .rules import AnimationOptions, BackgroundOptions, Profile, Rule, _comparison_key, normalize_directory

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
    validate_bytes: bool = True
    background: BackgroundOptions = BackgroundOptions()
    animation: AnimationOptions = AnimationOptions(enabled=True, fps_limit=24, speed=1.0, loop="source")
    profiles: dict[str, Profile] = field(default_factory=dict)


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


def _number(value: object, location: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigError(f"{location}: expected a finite number")
    if not 0 <= value <= 1:
        raise ConfigError(f"{location}: expected a number from 0 through 1")
    return float(value)


def _optional_number(data: dict[str, object], field: str, location: str) -> float | None:
    return None if field not in data else _number(data[field], f"{location}.{field}")


def _layout(value: object, location: str) -> str | None:
    if value is None:
        return value
    if type(value) is str and value in {"tiled", "mirror-tiled", "scaled", "clamped", "centered", "cscaled"}:
        return value
    raise ConfigError(f"{location}: unsupported layout")


def _optional_bool(value: object, location: str) -> bool | None:
    if value is None or type(value) is bool:
        return value
    raise ConfigError(f"{location}: expected a boolean")


def _background(value: object, location: str) -> BackgroundOptions:
    if value is None:
        return BackgroundOptions()
    data = _fields(value, {"layout", "linear", "tint", "tint_gaps", "opacity"}, location)
    return BackgroundOptions(
        layout=_layout(data.get("layout"), f"{location}.layout"),
        linear=_optional_bool(data.get("linear"), f"{location}.linear"),
        tint=_optional_number(data, "tint", location), tint_gaps=_optional_number(data, "tint_gaps", location),
        opacity=_optional_number(data, "opacity", location),
    )


def _supported_process_options(options: BackgroundOptions, location: str) -> BackgroundOptions:
    if options.tint is not None or options.tint_gaps is not None:
        raise ConfigError(f"{location}: tint and tint_gaps are unsupported by this kitty API")
    return options


def _fps(value: object, location: str) -> int | None:
    if value is None or (type(value) is int and 1 <= value <= 60):
        return value
    raise ConfigError(f"{location}: expected an integer from 1 through 60")


def _speed(value: object, location: str) -> float | None:
    if value is None:
        return None
    if type(value) in (int, float) and math.isfinite(value) and 0.1 <= value <= 4.0:
        return float(value)
    raise ConfigError(f"{location}: expected a finite number from 0.1 through 4")


def _loop(value: object, location: str) -> str | int | None:
    if value is None or value in ("source", "forever") or (type(value) is int and value >= 1):
        return value
    raise ConfigError(f"{location}: expected source, forever, or a positive integer")


def _animation(value: object, location: str, *, defaults: bool) -> AnimationOptions:
    if value is None:
        return AnimationOptions(enabled=True, fps_limit=24, speed=1.0, loop="source") if defaults else AnimationOptions()
    data = _fields(value, {"enabled", "fps_limit", "speed", "loop"}, location)
    enabled = _optional_bool(data.get("enabled"), f"{location}.enabled")
    fps = _fps(data.get("fps_limit"), f"{location}.fps_limit")
    speed = _speed(data.get("speed"), f"{location}.speed")
    loop = _loop(data.get("loop"), f"{location}.loop")
    if defaults:
        return AnimationOptions(
            enabled=True if enabled is None else enabled, fps_limit=24 if fps is None else fps,
            speed=1.0 if speed is None else speed, loop="source" if loop is None else loop,
        )
    return AnimationOptions(enabled=enabled, fps_limit=fps, speed=speed, loop=loop)


def _profiles(value: object, directory: str) -> dict[str, Profile]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("profiles: expected an object")
    profiles = {}
    for name, raw in value.items():
        if type(name) is not str or not name or not name.replace("_", "").isalnum():
            raise ConfigError("profiles: invalid profile name")
        item = _fields(raw, {"mode", "font_size", "padding", "margin", "config"}, f"profiles.{name}")
        mode = item.get("mode")
        profiles[name] = _profile(mode, item, name, directory)
    return profiles


def _profile(mode: object, item: dict[str, object], name: str, directory: str) -> Profile:
    if mode == "scoped":
        return _scoped_profile(item, name)
    if mode == "process":
        return _process_profile(item, name, directory)
    raise ConfigError(f"profiles.{name}.mode: expected scoped or process")


def _scoped_profile(item: dict[str, object], name: str) -> Profile:
    if "config" in item or not ({"font_size", "padding", "margin"} & item.keys()):
        raise ConfigError(f"profiles.{name}: scoped profile requires settings only")
    return Profile(
        "scoped", _profile_font(item.get("font_size"), name),
        _profile_spacing(item.get("padding"), name, "padding"),
        _profile_spacing(item.get("margin"), name, "margin"),
        name=name,
    )


def _profile_font(value: object, name: str) -> float | None:
    if value is None:
        return None
    if type(value) in (int, float) and 1 <= value <= 96:
        return float(value)
    raise ConfigError(f"profiles.{name}.font_size: expected number from 1 through 96")


def _profile_spacing(value: object, name: str, field: str) -> float | None:
    if value is None:
        return None
    if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100:
        return float(value)
    raise ConfigError(f"profiles.{name}.{field}: expected number from 0 through 100")


def _process_profile(item: dict[str, object], name: str, directory: str) -> Profile:
    if set(item) != {"mode", "config"}:
        raise ConfigError(f"profiles.{name}: process profile requires config only")
    path = _path_string(item.get("config"), f"profiles.{name}.config")
    if os.path.isabs(path) or ".." in Path(path).parts:
        raise ConfigError(f"profiles.{name}.config: expected relative local path")
    from .profiles import read_process_overlay

    selected = os.path.join(directory, path)
    try:
        commands = read_process_overlay(selected, directory)
    except ConfigError as error:
        raise ConfigError(f"profiles.{name}.config: {error}") from None
    return Profile("process", config=selected, commands=commands, name=name)


def _rule(value: object, index: int, config_directory: str, profiles: dict[str, Profile]) -> Rule:
    location = f"rules[{index}]"
    data = _fields(value, {"directory", "image", "background", "animation", "profile"}, location)
    directory = _path_string(data.get("directory"), f"{location}.directory")
    try:
        directory = normalize_directory(directory)
    except ValueError:
        raise ConfigError(f"{location}.directory: expected an existing absolute local directory") from None
    image = _image(data.get("image"), config_directory, f"{location}.image")
    background = _background(data.get("background"), f"{location}.background")
    if any(value is not None for value in (background.linear, background.tint, background.tint_gaps)):
        raise ConfigError(f"{location}.background: field requires process-wide top-level scope")
    profile = data.get("profile")
    if profile is not None and (type(profile) is not str or profile not in profiles):
        raise ConfigError(f"{location}.profile: unknown profile")
    return Rule(directory, image, background, _animation(data.get("animation"), f"{location}.animation", defaults=False), profile)


def _rules(value: object, config_directory: str, profiles: dict[str, Profile]) -> tuple[Rule, ...]:
    if not isinstance(value, list):
        raise ConfigError("rules: expected an array")
    if len(value) > MAX_RULES:
        raise ConfigError("rules: exceeds the 10000 rule limit")
    rules = []
    seen: dict[str, list[str]] = {}
    for index, item in enumerate(value):
        rule = _rule(item, index, config_directory, profiles)
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
    data = _fields(_decode(_read(selected_path)),
                   {"version", "enabled", "rules", "fallback", "validate_bytes", "background", "animation", "profiles"}, "config")
    version = data.get("version")
    if type(version) is not int or version != 1:
        raise ConfigError("version: expected integer schema version 1")
    enabled = data.get("enabled", True)
    if type(enabled) is not bool:
        raise ConfigError("enabled: expected a boolean")
    config_directory = os.path.dirname(selected_path)
    profiles = _profiles(data.get("profiles"), config_directory)
    rules = _rules(data.get("rules", []), config_directory, profiles)
    fallback = data.get("fallback")
    fallback_image = None if fallback is None else _image(fallback, config_directory, "fallback")
    validate_bytes = data.get("validate_bytes", True)
    if type(validate_bytes) is not bool:
        raise ConfigError("validate_bytes: expected a boolean")
    return Config(version=version, enabled=enabled, rules=rules, fallback=fallback_image, validate_bytes=validate_bytes,
                  background=_supported_process_options(_background(data.get("background"), "background"), "background"),
                  animation=_animation(data.get("animation"), "animation", defaults=True), profiles=profiles)
