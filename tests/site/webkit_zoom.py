"""Prove exact native WebKitGTK page zoom using existing libraries on owned :103.

Run with Python from the repository root. No compilation, browser installation,
CSS zoom, or viewport emulation is used. All generated state stays under /tmp.
"""

from __future__ import annotations

import ctypes as ct
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.dont_write_bytecode = True
import zoom as native

BUNDLE = Path("/home/sandwich/.cache/ms-playwright/webkit-2311/minibrowser-gtk")
EXTRA_LIBRARIES = "/tmp/kittyscape-webkit-wxpv4ff1/usr/lib/x86_64-linux-gnu"
ARTIFACTS = (Path("docs/.vitepress/dist").resolve(), Path("docs/.vitepress/dist-subpath").resolve())
READY = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_void_p, ct.c_void_p)


class GError(ct.Structure):
    _fields_ = [("domain", ct.c_uint), ("code", ct.c_int), ("message", ct.c_char_p)]


class ArtifactHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        route = unquote(urlsplit(path).path)
        root = ARTIFACTS[1] if route.startswith("/kittyscape/") else ARTIFACTS[0]
        route = route[len("/kittyscape"):] if root == ARTIFACTS[1] else route
        target = (root / route.lstrip("/")).resolve()
        if not target.is_relative_to(root):
            return str(root / "missing-invalid-path")
        return str(target)

    def log_message(self, _format, *_args):
        pass


