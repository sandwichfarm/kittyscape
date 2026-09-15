"""Directory selection and per-OS-window lifecycle, driven by kitty events."""

from __future__ import annotations

import hashlib
import shlex
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .compat import Background, Kitty, local_directory
from .config import Config, ConfigError, load_config
from .images import Image, ImageError, load_image
from .rules import normalize_directory, resolve


@dataclass
class WindowState:
    baseline: Background
    pane: int = 0
    generation: int = 0
    timer: int = 0
    event_due: float = 0.0
    owned: bool = False
    paused: bool = False
    reason: str = "directory-unreported"
    request: tuple = ()
    applied: tuple = ()
    uploads: int = 0
    failed: tuple = ()


class Runtime:
    """One rules engine per kitty process; filesystem work runs in one worker."""

    def __init__(self, boss: Any, config_path: Path):
        self.boss = boss
        self.path = Path(config_path)
        self.windows: dict[int, WindowState] = {}
        self.reports: dict[int, tuple[str | None, str]] = {}
        self.unsupported: set[int] = set()
        self.config: Config | None = None
        self.revision = 0
        self.reason = "config-loading"
        self.detail = ""
        self.suspended = False
        self.paused = False
        self.closed = False
        self.jobs: dict[str, tuple[Future, Any, float]] = {}
        self.waiting: dict[str, tuple[Any, Any]] = {}
        self.stalled: Future | None = None
        self.job_timer = 0
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kittyscape-files")
        self.images: OrderedDict[str, Image] = OrderedDict()
        self.kitty = Kitty(boss, self.external, self.options_changed)
        self.reload()

    def _submit(self, key: str, function: Any, done: Any) -> None:
        if self._reader_stalled():
            done(None, TimeoutError("filesystem-timeout"))
            return
        if self.jobs:
            self.waiting[key] = (function, done)
            return
        self.jobs[key] = (self.pool.submit(function), done, time.monotonic())
        self._arm_collector()

    def _reader_stalled(self) -> bool:
        if self.stalled is not None and self.stalled.done():
            self.stalled = None
        return self.stalled is not None

    def _arm_collector(self) -> None:
        if self.jobs and not self.closed and not self.job_timer:
            self.job_timer = self.kitty.timer(self._collect, 0.01, False)

    def _collect(self, timer: int) -> None:
        self.job_timer = 0
        # Kitty's native main loop retains the GIL between Python callbacks.
        # Yield without a timed delay so the filesystem worker can finish.
        time.sleep(0)
        for key, job in list(self.jobs.items()):
            self._collect_job(key, job)
        if not self.jobs and self.waiting:
            key = next(iter(self.waiting))
            function, done = self.waiting.pop(key)
            self._submit(key, function, done)
        self._arm_collector()

    def _collect_job(self, key: str, job: tuple) -> None:
        future, done, started = job
        if future.done():
            self.jobs.pop(key)
            _complete(future, done)
        elif time.monotonic() - started > 5:
            self.jobs.pop(key)
            if not future.cancel():
                self.stalled = future
            done(None, TimeoutError("filesystem-timeout"))
            self._reject_waiting()

    def _reject_waiting(self) -> None:
        for _, done in self.waiting.values():
            done(None, TimeoutError("filesystem-timeout"))
        self.waiting.clear()

    def reload(self) -> None:
        def read():
            config = load_config(self.path)
            self.images.clear()
            return config

        self._submit("config", read, self._loaded)

    def _loaded(self, config: Config | None, error: Exception | None) -> None:
        if error:
            self.reason = "filesystem-timeout" if isinstance(error, TimeoutError) else "config-invalid-or-unreadable"
            self.detail = str(error)[:240] if isinstance(error, ConfigError) else ""
            return
        self.config = config
        self.detail = ""
        self.revision += 1
        self.reason = self.kitty.capability_error()
        for state in self.windows.values():
            state.request = ()
        if self.config and not self.config.enabled:
            self._restore_all()
        self._schedule_all()

    def event(self, window: Any, *, command: str = "", starting: bool = False) -> None:
        if self.closed or window.destroyed:
            return
        state = self.windows.get(window.os_window_id)
        if state is None:
            state = WindowState(self.kitty.baseline(window.os_window_id), paused=self.paused)
            self.windows[window.os_window_id] = state
        if state.baseline.kind == "unknown":
            state.paused, state.reason = True, "baseline-unknown"
        self._update_report(window, command, starting)
        if self.kitty.active(window.os_window_id) is window:
            self._schedule(window.os_window_id)

    def _update_report(self, window: Any, command: str, starting: bool) -> None:
        issue = self.kitty.capability_error() or self.kitty.shell_error(window)
        if issue:
            self.reports[window.id] = (None, issue)
        elif starting and _unsupported_command(command):
            self.unsupported.add(window.id)
            self.reports[window.id] = (None, "context-unsupported")
        elif window.at_prompt:
            self._report(window)

    def _report(self, window: Any) -> None:
        if window.id in self.unsupported:
            self.reports[window.id] = (None, "context-unsupported")
            return
        issue = self.kitty.capability_error() or self.kitty.shell_error(window)
        if issue:
            self.reports[window.id] = (None, issue)
            return
        if not window.screen.last_reported_cwd:
            previous, reason = self.reports.get(window.id, (None, ""))
            issue = "directory-report-lost" if previous or reason == "directory-report-lost" else "directory-unreported"
            self.reports[window.id] = (None, issue)
            return
        try:
            directory = local_directory(window.screen.last_reported_cwd)
        except (ValueError, UnicodeError):
            self.reports[window.id] = (None, "directory-invalid-remote-or-unreported")
        else:
            self.reports[window.id] = (directory, "")

    def _schedule(self, os_id: int) -> None:
        state = self.windows.get(os_id)
        if state is None:
            return
        state.generation += 1
        state.event_due = time.monotonic() + 0.02
        if not state.timer:
            state.timer = self.kitty.timer(lambda _: self._event_ready(os_id), 0.02, False)

    def _event_ready(self, os_id: int) -> None:
        state = self.windows.get(os_id)
        if state is None or not state.timer:
            return
        state.timer = 0
        remaining = state.event_due - time.monotonic()
        if remaining > 0:
            state.timer = self.kitty.timer(lambda _: self._event_ready(os_id), remaining, False)
        else:
            self._update(os_id, state.generation)

    def _schedule_all(self) -> None:
        for window in list(self.boss.window_id_map.values()):
            if self.kitty.active(window.os_window_id) is window:
                self.event(window)

    def _update(self, os_id: int, generation: int) -> None:
        target = self._target(os_id, generation)
        if target is None:
            return
        state, window = target
        state.pane = window.id
        if window.at_prompt:
            self._report(window)
        self._select_for_window(os_id, state, window)

    def _target(self, os_id: int, generation: int) -> tuple | None:
        state = self.windows.get(os_id)
        if state is None or generation != state.generation:
            return None
        state.timer = 0
        window = self.kitty.active(os_id)
        if not window or window.destroyed:
            return None
        if self.suspended or state.paused or not self.config:
            return None
        return state, window

    def _select_for_window(self, os_id: int, state: WindowState, window: Any) -> None:
        directory, issue = self.reports.get(window.id, (None, "directory-unreported"))
        capability = self.kitty.capability_error()
        if not self.config.enabled or capability:
            state.reason = capability or "disabled"
            self._restore(os_id, state)
            return
        if directory is None and issue == "directory-unreported":
            state.reason = issue
            return
        request = (window.id, directory, issue, self.revision)
        if state.request != request:
            state.reason = issue
            state.failed = ()
        config, baseline, generation = self.config, state.baseline, state.generation
        self._submit(
            f"window:{os_id}", lambda: self._select(config, directory, baseline),
            lambda value, error: self._selected((os_id, generation, window.id, request), value, error),
        )

    def _image(self, path: str) -> Image:
        if path in self.images:
            self.images.move_to_end(path)
            return self.images[path]
        image = load_image(path)
        self.images[path] = image
        while len(self.images) > 64 or sum(len(value.data) for value in self.images.values()) > 32 * 1024 * 1024:
            self.images.popitem(last=False)
        return image

    def _select(self, config: Config, directory: str | None, baseline: Background) -> tuple:
        baseline = self._prepare_baseline(baseline)
        directory, issue = _usable_directory(directory)
        path = resolve(config, directory) if directory else config.fallback
        if path:
            return self._select_image(path, config.fallback, baseline, issue)
        return _baseline_selection(baseline, issue)

    def _prepare_baseline(self, baseline: Background) -> Background:
        if not baseline.path or baseline.data:
            return baseline
        if baseline.kind == "override":
            return replace(baseline, data=load_image(baseline.path).data)
        if not self.kitty.modern and baseline.kind == "inherited":
            return replace(baseline, data=self._image(baseline.path).data)
        return baseline

    def _select_image(self, path: str, fallback: str | None, baseline: Background, issue: str) -> tuple:
        try:
            image = self._image(path)
        except (ImageError, OSError):
            issue = "image-unavailable-or-invalid"
            image = self._fallback_image(fallback if fallback != path else None)
        if image is None:
            return _baseline_selection(baseline, issue)
        spec = replace(baseline, kind="override", path="kittyscape.png", data=image.data)
        return baseline, spec, (image.digest, spec.layout, spec.linear, spec.tint, spec.tint_gaps), False, issue

    def _fallback_image(self, path: str | None) -> Image | None:
        if path:
            try:
                return self._image(path)
            except (ImageError, OSError):
                pass
        return None

    def _selected(self, context: tuple, value: Any, error: Exception | None) -> None:
        os_id, generation, pane, request = context
        state = self._current_selection(os_id, generation, pane)
        if state is None:
            return
        state.request = request
        if error:
            state.reason = "filesystem-timeout" if isinstance(error, TimeoutError) else "baseline-or-filesystem-unavailable"
            return
        state.baseline = value[0]
        if value[4]:
            state.reason = value[4]
        elif state.failed != value[2]:
            state.reason = request[2]
        self._display(os_id, state, value)

    def _current_selection(self, os_id: int, generation: int, pane: int) -> WindowState | None:
        state = self.windows.get(os_id)
        window = self.kitty.active(os_id)
        if not state or state.generation != generation or state.paused:
            return None
        if not window or window.id != pane:
            return None
        return state

    def _display(self, os_id: int, state: WindowState, selection: tuple) -> None:
        _, spec, key, restore, _ = selection
        if state.applied == key or state.failed == key or (restore and not state.owned):
            return
        try:
            self.kitty.apply(os_id, spec, restore=restore)
        except Exception:
            state.reason = "image-apply-failed"
            state.failed = key
            return
        state.applied, state.owned = key, not restore
        state.failed = ()
        state.uploads += 1

    def _cancel_event(self, state: WindowState) -> None:
        state.generation += 1
        state.event_due = 0
        if state.timer:
            self.kitty.remove_timer(state.timer)
            state.timer = 0

    def _restore(self, os_id: int, state: WindowState) -> None:
        self._cancel_event(state)
        self.waiting.pop(f"window:{os_id}", None)
        if state.owned:
            try:
                self.kitty.apply(os_id, state.baseline, restore=True)
            except Exception:
                state.reason = "restore-failed"
                return
            state.owned = False
            state.applied = ()
            if state.reason == "restore-failed":
                state.reason = ""
            state.uploads += 1

    def _restore_all(self) -> None:
        for os_id, state in self.windows.items():
            self._restore(os_id, state)

    def external(self, os_id: int, baseline: Background) -> None:
        state = self.windows.get(os_id)
        if state:
            self._cancel_event(state)
            self.waiting.pop(f"window:{os_id}", None)
            state.baseline = baseline
            state.owned = False
            state.paused = True
            state.request = state.applied = ()
            state.reason = "external-writer-paused"

    def options_changed(self, phase: str, theme_windows: tuple[int, ...] = ()) -> None:
        if phase == "before":
            self.suspended = True
            self._restore_all()
            return
        for os_id, state in self.windows.items():
            if os_id in theme_windows:
                state.baseline = self.kitty.inherited()
            elif state.baseline.kind == "inherited":
                current = self.kitty.inherited()
                if self.kitty.modern:
                    state.baseline = replace(current, index=state.baseline.index)
                else:
                    state.baseline = replace(
                        state.baseline, layout=current.layout, linear=current.linear,
                        tint=current.tint, tint_gaps=current.tint_gaps,
                    )
            state.request = state.applied = ()
        self.suspended = False
        self._schedule_all()

    def action(self, name: str) -> dict:
        if name == "reload":
            self.reload()
        elif name in ("pause", "restore"):
            self._pause_all()
        elif name == "resume":
            self.paused = False
            self.unsupported.clear()
            for state in self.windows.values():
                state.paused = state.baseline.kind == "unknown"
                state.request = state.applied = ()
                state.reason = "baseline-unknown" if state.paused else ""
            self._schedule_all()
        elif name != "status":
            raise ValueError("unknown-action")
        return self.status()

    def _pause_all(self) -> None:
        self.paused = True
        self._restore_all()
        for state in self.windows.values():
            state.paused = True
            if state.reason != "restore-failed":
                state.reason = "paused"

    def status(self) -> dict:
        stalled = self.stalled is not None and not self.stalled.done()
        return {
            "enabled": bool(self.config and self.config.enabled), "revision": self.revision,
            "reason": self.reason, "detail": self.detail,
            "pending_jobs": len(self.jobs) + len(self.waiting) + int(stalled), "filesystem_stalled": stalled,
            "modern_background_api": self.kitty.modern,
            "pending_events": sum(bool(state.timer) for state in self.windows.values()),
            "windows": {
                str(os_id): {key: getattr(state, key) for key in ("pane", "owned", "paused", "reason", "uploads")}
                for os_id, state in self.windows.items()
            },
        }

    def removed(self, window: Any) -> None:
        self.reports.pop(window.id, None)
        self.unsupported.discard(window.id)
        self.waiting.pop(f"window:{window.os_window_id}", None)
        # on_close runs before kitty removes the window from its maps.
        self.kitty.timer(lambda _: self._prune(), 0, False)

    def _prune(self) -> None:
        for os_id in list(self.windows):
            if os_id not in self.boss.os_window_map:
                state = self.windows.pop(os_id)
                if state.timer:
                    self.kitty.remove_timer(state.timer)
                self.kitty.overrides.pop(os_id, None)
                self.waiting.pop(f"window:{os_id}", None)
        self._schedule_all()

    def close(self) -> None:
        self.closed = True
        self.waiting.clear()
        if self.job_timer:
            self.kitty.remove_timer(self.job_timer)
        for state in self.windows.values():
            if state.timer:
                self.kitty.remove_timer(state.timer)
        self.pool.shutdown(wait=False, cancel_futures=True)


def _complete(future: Future, done: Any) -> None:
    try:
        value = future.result()
    except Exception as error:
        done(None, error)
    else:
        done(value, None)


def _usable_directory(directory: str | None) -> tuple[str | None, str]:
    if directory:
        try:
            normalize_directory(directory)
        except ValueError:
            return None, "directory-unavailable"
    return directory, ""


def _baseline_selection(baseline: Background, issue: str) -> tuple:
    digest = hashlib.sha256(baseline.data).hexdigest() if baseline.data else ""
    return baseline, baseline, ("baseline", baseline.path, baseline.index, digest), True, issue


def _unsupported_command(command: str) -> bool:
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    while words and words[0] in ("command", "builtin", "exec"):
        words.pop(0)
    if not words:
        return False
    excluded = {"ssh", "mosh", "tmux", "zellij", "docker", "podman", "machinectl"}
    executable = Path(words[0]).name
    return executable in excluded or _nested_interactive_shell(executable, words[1:])


def _nested_interactive_shell(executable: str, arguments: list[str]) -> bool:
    if executable not in ("bash", "zsh", "fish"):
        return False
    if any(argument in ("-c", "--command") for argument in arguments):
        return False
    return all(argument.startswith("-") for argument in arguments)
