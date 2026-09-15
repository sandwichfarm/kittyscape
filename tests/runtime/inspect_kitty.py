"""Read actual kitty state inside a disposable graphical test instance."""

import json
import sys
import time

from kittens.tui.handler import result_handler


def main(args):
    pass


@result_handler(no_ui=True)
def handle_result(args, answer, target_window_id, boss):
    from kitty.fast_data_types import get_options, os_window_has_background_image

    opts = get_options()
    window = boss.window_id_map[target_window_id]
    keys = (
        "background_image", "background_image_layout", "background_image_linear",
        "background_tint", "background_tint_gaps", "background_opacity", "background", "foreground",
    )
    result = {key: str(getattr(opts, key)) for key in keys}
    result["watchers"] = list(opts.watcher)
    result["has_image"] = os_window_has_background_image(window.os_window_id)
    result["cwd"] = (window.screen.last_reported_cwd or b"").decode("utf-8", "backslashreplace")
    result["prompt"] = window.at_prompt
    runtime = getattr(boss, "_kittyscape", None)
    if runtime:
        result.update(_runtime_state(runtime, window, args))
    if len(args) > 1 and args[1] == "set":
        boss.set_background_image(args[2] if args[2] != "none" else None, (window.os_window_id,), False, None)
        result["has_image_after"] = os_window_has_background_image(window.os_window_id)
    if len(args) > 1 and args[1] == "arrange":
        _arrange(window.os_window_id, args[2])
    return json.dumps(result)


def _runtime_state(runtime, window, args):
    if len(args) > 1 and args[1] == "arm-idle":
        _arm_idle(runtime)
    return {
        "engine_file": sys.modules[type(runtime).__module__].__file__, "config_path": str(runtime.path),
        "test_timer_count": getattr(runtime, "test_timer_count", None),
        "jobs": {key: {"done": job[0].done(), "running": job[0].running(), "age": time.monotonic() - job[2]}
                 for key, job in runtime.jobs.items()},
        "job_timer": runtime.job_timer, "runtime": runtime.status(),
        "state": {key: getattr(runtime.windows.get(window.os_window_id), key, None)
                  for key in ("request", "generation", "timer", "applied")},
    }


def _arm_idle(runtime):
    original_timer = runtime.kitty.timer
    runtime.test_timer_count = 0

    def counted(*values):
        runtime.test_timer_count += 1
        return original_timer(*values)

    runtime.kitty.timer = counted


def _arrange(os_id, column):
    from kitty.fast_data_types import set_os_window_pos, set_os_window_size, wakeup_main_loop

    width = 960 if column == "single" else 600
    x = 0 if column == "single" else int(column) * 620
    set_os_window_size(os_id, width, 640)
    set_os_window_pos(os_id, x, 0)
    wakeup_main_loop()
