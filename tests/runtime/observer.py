"""Minimal test-only evidence observer. Never installed with the extension."""

import functools
import hashlib
import json
import os
import sys
import time


def record(row):
    row["time"] = time.monotonic()
    with open(os.environ["KITTYSCAPE_PROBE_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")


def on_load(boss, data):
    from kitty.constants import version

    record({"event": "load", "pid": os.getpid(), "kitty": list(version), "python": sys.version})
    original = boss.set_background_image

    @functools.wraps(original)
    def observed(*args, **kwargs):
        original(*args, **kwargs)
        raw = args[4] if len(args) > 4 else kwargs.get("png_data", b"")
        record({"event": "image", "os_windows": args[1], "digest": hashlib.sha256(raw).hexdigest(), "configured": args[2]})

    boss.set_background_image = observed


def on_cmd_startstop(boss, window, data):
    record({"event": "command-start" if data["is_start"] else "command-stop", "pane": window.id})
