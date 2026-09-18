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
from kittyscape.rules import AnimationOptions, Profile, Rule


class FakeKitty:
    def __init__(self, boss, changed, reloaded):
        self.boss = boss
        self.modern = True
        self.pending = {}
        self.writes = []
        self.counter = 0
        self.overrides = {}
        self.profile_writes = []
        self.scoped = {}
        self.process = None

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

    def focused_os_id(self):
        selected = self.boss.focused or self.boss.last_focused
        return selected if selected in self.boss.os_window_map else 0

    def apply_scoped_profile(self, os_id, profile):
        identity = None if profile is None else profile.identity
        if self.scoped.get(os_id) != identity:
            self.profile_writes.append(("scoped", os_id, identity))
        if identity is None:
            self.scoped.pop(os_id, None)
        else:
            self.scoped[os_id] = identity

    def release_scoped_profile(self, os_id, _restore):
        if os_id in self.scoped:
            self.profile_writes.append(("scoped-release", os_id))
            self.scoped.pop(os_id)

    def release_all_scoped_profiles(self, restore):
        for os_id in list(self.scoped):
            self.release_scoped_profile(os_id, restore)

    def apply_process_profile(self, profile):
        if profile is None or profile.mode != "process":
            return False
        if self.process != profile.identity:
            self.profile_writes.append(("process", profile.identity))
            self.process = profile.identity
        return True

    def release_process_profile(self):
        if self.process is not None:
            self.profile_writes.append(("process-release",))
            self.process = None

    def restore_process_baseline(self):
        self.release_process_profile()

    def abandon_process_profile(self):
        self.process = None

    def adopt_process_baseline(self):
        pass


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "kittyscape.json"
        self.config.write_text(json.dumps({"version": 1, "rules": []}))
        self.boss = SimpleNamespace(active={}, window_id_map={}, os_window_map={}, focused=1, last_focused=1)
        with patch("kittyscape.engine.Kitty", FakeKitty):
            self.runtime = Runtime(self.boss, self.config)
        self.addCleanup(self.runtime.close)
        self.backend = self.runtime.kitty
        self.backend.drain()

    def pane(self, pane_id, os_id=1, directory=None):
        pane = SimpleNamespace(
            id=pane_id, os_window_id=os_id, at_prompt=True, destroyed=False,
            screen=SimpleNamespace(last_reported_cwd=f"kitty-shell-cwd://localhost{directory or self.root}".encode()),
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

    def test_focused_window_arbitrates_process_profile_and_suspends_scoped(self):
        process_dir = self.root / "process"
        scoped_dir = self.root / "scoped"
        process_dir.mkdir()
        scoped_dir.mkdir()
        image = Media((Frame(Image(b"x", "same", 1, 1), 0),), "png", 1)
        process = Profile("process", config="process.conf", commands=("font_size 18",))
        scoped = Profile("scoped", font_size=13)
        self.runtime.config = Config(
            profiles={"process": process, "scoped": scoped},
            rules=(Rule(str(process_dir), "same.png", profile="process"), Rule(str(scoped_dir), "same.png", profile="scoped")),
        )
        self.runtime._image = lambda _path: image
        first = self.pane(1, 1, process_dir)
        second = self.pane(2, 2, scoped_dir)
        self.boss.active.update({1: first, 2: second})
        self.runtime.event(second)
        self.runtime.event(first)
        self.backend.drain()
        self.assertEqual(self.backend.process, process.identity)
        self.assertEqual(self.backend.scoped, {})
        writes = len(self.backend.profile_writes)
        uploads = len(self.backend.writes)
        self.runtime.event(first)
        self.backend.drain()
        self.assertEqual((len(self.backend.profile_writes), len(self.backend.writes)), (writes, uploads))
        self.boss.focused = self.boss.last_focused = 2
        self.runtime.event(second)
        self.backend.drain()
        self.assertIsNone(self.backend.process)
        self.assertEqual(self.backend.scoped, {2: scoped.identity})

    def test_process_transition_uses_new_profile_without_intermediate_release(self):
        parent = self.root / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        image = Media((Frame(Image(b"x", "same", 1, 1), 0),), "png", 1)
        first_profile = Profile("process", config="one.conf", commands=("font_size 15",))
        second_profile = Profile("process", config="two.conf", commands=("font_size 19",))
        self.runtime.config = Config(
            profiles={"one": first_profile, "two": second_profile},
            rules=(Rule(str(parent), "same.png", profile="one"), Rule(str(child), "same.png", profile="two")),
        )
        self.runtime._image = lambda _path: image
        pane = self.pane(1, 1, parent)
        self.boss.active[1] = pane
        self.runtime.event(pane)
        self.backend.drain()
        uploads = len(self.backend.writes)
        pane.screen.last_reported_cwd = f"kitty-shell-cwd://localhost{child}".encode()
        self.runtime.event(pane)
        self.backend.drain()
        process_writes = [entry for entry in self.backend.profile_writes if entry[0].startswith("process")]
        self.assertEqual(process_writes, [("process", first_profile.identity), ("process", second_profile.identity)])
        self.assertEqual(len(self.backend.writes), uploads, "profile-only change must not upload the same image")

    def test_process_profile_survives_focus_loss_then_releases_when_controller_closes(self):
        image = Media((Frame(Image(b"x", "same", 1, 1), 0),), "png", 1)
        profile = Profile("process", config="one.conf", commands=("font_size 15",))
        self.runtime.config = Config(
            profiles={"one": profile}, rules=(Rule(str(self.root), "same.png", profile="one"),),
        )
        self.runtime._image = lambda _path: image
        pane = self.pane(1)
        self.boss.active[1] = pane
        self.runtime.event(pane)
        self.backend.drain()
        self.boss.focused = 0
        self.runtime._reconcile_profiles()
        self.assertEqual(self.backend.process, profile.identity)
        self.boss.os_window_map.clear()
        self.runtime._prune()
        self.assertIsNone(self.backend.process)

    def test_unchanged_scoped_selection_does_not_reapply_profile(self):
        image = Media((Frame(Image(b"x", "same", 1, 1), 0),), "png", 1)
        profile = Profile("scoped", font_size=15)
        self.runtime.config = Config(
            profiles={"one": profile}, rules=(Rule(str(self.root), "same.png", profile="one"),),
        )
        self.runtime._image = lambda _path: image
        pane = self.pane(1)
        self.boss.active[1] = pane
        with patch.object(self.backend, "apply_scoped_profile", wraps=self.backend.apply_scoped_profile) as applied:
            self.runtime.event(pane)
            self.backend.drain()
            calls = applied.call_count
            self.runtime.event(pane)
            self.backend.drain()
            self.assertEqual(applied.call_count, calls)

    def test_failed_process_profile_is_not_retried_until_reload(self):
        image = Media((Frame(Image(b"x", "same", 1, 1), 0),), "png", 1)
        profile = Profile("process", config="one.conf", commands=("font_size bad",))
        config = Config(profiles={"one": profile}, rules=(Rule(str(self.root), "same.png", profile="one"),))
        self.runtime.config = config
        self.runtime._image = lambda _path: image
        pane = self.pane(1)
        self.boss.active[1] = pane
        with patch.object(self.backend, "apply_process_profile", side_effect=RuntimeError) as applied:
            self.runtime.event(pane)
            self.backend.drain()
            self.runtime.event(pane)
            self.backend.drain()
            self.assertEqual(applied.call_count, 1)
            self.runtime._loaded(config, None)
            self.backend.drain()
            self.assertEqual(applied.call_count, 2)

    def test_pause_reports_scoped_restore_failure_without_escaping(self):
        pane = self.pane(1)
        self.boss.active[1] = pane
        self.runtime.event(pane)
        self.backend.drain()
        with patch.object(self.backend, "release_all_scoped_profiles", side_effect=RuntimeError("restore")):
            status = self.runtime.action("pause")
        self.assertEqual(status["reason"], "profile-restore-failed")
        self.assertTrue(self.runtime.windows[1].paused)


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

    def test_process_profile_reloads_base_then_overlay(self):
        backend = object.__new__(Kitty)
        backend._process_profile = None
        backend._process_expected = {}
        backend._process_font_expected = {}
        backend._process_font_baselines = {}
        backend._base_process_values = {"font_size": 11}
        backend.boss = SimpleNamespace(os_window_map={}, all_tab_managers=[])
        profile = Profile("process", config="talk.conf", commands=("font_size 18",))
        with patch.object(backend, "_profile_values", return_value={"font_size": 18}), patch.object(
            backend, "_apply_process_values",
        ) as applied, patch.object(backend, "_restored_process_values", return_value={"font_size": 11}):
            self.assertTrue(backend.apply_process_profile(profile))
            backend.release_process_profile()
        self.assertEqual(applied.call_args_list, [(({"font_size": 18},), {}), (({"font_size": 11},), {"restore": True})])

    def test_process_restore_preserves_external_os_window_font(self):
        backend = object.__new__(Kitty)
        backend._process_font_expected = {7: 18}
        backend._process_font_baselines = {7: 11}
        backend._base_process_values = {"font_size": 11}
        backend._font_size = lambda _os_id: 17
        backend.boss = SimpleNamespace(os_window_map={7: object()})
        self.assertEqual(backend._process_font_changes(11, True), {})

    def test_failed_process_apply_retains_marker_for_restore_retry(self):
        backend = object.__new__(Kitty)
        backend._process_profile = None
        backend._process_expected = {}
        backend._process_font_expected = {}
        backend._process_font_baselines = {}
        backend.boss = SimpleNamespace(os_window_map={})
        profile = Profile("process", commands=("font_size 18",))
        with patch.object(backend, "_profile_values", return_value={"font_size": 18}), patch.object(
            backend, "_apply_process_values", side_effect=RuntimeError("apply"),
        ):
            with self.assertRaises(RuntimeError):
                backend.apply_process_profile(profile)
        self.assertEqual(backend._process_profile, profile.identity)

    def test_process_transition_adopts_external_font_as_new_restore_baseline(self):
        backend = object.__new__(Kitty)
        first = Profile("process", commands=("font_size 18",), name="first")
        second = Profile("process", commands=("font_size 20",), name="second")
        backend._process_profile = first.identity
        backend._process_expected = {"font_size": 18}
        backend._process_font_expected = {7: 18}
        backend._process_font_baselines = {7: 11}
        backend._base_process_values = {"font_size": 11}
        font = [17]
        backend._font_size = lambda _os_id: font[0]
        backend.options = lambda: SimpleNamespace(font_size=18)
        backend.boss = SimpleNamespace(os_window_map={7: object()})
        def apply(values):
            font[0] = values["font_size"]
        with patch.object(backend, "_profile_values", return_value={"font_size": 20}), patch.object(
            backend, "_apply_process_values", side_effect=apply,
        ):
            backend.apply_process_profile(second)
        self.assertEqual(backend._process_font_baselines, {7: 17})
        self.assertEqual(backend._process_font_changes(11, True), {7: 17})

    def test_process_transition_adopts_untracked_new_window_external_font(self):
        backend = object.__new__(Kitty)
        first = Profile("process", commands=("font_size 18",), name="first")
        second = Profile("process", commands=("font_size 20",), name="second")
        backend._process_profile = first.identity
        backend._process_expected = {"font_size": 18}
        backend._process_font_expected = {1: 18}
        backend._process_font_baselines = {1: 11}
        backend._base_process_values = {"font_size": 11}
        fonts = {1: 18, 2: 17}
        backend._font_size = fonts.__getitem__
        backend.options = lambda: SimpleNamespace(font_size=18)
        backend.boss = SimpleNamespace(os_window_map={1: object(), 2: object()})
        def apply(values):
            fonts.update({os_id: values["font_size"] for os_id in fonts})
        with patch.object(backend, "_profile_values", return_value={"font_size": 20}), patch.object(
            backend, "_apply_process_values", side_effect=apply,
        ):
            backend.apply_process_profile(second)
        self.assertEqual(backend._process_font_baselines, {1: 11, 2: 17})
        self.assertEqual(backend._process_font_changes(11, True), {1: 11, 2: 17})

    def test_unchanged_process_profile_does_not_overwrite_new_window_external_font(self):
        backend = object.__new__(Kitty)
        profile = Profile("process", commands=("font_size 18",))
        backend._process_profile = profile.identity
        backend._process_expected = {"font_size": 18}
        backend._process_font_expected = {1: 18}
        backend._process_font_baselines = {1: 11}
        backend._base_process_values = {"font_size": 11}
        backend._font_size = lambda os_id: {1: 18, 2: 17}[os_id]
        backend.boss = SimpleNamespace(os_window_map={1: object(), 2: object()}, _change_font_size=Mock())
        backend.apply_process_profile(profile)
        backend.boss._change_font_size.assert_not_called()
        self.assertEqual(backend._process_font_baselines, {1: 11, 2: 17})

    def test_scoped_profile_restores_live_font_and_padding(self):
        backend = object.__new__(Kitty)
        edges = SimpleNamespace(left=1.0, top=2.0, right=3.0, bottom=4.0)
        margin = SimpleNamespace(left=0.0, top=0.0, right=0.0, bottom=0.0)
        def patch_edge(which, edge, value):
            setattr(getattr(window, which), edge, value)
        window = SimpleNamespace(id=3, os_window_id=7, padding=edges, margin=margin, patch_edge_width=Mock(side_effect=patch_edge))
        backend._font_owners = {}
        backend._edge_owners = {}
        font = [11.0]
        backend._font_size = Mock(side_effect=lambda _os_id: font[0])
        backend.active = Mock(return_value=window)
        def change_font(values):
            font[0] = values[7]
        backend.boss = SimpleNamespace(_change_font_size=Mock(side_effect=change_font), window_id_map={3: window})
        profile = Profile("scoped", font_size=15.0, padding=8)
        backend.apply_scoped_profile(7, profile)
        backend.release_scoped_profile(7, True)
        self.assertEqual(backend.boss._change_font_size.call_args_list, [(({7: 15.0},), {}), (({7: 11.0},), {})])
        self.assertEqual(window.patch_edge_width.call_count, 8)

    def test_scoped_restore_does_not_overwrite_external_values(self):
        backend = object.__new__(Kitty)
        padding = SimpleNamespace(left=1.0, top=1.0, right=1.0, bottom=1.0)
        margin = SimpleNamespace(left=0.0, top=0.0, right=0.0, bottom=0.0)
        window = SimpleNamespace(id=3, os_window_id=7, padding=padding, margin=margin)
        window.patch_edge_width = lambda which, edge, value: setattr(getattr(window, which), edge, value)
        backend._font_owners, backend._edge_owners = {}, {}
        font = [11.0]
        backend._font_size = lambda _os_id: font[0]
        backend.active = lambda _os_id: window
        backend.boss = SimpleNamespace(_change_font_size=lambda values: font.__setitem__(0, values[7]), window_id_map={3: window})
        backend.apply_scoped_profile(7, Profile("scoped", font_size=15, padding=8))
        font[0] = 17.0
        padding.left = 9.0
        backend.release_scoped_profile(7, True)
        self.assertEqual(font[0], 17.0)
        self.assertEqual(padding.left, 9.0)
        self.assertEqual((padding.top, padding.right, padding.bottom), (1.0, 1.0, 1.0))

    def test_failed_scoped_restore_keeps_ownership_for_retry(self):
        backend = object.__new__(Kitty)
        backend._font_owners, backend._edge_owners = {}, {}
        font = [11.0]
        backend._font_size = lambda _os_id: font[0]
        backend.active = lambda _os_id: None
        def change(values):
            if values[7] == 11.0:
                raise RuntimeError("restore")
            font[0] = values[7]
        backend.boss = SimpleNamespace(_change_font_size=change, window_id_map={})
        backend.apply_scoped_profile(7, Profile("scoped", font_size=15))
        with self.assertRaises(RuntimeError):
            backend.release_scoped_profile(7, True)
        self.assertEqual(backend._font_owners[7], (11.0, 15))

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
                              current_focused_os_window_id=lambda: 0, last_focused_os_window_id=lambda: 0,
                              os_window_font_size=lambda _os_id: 12.0,
                              get_options=lambda: SimpleNamespace(
                                  font_size=12.0, window_padding_width=(), window_margin_width=(),
                              ), wakeup_main_loop=lambda: None)
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
