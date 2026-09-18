"""The only module coupled to kitty's version-dependent Python interfaces.

Known startup defaults and observed writes are recoverable. Arbitrary existing
GPU state and direct C writes from other custom kittens are not introspectable.
"""

from __future__ import annotations

import inspect
import os
import socket
from dataclasses import dataclass, replace
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from .images import MAX_BYTES


@dataclass(frozen=True)
class Background:
    kind: str = "inherited"
    path: str | None = None
    data: bytes = b""
    layout: str = "tiled"
    linear: bool = False
    tint: float = 0.0
    tint_gaps: float = 1.0
    opacity: float | None = None
    index: int = 0


def local_directory(report: bytes | str | None) -> str:
    """Decode native kitty or OSC 7 file reports without treating remote paths as local."""
    host, path = _reported_location(report)
    if not path:
        raise ValueError("directory-report-format")
    hostname = socket.gethostname()
    if host not in ("", "localhost", hostname, hostname.partition(".")[0]):
        raise ValueError("directory-remote")
    if not path.startswith("/") or any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError("directory-report-format")
    return path


def _reported_location(report: bytes | str | None) -> tuple[str, str]:
    """Decode each report format without interpreting native path punctuation as a URI."""
    if not report:
        raise ValueError("directory-unreported")
    text = report.decode("utf-8", "strict") if isinstance(report, bytes) else report
    if text.startswith("kitty-shell-cwd://"):
        host, slash, tail = text[len("kitty-shell-cwd://"):].partition("/")
        return host, slash + tail
    parsed = urlsplit(text)
    if parsed.scheme != "file" or parsed.query or parsed.fragment:
        raise ValueError("directory-report-format")
    return parsed.netloc, unquote(parsed.path, errors="strict")


def _captured_override(fields: dict, inherited: Background) -> Background:
    """Preserve an observed image and use inherited rendering values where omitted."""
    return Background(
        kind="override", path=fields["path"], data=fields.get("png_data", b""),
        layout=fields["layout"] or inherited.layout,
        linear=inherited.linear if fields.get("linear_interpolation") is None else fields["linear_interpolation"],
        tint=inherited.tint if fields.get("tint") is None else fields["tint"],
        tint_gaps=inherited.tint_gaps if fields.get("tint_gaps") is None else fields["tint_gaps"],
    )


