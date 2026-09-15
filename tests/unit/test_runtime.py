"""State regressions run the real engine with a bounded fake kitty event loop."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from kittyscape.compat import Background, Kitty, local_directory
from kittyscape.config import Config
from kittyscape.engine import Runtime, _timeline_frame
from kittyscape.images import Image
from kittyscape.media import Frame, Media
from kittyscape.rules import AnimationOptions, Rule


class FakeKitty:
    def __init__(self, boss, changed, reloaded):
        self.boss = boss
        self.modern = True
        self.pending = {}
        self.writes = []
        self.counter = 0
        self.overrides = {}

    def timer(self, callback, delay, repeat):
        self.counter += 1
        due = time.monotonic() + delay

        def ready(timer):
            with patch("kittyscape.engine.time.monotonic", return_value=max(due, time.monotonic())):
                callback(timer)

        self.pending[self.counter] = ready
        return self.counter

    def remove_timer(self, timer):
        self.pending.pop(timer, None)

    def drain(self):
        deadline = time.monotonic() + 3
        while self.pending and time.monotonic() < deadline:
            timer, callback = self.pending.popitem()
            callback(timer)
            time.sleep(0.001)
        assert not self.pending, "event loop did not become idle"

    def capability_error(self):
        return ""

    def shell_error(self, window):
        return ""

    def active(self, os_id):
        return self.boss.active.get(os_id)

    def baseline(self, os_id):
        return self.overrides.get(os_id, Background())

    def inherited(self):
        return Background()

    def apply(self, os_id, spec, *, restore=False):
        self.writes.append((os_id, spec, restore))

    def acquire_linear(self, _os_id, _value):
        pass

    def release_linear(self, _os_id):
        pass


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "kittyscape.json"
        self.config.write_text(json.dumps({"version": 1, "rules": []}))
        self.boss = SimpleNamespace(active={}, window_id_map={}, os_window_map={})
        with patch("kittyscape.engine.Kitty", FakeKitty):
            self.runtime = Runtime(self.boss, self.config)
        self.addCleanup(self.runtime.close)
        self.backend = self.runtime.kitty
        self.backend.drain()

    def pane(self, pane_id, os_id=1):
        pane = SimpleNamespace(
            id=pane_id, os_window_id=os_id, at_prompt=True, destroyed=False,
            screen=SimpleNamespace(last_reported_cwd=f"kitty-shell-cwd://localhost{self.root}".encode()),
        )
        self.boss.window_id_map[pane_id] = pane
        self.boss.os_window_map[os_id] = object()
        return pane

    def test_inactive_pane_never_controls_os_window(self):
        active, inactive = self.pane(1), self.pane(2)
        self.boss.active[1] = active
        self.runtime.event(inactive)
        self.backend.drain()
        self.assertFalse(self.backend.writes)

    def test_focus_race_discards_previous_selection(self):
        first, second = self.pane(1), self.pane(2)
        self.boss.active[1] = first
        self.runtime.event(first)
        self.boss.active[1] = second
        self.runtime.event(second)
        self.backend.drain()
        self.assertEqual(self.runtime.windows[1].pane, second.id)

    def test_burst_uses_one_native_timer_and_reads_latest_pane(self):
        first, second = self.pane(1), self.pane(2)
        before = self.backend.counter
        for index in range(500):
            pane = first if index % 2 == 0 else second
            self.boss.active[1] = pane
            self.runtime.event(pane)
        self.assertEqual(self.backend.counter - before, 1)
        self.backend.drain()
        self.assertEqual(self.runtime.windows[1].pane, second.id)

    def test_late_event_waits_for_quiet_before_reading_initial_report(self):
        pane = self.pane(1)
        pane.at_prompt = False
        pane.screen.last_reported_cwd = b""
        self.boss.active[1] = pane
        with patch("kittyscape.engine.time.monotonic", return_value=0) as clock, patch.object(
            self.runtime, "_select_for_window",
        ) as selected:
            self.runtime.event(pane)
            timer = self.runtime.windows[1].timer
            clock.return_value = 0.015
            self.runtime.event(pane)
            clock.return_value = 0.020
            self.backend.pending.pop(timer)(timer)
            selected.assert_not_called()
            pane.at_prompt = True
            pane.screen.last_reported_cwd = f"kitty-shell-cwd://localhost{self.root}".encode()
            clock.return_value = 0.035
            timer = self.runtime.windows[1].timer
            self.backend.pending.pop(timer)(timer)
            selected.assert_called_once()
            self.assertEqual(self.runtime.reports[1][0], str(self.root))

    def test_external_writer_pauses_and_restore_does_not_overwrite_it(self):
        pane = self.pane(1)
        self.boss.active[1] = pane
        self.runtime.event(pane)
        self.backend.drain()
        self.runtime.external(1, Background(kind="override"))
        self.runtime.action("restore")
        self.runtime.event(pane)
        self.backend.drain()
        self.assertTrue(self.runtime.windows[1].paused)
        self.assertFalse(self.backend.writes)

    def test_bad_reload_keeps_last_valid_config(self):
        original = self.runtime.config
        self.config.write_text('{"version":99}')
        self.runtime.action("reload")
        self.backend.drain()
        self.assertIs(self.runtime.config, original)
        self.assertIn("config", self.runtime.reason)

    def test_pause_cancels_pending_directory_callback(self):
        pane = self.pane(1)
        self.boss.active[1] = pane
        self.runtime.event(pane)
        self.runtime.action("pause")
        self.backend.drain()
        self.assertEqual(self.runtime.status()["pending_events"], 0)

    def test_finite_animated_media_stops_its_single_window_timer(self):
        image = Image(b"frame", "digest", 1, 1)
        media = Media((Frame(image, 100), Frame(Image(b"next", "next", 1, 1), 100)), "gif", 1)
        self.runtime.config = Config(rules=(Rule(str(self.root), "animated.gif"),),
                                     animation=AnimationOptions(True, 60, 1.0, "source"))
        self.runtime._image = lambda _path: media
        pane = self.pane(1)
        self.boss.active[1] = pane
        self.runtime.event(pane)
        self.backend.drain()
        state = self.runtime.windows[1]
        self.assertEqual(state.playback, "completed")
        self.assertEqual(state.playback_timer, 0)
        self.assertEqual(state.uploads, 2)

    def test_playback_timeline_skips_frames_without_stretching_source_time(self):
        image = Image(b"first", "first", 1, 1)
        media = Media((Frame(image, 10), Frame(Image(b"second", "second", 1, 1), 10),
                       Frame(Image(b"third", "third", 1, 1), 10)), "gif", None)
        animation = AnimationOptions(True, 24, 1.0, "source")
        self.assertEqual(_timeline_frame(media, animation, 0.025), (2, 0))

    def test_report_native_metacharacters_and_remote_locality(self):
        self.assertEqual(local_directory(b"kitty-shell-cwd://localhost/tmp/a#b?c%20"), "/tmp/a#b?c%20")
        self.assertEqual(local_directory("file://localhost/tmp/a%20b"), "/tmp/a b")
        with self.assertRaises(ValueError):
            local_directory("file://remote.invalid/tmp/a")


class CompatibilityTests(unittest.TestCase):
    def test_background_restore_refreshes_only_its_os_window(self):
        backend = object.__new__(Kitty)
        backend.modern = True
        backend.original_set, backend.wake = Mock(), Mock()
        backend.options = lambda: SimpleNamespace(dynamic_background_opacity=True)
        windows = {key: SimpleNamespace(destroyed=False, refresh=Mock()) for key in (1, 2)}
        backend.boss = SimpleNamespace(os_window_map={
            key: SimpleNamespace(active_tab=SimpleNamespace(active_window=window)) for key, window in windows.items()
        })
        backend.apply(1, Background(), restore=True)
        backend.original_set.assert_called_once_with(None, (1,), False, None, global_index=0)
        windows[1].refresh.assert_called_once_with()
        windows[2].refresh.assert_not_called()

    def test_dynamic_opacity_uses_only_the_target_os_window(self):
        backend = object.__new__(Kitty)
        backend.modern = True
        backend.original_set, backend.wake = Mock(), Mock()
        backend.options = lambda: SimpleNamespace(dynamic_background_opacity=True)
        backend.boss = SimpleNamespace(_set_os_window_background_opacity=Mock(), os_window_map={})
        backend.apply(7, Background(opacity=0.5))
        backend.boss._set_os_window_background_opacity.assert_called_once_with(7, 0.5)

    def test_global_linear_layer_restores_after_the_last_owner(self):
        backend = object.__new__(Kitty)
        backend.original_set = Mock()
        backend.options = lambda: SimpleNamespace(background_image_linear=False)
        backend._linear_owners, backend._linear_baseline = set(), None
        backend.internal = False
        backend.acquire_linear(1, True)
        backend.acquire_linear(2, True)
        backend.release_linear(1)
        backend.release_linear(2)
        self.assertEqual(backend.original_set.call_args_list, [
            ((None, (), True, None, b""), {"linear_interpolation": True}),
            ((None, (), True, None, b""), {"linear_interpolation": False}),
        ])

    def test_cancelled_timer_in_native_dispatch_batch_never_runs_user_callback(self):
        native, observed = {}, []

        def add(callback, delay, repeats):
            timer = len(native) + 1
            native[timer] = callback
            return timer

        class Boss:
            window_id_map = {}

            def set_background_image(self, *args):
                pass

            def apply_new_options(self, *args):
                pass

        api = SimpleNamespace(add_timer=add, remove_timer=lambda timer: native.pop(timer),
                              background_opacity_of=lambda _os_id: None,
                              get_options=lambda: None, wakeup_main_loop=lambda: None)
        with patch.dict("sys.modules", {"kitty.fast_data_types": api}):
            backend = Kitty(Boss(), lambda *args: None, lambda *args: None)
        first = backend.timer(lambda timer: backend.remove_timer(second), 0.1, False)
        second = backend.timer(lambda timer: observed.append("cancelled"), 0.1, False)
        # Kitty snapshots callback pointers before any due timer executes.
        batch = list(native.items())
        for timer, callback in batch:
            callback(timer)
        self.assertEqual(observed, [])
        self.assertEqual(set(native), {first, second}, "Native removal invalidates pointers in the dispatch batch")


if __name__ == "__main__":
    unittest.main()
