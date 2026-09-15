"""Load Kittyscape as a global kitty watcher without changing sys.path."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def on_load(boss, data):
    if getattr(boss, "_kittyscape", None) is not None:
        return
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        _load(boss)
    finally:
        sys.dont_write_bytecode = previous


def _load(boss):
    package = Path(__file__).resolve().parent
    name = "_kittyscape_" + hashlib.sha256(str(package).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, package / "__init__.py", submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    from importlib import import_module
    from kitty.constants import config_dir

    location = package / "location.json"
    config = json.loads(location.read_text())["config"] if location.is_file() else str(Path(config_dir) / "kittyscape.json")
    boss._kittyscape = import_module(name + ".engine").Runtime(boss, Path(config))


def on_resize(boss, window, data):
    _event(boss, window)


def on_title_change(boss, window, data):
    _event(boss, window)


def on_focus_change(boss, window, data):
    _event(boss, window)


def on_tab_bar_dirty(boss, window, data):
    runtime = getattr(boss, "_kittyscape", None)
    if runtime:
        runtime._schedule_all()


def on_cmd_startstop(boss, window, data):
    runtime = getattr(boss, "_kittyscape", None)
    if runtime:
        runtime.event(window, command=data.get("cmdline", ""), starting=data["is_start"])


def on_close(boss, window, data):
    runtime = getattr(boss, "_kittyscape", None)
    if runtime:
        runtime.removed(window)


def _event(boss, window):
    runtime = getattr(boss, "_kittyscape", None)
    if runtime:
        runtime.event(window)
