"""Observable ownership and asynchronous event regressions using the real engine."""

import json
import threading
import time
import unittest
from unittest.mock import patch

import test_images as images
import test_runtime as fixtures
from kittyscape.compat import Background


class RuntimeRegressionTests(unittest.TestCase):
    def setUp(self):
        fixtures.RuntimeTests.setUp(self)

    pane = fixtures.RuntimeTests.pane

    def test_stalled_reader_coalesces_500_events_and_applies_only_latest(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        started, release = threading.Event(), threading.Event()
        original = self.runtime._select

        def blocked(*args):
            started.set()
            self.assertTrue(release.wait(2))
            return original(*args)

        with patch.object(self.runtime, "_select", blocked), patch.object(
            self.runtime.pool, "submit", wraps=self.runtime.pool.submit,
        ) as submitted:
            try:
                self.runtime.event(pane)
                self.fire_update()
                self.assertTrue(started.wait(1))
                pane.screen.last_reported_cwd = f"kitty-shell-cwd://localhost{self.root}".encode()
                for _ in range(500):
                    self.runtime.event(pane)
                    self.fire_update()
                self.assertLessEqual(submitted.call_count, 2)
            finally:
                release.set()
            self.backend.drain()
        self.assertFalse(self.backend.writes)
        self.assertEqual(self.runtime.status()["pending_jobs"], 0)

    def test_timed_out_reader_stops_polling_and_recovers_on_next_event(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        started, release = threading.Event(), threading.Event()
        original = self.runtime._select

        def blocked(*args):
            started.set()
            self.assertTrue(release.wait(2))
            return original(*args)

        with patch.object(self.runtime, "_select", blocked), patch.object(
            self.runtime.pool, "submit", wraps=self.runtime.pool.submit,
        ) as submitted:
            try:
                self.runtime.event(pane)
                self.fire_update()
                self.assertTrue(started.wait(1))
                future = next(iter(self.runtime.jobs.values()))[0]
                with patch("kittyscape.engine.time.monotonic", return_value=time.monotonic() + 6):
                    timer = self.runtime.job_timer
                    self.backend.pending.pop(timer)(timer)
                self.assertFalse(self.backend.pending)
                for _ in range(20):
                    self.runtime.event(pane)
                    self.fire_update()
                self.assertEqual(submitted.call_count, 1)
                self.assertFalse(self.backend.pending)
                self.assertEqual(self.runtime.windows[1].reason, "filesystem-timeout")
            finally:
                release.set()
            future.result(timeout=1)
            self.runtime.event(pane)
            self.backend.drain()
        self.assertTrue(self.runtime.windows[1].owned)
        self.assertEqual(self.runtime.windows[1].reason, "")

    def test_closed_window_work_is_discarded_before_the_reader_runs_it(self):
        directory, _ = self.configure_rule(images.rgb_png())
        first = self.active_pane(directory)
        second = self.pane(2, os_id=2)
        self.boss.active[2] = second
        started, release = threading.Event(), threading.Event()
        observed = []
        original = self.runtime._select

        def blocked(config, cwd, baseline):
            observed.append(cwd)
            started.set()
            self.assertTrue(release.wait(2))
            return original(config, cwd, baseline)

        with patch.object(self.runtime, "_select", blocked):
            try:
                self.runtime.event(first)
                self.fire_update()
                self.assertTrue(started.wait(1))
                self.runtime.event(second)
                timer = self.runtime.windows[2].timer
                self.backend.pending.pop(timer)(timer)
                del self.boss.active[2], self.boss.window_id_map[2], self.boss.os_window_map[2]
                self.runtime.removed(second)
                timer = self.backend.counter
                self.backend.pending.pop(timer)(timer)
            finally:
                release.set()
            self.backend.drain()
        self.assertNotIn(str(self.root), observed)
        self.assertNotIn("2", self.runtime.status()["windows"])

    def test_resume_and_reload_retry_transient_upload_failures(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        for action in ("resume", "reload"):
            with self.subTest(action=action):
                self.runtime.windows.clear()
                with patch.object(self.backend, "apply", side_effect=ValueError("temporary")):
                    self.runtime.event(pane)
                    self.backend.drain()
                self.assertFalse(self.runtime.windows[1].owned)
                self.runtime.action(action)
                self.backend.drain()
                self.assertTrue(self.runtime.windows[1].owned)

    def test_ordinary_reload_preserves_an_absolute_background_index(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        with patch.object(self.backend, "baseline", return_value=Background(index=1)):
            self.runtime.event(pane)
            self.backend.drain()
        self.runtime.options_changed("before")
        self.runtime.options_changed("after")
        self.backend.drain()
        self.runtime.action("pause")
        self.assertEqual(self.backend.writes[-1][1].index, 1)

    def test_restore_failure_stays_visible_and_can_be_retried(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        with patch.object(self.backend, "apply", side_effect=ValueError("temporary")):
            result = self.runtime.action("pause")
        self.assertEqual(result["windows"]["1"]["reason"], "restore-failed")
        self.assertTrue(result["windows"]["1"]["owned"])
        result = self.runtime.action("restore")
        self.assertFalse(result["windows"]["1"]["owned"])
        self.assertEqual(result["windows"]["1"]["reason"], "paused")

    def test_configuration_diagnostic_reports_safe_field_location(self):
        directory = self.root / "private-project"
        directory.mkdir()
        self.config.write_text(json.dumps({"version": 1, "rules": [{"directory": str(directory), "image": 7}]}))
        self.runtime.action("reload")
        self.backend.drain()
        detail = self.runtime.status().get("detail", "")
        self.assertIn("rules[0].image", detail)
        self.assertNotIn(str(self.root), detail)
        self.config.write_text('{"version":1}')
        self.runtime.action("reload")
        self.backend.drain()
        self.assertEqual(self.runtime.status()["detail"], "")

    def test_nonreporting_unsupported_shell_restores_the_previous_pane_image(self):
        directory, _ = self.configure_rule(images.rgb_png())
        first = self.active_pane(directory)
        self.runtime.event(first)
        self.backend.drain()
        other = self.pane(2)
        other.at_prompt = False
        other.screen.last_reported_cwd = None
        self.boss.active[1] = other
        with patch.object(self.backend, "shell_error", return_value="shell-unqualified"):
            self.runtime.event(other)
            self.backend.drain()
        self.assertFalse(self.runtime.windows[1].owned)
        self.assertEqual(self.runtime.windows[1].reason, "shell-unqualified")

    def test_nested_shell_is_paused_until_explicit_resume(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        self.runtime.event(pane, command="bash", starting=True)
        self.backend.drain()
        self.assertFalse(self.runtime.windows[1].owned)
        self.runtime.event(pane)
        self.backend.drain()
        self.assertEqual(self.runtime.windows[1].reason, "context-unsupported")
        self.runtime.action("resume")
        self.backend.drain()
        self.assertTrue(self.runtime.windows[1].owned)

    def test_command_arguments_and_noninteractive_shell_do_not_change_ownership(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        writes = len(self.backend.writes)
        for command in ("echo ssh", "printf tmux", "bash -c 'cd /tmp'"):
            self.runtime.event(pane, command=command, starting=True)
            self.backend.drain()
            self.assertTrue(self.runtime.windows[1].owned, command)
        self.assertEqual(len(self.backend.writes), writes)

    def configure_rule(self, data, *, fallback=None):
        directory = self.root / "app"
        directory.mkdir(exist_ok=True)
        image_path = self.root / "selected.png"
        image_path.write_bytes(data)
        document = {"version": 1, "rules": [{"directory": str(directory), "image": str(image_path)}]}
        if fallback is not None:
            fallback_path = self.root / "fallback.png"
            fallback_path.write_bytes(fallback)
            document["fallback"] = str(fallback_path)
        self.config.write_text(json.dumps(document))
        self.runtime.reload()
        self.backend.drain()
        return directory, image_path

    def active_pane(self, directory, pane_id=1):
        pane = self.pane(pane_id)
        pane.screen.last_reported_cwd = f"kitty-shell-cwd://localhost{directory}".encode()
        self.boss.active[1] = pane
        return pane

    def fire_update(self):
        while timer := self.runtime.windows[1].timer:
            self.backend.pending.pop(timer)(timer)

    def test_same_directory_event_during_selection_eventually_displays_image(self):
        selected = images.rgb_png()
        directory, _ = self.configure_rule(selected)
        pane = self.active_pane(directory)
        started, release = threading.Event(), threading.Event()
        original = self.runtime._select

        def delayed(*args):
            started.set()
            self.assertTrue(release.wait(2), "fixture worker was not released")
            return original(*args)

        with patch.object(self.runtime, "_select", delayed):
            try:
                self.runtime.event(pane)
                self.fire_update()
                self.assertTrue(started.wait(1), "fixture selection never started")
                self.runtime.event(pane)
                self.fire_update()
            finally:
                release.set()
            self.backend.drain()
        self.assertEqual([spec.data for _, spec, _ in self.backend.writes], [selected])

    def test_late_result_cannot_paint_a_pane_that_lost_focus(self):
        directory, _ = self.configure_rule(images.rgb_png())
        first = self.active_pane(directory)
        second = self.pane(2)
        started, release = threading.Event(), threading.Event()
        original = self.runtime._select

        def delayed(*args):
            started.set()
            self.assertTrue(release.wait(2), "fixture worker was not released")
            return original(*args)

        with patch.object(self.runtime, "_select", delayed):
            try:
                self.runtime.event(first)
                self.fire_update()
                self.assertTrue(started.wait(1), "fixture selection never started")
                self.boss.active[1] = second
            finally:
                release.set()
            self.backend.drain()
        self.assertFalse(self.backend.writes)

    def test_unchanged_events_do_not_upload_the_image_again(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        for _ in range(20):
            self.runtime.event(pane)
            self.backend.drain()
        self.assertEqual(len(self.backend.writes), 1)

    def test_initial_missing_directory_report_preserves_the_existing_background(self):
        directory, _ = self.configure_rule(images.rgb_png(), fallback=images.rgb_png(b"\0\xff\0"))
        pane = self.active_pane(directory)
        pane.screen.last_reported_cwd = None
        self.runtime.event(pane)
        self.backend.drain()
        self.assertFalse(self.backend.writes)

    def test_lost_report_after_valid_directory_selects_fallback(self):
        fallback = images.rgb_png(b"\0\xff\0")
        directory, _ = self.configure_rule(images.rgb_png(), fallback=fallback)
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        pane.screen.last_reported_cwd = None
        self.runtime.event(pane)
        self.backend.drain()
        self.assertEqual(self.backend.writes[-1][1].data, fallback)
        self.assertEqual(self.runtime.status()["windows"]["1"]["reason"], "directory-report-lost")

    def test_invalid_idat_selects_the_explicit_fallback(self):
        corrupt = images.png(images.chunk(b"IHDR", images.HEADER), images.chunk(b"IDAT", b"invalid"), images.chunk(b"IEND", b""))
        fallback = images.rgb_png(b"\0\xff\0")
        directory, _ = self.configure_rule(corrupt, fallback=fallback)
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        self.assertEqual([spec.data for _, spec, _ in self.backend.writes], [fallback])

    def test_unchanged_prompt_keeps_the_image_failure_diagnostic(self):
        directory, _ = self.configure_rule(b"not a PNG", fallback=images.rgb_png())
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        self.assertEqual(self.runtime.status()["windows"]["1"]["reason"], "image-unavailable-or-invalid")
        self.runtime.event(pane)
        self.backend.drain()
        self.assertEqual(self.runtime.status()["windows"]["1"]["reason"], "image-unavailable-or-invalid")

    def test_unchanged_prompt_keeps_the_apply_failure_diagnostic(self):
        directory, _ = self.configure_rule(images.rgb_png())
        pane = self.active_pane(directory)
        with patch.object(self.backend, "apply", side_effect=RuntimeError("fixture upload failed")):
            self.runtime.event(pane)
            self.backend.drain()
        self.assertEqual(self.runtime.status()["windows"]["1"]["reason"], "image-apply-failed")
        self.runtime.event(pane)
        self.backend.drain()
        self.assertEqual(self.runtime.status()["windows"]["1"]["reason"], "image-apply-failed")

    def test_old_runtime_reload_keeps_baseline_bytes_and_updates_rendering(self):
        old, new = images.rgb_png(), images.rgb_png(b"\0\xff\0")
        directory, _ = self.configure_rule(images.rgb_png(b"\0\0\xff"))
        old_path, new_path = self.root / "old.png", self.root / "new.png"
        old_path.write_bytes(old)
        new_path.write_bytes(new)
        self.backend.modern = False
        old_baseline = Background(path=str(old_path), layout="tiled")
        new_baseline = Background(path=str(new_path), layout="scaled")
        with patch.object(self.backend, "baseline", return_value=old_baseline):
            pane = self.active_pane(directory)
            self.runtime.event(pane)
            self.backend.drain()
            self.runtime.options_changed("before")
            with patch.object(self.backend, "inherited", return_value=new_baseline):
                self.runtime.options_changed("after")
                self.backend.drain()
        self.runtime.action("pause")
        _, restored, is_restore = self.backend.writes[-1]
        self.assertTrue(is_restore)
        self.assertEqual(restored.data, old)
        self.assertEqual(restored.layout, "scaled")

    def test_external_override_never_captures_stale_cached_image_bytes(self):
        self.external_override_roundtrip()

    def test_old_runtime_external_override_never_captures_stale_cached_image_bytes(self):
        self.backend.modern = False
        self.external_override_roundtrip()

    def external_override_roundtrip(self):
        first, external = images.rgb_png(), images.rgb_png(b"\0\xff\0")
        directory, image_path = self.configure_rule(first)
        pane = self.active_pane(directory)
        self.runtime.event(pane)
        self.backend.drain()
        image_path.write_bytes(external)
        self.runtime.external(1, Background(kind="override", path=str(image_path)))
        self.runtime.action("resume")
        self.backend.drain()
        self.runtime.action("pause")
        self.assertEqual(self.backend.writes[-1][1].data, external)


if __name__ == "__main__":
    unittest.main()
