"""Actual graphical acceptance against a checkout or extracted source artifact.

Use a private Xvfb DISPLAY for X11. Wayland fixtures belong on workspace 15 in a
private Hyprland instance. The verifier never switches the operator's workspace.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import struct
import subprocess
import tempfile
import time
import zlib
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def png(path: Path, color: tuple[int, int, int]) -> None:
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = chunk(b"IHDR", struct.pack("!2I5B", 1920, 1080, 8, 2, 0, 0, 0))
    body = chunk(b"IDAT", zlib.compress((b"\0" + bytes(color) * 1920) * 1080))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + header + body + chunk(b"IEND", b""))


class Session:
    def __init__(self, args):
        self.args = args
        self.root = Path(tempfile.mkdtemp(prefix="kittyscape-qualify-"))
        self.home = self.root / "home"
        self.home.mkdir()
        (self.home / ".bashrc").write_text("PS1='kittyscape> '\n")
        (self.home / ".bash_profile").write_text('. "$HOME/.bashrc"\n')
        (self.home / ".zshrc").write_text("PS1='kittyscape> '\n")
        if getattr(args, "zsh_modules", None):
            (self.home / ".zshenv").write_text("module_path=(" + shlex.quote(str(args.zsh_modules)) + ")\n")
        self.dirs = {key: self.root / path for key, path in {
            "A": "projects/Project A", "nested": "projects/Project A/deep", "B": "projects/Project B",
            "weird": "projects/space # percent% quote' ü", "sibling": "projects/Project Application",
        }.items()}
        for path in self.dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        self.images = {key: self.root / f"{key}.png" for key in ("A", "B", "baseline")}
        for key, color in {"A": (150, 70, 30), "B": (35, 110, 70), "baseline": (30, 45, 140)}.items():
            png(self.images[key], color)
        self.config = {"version": 1, "rules": [
            {"directory": str(self.dirs[key]), "image": str(self.images[image])}
            for key, image in (("A", "A"), ("nested", "B"), ("B", "B"), ("weird", "A"))
        ]}
        self.config_file = self.root / "kittyscape.json"
        self.config_file.write_text(json.dumps(self.config))
        self.conf = self.root / "kitty.conf"
        self._write_kitty_config()
        self.original_conf = self.conf.read_bytes()
        self.log_path = self.root / "kitty.log"
        self.probe_path = self.root / "events.jsonl"
        self.socket = "unix:" + str(self.root / "control")
        self.process = None
        self.pid = None
        self.results = []
        self.points = {}
        self._launch()

    def _write_kitty_config(self):
        lines = [
            f"watcher {PROJECT / 'tests/runtime/observer.py'}",
            f"watcher {self.args.bundle / 'kittyscape/watcher.py'}",
            "allow_remote_control socket-only", "confirm_os_window_close 0", "remember_window_size no",
            "initial_window_width 960", "initial_window_height 640", "background_image_layout scaled",
            "background_image_linear yes", "background_tint 0.2", "background_tint_gaps 0.4",
            "background_opacity 0.85", "foreground #f0e8df", "background #16151b",
            f"linux_display_server {self.args.backend}",
        ]
        if self.args.baseline == "single":
            lines.append("background_image " + str(self.images["baseline"]))
        if self.args.baseline == "list":
            lines.append("background_image " + str(self.root / "*.png"))
        self.conf.write_text("\n".join(lines) + "\n")

    def _verify_display(self):
        if self.args.backend == "wayland":
            runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/")).resolve()
            assert runtime.is_relative_to("/tmp"), "Wayland tests require an isolated compositor under /tmp"
            workspace = json.loads(subprocess.check_output(["hyprctl", "activeworkspace", "-j"]))
            assert workspace["id"] == 15, "Activate workspace 15 in the private compositor before testing"

    def _launch(self):
        self._verify_display()
        env = dict(os.environ)
        env.update({
            "HOME": str(self.home), "ZDOTDIR": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"), "KITTY_CONFIG_DIRECTORY": str(self.root),
            "XDG_DATA_HOME": str(self.home / ".local/share"), "XDG_STATE_HOME": str(self.home / ".local/state"),
            "KITTYSCAPE_PROBE_LOG": str(self.probe_path), "LIBGL_ALWAYS_SOFTWARE": "1",
        })
        if getattr(self.args, "shell_lib_dirs", None):
            env["LD_LIBRARY_PATH"] = self.args.shell_lib_dirs
        for key in ("TMUX", "ZELLIJ", "SSH_CONNECTION", "SSH_TTY", "KITTY_LISTEN_ON", "KITTY_WINDOW_ID", "BASH_ENV"):
            env.pop(key, None)
        command = [str(self.args.kitty), "--config", str(self.conf), "--listen-on", self.socket,
                   "--class=kittyscape-qualification", "--directory", str(self.home), str(self.args.shell)]
        if getattr(self.args, "login", False):
            command.append("-l")
        if self.args.backend == "x11":
            env.pop("WAYLAND_DISPLAY", None)
            env["DISPLAY"] = self.args.display
        with self.log_path.open("w") as stream:
            self.process = subprocess.Popen(command, env=env, stdout=stream, stderr=stream)
        self.pid = self.process.pid
        self.wait(lambda: self._ready(), "kitty startup", timeout=10)
        loads = [row for row in self.events() if row["event"] == "load"]
        self.pid = loads[0]["pid"]
        self.runtime = loads[0]
        self.wait(lambda: self.status()["revision"] == 1, "configuration load")

    def _ready(self):
        if self.process and self.process.poll() is not None:
            raise RuntimeError(self.log_path.read_text())
        try:
            self.rc("ls")
            return self.probe_path.exists()
        except RuntimeError:
            return False

    def rc(self, *arguments):
        command = ["kitten", "@", "--to", self.socket, "--use-password=never", *arguments]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout

    def action(self, name, *, pane=1):
        return json.loads(self.rc("kitten", "--match", f"id:{pane}", str(self.args.bundle / "kittyscape/action.py"), name, "--json"))

    def status(self):
        return self.action("status")

    def inspect(self, pane=1):
        return json.loads(self.rc("kitten", "--match", f"id:{pane}", str(PROJECT / "tests/runtime/inspect_kitty.py")))

    def send(self, text, pane=1):
        self.rc("send-text", "--match", f"id:{pane}", text.replace("\\", "\\\\") + "\r")

    def cd(self, directory, pane=1):
        self.send("cd " + shlex.quote(str(directory)), pane)

    def wait(self, predicate, label, *, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        raise AssertionError(label + " timed out; " + json.dumps(self.status()))

    def settle(self, directory, *, pane=1):
        def settled():
            snapshot = self.inspect(pane)
            request = snapshot["state"]["request"] or []
            return len(request) > 1 and request[1] == str(directory) and not snapshot["state"]["timer"]

        self.wait(settled, "directory selection")

    def events(self):
        return [json.loads(row) for row in self.probe_path.read_text().splitlines()]

    def screenshot(self, name, *, pane=1):
        path = self.root / (name + ".png")
        if self.args.backend == "x11":
            subprocess.run(["magick", "xwd:" + self.args.framebuffer, str(path)], capture_output=True, check=True)
        else:
            from wayland_capture import identifier

            client = self._wayland_client(pane)
            if client["workspace"]["id"] != 15:
                selector = json.dumps("address:" + client["address"])
                command = f'hl.dsp.window.move({{window={selector}, workspace="15", follow=false}})'
                subprocess.run(["hyprctl", "dispatch", command], capture_output=True, check=True)
            subprocess.run(["grim", "-T", identifier(client["title"]), str(path)], check=True, timeout=5)
        return path

    def _wayland_client(self, pane):
        os_window, active = self._active_peer(pane)
        title = f"{self.root.name} OS {os_window}"
        if active["title"] != title:
            self.rc("set-window-title", "--match", f"id:{active['id']}", title)
        for _ in range(30):
            clients = json.loads(subprocess.check_output(["hyprctl", "clients", "-j"]))
            matches = [client for client in clients if client["pid"] == self.pid and title in client["title"]]
            if matches:
                return matches[0]
            time.sleep(0.02)
        raise AssertionError("Owned Wayland OS window not found")

    def _active_peer(self, pane):
        for os_window in json.loads(self.rc("ls")):
            panes = [window for tab in os_window["tabs"] for window in tab["windows"]]
            if any(window["id"] == pane for window in panes):
                tab = next(tab for tab in os_window["tabs"] if tab["is_active"])
                active = next(window for window in tab["windows"] if window["is_active"])
                return os_window["id"], active
        raise AssertionError("Test pane disappeared")

    def arrange(self, panes):
        if self.args.backend == "x11":
            for column, pane in enumerate(panes):
                self.rc("kitten", "--match", f"id:{pane}", str(PROJECT / "tests/runtime/inspect_kitty.py"), "arrange", str(column))
                self.points[pane] = (column * 620 + 550, 600)

    def reset_arrangement(self):
        if self.args.backend == "x11":
            self.rc("kitten", "--match", "id:1", str(PROJECT / "tests/runtime/inspect_kitty.py"), "arrange", "single")
        self.points.clear()

    def pixel(self, *, pane=1):
        point = self.points.get(pane, (900, 600))
        if self.args.backend == "x11":
            return _framebuffer_pixel(self.args.framebuffer, point)
        from PIL import Image

        with Image.open(self.screenshot("current-pixel", pane=pane)) as image:
            x, y = int(image.width * 0.85), int(image.height * 0.9)
            colors = image.convert("RGB").crop((x - 4, y - 4, x + 5, y + 5)).getcolors()
            return max(colors)[1]

    def record(self, name, data=None):
        self.results.append({"scenario": name, "result": "pass", "detail": data})
        print(name + ": pass", flush=True)

    def close(self):
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self.process:
            self.process.wait(timeout=5)


def core_scenarios(session):
    session.settle(session.home)
    baseline = session.inspect()
    baseline_pixel = session.pixel()
    session.baseline_pixel = baseline_pixel
    uploads = session.status()["windows"]["1"]["uploads"]
    for label in ("A", "nested", "B", "weird", "sibling"):
        session.cd(session.dirs[label])
        session.settle(session.dirs[label])
        status = session.status()["windows"]["1"]
        assert status["owned"] == (label != "sibling"), status
        if label == "sibling":
            session.wait(lambda: session.pixel() == baseline_pixel, "displayed baseline")
        else:
            green = label in ("nested", "B")
            session.wait(lambda: _is_color(session.pixel(), green), "displayed rule image")
    session.cd(session.home)
    session.settle(session.home)
    after = session.inspect()
    fields = [key for key in baseline if key.startswith("background") or key == "foreground"]
    assert all(baseline[key] == after[key] for key in fields)
    assert after["has_image"] == baseline["has_image"]
    assert session.conf.read_bytes() == session.original_conf
    session.record("T01-T03-T07-restoration", {"rendering": {key: after[key] for key in fields}})
    directory_stack_scenario(session)
    session.cd(session.dirs["A"])
    session.settle(session.dirs["A"])
    image = session.screenshot("directory-A")
    before = session.status()["windows"]["1"]["uploads"]
    for _ in range(12):
        session.send(":")
    time.sleep(0.4)
    assert session.status()["windows"]["1"]["uploads"] == before
    assert before > uploads
    session.record("T14-unchanged-prompts", {"extra_writes": 0, "screenshot": image.name})
    session.action("pause")
    assert not session.status()["windows"]["1"]["owned"]
    assert session.inspect()["has_image"] == baseline["has_image"]
    session.action("resume")
    session.wait(lambda: session.status()["windows"]["1"]["owned"], "resume")
    session.action("restore")
    assert not session.status()["windows"]["1"]["owned"]
    session.record("T08-pause-resume-restore")
    session.action("resume")


def directory_stack_scenario(session):
    session.send("pushd " + shlex.quote(str(session.dirs["A"])))
    session.settle(session.dirs["A"])
    session.wait(lambda: _is_color(session.pixel(), False), "directory-stack push")
    session.send("popd")
    session.settle(session.home)
    session.wait(lambda: session.pixel() == session.baseline_pixel, "directory-stack pop")
    session.record("T03-directory-stack")


def focus_scenarios(session):
    session.cd(session.dirs["A"])
    session.settle(session.dirs["A"])
    tab = int(session.rc("launch", "--type=tab", "--cwd=" + str(session.dirs["B"]), str(session.args.shell)))
    session.wait(lambda: session.status()["windows"]["1"]["pane"] == tab, "tab focus")
    session.settle(session.dirs["B"], pane=tab)
    session.wait(lambda: _is_color(session.pixel(pane=tab), True), "displayed focused tab B")
    before = session.status()["windows"]["1"]["uploads"]
    session.cd(session.home, pane=1)
    time.sleep(0.3)
    assert session.status()["windows"]["1"]["uploads"] == before
    assert _is_color(session.pixel(pane=tab), True)
    split = int(session.rc("launch", "--type=window", "--cwd=" + str(session.dirs["A"]), str(session.args.shell)))
    session.wait(lambda: session.status()["windows"]["1"]["pane"] == split, "split focus")
    session.settle(session.dirs["A"], pane=split)
    session.wait(lambda: _is_color(session.pixel(pane=split), False), "displayed focused split A")
    for pane, green in ((tab, True), (split, False)):
        session.rc("focus-window", "--match", f"id:{pane}")
        session.wait(lambda: _is_color(session.pixel(pane=pane), green), "displayed focus destination")
    for pane in (tab, split, 1, split, tab):
        session.rc("focus-window", "--match", f"id:{pane}")
    session.wait(lambda: session.status()["windows"]["1"]["pane"] == tab, "rapid final focus")
    session.wait(lambda: _is_color(session.pixel(pane=tab), True), "displayed rapid focus destination")
    session.record("T04-T06-tabs-splits-focus")
    other = int(session.rc("launch", "--type=os-window", "--cwd=" + str(session.dirs["A"]), str(session.args.shell)))
    session.wait(lambda: len(session.status()["windows"]) == 2, "second OS window")
    session.wait(lambda: session.status()["windows"]["2"]["owned"], "second OS image")
    session.arrange((tab, other))
    session.wait(lambda: _is_color(session.pixel(pane=tab), True), "first OS shows B")
    session.wait(lambda: _is_color(session.pixel(pane=other), False), "second OS shows A")
    session.screenshot("two-os-windows-B", pane=tab)
    session.screenshot("two-os-windows-A", pane=other)
    before = session.status()["windows"]["2"]["uploads"]
    session.cd(session.home, pane=tab)
    session.settle(session.home, pane=tab)
    assert session.status()["windows"]["2"]["uploads"] == before
    session.wait(lambda: session.pixel(pane=tab) == session.baseline_pixel, "first OS restores its baseline")
    assert _is_color(session.pixel(pane=other), False)
    session.screenshot("two-os-windows-after-restore", pane=other)
    session.record("T05-independent-OS-windows")
    session.rc("close-window", "--match", f"id:{other}")
    session.rc("close-window", "--match", f"id:{split}")
    session.rc("close-window", "--match", f"id:{tab}")
    session.wait(lambda: len(session.status()["windows"]) == 1, "closed window state released")
    session.reset_arrangement()
    session.record("T14-window-state-release")


def lifecycle_scenarios(session):
    session.cd(session.dirs["A"])
    session.settle(session.dirs["A"])
    session.rc("set-background-image", "--match", "id:1", str(session.images["B"]))
    state = session.status()["windows"]["1"]
    assert state["paused"] and not state["owned"], state
    session.cd(session.home)
    time.sleep(0.3)
    before = session.status()["windows"]["1"]["uploads"]
    session.action("restore")
    assert session.status()["windows"]["1"]["uploads"] == before
    session.action("resume")
    session.cd(session.dirs["A"])
    session.settle(session.dirs["A"])
    session.action("pause")
    assert session.inspect()["has_image"]
    session.record("T13-external-writer-resume")
    old_config = session.config_file.read_text()
    revision = session.status()["revision"]
    session.config_file.write_text('{"version":999}')
    session.action("reload")
    session.wait(lambda: "config" in session.status()["reason"], "invalid reload diagnostic")
    assert session.status()["revision"] == revision
    session.config_file.write_text(old_config)
    session.action("reload")
    session.wait(lambda: session.status()["revision"] > revision, "valid reload recovery")
    session.record("T10-last-valid-configuration")


def _framebuffer_pixel(path, point):
    samples = []
    with open(path, "rb") as stream:
        header = struct.unpack("!25I", stream.read(100))
        size = header[11] // 8
        byte_order = "little" if header[7] == 0 else "big"
        for y in range(point[1] - 4, point[1] + 5):
            stream.seek(header[0] + header[19] * 12 + y * header[12] + (point[0] - 4) * size)
            values = stream.read(9 * size)
            samples.extend(int.from_bytes(values[x:x + size], byte_order) for x in range(0, len(values), size))
    value = Counter(samples).most_common(1)[0][0]
    return tuple((value >> shift) & 255 for shift in (16, 8, 0))


def _is_color(pixel, green):
    red, actual_green, blue = pixel
    return actual_green > red + 25 if green else red > actual_green + 25


def performance_scenario(session):
    assert session.args.backend == "x11", "pixel timing requires the dedicated Xvfb framebuffer"
    session.action("resume")
    latencies = []
    for index in range(110):
        label = "A" if index % 2 == 0 else "B"
        session.cd(session.dirs[label])
        deadline = time.monotonic() + 3
        while not _is_color(session.pixel(), label == "B"):
            if time.monotonic() > deadline:
                raise AssertionError(f"display timing exceeded 3 seconds at {index}/{label}; pixel={session.pixel()}")
            time.sleep(0.002)
        displayed = time.monotonic()
        stops = [row["time"] for row in session.events() if row["event"] == "command-stop" and row["pane"] == 1]
        if index >= 10:
            latencies.append((displayed - stops[-1]) * 1000)
    p95 = sorted(latencies)[94]
    assert p95 < 250, p95
    session.record("performance-100-transitions", {"count": len(latencies), "p95_ms": p95, "samples_ms": latencies})
    session.settle(session.dirs["B"])
    session.wait(lambda: not session.status()["pending_jobs"] and not session.status()["pending_events"], "idle start")
    session.rc("kitten", str(PROJECT / "tests/runtime/inspect_kitty.py"), "arm-idle")
    writes = sum(row["event"] == "image" for row in session.events())
    print("Idle observation: 60 seconds", flush=True)
    time.sleep(60)
    assert session.inspect()["test_timer_count"] == 0
    assert sum(row["event"] == "image" for row in session.events()) == writes
    session.record("T14-idle-60-seconds", {"scheduled_timers": 0, "image_writes": 0})


def qualify(args):
    session = Session(args)
    error = None
    try:
        core_scenarios(session)
        focus_scenarios(session)
        lifecycle_scenarios(session)
        if args.performance:
            performance_scenario(session)
    except Exception as caught:
        error = repr(caught)
        (session.root / "failure-state.json").write_text(json.dumps(session.inspect(), indent=2))
        session.screenshot("failure")
        raise
    finally:
        result = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "backend": args.backend, "platform": os.uname().sysname, "architecture": os.uname().machine,
            "kitty": session.runtime, "shell": subprocess.check_output([str(args.shell), "--version"], text=True).splitlines()[0],
            "baseline": args.baseline, "bundle": str(args.bundle), "scenarios": session.results, "error": error,
        }
        (session.root / "result.json").write_text(json.dumps(result, indent=2))
        print("Evidence: " + str(session.root), flush=True)
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kitty", type=Path, default=Path("/usr/bin/kitty"))
    parser.add_argument("--shell", type=Path, default=Path("/usr/bin/bash"))
    parser.add_argument("--bundle", type=Path, default=PROJECT)
    parser.add_argument("--backend", choices=("wayland", "x11"), default="x11")
    parser.add_argument("--display", default=":101")
    parser.add_argument("--framebuffer", default="/tmp/kittyscape-x11-experiment/frames/Xvfb_screen0")
    parser.add_argument("--baseline", choices=("none", "single", "list"), default="none")
    parser.add_argument("--performance", action="store_true")
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--zsh-modules", type=Path)
    parser.add_argument("--shell-lib-dirs")
    qualify(parser.parse_args())
