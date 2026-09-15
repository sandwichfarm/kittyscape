"""Kittyscape controls invoked through kitty key mappings or its kitten action."""

import json

from kittens.tui.handler import result_handler


def main(args):
    raise SystemExit("Run this kitten through a kitty key mapping: kitten /path/to/action.py status")


@result_handler(no_ui=True)
def handle_result(args, answer, target_window_id, boss):
    runtime = getattr(boss, "_kittyscape", None)
    name = args[1] if len(args) > 1 else "status"
    if runtime is None:
        result = {"error": "watcher-not-loaded"}
    else:
        try:
            result = runtime.action(name)
        except ValueError:
            result = {"error": "unknown-action", "actions": ["status", "reload", "pause", "resume", "restore"]}
    text = json.dumps(result, indent=2)
    if "--json" not in args and (name == "status" or "error" in result):
        window = boss.window_id_map.get(target_window_id)
        if window:
            boss.display_scrollback(window, text.encode(), title="Kittyscape status")
    return text
