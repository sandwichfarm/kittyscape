"""Observable directory-selection contracts without kitty or shell dependencies."""

from __future__ import annotations

import os
import random
import tempfile
import unicodedata
import unittest
from pathlib import Path

from kittyscape.config import Config
from kittyscape.rules import Rule, normalize_directory, resolve


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kittyscape-rules-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.app = self.directory("app")
        self.child = self.directory("app/child")
        self.deep = self.directory("app/child/deep")
        self.sibling = self.directory("application")

    def directory(self, name):
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_directory_sequence_selects_deepest_rule_then_fallback(self):
        config = Config(rules=(Rule(str(self.child), "nested.png"), Rule(str(self.app), "app.png")), fallback="default.png")
        observed = [resolve(config, str(path)) for path in (self.app, self.child, self.deep, self.root)]
        self.assertEqual(observed, ["app.png", "nested.png", "nested.png", "default.png"])

    def test_sibling_prefix_is_not_a_directory_match(self):
        config = Config(rules=(Rule(str(self.app), "app.png"),))
        self.assertIsNone(resolve(config, str(self.sibling)))

    def test_root_rule_applies_to_descendants(self):
        config = Config(rules=(Rule(os.path.abspath(os.sep), "root.png"),))
        self.assertEqual(resolve(config, str(self.app)), "root.png")

    def test_rule_order_does_not_change_selection(self):
        rules = (Rule(str(self.root), "root.png"), Rule(str(self.app), "app.png"), Rule(str(self.child), "child.png"))
        self.assertEqual(resolve(Config(rules=rules), str(self.deep)), resolve(Config(rules=tuple(reversed(rules))), str(self.deep)))

    def test_disabled_configuration_restores_instead_of_selecting_fallback(self):
        config = Config(enabled=False, rules=(Rule(str(self.app), "app.png"),), fallback="fallback.png")
        self.assertIsNone(resolve(config, str(self.app)))

    def test_symlink_reports_use_the_physical_directory(self):
        link = self.root / "linked app"
        link.symlink_to(self.app, target_is_directory=True)
        self.assertEqual(normalize_directory(str(link / "child/../child")), str(self.child))
        self.assertEqual(resolve(Config(rules=(Rule(str(self.app), "app.png"),)), str(link / "child")), "app.png")

    def test_unicode_spaces_quotes_and_shell_metacharacters_are_literal(self):
        named = self.directory("café 猫/' quoted ; $(touch sentinel) [1] $USER")
        config = Config(rules=(Rule(str(named), "literal.png"),))
        self.assertEqual(resolve(config, str(named)), "literal.png")
        self.assertFalse((self.root / "sentinel").exists())

    def test_home_shortcut_expands_only_at_the_start(self):
        self.assertEqual(normalize_directory("~/"), str(Path.home().resolve()))
        literal = self.directory("~/literal-$HOME")
        self.assertEqual(normalize_directory(str(literal)), str(literal))

    def test_normalization_requires_an_existing_absolute_directory(self):
        file_path = self.root / "regular-file"
        file_path.write_text("fixture", encoding="utf-8")
        invalid = ("", "relative", "~another-user", "$HOME", "https://example.invalid/a", "bad\0path", None, 4, str(file_path))
        for value in invalid:
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                normalize_directory(value)

    def test_deleted_directory_uses_fallback(self):
        deleted = self.directory("app/deleted")
        deleted.rmdir()
        with self.assertRaises(ValueError):
            normalize_directory(str(deleted))
        self.assertEqual(resolve(Config(rules=(Rule(str(self.app), "app.png"),), fallback="fallback.png"), str(deleted)), "fallback.png")

    def test_missing_directory_before_parent_component_is_invalid(self):
        self.assertEqual(resolve(Config(fallback="fallback.png"), str(self.root / "missing/../app")), "fallback.png")

    def test_case_aliases_follow_actual_filesystem_identity(self):
        upper = self.directory("MixedCase")
        lower = self.root / "mixedcase"
        config = Config(rules=(Rule(str(upper), "upper.png"),))
        if lower.exists() and os.path.samefile(upper, lower):
            self.assertEqual(resolve(config, str(lower)), "upper.png")
        else:
            lower.mkdir()
            self.assertIsNone(resolve(config, str(lower)))

    def test_unicode_normalization_aliases_follow_filesystem_identity(self):
        composed = self.directory("café")
        decomposed = self.root / unicodedata.normalize("NFD", composed.name)
        config = Config(rules=(Rule(str(composed), "cafe.png"),))
        if decomposed.exists() and os.path.samefile(composed, decomposed):
            self.assertEqual(resolve(config, str(decomposed)), "cafe.png")
        else:
            decomposed.mkdir()
            self.assertIsNone(resolve(config, str(decomposed)))

    def test_seeded_adversarial_paths_match_component_ancestor_oracle(self):
        rng = random.Random(0xCA7)
        paths = [self.root]
        fragments = ["cat", "cats", "a b", "猫", "é", "'quote'", "$value", "[star]*", ";literal"]
        for index in range(100):
            parent = rng.choice(paths)
            path = parent / (rng.choice(fragments) + str(index))
            path.mkdir()
            paths.append(path)
        selected = rng.sample(paths, 45)
        rules = [Rule(str(path), f"image-{index}.png") for index, path in enumerate(selected)]
        queries = list(paths)
        for path in rng.sample(paths[1:], 25):
            sibling = path.with_name(path.name + "-sibling")
            sibling.mkdir()
            queries.append(sibling)
        for query in queries:
            ancestors = (query, *query.parents)
            matches = [rule for rule in rules if Path(rule.directory) in ancestors]
            expected = max(matches, key=lambda rule: len(Path(rule.directory).parts)).image if matches else "fallback.png"
            rng.shuffle(rules)
            self.assertEqual(resolve(Config(rules=tuple(rules), fallback="fallback.png"), str(query)), expected)


if __name__ == "__main__":
    unittest.main()