class Kitty:
    """Confine scoped image writes, capability checks, and ownership observation."""

    def __init__(self, boss: Any, changed: Callable, reloaded: Callable):
        from kitty.fast_data_types import (
            add_timer, background_opacity_of, current_focused_os_window_id, get_options,
            last_focused_os_window_id, os_window_font_size, wakeup_main_loop,
        )

        self.boss = boss
        self.options = get_options
        self._opacity_of = background_opacity_of
        self._font_size = os_window_font_size
        self._current_focused_os_window_id = current_focused_os_window_id
        self._last_focused_os_window_id = last_focused_os_window_id
        self._add_timer = add_timer
        self._timer_callbacks: dict[int, Callable] = {}
        self._timer_dispatcher = self._dispatch_timer
        self.wake = wakeup_main_loop
        self.original_set = boss.set_background_image
        self.original_options = boss.apply_new_options
        self.original_theme = getattr(boss, "on_system_color_scheme_change", None)
        self.signature = inspect.signature(type(boss).set_background_image.__get__(boss))
        self.modern = "global_index" in self.signature.parameters
        self.internal = False
        self.reload_depth = 0
        self.theme_windows: set[int] = set()
        self.changed = changed
        self.reloaded = reloaded
        self.preexisting = {w.os_window_id for w in boss.window_id_map.values()}
        self.overrides: dict[int, Background] = {}
        self._linear_owners: set[int] = set()
        self._linear_baseline: bool | None = None
        self._font_owners: dict[int, tuple[float, float]] = {}
        self._edge_owners: dict[tuple[int, int, str, str], tuple[float | None, float]] = {}
        self._process_profile: tuple | None = None
        self._capture_process_baseline()
        boss.set_background_image = self._observed_set
        boss.apply_new_options = self._observed_options
        if self.original_theme:
            boss.on_system_color_scheme_change = self._observed_theme

    def timer(self, callback: Callable, delay: float, repeats: bool) -> int:
        """Schedule a one-shot callback without freeing native dispatch-batch pointers."""
        if repeats:
            raise ValueError("Kittyscape only schedules one-shot timers")
        timer = self._add_timer(self._timer_dispatcher, delay, False)
        self._timer_callbacks[timer] = callback
        return timer

    def _dispatch_timer(self, timer: int) -> None:
        callback = self._timer_callbacks.pop(timer, None)
        if callback:
            callback(timer)

    def remove_timer(self, timer: int) -> None:
        # Kitty snapshots raw callback pointers for all due timers. A native
        # removal can free a later entry in that batch; let the one-shot expire.
        self._timer_callbacks.pop(timer, None)

    def capability_error(self) -> str:
        from kitty.constants import version

        if tuple(version) < (0, 38, 1):
            return "kitty-version-unqualified"
        flags = set(self.options().shell_integration)
        if flags.intersection({"disabled", "no-cwd", "no-prompt-mark"}):
            return "shell-reports-disabled"
        return ""

    def inherited(self) -> Background:
        opts = self.options()
        paths = opts.background_image
        path = (paths[0] if paths else None) if isinstance(paths, (tuple, list)) else paths
        return Background(
            path=path, layout=opts.background_image_layout, linear=opts.background_image_linear,
            tint=opts.background_tint, tint_gaps=opts.background_tint_gaps,
        )

    def baseline(self, os_id: int) -> Background:
        if os_id in self.overrides:
            return self.overrides[os_id]
        if os_id in self.preexisting:
            return Background(kind="unknown")
        inherited = self.inherited()
        if self.options().dynamic_background_opacity:
            return replace(inherited, opacity=self._opacity_of(os_id))
        return inherited

    def active(self, os_id: int) -> Any:
        manager = self.boss.os_window_map.get(os_id)
        return manager.active_tab.active_window if manager and manager.active_tab else None

    def focused_os_id(self) -> int:
        """Keep last kitty OS window while application temporarily lacks focus."""
        current = self._current_focused_os_window_id()
        selected = current if current > 0 else self._last_focused_os_window_id()
        return selected if selected in self.boss.os_window_map else 0

    def _observed_set(self, *args: Any, **kwargs: Any) -> None:
        self.original_set(*args, **kwargs)
        if self.internal:
            return
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        fields = bound.arguments
        if self.reload_depth and fields["configured"]:
            self.theme_windows.update(fields["os_windows"])
            return
        for os_id in fields["os_windows"]:
            spec = self._external_spec(fields)
            self.overrides[os_id] = spec
            self.changed(os_id, spec)

    def _external_spec(self, fields: dict) -> Background:
        inherited = self.inherited()
        index = fields.get("global_index", -1)
        if index > -1 or fields.get("is_increment"):
            # Relative indices cannot be reconstructed from an arbitrary existing state.
            if fields.get("is_increment"):
                return Background(kind="unknown")
            return replace(inherited, index=index)
        if fields["path"] and not fields.get("png_data"):
            # The C loader owns bytes we cannot retrieve. A later disk read cannot
            # prove which bytes were displayed at the instant this setter ran.
            return Background(kind="unknown")
        if len(fields.get("png_data") or b"") > MAX_BYTES:
            return Background(kind="unknown")
        return _captured_override(fields, inherited)

    def _observed_options(self, opts: Any) -> None:
        self._run_reload(self.original_options, (opts,), {})

    def _observed_theme(self, *args: Any, **kwargs: Any) -> Any:
        return self._run_reload(self.original_theme, args, kwargs)

    def _run_reload(self, operation: Callable, args: tuple, kwargs: dict) -> Any:
        outer = self.reload_depth == 0
        if outer:
            self.theme_windows.clear()
            self.reloaded("before")
        self.reload_depth += 1
        try:
            return operation(*args, **kwargs)
        finally:
            self.reload_depth -= 1
            if outer:
                for os_id in self.theme_windows:
                    self.overrides.pop(os_id, None)
                self.reloaded("after", tuple(self.theme_windows))

    def apply(self, os_id: int, spec: Background, *, restore: bool = False) -> None:
        """Write one OS window; never modify defaults shared by future windows."""
        self._check_opacity(spec)
        self.internal = True
        try:
            self._set_image(os_id, spec, restore)
            self._set_opacity(os_id, spec)
            window = self.active(os_id)
            if window is not None and not window.destroyed:
                window.refresh()
            else:
                self.wake()
        finally:
            self.internal = False

    def acquire_linear(self, os_id: int, value: bool | None) -> None:
        if value is None or os_id in self._linear_owners:
            return
        if self._linear_baseline is None:
            self._linear_baseline = self.options().background_image_linear
            self._set_global_linear(value)
        self._linear_owners.add(os_id)

    def release_linear(self, os_id: int) -> None:
        self._linear_owners.discard(os_id)
        if not self._linear_owners and self._linear_baseline is not None:
            self._set_global_linear(self._linear_baseline)
            self._linear_baseline = None

    def apply_scoped_profile(self, os_id: int, profile: Any) -> None:
        if profile is None or profile.mode != "scoped":
            self.release_scoped_profile(os_id, True)
            return
        self._apply_font(os_id, profile.font_size)
        window = self.active(os_id)
        keep = set()
        if window is not None:
            for which in ("padding", "margin"):
                value = getattr(profile, which)
                if value is not None:
                    for edge in ("left", "top", "right", "bottom"):
                        key = (os_id, window.id, which, edge)
                        keep.add(key)
                        self._apply_edge(window, key, value)
        self._release_edges(os_id, True, keep)

    def _apply_font(self, os_id: int, value: float | None) -> None:
        owner = self._font_owners.get(os_id)
        current = self._font_size(os_id)
        if value is None:
            self._release_font(os_id, True)
            return
        if not current:
            raise RuntimeError("font-size-unavailable")
        if owner is None or current != owner[1]:
            baseline = current
        else:
            baseline = owner[0]
        if current != value:
            self.boss._change_font_size({os_id: value})
        self._font_owners[os_id] = (baseline, value)

    def _apply_edge(self, window: Any, key: tuple[int, int, str, str], value: float) -> None:
        _, _, which, edge = key
        current = getattr(getattr(window, which), edge)
        owner = self._edge_owners.get(key)
        baseline = current if owner is None or current != owner[1] else owner[0]
        if current != value:
            window.patch_edge_width(which, edge, value)
        self._edge_owners[key] = (baseline, value)

    def release_scoped_profile(self, os_id: int, restore: bool) -> None:
        self._release_font(os_id, restore)
        self._release_edges(os_id, restore, set())

    def release_all_scoped_profiles(self, restore: bool) -> None:
        os_ids = set(self._font_owners)
        os_ids.update(
            os_id for os_id, _, _, _ in self._edge_owners
        )
        for os_id in os_ids:
            self.release_scoped_profile(os_id, restore)
        if not restore:
            self._edge_owners.clear()

    def _release_font(self, os_id: int, restore: bool) -> None:
        owner = self._font_owners.get(os_id)
        if owner is None:
            return
        if not restore or self._font_size(os_id) != owner[1]:
            self._font_owners.pop(os_id)
            return
        self.boss._change_font_size({os_id: owner[0]})
        self._font_owners.pop(os_id)

    def _release_edges(self, os_id: int, restore: bool, keep: set[tuple[int, int, str, str]]) -> None:
        for key, owner in list(self._edge_owners.items()):
            if key in keep or key[0] != os_id:
                continue
            _, window_id, which, edge = key
            window = self.boss.window_id_map.get(window_id)
            if not restore or window is None or getattr(getattr(window, which), edge) != owner[1]:
                self._edge_owners.pop(key)
                continue
            window.patch_edge_width(which, edge, owner[0])
            self._edge_owners.pop(key)

    def apply_process_profile(self, profile: Any) -> bool:
        if profile is None or profile.mode != "process":
            return False
        if self._process_profile == profile.identity:
            self._extend_process_font_ownership()
            return True
        if self._process_profile is not None:
            self._adopt_process_divergence()
        values = self._profile_values(profile.commands)
        if self._process_profile is None:
            self._process_font_baselines = {
                os_id: self._font_size(os_id) for os_id in self.boss.os_window_map
            }
        self._process_expected = values
        self._process_font_expected = {
            os_id: values["font_size"] for os_id in self.boss.os_window_map
        }
        self._process_profile = profile.identity
        self._apply_process_values(values)
        return True

    def _adopt_process_divergence(self) -> None:
        options = self.options()
        for field, expected in self._process_expected.items():
            current = getattr(options, field)
            if current != expected:
                self._base_process_values[field] = current
        outgoing = self._process_expected.get("font_size")
        for os_id in self.boss.os_window_map:
            current = self._font_size(os_id)
            expected = self._process_font_expected.get(os_id, outgoing)
            if os_id not in self._process_font_baselines:
                self._process_font_baselines[os_id] = (
                    self._base_process_values["font_size"] if current == expected else current
                )
            elif current != expected:
                self._process_font_baselines[os_id] = current

    def release_process_profile(self) -> None:
        if self._process_profile is None:
            return
        self.restore_process_baseline()

    def restore_process_baseline(self) -> None:
        values = self._restored_process_values()
        self._apply_process_values(values, restore=True)
        self._process_profile = None
        self._process_expected = {}
        self._process_font_expected = {}
        self._process_font_baselines = {}

    def abandon_process_profile(self) -> None:
        """Relinquish ownership when an external native reload will supply baseline."""
        self._process_profile = None
        self._process_expected = {}
        self._process_font_expected = {}
        self._process_font_baselines = {}

    def adopt_process_baseline(self) -> None:
        self._capture_process_baseline()

    def _capture_process_baseline(self) -> None:
        options = self.options()
        fields = ("font_size", "window_padding_width", "window_margin_width")
        self._base_process_values = {field: getattr(options, field) for field in fields}
        self._process_expected: dict[str, Any] = {}
        self._process_font_expected: dict[int, float] = {}
        self._process_font_baselines: dict[int, float] = {}

    def _profile_values(self, commands: tuple[str, ...]) -> dict[str, Any]:
        from kitty.config import load_config

        bad_lines = []
        parsed = load_config(overrides=commands, accumulate_bad_lines=bad_lines)
        if bad_lines:
            from .config import ConfigError
            raise ConfigError("process profile: invalid native configuration value")
        values = dict(self._base_process_values)
        for command in commands:
            key = command.split(None, 1)[0]
            values[key] = getattr(parsed, key)
        return values

    def _restored_process_values(self) -> dict[str, Any]:
        options = self.options()
        return {
            field: baseline if getattr(options, field) == self._process_expected.get(field) else getattr(options, field)
            for field, baseline in self._base_process_values.items()
        }

    def _apply_process_values(self, values: dict[str, Any], *, restore: bool = False) -> None:
        options = self.options()
        for field, value in values.items():
            setattr(options, field, value)
        font_changes = self._process_font_changes(values["font_size"], restore)
        if font_changes:
            self.boss._change_font_size(font_changes)
        for manager in self.boss.all_tab_managers:
            manager.resize()

    def _process_font_changes(self, selected: float, restore: bool) -> dict[int, float]:
        changes = {}
        for os_id in self.boss.os_window_map:
            current = self._font_size(os_id)
            if restore:
                expected = self._process_font_expected.get(os_id)
                if current == expected:
                    changes[os_id] = self._process_font_baselines.get(os_id, self._base_process_values["font_size"])
            elif current != selected:
                changes[os_id] = selected
        return changes

    def _extend_process_font_ownership(self) -> None:
        selected = self._process_expected.get("font_size")
        if selected is None:
            return
        for os_id in self.boss.os_window_map:
            if os_id not in self._process_font_baselines:
                current = self._font_size(os_id)
                self._process_font_baselines[os_id] = (
                    self._base_process_values["font_size"] if current == selected else current
                )
            if os_id not in self._process_font_expected:
                self._process_font_expected[os_id] = selected

    def _set_global_linear(self, value: bool) -> None:
        self.internal = True
        try:
            self.original_set(None, (), True, None, b"", linear_interpolation=value)
        finally:
            self.internal = False

    def _check_opacity(self, spec: Background) -> None:
        if spec.opacity is not None and not self.options().dynamic_background_opacity:
            raise ValueError("background-opacity-requires-startup-capability")

    def _set_image(self, os_id: int, spec: Background, restore: bool) -> None:
        if restore and spec.kind == "inherited" and self.modern:
            self.original_set(None, (os_id,), False, None, global_index=spec.index)
        elif self.modern:
            self.original_set(spec.path, (os_id,), False, spec.layout, spec.data,
                              linear_interpolation=spec.linear, tint=spec.tint, tint_gaps=spec.tint_gaps)
        else:
            self.original_set(spec.path, (os_id,), False, spec.layout, spec.data)

    def _set_opacity(self, os_id: int, spec: Background) -> None:
        if spec.opacity is not None:
            self.boss._set_os_window_background_opacity(os_id, spec.opacity)

    def shell_error(self, window: Any) -> str:
        argv = window.child.argv
        if not argv or os.path.basename(argv[0]).lstrip("-") not in ("bash", "zsh", "fish"):
            return "shell-unqualified"
        env = window.child.final_env
        if any(env.get(key) for key in ("TMUX", "ZELLIJ", "SSH_CONNECTION", "SSH_TTY", "container")):
            return "context-unsupported"
        return ""
