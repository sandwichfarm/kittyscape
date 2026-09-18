"""Remaining graphical scenarios in isolated X11 or Wayland kitty instances.

This verifier never changes runtime code or a desktop configuration. Each case
gets a fresh kitty process and records actual framebuffer pixels and screenshots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import struct
import subprocess
import tempfile
import time
import zlib
from contextlib import contextmanager
from pathlib import Path

from installed import installer_module, verify_artifact
from qualify import PROJECT, Session, _is_color, png


KITTEN = '''"""Test-only native operations in one isolated kitty process."""
import json
from pathlib import Path
from kittens.tui.handler import result_handler

def main(args):
    pass

@result_handler(no_ui=True)
def handle_result(args, answer, target_window_id, boss):
    window = boss.window_id_map[target_window_id]
    name = args[1]
    if name == "override":
        boss.set_background_image("fixture.png", (window.os_window_id,), False, args[3], Path(args[2]).read_bytes())
    elif name == "path":
        boss.set_background_image(args[2], (window.os_window_id,), False, "centered")
    elif name == "index":
        boss.set_background_image(None, (window.os_window_id,), False, None,
                                  global_index=int(args[2]), is_increment=args[3] == "relative")
    elif name == "theme":
        boss.on_system_color_scheme_change(args[2], False)
    elif name == "global-options":
        from kitty.fast_data_types import get_options
        before = tuple(get_options().background_image)
        boss.set_background_image(None, (), True, None, b"", linear_interpolation=True, tint=0.3, tint_gaps=0.6)
        opts = get_options()
        return json.dumps({"before": before, "after": tuple(opts.background_image),
                           "linear": opts.background_image_linear, "tint": opts.background_tint,
                           "tint_gaps": opts.background_tint_gaps})
    elif name == "theme-local":
        from kitty.colors import patch_colors
        before = {tm.os_window_id: dict(tm.tab_bar.current_colors) for tm in boss.all_tab_managers}
        patch_colors({"tab_bar_background": 0x66ccff}, configured=False, windows=(window,))
        after = {tm.os_window_id: dict(tm.tab_bar.current_colors) for tm in boss.all_tab_managers}
        return json.dumps({"tab_bars": len(after), "tab_changed": before != after})
    elif name == "profile-inspect":
        from kitty.fast_data_types import get_options, os_window_font_size
        opts = get_options()
        windows = {}
        for candidate in boss.window_id_map.values():
            windows[str(candidate.id)] = {
                "os": candidate.os_window_id,
                "padding": {edge: getattr(candidate.padding, edge) for edge in ("left", "top", "right", "bottom")},
                "margin": {edge: getattr(candidate.margin, edge) for edge in ("left", "top", "right", "bottom")},
                "foreground": int(candidate.screen.color_profile.default_fg),
            }
        return json.dumps({
            "fonts": {str(os_id): os_window_font_size(os_id) for os_id in boss.os_window_map},
            "configured_padding": tuple(opts.window_padding_width),
            "configured_margin": tuple(opts.window_margin_width),
            "foreground": int(opts.foreground),
            "windows": windows,
            "status": boss._kittyscape.status(),
        })
    elif name == "font":
        boss._change_font_size({window.os_window_id: float(args[2])})
    from kitty.colors import theme_colors
    state = boss._kittyscape.windows.get(window.os_window_id)
    baseline = state.baseline if state else None
    return json.dumps({"theme": theme_colors.applied_theme, "dark": theme_colors.has_dark_theme,
                       "light": theme_colors.has_light_theme,
                       "baseline": None if baseline is None else {"kind": baseline.kind, "layout": baseline.layout,
                                                                   "index": baseline.index, "bytes": len(baseline.data)},
                       "status": boss._kittyscape.status()})
'''


class ExtendedSession(Session):
    """Reuse the existing graphical harness with case-local launch fixtures."""

    def _write_kitty_config(self):
        super()._write_kitty_config()
        with self.conf.open("a") as stream:
            stream.write("\n".join(self.args.extra) + "\n")
        if self.args.themes:
            for name, image in (("light", "B"), ("dark", "baseline"), ("no-preference", "baseline")):
                (self.root / f"{name}-theme.auto.conf").write_text(
                    f"background_image {self.images[image]}\nbackground_image_layout scaled\n"
                    "background_image_linear yes\nbackground_tint 0.2\nbackground_tint_gaps 0.4\n"
                    "background #16151b\nforeground #f0e8df\n"
                )

    def native(self, name, *values):
        return json.loads(self.rc("kitten", "--match", "id:1", self.args.kitten, name, *map(str, values)))

    def send(self, text, pane=1):
        # Remote send-text itself decodes Python escapes before Readline sees text.
        self.rc("send-text", "--match", f"id:{pane}", text.replace("\\", "\\\\") + "\r")

    def focus_os(self, pane):
        if self.args.backend == "x11":
            self.rc("focus-window", "--match", f"id:{pane}")
            return
        client = self._wayland_client(pane)
        selector = json.dumps("address:" + client["address"])
        command = f"hl.dsp.focus({{window={selector}}})"
        subprocess.run(["hyprctl", "dispatch", command], capture_output=True, check=True)

    def change_rules(self, config):
        revision = self.status()["revision"]
        self.config_file.write_text(json.dumps(config))
        self.action("reload")
        self.wait(lambda: self.status()["revision"] > revision, "rules reload")

    def observe(self, label):
        self.wait(lambda: not self.status()["pending_jobs"] and not self.status()["pending_events"], "settled work")
        result = {"pixel": self.pixel(), "inspect": self.inspect(), "native": self.native("inspect")}
        result["screenshot"] = str(self.screenshot(label))
        (self.root / f"{label}.json").write_text(json.dumps(result, indent=2))
        return result


def state(session):
    return session.status()["windows"]["1"]


def baseline(session):
    session.settle(session.home)
    session.wait(lambda: session.pixel() != (0, 0, 0), "initial framebuffer")
    return session.pixel()


def select(session, label):
    session.cd(session.dirs[label])
    session.settle(session.dirs[label])
    session.wait(lambda: _is_color(session.pixel(), label == "B"), "rule pixels")


def paths(session):
    original = baseline(session)
    punctuation = session.root / "literal $() `printf none` ; quote' backslash\\ ü"
    punctuation.mkdir()
    config = dict(session.config, rules=[*session.config["rules"],
                                        {"directory": str(punctuation), "image": str(session.images["A"])}])
    session.change_rules(config)
    session.cd(punctuation)
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "literal punctuation path")
    session.record("T03-literal-punctuation", session.observe("punctuation"))
    alias = session.root / "symlink with spaces ü"
    alias.symlink_to(session.dirs["A"], target_is_directory=True)
    session.cd(alias)
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "symlink rule")
    session.record("T03-symlink", session.observe("symlink"))
    vanished = session.dirs["A"] / "vanished"
    vanished.mkdir()
    session.cd(vanished)
    session.settle(vanished)
    vanished.rmdir()
    session.send(":")
    session.wait(lambda: state(session)["reason"] == "directory-unavailable", "deleted cwd diagnostic")
    session.wait(lambda: session.pixel() == original, "deleted cwd restores baseline")
    session.record("T03-deleted-cwd", session.observe("deleted-cwd"))
    session.cd(session.home)
    session.settle(session.home)


def invalid_images(session):
    original = baseline(session)
    invalid = {key: session.root / f"invalid-{key}.png" for key in ("missing", "corrupt", "oversized", "unreadable")}
    invalid["corrupt"].write_bytes(b"not a PNG")
    with invalid["oversized"].open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    png(invalid["unreadable"], (150, 70, 30))
    invalid["unreadable"].chmod(0)
    try:
        for label, image in invalid.items():
            session.cd(session.home)
            session.settle(session.home)
            config = {"version": 1, "rules": [{"directory": str(session.dirs["A"]), "image": str(image)}]}
            session.change_rules(config)
            session.cd(session.dirs["A"])
            session.settle(session.dirs["A"])
            session.wait(lambda: state(session)["reason"] == "image-unavailable-or-invalid", label + " diagnostic")
            assert not state(session)["owned"]
            session.wait(lambda: session.pixel() == original, label + " fallback")
            before = state(session)["uploads"]
            for _ in range(4):
                session.send(":")
            time.sleep(0.15)
            assert state(session)["uploads"] == before
            session.record("T10-image-" + label, session.observe("image-" + label))
    finally:
        invalid["unreadable"].chmod(0o600)
    session.change_rules(session.config)
    session.cd(session.dirs["B"])
    session.settle(session.dirs["B"])
    session.wait(lambda: _is_color(session.pixel(), True), "valid image recovery")
    session.record("T10-image-recovery", session.observe("image-recovered"))


def disabled_runtime(session):
    original = baseline(session)
    select(session, "A")
    disabled = dict(session.config, enabled=False)
    session.change_rules(disabled)
    session.wait(lambda: not state(session)["owned"] and session.pixel() == original, "disabled restoration")
    before = state(session)["uploads"]
    session.cd(session.dirs["B"])
    time.sleep(0.2)
    assert not session.status()["enabled"] and state(session)["uploads"] == before
    session.record("T10-enabled-false", session.observe("disabled"))
    session.change_rules(session.config)
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), True), "re-enable")
    session.record("T10-enabled-recovery", session.observe("enabled-again"))


def reload_config(session, image, layout="scaled"):
    lines = [line for line in session.conf.read_text().splitlines()
             if not line.startswith(("background_image ", "background_image_layout "))]
    lines.extend(("background_image " + str(image), "background_image_layout " + layout))
    session.conf.write_text("\n".join(lines) + "\n")
    session.rc("load-config", str(session.conf))


def reload_inherited(session):
    baseline(session)
    select(session, "A")
    reload_config(session, session.images["B"], "mirror-tiled")
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "rule survives config reload")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: _is_color(session.pixel(), True), "new inherited baseline")
    observed = session.observe("reload-inherited")
    assert observed["inspect"]["background_image_layout"] == "mirror-tiled"
    session.record("T09-reload-inherited", observed)


def bands(path, left, right):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\0" + bytes(left) * 1620 + bytes(right) * 300
    header = chunk(b"IHDR", struct.pack("!2I5B", 1920, 1080, 8, 2, 0, 0, 0))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + header + chunk(b"IDAT", zlib.compress(row * 1080)) + chunk(b"IEND", b""))


def reload_override(session):
    baseline(session)
    override = session.root / "override.png"
    bands(override, (30, 45, 140), (170, 140, 25))
    bands(session.images["A"], (150, 70, 30), (35, 110, 70))
    session.native("override", override, "centered")
    session.wait(lambda: session.pixel()[2] > session.pixel()[0] + 45, "centered override pixels")
    original = session.pixel()
    session.action("resume")
    select(session, "A")
    assert session.native("inspect")["baseline"]["layout"] == "centered"
    reload_config(session, session.images["B"], "scaled")
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "centered rule after reload")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: session.pixel() == original, "explicit override preserved across reload")
    session.record("T09-reload-explicit-override", session.observe("reload-override"))
    session.native("path", session.images["B"])
    session.wait(lambda: _is_color(session.pixel(), True), "external path-only writer pixels")
    session.action("resume")
    assert state(session)["paused"] and state(session)["reason"] == "baseline-unknown"
    before = state(session)["uploads"]
    session.cd(session.dirs["A"])
    time.sleep(0.2)
    assert state(session)["uploads"] == before and _is_color(session.pixel(), True)
    session.record("T13-path-only-writer-rejected", session.observe("path-only-rejected"))


def glob_index(session):
    original = baseline(session)
    select(session, "B")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: session.pixel() == original, "configured glob index zero")
    session.native("index", 1, "absolute")
    session.wait(lambda: _is_color(session.pixel(), True), "absolute glob index one")
    session.action("resume")
    select(session, "A")
    session.rc("load-config", str(session.conf))
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "rule after same-config reload")
    assert session.native("inspect")["baseline"]["index"] == 1, "Config reload lost the captured absolute index"
    session.action("pause")
    session.wait(lambda: _is_color(session.pixel(), True), "absolute index baseline after reload and pause")
    session.record("T09-glob-index-reload-pause", session.observe("glob-index-reload-paused"))
    session.action("resume")
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "rule after paused-index resume")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: _is_color(session.pixel(), True), "absolute index restoration")
    session.record("T09-glob-absolute-index", session.observe("glob-index-one"))
    session.native("index", 1, "relative")
    session.action("resume")
    assert state(session)["paused"] and state(session)["reason"] == "baseline-unknown"
    before = state(session)["uploads"]
    session.cd(session.dirs["A"])
    time.sleep(0.2)
    assert state(session)["uploads"] == before
    session.record("T09-relative-index-rejected", session.observe("relative-index-rejected"))


def global_options(session):
    observed = session.native("global-options")
    assert observed["before"] == observed["after"], observed
    assert observed["linear"] and observed["tint"] == 0.2 and observed["tint_gaps"] == 0.4, observed
    session.record("T15-global-background-options", observed)


def theme_local_scope(session):
    pane = int(session.rc("launch", "--type=os-window", "--cwd=" + str(session.home), "/usr/bin/bash"))
    session.wait(lambda: pane in session.boss.window_id_map if hasattr(session, "boss") else True, "second OS window")
    observed = session.native("theme-local")
    assert observed["tab_bars"] == 2 and observed["tab_changed"], observed
    session.record("T16-theme-local-scope", observed)


def directory_profiles(session):
    """Prove scoped ownership and focused-OS process arbitration in one process."""
    animated = session.root / "profile-animated.gif"
    subprocess.run([
        "/usr/bin/magick", "-size", "1920x1080", "xc:#96461e", "-delay", "12",
        "-size", "1920x1080", "xc:#237046", "-delay", "12", "-loop", "0", str(animated),
    ], check=True)
    first_overlay = session.root / "profile-one.conf"
    second_overlay = session.root / "profile-two.conf"
    first_overlay.write_text(
        "font_size 18\nwindow_padding_width 9\nwindow_margin_width 7\n",
    )
    second_overlay.write_text("font_size 20\nwindow_padding_width 11\n")
    process_child = session.dirs["B"] / "process-child"
    process_child.mkdir()
    config = {
        "version": 1,
        "profiles": {
            "scoped": {"mode": "scoped", "font_size": 14, "padding": 6, "margin": 4},
            "process_one": {"mode": "process", "config": first_overlay.name},
            "process_two": {"mode": "process", "config": second_overlay.name},
        },
        "rules": [
            {"directory": str(session.dirs["A"]), "image": str(animated), "profile": "scoped"},
            {"directory": str(session.dirs["nested"]), "image": str(animated), "profile": "process_one"},
            {"directory": str(session.dirs["B"]), "image": str(session.images["B"]), "profile": "process_one"},
            {"directory": str(process_child), "image": str(session.images["B"]), "profile": "process_two"},
        ],
    }
    session.change_rules(config)
    scoped, process = _single_window_profiles(session, process_child)
    released, final = _two_window_profiles(session, process_child)
    session.record("T17-directory-profiles", {"scoped": scoped, "process": process, "released": released, "final": final})


def _single_window_profiles(session, process_child):
    session.cd(session.dirs["A"])
    session.settle(session.dirs["A"])
    session.wait(lambda: state(session)["profile_mode"] == "scoped" and state(session)["playback"] == "playing", "scoped animation")
    scoped = session.native("profile-inspect")
    assert scoped["fonts"]["1"] == 14, scoped
    assert set(scoped["windows"]["1"]["padding"].values()) == {6}, scoped
    assert set(scoped["windows"]["1"]["margin"].values()) == {4}, scoped
    split = int(session.rc("launch", "--type=window", "--cwd=" + str(session.home), str(session.args.shell)))
    session.wait(
        lambda: state(session)["pane"] == split and state(session)["profile_mode"] is None
        and not session.status()["pending_jobs"] and not session.status()["pending_events"],
        "split selection",
    )
    restored = session.native("profile-inspect")
    assert restored["fonts"]["1"] == 11, restored
    assert set(restored["windows"]["1"]["padding"].values()) == {None}, restored
    session.rc("close-window", "--match", f"id:{split}")
    session.focus_os(1)
    session.wait(lambda: state(session)["pane"] == 1 and state(session)["profile_mode"] == "scoped", "scoped pane restored")
    session.cd(session.dirs["nested"])
    session.settle(session.dirs["nested"])
    session.wait(lambda: session.status()["process_profile_active"], "scoped to process")
    process = session.native("profile-inspect")
    assert process["fonts"]["1"] == 18, process
    assert process["configured_padding"] == [9, 9, 9, 9], process
    assert process["configured_margin"] == [7, 7, 7, 7], process
    assert state(session)["playback"] == "playing", session.status()
    transitions = session.status()["profile_transitions"]
    session.send(":")
    time.sleep(0.2)
    assert session.status()["profile_transitions"] == transitions, session.status()
    session.send("printf '\\033]10;#123456\\007'")
    session.wait(
        lambda: session.native("profile-inspect")["windows"]["1"]["foreground"] == 0x123456,
        "external OSC color",
    )
    session.native("font", 17)
    session.wait(lambda: session.native("profile-inspect")["fonts"]["1"] == 17, "external font size")
    session.cd(process_child)
    session.settle(process_child)
    session.wait(lambda: session.native("profile-inspect")["fonts"]["1"] == 20, "direct process transition")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: not session.status()["process_profile_active"], "direct process release")
    after_direct = session.native("profile-inspect")
    assert after_direct["fonts"]["1"] == 17, after_direct
    assert after_direct["windows"]["1"]["foreground"] == 0x123456, after_direct
    session.cd(session.dirs["nested"])
    session.settle(session.dirs["nested"])
    session.wait(lambda: session.status()["process_profile_active"], "process reactivation")
    return scoped, process


def _two_window_profiles(session, process_child):
    other = int(session.rc("launch", "--type=os-window", "--cwd=" + str(session.dirs["A"]), str(session.args.shell)))
    session.wait(lambda: len(session.status()["windows"]) == 2, "profile second OS window")
    session.wait(
        lambda: not session.status()["process_profile_active"]
        and not session.status()["pending_jobs"] and not session.status()["pending_events"],
        "focused scoped OS releases process",
    )
    released = session.native("profile-inspect")
    assert released["fonts"] == {"1": 17, "2": 14}, released
    assert released["windows"]["1"]["foreground"] == 0x123456, released
    session.cd(session.dirs["nested"], pane=other)
    session.settle(session.dirs["nested"], pane=other)
    session.wait(
        lambda: session.status()["process_profile_active"] and session.status()["process_profile_controller"] == 2
        and not session.status()["pending_jobs"] and not session.status()["pending_events"],
        "second OS controls process",
    )
    assert session.native("profile-inspect")["fonts"] == {"1": 18, "2": 18}, session.native("profile-inspect")
    transitions = session.status()["profile_transitions"]
    session.send(":", pane=1)
    time.sleep(0.2)
    assert session.status()["profile_transitions"] == transitions, session.status()
    session.cd(session.dirs["B"], pane=other)
    session.settle(session.dirs["B"], pane=other)
    session.wait(lambda: session.native("profile-inspect")["fonts"]["2"] == 18, "first process profile")
    session.cd(process_child, pane=other)
    session.settle(process_child, pane=other)
    session.wait(lambda: session.native("profile-inspect")["fonts"]["2"] == 20, "base-derived process transition")
    session.cd(session.home, pane=other)
    session.settle(session.home, pane=other)
    session.wait(lambda: not session.status()["process_profile_active"], "process profile release")
    session.cd(session.dirs["A"], pane=other)
    session.settle(session.dirs["A"], pane=other)
    session.cd(session.home, pane=1)
    session.settle(session.home, pane=1)
    final = session.native("profile-inspect")
    assert final["fonts"] == {"1": 17, "2": 14}, final
    session.rc("close-window", "--match", f"id:{other}")
    return released, final


def automatic_theme(session):
    baseline(session)
    session.cd(session.dirs["A"])
    session.wait(lambda: not session.status()["pending_jobs"] and not session.status()["pending_events"], "theme profile settles")
    initial = session.observe("theme-before-switch")
    issue = session.status()["reason"] + " " + state(session)["reason"]
    if "theme" in issue and not state(session)["owned"] and state(session)["uploads"] == 0:
        session.record("T09-auto-theme-preactivation-rejection", initial)
        return
    assert state(session)["owned"], initial
    session.native("theme", "light")
    session.wait(lambda: not session.status()["pending_jobs"] and not session.status()["pending_events"], "theme update settles")
    changed = session.observe("theme-changed")
    assert state(session)["owned"], changed
    assert not state(session)["paused"], changed
    assert changed["native"]["theme"] == "light", changed
    assert _is_color(session.pixel(), False), changed
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: _is_color(session.pixel(), True), "new light-theme baseline restoration")
    final = session.observe("theme-resume")
    session.record("T09-auto-theme-boundary", final)
    select(session, "A")
    session.action("pause")
    session.native("theme", "dark")
    session.wait(lambda: session.pixel()[2] > session.pixel()[0] + 45, "dark theme while manually paused")
    assert state(session)["paused"]
    assert not state(session)["owned"]
    session.record("T09-theme-respects-manual-pause", session.observe("theme-manual-pause"))
    session.action("resume")
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "resume after dark theme")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: session.pixel()[2] > session.pixel()[0] + 45, "dark theme baseline restoration")
    session.record("T09-theme-dark-restoration", session.observe("theme-dark-restored"))


def disabled_reports(session):
    session.wait(lambda: bool(session.status()["windows"]), "window registration")
    session.wait(lambda: session.status()["reason"] == "shell-reports-disabled", "disabled-report preflight")
    session.send("cd " + shlex.quote(str(session.dirs["A"])))
    output = session.root / "shell-still-usable"
    session.send("printf usable > " + shlex.quote(str(output)))
    session.wait(output.exists, "usable shell despite disabled reports")
    assert output.read_text() == "usable" and not state(session)["owned"] and state(session)["uploads"] == 0
    session.record("T11-" + session.args.extra[0].replace(" ", "-"), session.observe("reports-disabled"))


def remote_report(session):
    baseline(session)
    select(session, "A")
    command = "__ks_remote(){ printf '\\033]7;file://remote.invalid/example/Project\\007'; }; PROMPT_COMMAND+=(__ks_remote)"
    session.send(command)
    session.wait(lambda: state(session)["reason"] == "directory-invalid-remote-or-unreported", "remote OSC7 rejected")
    assert not state(session)["owned"]
    session.record("T11-remote-OSC7", session.observe("remote-report"))
    session.send("unset 'PROMPT_COMMAND[-1]'")
    session.cd(session.dirs["B"])
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), True), "fresh local report recovers")
    session.record("T11-remote-report-recovery", session.observe("remote-recovered"))
    session.send("__ks_missing(){ printf '\\033]7;\\007'; }; PROMPT_COMMAND+=(__ks_missing)")
    session.wait(lambda: state(session)["reason"] == "directory-report-lost", "lost report is distinct from startup")
    assert not state(session)["owned"]
    session.record("T11-lost-OSC7", session.observe("lost-report"))
    session.send("unset 'PROMPT_COMMAND[-1]'")
    session.cd(session.dirs["A"])
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "fresh report after loss")
    session.record("T11-lost-report-recovery", session.observe("lost-recovered"))


def nested_shell(session):
    original = baseline(session)
    select(session, "A")
    session.send("bash")
    time.sleep(0.15)
    session.cd(session.dirs["B"])
    time.sleep(0.4)
    observed = session.observe("nested-shell")
    assert not state(session)["owned"] and state(session)["reason"] == "context-unsupported", observed
    assert session.pixel() == original, observed
    session.send("exit")
    session.wait(lambda: session.inspect()["prompt"], "outer prompt recovers")
    assert not state(session)["owned"] and state(session)["reason"] == "context-unsupported"
    session.action("resume")
    session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), False), "explicit outer-shell resume")
    session.record("T11-nested-local-shell-rejected", {"observation": observed, "recovered": session.observe("nested-recovered")})


def unsupported_commands(session):
    original = baseline(session)
    for name in ("ssh", "tmux", "zellij", "docker"):
        select(session, "A")
        executable = session.root / name
        executable.write_text("#!/bin/sh\nprintf '\\033]7;file://localhost/example\\007\\033]133;A\\007'\n")
        executable.chmod(0o700)
        session.send(shlex.quote(str(executable)))
        session.wait(lambda: state(session)["reason"] == "context-unsupported", name + " rejected")
        session.wait(lambda: session.pixel() == original, name + " fallback")
        session.cd(session.dirs["B"])
        time.sleep(0.12)
        assert not state(session)["owned"] and state(session)["reason"] == "context-unsupported"
        session.record("T11-unsupported-command-" + name, session.observe("unsupported-" + name))
        session.action("resume")
        session.wait(lambda: state(session)["owned"] and _is_color(session.pixel(), True), "explicit context resume")


def unsupported_environment(session):
    original = baseline(session)
    for name in ("TMUX", "ZELLIJ", "container", "SSH_CONNECTION"):
        pane = int(session.rc("launch", "--type=tab", "--env=" + name + "=fixture",
                              "--cwd=" + str(session.dirs["A"]), str(session.args.shell)))
        session.wait(lambda: state(session)["pane"] == pane and state(session)["reason"] == "context-unsupported", name)
        assert not state(session)["owned"]
        session.wait(lambda: session.pixel() == original, name + " startup fallback")
        session.record("T11-declared-environment-" + name, {"status": session.status(), "pixel": session.pixel()})
        session.rc("close-window", "--match", f"id:{pane}")
        session.wait(lambda: state(session)["pane"] == 1, "original pane restored")


def unsupported_shell(session):
    original = baseline(session)
    select(session, "A")
    pane = int(session.rc("launch", "--type=tab", "--cwd=" + str(session.dirs["B"]), "/usr/bin/sh"))
    session.wait(lambda: state(session)["pane"] == pane, "unsupported shell active")
    time.sleep(0.2)
    observed = session.observe("unsupported-sh")
    observed["active_pane"] = session.inspect(pane)
    session.rc("close-window", "--match", f"id:{pane}")
    actual = observed["inspect"]["runtime"]["windows"]["1"]
    assert actual["reason"] == "shell-unqualified" and not actual["owned"], observed
    assert tuple(observed["pixel"]) == original, observed
    session.record("T11-unqualified-shell-fallback", observed)


def exit_status(session):
    baseline(session)
    select(session, "A")
    before = sum(row["event"] == "command-stop" for row in session.events())
    session.send("false")
    session.wait(lambda: sum(row["event"] == "command-stop" for row in session.events()) > before, "false completes")
    session.wait(lambda: session.inspect()["prompt"], "false prompt")
    output = session.root / "exit-status"
    session.send("printf '%s\\n' \"$?\" > " + shlex.quote(str(output)))
    session.wait(output.exists, "exit status capture")
    assert output.read_text().strip() == "1", output.read_text()
    session.record("T11-prompt-exit-status", {"captured_status": 1, "pixel": session.pixel()})


CASES = {
    "paths": (paths, "single", (), False),
    "invalid-images": (invalid_images, "single", (), False),
    "disabled-runtime": (disabled_runtime, "single", (), False),
    "reload-inherited": (reload_inherited, "single", (), False),
    "reload-override": (reload_override, "single", (), False),
    "glob-index": (glob_index, "list", (), False),
    "global-options": (global_options, "list", (), False),
    "theme-local-scope": (theme_local_scope, "single", (), False),
    "directory-profiles": (directory_profiles, "single", (), False),
    "automatic-theme": (automatic_theme, "single", (), True),
    "disabled-integration": (disabled_reports, "single", ("shell_integration disabled",), False),
    "disabled-cwd": (disabled_reports, "single", ("shell_integration no-cwd",), False),
    "disabled-prompt": (disabled_reports, "single", ("shell_integration no-prompt-mark",), False),
    "remote-report": (remote_report, "single", (), False),
    "nested-shell": (nested_shell, "single", (), False),
    "unsupported-commands": (unsupported_commands, "single", (), False),
    "unsupported-environment": (unsupported_environment, "single", (), False),
    "unsupported-shell": (unsupported_shell, "single", (), False),
    "exit-status": (exit_status, "single", (), False),
}


def run_case(name, options, result_root, kitten):
    function, profile, extra, themes = CASES[name]
    args = argparse.Namespace(kitty=options.kitty, shell=options.shell, bundle=options.bundle, backend=options.backend, display=":102",
                              framebuffer=str(result_root / "frames/Xvfb_screen0"), baseline=profile, extra=extra,
                              themes=themes, kitten=str(kitten))
    session = ExtendedSession.__new__(ExtendedSession)
    result = {
        "case": name, "status": "failed", "baseline": profile, "extra_config": extra, "automatic_theme_files": themes,
        "backend": options.backend, "artifact": options.artifact,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": {str(p.relative_to(options.bundle)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((options.bundle / "kittyscape").glob("*.py"))},
    }
    try:
        session.__init__(args)
        result.update({"evidence": str(session.root), "runtime": session.runtime})
        function(session)
        result["status"] = "passed"
    except Exception as error:
        result["error"] = repr(error)
        if getattr(session, "pid", None):
            try:
                result["failure"] = session.observe("failure")
            except Exception as capture_error:
                result["capture_error"] = repr(capture_error)
        print("FAILED " + name + ": " + repr(error), flush=True)
    finally:
        result["scenarios"] = getattr(session, "results", [])
        if getattr(session, "pid", None):
            session.close()
        (result_root / (name + ".json")).write_text(json.dumps(result, indent=2))
        print("CASE " + name + ": " + result["status"], flush=True)
    return result


def check_private_display():
    """Refuse any existing lock or socket; never auto-select a desktop display."""
    for path in ("/tmp/.X102-lock", "/tmp/.X11-unix/X102"):
        if os.path.lexists(path):
            raise SystemExit("Refusing occupied dedicated display :102: " + path)


@contextmanager
def private_display(options, root):
    """Own Xvfb only for X11; Wayland keeps the Session's private capture workflow."""
    if options.backend == "wayland":
        yield
        return
    check_private_display()
    (root / "frames").mkdir()
    with (root / "xvfb.log").open("w") as log:
        process = subprocess.Popen([str(options.xvfb), ":102", "-screen", "0", "1280x800x24",
                                    "-fbdir", str(root / "frames"), "-nolisten", "tcp"], stdout=log, stderr=log)
    try:
        wait_for_framebuffer(process, root)
        yield
    finally:
        process.terminate()
        process.wait(timeout=5)


