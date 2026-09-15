"""Disposable kitty watcher used to measure native event ordering.

Only use with KITTYSCAPE_PROBE_LOG in a temporary, private configuration.
These logs deliberately include fixture directories and are not product logging.
"""

import json
import os
import sys
import time

from kitty.fast_data_types import add_timer


def sample(boss, window, event, delay=0):
    """Record the actual shell report, independent of process cwd lookup."""
    if window.destroyed:
        return
    manager = boss.os_window_map.get(window.os_window_id)
    active = manager.active_tab.active_window if manager and manager.active_tab else None
    row = {
        "event": event,
        "delay": delay,
        "time": time.monotonic(),
        "pane": window.id,
        "os_window": window.os_window_id,
        "active": active.id if active else None,
        "prompt": window.at_prompt,
        "cwd": (window.screen.last_reported_cwd or b"").decode("utf-8", "backslashreplace"),
    }
    with open(os.environ["KITTYSCAPE_PROBE_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")


def event(boss, window, name):
    sample(boss, window, name)
    for delay in (0, 0.02, 0.08):
        add_timer(lambda _, delay=delay: sample(boss, window, name, delay), delay, False)


def on_load(boss, data):
    with open(os.environ["KITTYSCAPE_PROBE_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps({"load": True, "pid": os.getpid(), "python": sys.version}) + "\n")
    original = boss.set_background_image

    def observed(*args, **kwargs):
        original(*args, **kwargs)
        row = {"background_write": str(args[:4]), "kwargs": str(kwargs.keys()), "time": time.monotonic()}
        with open(os.environ["KITTYSCAPE_PROBE_LOG"], "a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")

    boss.set_background_image = observed


def on_cmd_startstop(boss, window, data):
    event(boss, window, "start" if data["is_start"] else "stop")


def on_focus_change(boss, window, data):
    event(boss, window, "focus")


def on_resize(boss, window, data):
    event(boss, window, "resize")


def on_title_change(boss, window, data):
    event(boss, window, "title")