def bind(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


class WebKitHost:
    def __init__(self, owner, output):
        native.verify_owner(owner)
        self.owner, self.output = owner, output
        self.callbacks = []
        self.gtk = ct.CDLL("libgtk-4.so.1")
        self.glib = ct.CDLL("libglib-2.0.so.0")
        self.gobject = ct.CDLL("libgobject-2.0.so.0")
        self.webkit = ct.CDLL(str(BUNDLE / "lib/libwebkitgtk-6.0.so.4"))
        self.jsc = ct.CDLL(str(BUNDLE / "lib/libjavascriptcoregtk-6.0.so.1"))
        self.bindings()
        self.window = self.create_window()
        self.x11, self.xtest = native.libraries()
        self.display = self.x11.XOpenDisplay(b":103")
        if not self.display:
            raise RuntimeError("Cannot connect to owned display :103")
        self.pump(.3)
        self.xwindow = native.browser_window(self.x11, self.display)

    def bindings(self):
        pointer = ct.c_void_p
        declarations = {
            self.gtk: {
                "gtk_init": ([], None), "gtk_window_new": ([], pointer),
                "gtk_window_set_child": ([pointer, pointer], None),
                "gtk_window_set_default_size": ([pointer, ct.c_int, ct.c_int], None),
                "gtk_window_set_decorated": ([pointer, ct.c_int], None),
                "gtk_window_set_title": ([pointer, ct.c_char_p], None),
                "gtk_window_present": ([pointer], None), "gtk_window_destroy": ([pointer], None),
                "gtk_widget_grab_focus": ([pointer], ct.c_int),
            },
            self.glib: {
                "g_main_context_iteration": ([pointer, ct.c_int], ct.c_int),
                "g_free": ([pointer], None), "g_error_free": ([pointer], None),
            },
            self.gobject: {
                "g_object_new": ([ct.c_size_t, ct.c_char_p], pointer), "g_object_unref": ([pointer], None),
            },
            self.webkit: {
                "webkit_web_view_get_type": ([], ct.c_size_t),
                "webkit_network_session_new_ephemeral": ([], pointer),
                "webkit_network_session_is_ephemeral": ([pointer], ct.c_int),
                "webkit_web_view_load_uri": ([pointer, ct.c_char_p], None),
                "webkit_web_view_is_loading": ([pointer], ct.c_int),
                "webkit_web_view_set_zoom_level": ([pointer, ct.c_double], None),
                "webkit_web_view_get_zoom_level": ([pointer], ct.c_double),
                "webkit_web_view_evaluate_javascript":
                    ([pointer, ct.c_char_p, ct.c_ssize_t, ct.c_char_p, ct.c_char_p, pointer, READY, pointer], None),
                "webkit_web_view_evaluate_javascript_finish": ([pointer, pointer, ct.POINTER(pointer)], pointer),
            },
            self.jsc: {"jsc_value_to_string": ([pointer], pointer)},
        }
        for library, functions in declarations.items():
            for name, (arguments, result) in functions.items():
                bind(library, name, arguments, result)

    def create_window(self):
        self.gtk.gtk_init()
        session = self.webkit.webkit_network_session_new_ephemeral()
        assert self.webkit.webkit_network_session_is_ephemeral(session)
        self.view = self.gobject.g_object_new(
            self.webkit.webkit_web_view_get_type(), b"network-session", ct.c_void_p(session), ct.c_void_p(),
        )
        self.gobject.g_object_unref(session)
        if not self.view:
            raise RuntimeError("WebKit did not create a native WebView")
        window = self.gtk.gtk_window_new()
        self.gtk.gtk_window_set_decorated(window, False)
        self.gtk.gtk_window_set_default_size(window, 1440, 1000)
        self.gtk.gtk_window_set_title(window, b"Kittyscape native WebKitGTK zoom proof")
        self.gtk.gtk_window_set_child(window, self.view)
        self.gtk.gtk_window_present(window)
        return window

    def pump(self, duration=.02):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            for _ in range(100):
                if not self.glib.g_main_context_iteration(None, False):
                    break
            time.sleep(.002)

    def evaluate(self, expression):
        completed = []

        def finish(_source, result, _data):
            try:
                completed.append((True, self.result(result)))
            except Exception as error:
                completed.append((False, str(error)))

        callback = READY(finish)
        self.callbacks.append(callback)
        script = f"JSON.stringify(({expression}))".encode()
        self.webkit.webkit_web_view_evaluate_javascript(self.view, script, -1, None, None, None, callback, None)
        deadline = time.monotonic() + 10
        while not completed and time.monotonic() < deadline:
            self.pump()
        if not completed:
            raise TimeoutError("WebKit JavaScript evaluation did not complete")
        success, value = completed[0]
        if not success:
            raise RuntimeError(value)
        return value

    def result(self, result):
        error = ct.c_void_p()
        value = self.webkit.webkit_web_view_evaluate_javascript_finish(self.view, result, ct.byref(error))
        if error:
            message = ct.cast(error, ct.POINTER(GError)).contents.message.decode()
            self.glib.g_error_free(error)
            raise RuntimeError(message)
        if not value:
            raise RuntimeError("WebKit returned no JavaScript value")
        text = self.jsc.jsc_value_to_string(value)
        try:
            return json.loads(ct.string_at(text).decode())
        finally:
            self.glib.g_free(text)
            self.gobject.g_object_unref(value)

    def load(self, uri):
        self.webkit.webkit_web_view_load_uri(self.view, uri.encode())
        deadline = time.monotonic() + 15
        while self.webkit.webkit_web_view_is_loading(self.view) and time.monotonic() < deadline:
            self.pump()
        if self.webkit.webkit_web_view_is_loading(self.view):
            raise TimeoutError("Built documentation did not finish loading")
        self.pump(.15)
        assert self.evaluate("document.readyState") == "complete"
        assert self.evaluate("Boolean(document.querySelector('main h1'))")

    def geometry(self):
        attributes = native.WindowAttributes()
        self.x11.XGetWindowAttributes(self.display, self.xwindow, ct.byref(attributes))
        return {"width": attributes.width, "height": attributes.height}

    def metrics(self):
        value = self.evaluate("""({dpr: devicePixelRatio, innerWidth, innerHeight, outerWidth, outerHeight,
            cssZoom: getComputedStyle(document.documentElement).zoom, viewportScale: visualViewport.scale,
            scrollWidth: document.documentElement.scrollWidth, userAgent: navigator.userAgent,
            theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
            heading: document.querySelector('main h1').textContent.trim()})""")
        value["nativeWindow"] = self.geometry()
        value["nativeZoom"] = self.webkit.webkit_web_view_get_zoom_level(self.view)
        return value

    def keys(self, *names):
        native.verify_owner(self.owner)
        self.x11.XRaiseWindow(self.display, self.xwindow)
        self.x11.XSetInputFocus(self.display, self.xwindow, 2, 0)
        native.press(self.x11, self.xtest, self.display, names)
        self.pump(.15)

    def screenshot(self, name):
        native.verify_owner(self.owner)
        attributes = native.WindowAttributes()
        self.x11.XGetWindowAttributes(self.display, self.xwindow, ct.byref(attributes))
        native.screenshot(self.x11, self.display, self.xwindow, attributes, str(self.output / f"{name}.png"))

    def close(self):
        self.gtk.gtk_window_destroy(self.window)
        self.pump(.1)
        self.x11.XCloseDisplay(self.display)


def identity(host):
    version = []
    for part in ("major", "minor", "micro"):
        version.append(bind(host.webkit, f"webkit_get_{part}_version", [], ct.c_uint)())
    paths = [BUNDLE / "lib/libwebkitgtk-6.0.so.4", BUNDLE / "lib/libjavascriptcoregtk-6.0.so.1"]
    return {"webkitGtkVersion": ".".join(map(str, version)), "bundle": str(BUNDLE), "libraries": {
        str(path.resolve()): file_hash(path) for path in paths
    }}


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def keyboard_check(host, uri):
    host.load(uri)
    host.gtk.gtk_widget_grab_focus(host.view)
    host.keys("Tab")
    focus = host.evaluate("({name: document.activeElement.textContent.trim(), outline: getComputedStyle(document.activeElement).outlineStyle})")
    assert "Skip to content" in focus["name"], focus
    assert focus["outline"] != "none", focus
    host.keys("Return")
    assert host.evaluate("location.hash") == "#VPContent"
    host.keys("Tab")
    assert "Read the docs" in host.evaluate("document.activeElement.textContent")
    host.keys("Return")
    deadline = time.monotonic() + 5
    while not host.evaluate("location.pathname.endsWith('/guide/getting-started.html')") and time.monotonic() < deadline:
        host.pump()
    assert host.evaluate("location.pathname.endsWith('/guide/getting-started.html')")
    assert "Getting started" in host.evaluate("document.querySelector('main h1').textContent")
    return {"status": "passed", "skipFocus": focus}


def check_base(host, origin, base):
    label = "root" if base == "/" else "subpath"
    host.webkit.webkit_web_view_set_zoom_level(host.view, 1.0)
    host.load(origin + base)
    baseline = host.metrics()
    host.webkit.webkit_web_view_set_zoom_level(host.view, 2.0)
    host.pump(.25)
    zoomed = host.metrics()
    assert zoomed["nativeZoom"] == 2.0
    assert abs(zoomed["dpr"] / baseline["dpr"] - 2) < .001
    assert abs(baseline["innerWidth"] / zoomed["innerWidth"] - 2) < .005
    assert zoomed["nativeWindow"] == baseline["nativeWindow"]
    assert zoomed["cssZoom"] == baseline["cssZoom"] == "1"
    assert zoomed["viewportScale"] == baseline["viewportScale"] == 1
    routes = []
    for theme in ("light", "dark"):
        host.evaluate(f"(localStorage.setItem('vitepress-theme-appearance', {json.dumps(theme)}), true)")
        for route in ("index.html", "guide/configuration.html", "reference/configuration.html"):
            host.load(origin + base + route)
            metrics = host.metrics()
            assert metrics["nativeZoom"] == 2.0 and abs(metrics["dpr"] / baseline["dpr"] - 2) < .001
            assert metrics["scrollWidth"] <= metrics["innerWidth"] + 1, metrics
            assert metrics["theme"] == theme, metrics
            host.screenshot(f"webkit-native-{label}-{theme}-{route.replace('/', '-').replace('.html', '')}")
            routes.append({"route": route, "theme": theme, **metrics})
    keyboard = keyboard_check(host, origin + base)
    return {"base": base, "baseline": baseline, "zoomed": zoomed, "routes": routes, "keyboard": keyboard, "exact200": True}


def host_main(owner, origin, output):
    host = WebKitHost(owner, output)
    report = {"checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "display": ":103", "rows": []}
    try:
        report.update(identity(host))
        for base in ("/", "/kittyscape/"):
            row = check_base(host, origin, base)
            report["rows"].append(row)
            print(json.dumps({"base": base, "exact200": row["exact200"], "keyboard": row["keyboard"]["status"]}), flush=True)
        report["status"] = "passed"
    except Exception as error:
        report["status"], report["error"] = "failed", str(error)
        raise
    finally:
        host.close()
        (output / "webkit-native-results.json").write_text(json.dumps(report, indent=2) + "\n")


def artifact_hashes():
    return {str(path): file_hash(path)
            for root in ARTIFACTS for path in sorted(root.rglob("*")) if path.is_file()}


def child_environment(output):
    return dict(os.environ, DISPLAY=":103", WAYLAND_DISPLAY="", GDK_BACKEND="x11",
                WEBKIT_EXEC_PATH=str(BUNDLE / "bin"), WEBKIT_INJECTED_BUNDLE_PATH=str(BUNDLE / "lib"),
                LD_LIBRARY_PATH=f"{BUNDLE}/lib:{BUNDLE}/sys/lib:{EXTRA_LIBRARIES}",
                XDG_CACHE_HOME=str(output / "cache"), XDG_CONFIG_HOME=str(output / "config"), XDG_DATA_HOME=str(output / "data"))


def controller():
    for path in ("/tmp/.X103-lock", "/tmp/.X11-unix/X103"):
        if os.path.lexists(path):
            raise RuntimeError(f"Refusing existing display resource: {path}")
    output = Path(tempfile.mkdtemp(prefix="kittyscape-browser-zoom-webkit-native-"))
    before = artifact_hashes()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ArtifactHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    with (output / "xvfb.log").open("xb") as log:
        display = subprocess.Popen(["/tmp/kittyscape-tools/xvfb/usr/bin/Xvfb", ":103", "-screen", "0", "1600x1200x24",
                                    "-dpi", "96", "-nolisten", "tcp"], stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_display(display)
        with (output / "host-stderr.log").open("wb") as errors:
            result = subprocess.run([sys.executable, __file__, "--host", str(display.pid), origin, str(output)],
                                    env=child_environment(output), stderr=errors, timeout=120)
        assert result.returncode == 0, f"Native host failed; see {output}/host-stderr.log"
    finally:
        server.shutdown()
        server.server_close()
        if display.poll() is None:
            display.terminate()
            display.wait(timeout=5)
        record = {"output": str(output), "displayPid": display.pid, "displayExit": display.returncode,
                  "artifactsUnchanged": before == artifact_hashes(),
                  "resourcesRemain": {path: os.path.lexists(path) for path in ("/tmp/.X103-lock", "/tmp/.X11-unix/X103")}}
        (output / "controller.json").write_text(json.dumps(record, indent=2) + "\n")
        (output / "artifact-manifest.json").write_text(json.dumps(before, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    assert record["artifactsUnchanged"], "Built artifacts changed during the native zoom check"
    assert not any(record["resourcesRemain"].values()), "Owned display resources remain after shutdown"


def wait_display(display):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if display.poll() is not None:
            raise RuntimeError("Owned Xvfb exited during startup")
        try:
            native.verify_owner(display.pid)
            time.sleep(.1)
            return
        except FileNotFoundError:
            time.sleep(.02)
        except RuntimeError:
            time.sleep(.02)
    raise TimeoutError("Owned Xvfb did not become ready")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--host":
        host_main(int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
    else:
        controller()