def wait_for_framebuffer(process, root):
    deadline = time.monotonic() + 5
    while not (root / "frames/Xvfb_screen0").exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError((root / "xvfb.log").read_text())
        time.sleep(0.02)


def save_report(root, options, results, error):
    report = {"backend": options.backend, "display": ":102" if options.backend == "x11" else os.environ.get("WAYLAND_DISPLAY"),
              "platform": os.uname().sysname, "architecture": os.uname().machine, "artifact": options.artifact,
              "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": results, "error": error,
              "kitty_executable": str(options.kitty), "shell_executable": str(options.shell),
              "shell_version": subprocess.check_output([str(options.shell), "--version"], text=True).splitlines()[0],
              "scope": "Bash advanced cases; unsupported-command fixtures are API/OSC injection, not actual remote support",
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root / "result.json").write_text(json.dumps(report, indent=2))
    print("Result: " + str(root / "result.json"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kitty", type=Path, default=Path("/usr/bin/kitty"))
    parser.add_argument("--shell", type=Path, default=Path("/usr/bin/bash"), help="Bash executable for the advanced cases")
    parser.add_argument("--bundle", type=Path, default=PROJECT)
    parser.add_argument("--archive", type=Path, help="Verify and bind an original source archive to the extracted bundle")
    parser.add_argument("--backend", choices=("x11", "wayland"), default="x11")
    parser.add_argument("--xvfb", type=Path, default=Path("/tmp/kittyscape-tools/xvfb/usr/bin/Xvfb"))
    parser.add_argument("--case", choices=CASES, action="append", help="glob-index and automatic-theme require current kitty APIs")
    options = parser.parse_args()
    options.bundle = options.bundle.resolve(strict=True)
    options.artifact = verify_artifact(options, installer_module()) if options.archive else None
    root = Path(tempfile.mkdtemp(prefix="kittyscape-extended-"))
    kitten = root / "k.py"
    kitten.write_text(KITTEN)
    results = []
    error = None
    print("Evidence root: " + str(root), flush=True)
    try:
        with private_display(options, root):
            for name in options.case or CASES:
                results.append(run_case(name, options, root, kitten))
    except Exception as caught:
        error = repr(caught)
        raise
    finally:
        save_report(root, options, results, error)
    return 1 if any(row["status"] != "passed" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
