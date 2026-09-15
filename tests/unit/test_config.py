"""Strict, data-only configuration and privacy-safe error contracts."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from kittyscape.config import Config, ConfigError, load_config
from kittyscape.rules import AnimationOptions, BackgroundOptions, Rule


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kittyscape-config-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.config_dir = self.root / "custom config"
        self.config_dir.mkdir()
        self.path = self.config_dir / "kittyscape.json"

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return self.path

    def document(self, **overrides):
        return {"version": 1, "rules": [{"directory": str(self.project), "image": "images/cat.png"}], **overrides}

    def assert_invalid(self, data, location):
        self.write(data)
        with self.assertRaises(ConfigError) as raised:
            load_config(self.path)
        self.assertIn(location, str(raised.exception))
        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertNotIn("images/cat.png", str(raised.exception))

    def test_defaults_and_data_are_immutable(self):
        config = load_config(self.write({"version": 1}))
        self.assertEqual(config, Config())
        self.assertIsInstance(config.rules, tuple)
        with self.assertRaises(FrozenInstanceError):
            config.enabled = False
        rule = Rule(str(self.project), "image.png")
        with self.assertRaises(FrozenInstanceError):
            rule.image = "changed.png"

    def test_images_are_resolved_beside_the_selected_config(self):
        config = load_config(self.write(self.document(fallback="fallback/default.png")))
        self.assertEqual(config.rules, (Rule(str(self.project), str(self.config_dir / "images/cat.png")),))
        self.assertEqual(config.fallback, str(self.config_dir / "fallback/default.png"))
        self.assertFalse(Path(config.rules[0].image).exists())

    def test_symlinked_config_uses_the_selected_configuration_directory(self):
        source_dir = self.root / "shared"
        source_dir.mkdir()
        source = source_dir / "shared.json"
        source.write_text(json.dumps(self.document()), encoding="utf-8")
        self.path.symlink_to(source)
        self.assertEqual(load_config(self.path).rules[0].image, str(self.config_dir / "images/cat.png"))

    def test_directory_roots_use_physical_normalized_paths(self):
        child = self.project / "child"
        child.mkdir()
        link = self.root / "linked"
        link.symlink_to(self.project, target_is_directory=True)
        data = {"version": 1, "rules": [{"directory": str(link / "child/.."), "image": "cat.png"}]}
        self.assertEqual(load_config(self.write(data)).rules[0].directory, str(self.project))

    def test_duplicate_normalized_or_symlink_roots_are_rejected(self):
        link = self.root / "linked"
        link.symlink_to(self.project, target_is_directory=True)
        for alias in (str(self.project) + "/./", str(link)):
            rules = [{"directory": str(self.project), "image": "first.png"}, {"directory": alias, "image": "second.png"}]
            with self.subTest(alias=alias):
                self.assert_invalid({"version": 1, "rules": rules}, "rules[1].directory")

    def test_case_only_roots_follow_the_actual_filesystem(self):
        upper = self.root / "MixedCase"
        upper.mkdir()
        lower = self.root / "mixedcase"
        aliases = lower.exists() and os.path.samefile(upper, lower)
        if not aliases:
            lower.mkdir()
        rules = [{"directory": str(upper), "image": "upper.png"}, {"directory": str(lower), "image": "lower.png"}]
        if aliases:
            self.assert_invalid({"version": 1, "rules": rules}, "rules[1].directory")
        else:
            self.assertEqual(len(load_config(self.write({"version": 1, "rules": rules})).rules), 2)

    def test_home_shortcut_is_supported_without_environment_interpolation(self):
        config = load_config(self.write(self.document(fallback="~/cat.png")))
        self.assertEqual(config.fallback, str(Path.home() / "cat.png"))
        config = load_config(self.write(self.document(fallback="$HOME/cat.png")))
        self.assertEqual(config.fallback, str(self.config_dir / "$HOME/cat.png"))

    def test_missing_required_version_and_invalid_versions_are_rejected(self):
        self.assert_invalid({}, "version")
        for value in (0, 2, True, False, 1.0, "1", None, [], {}):
            with self.subTest(value=value):
                self.assert_invalid(self.document(version=value), "version")

    def test_unknown_fields_never_echo_user_supplied_keys(self):
        private_key = "/private/person/project"
        self.assert_invalid(self.document(**{private_key: 1}), "config")
        with self.assertRaises(ConfigError) as raised:
            load_config(self.path)
        self.assertNotIn(private_key, str(raised.exception))
        rule = {"directory": str(self.project), "image": "cat.png", private_key: True}
        self.assert_invalid({"version": 1, "rules": [rule]}, "rules[0]")

    def test_enabled_requires_a_boolean(self):
        self.assertFalse(load_config(self.write(self.document(enabled=False))).enabled)
        for value in (0, 1, "true", None, [], {}):
            with self.subTest(value=value):
                self.assert_invalid(self.document(enabled=value), "enabled")

    def test_additive_background_animation_and_validation_fields_are_strict(self):
        config = load_config(self.write(self.document(
            validate_bytes=False,
            background={"layout": "scaled", "linear": True, "opacity": 0.5},
            animation={"enabled": False, "fps_limit": 12, "speed": 1.5, "loop": 2},
        )))
        self.assertFalse(config.validate_bytes)
        self.assertEqual(config.background, BackgroundOptions("scaled", True, None, None, 0.5))
        self.assertEqual(config.animation, AnimationOptions(False, 12, 1.5, 2))
        for value in (None, 0, 1, "false", []):
            with self.subTest(value=value):
                self.assert_invalid(self.document(validate_bytes=value), "validate_bytes")
        invalid = (
            ("background", {"layout": "stretch"}),
            ("animation", {"enabled": 1}), ("animation", {"fps_limit": True}),
            ("animation", {"fps_limit": 61}), ("animation", {"speed": 0.01}),
            ("animation", {"loop": 0}), ("animation", {"loop": True}),
        )
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                self.assert_invalid(self.document(**{field: value}), field)
        self.assert_invalid(self.document(background={"tint": float("nan")}), "config")

    def test_rule_options_inherit_without_per_rule_validation(self):
        config = load_config(self.write(self.document(
            background={"layout": "scaled"}, animation={"fps_limit": 20},
            rules=[{"directory": str(self.project), "image": "cat.png",
                    "background": {"layout": "centered"}, "animation": {"speed": 2.0}}],
        )))
        rule = config.rules[0]
        self.assertEqual(rule.background, BackgroundOptions(layout="centered"))
        self.assertEqual(rule.animation, AnimationOptions(speed=2.0))
        self.assert_invalid(self.document(rules=[{"directory": str(self.project), "image": "cat.png",
                                                   "validate_bytes": False}]), "rules[0]")
        self.assert_invalid(self.document(rules=[{"directory": str(self.project), "image": "cat.png",
                                                   "background": {"tint": 0.2}}]), "rules[0].background")
        self.assert_invalid(self.document(background={"tint": 0.2}), "background")

    def test_top_level_and_rules_require_correct_container_types(self):
        for value in (None, [], "config", 1, True):
            self.assert_invalid(value, "config")
        for value in (None, {}, "rules", 1, True):
            self.assert_invalid(self.document(rules=value), "rules")
        for value in (None, [], "rule", 1, True):
            self.assert_invalid(self.document(rules=[value]), "rules[0]")

    def test_path_fields_reject_invalid_types_and_nul(self):
        for field in ("directory", "image"):
            for value in (None, [], {}, 1, True, "", "bad\0path"):
                with self.subTest(field=field, value=value):
                    rule = {"directory": str(self.project), "image": "cat.png", field: value}
                    self.assert_invalid({"version": 1, "rules": [rule]}, f"rules[0].{field}")
        for value in ([], {}, 1, True, "", "bad\0path"):
            self.assert_invalid(self.document(fallback=value), "fallback")

    def test_missing_rule_fields_are_rejected(self):
        self.assert_invalid(self.document(rules=[{"image": "cat.png"}]), "rules[0].directory")
        self.assert_invalid(self.document(rules=[{"directory": str(self.project)}]), "rules[0].image")

    def test_relative_and_missing_directory_roots_are_rejected(self):
        for directory in ("relative", "~someone/project", "$HOME/project", str(self.root / "missing")):
            self.assert_invalid(self.document(rules=[{"directory": directory, "image": "cat.png"}]), "rules[0].directory")

    def test_remote_images_are_rejected(self):
        for image in ("https://example.invalid/cat.png", "file:///private/cat.png", "ssh://host/cat.png"):
            self.assert_invalid(self.document(rules=[{"directory": str(self.project), "image": image}]), "rules[0].image")
            self.assert_invalid(self.document(fallback=image), "fallback")

    def test_config_size_is_bounded_by_bytes(self):
        valid = b'{"version": 1}'
        self.path.write_bytes(valid + b" " * (1024 * 1024 - len(valid)))
        self.assertEqual(load_config(self.path), Config())
        with self.path.open("ab") as stream:
            stream.write(b" ")
        with self.assertRaisesRegex(ConfigError, "config.*1 MiB"):
            load_config(self.path)

    def test_config_has_a_rule_count_limit(self):
        rule = {"directory": str(self.project), "image": "cat.png"}
        self.assert_invalid({"version": 1, "rules": [rule] * 10001}, "rules")

    def test_invalid_json_duplicate_keys_and_nonfinite_numbers_are_rejected(self):
        documents = (b"\xff", b"{", b'{"version": 1, "version": 1}', b'{"version": 1, "enabled": NaN}')
        for document in documents:
            with self.subTest(document=document):
                self.path.write_bytes(document)
                with self.assertRaises(ConfigError):
                    load_config(self.path)
        self.path.write_text('[' * 1500 + ']' * 1500, encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(self.path)

    def test_large_json_integer_is_reported_as_a_config_error(self):
        self.path.write_text('{"version": ' + '9' * 5000 + '}', encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(self.path)

    def test_config_filename_must_be_a_text_path(self):
        self.write(self.document())
        for value in (None, 1, os.fsencode(self.path), "bad\0path"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_config(value)

    def test_missing_and_unreadable_config_errors_do_not_disclose_paths(self):
        with self.assertRaises(ConfigError) as missing:
            load_config(self.path)
        self.assertNotIn(str(self.path), str(missing.exception))
        self.write(self.document())
        with patch("kittyscape.config.os.open", side_effect=PermissionError(str(self.path))):
            with self.assertRaises(ConfigError) as unreadable:
                load_config(self.path)
        self.assertNotIn(str(self.path), str(unreadable.exception))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires a POSIX named pipe")
    def test_nonregular_config_is_rejected_without_waiting_for_a_writer(self):
        os.mkfifo(self.path)
        with self.assertRaises(ConfigError):
            load_config(self.path)


if __name__ == "__main__":
    unittest.main()
