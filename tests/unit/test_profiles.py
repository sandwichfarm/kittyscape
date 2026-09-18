import tempfile
import unittest
from pathlib import Path

from kittyscape.config import ConfigError
from kittyscape.profiles import read_process_overlay


class ProcessProfileTests(unittest.TestCase):
    def test_allowlist_and_forbidden_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "talk.conf"
            path.write_text("font_size 15\nwindow_padding_width 9\n")
            self.assertEqual(read_process_overlay(str(path)), ("font_size 15", "window_padding_width 9"))
            path.write_text("include unsafe.conf\n")
            with self.assertRaises(ConfigError):
                read_process_overlay(str(path))
            for line in ("foreground #abcdef\n", "enabled_layouts tall\n", "background_opacity 0.8\n"):
                path.write_text(line)
                with self.subTest(line=line), self.assertRaises(ConfigError):
                    read_process_overlay(str(path))

    def test_rejects_missing_values_size_overflow_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            path = root / "profile.conf"
            path.write_text("font_size\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                read_process_overlay(str(path), root)
            path.write_bytes(b"#" + b"x" * (1024 * 1024))
            with self.assertRaises(ConfigError):
                read_process_overlay(str(path), root)
            target = Path(outside) / "outside.conf"
            target.write_text("font_size 17\n", encoding="utf-8")
            path.unlink()
            path.symlink_to(target)
            with self.assertRaises(ConfigError):
                read_process_overlay(str(path), root)


if __name__ == "__main__":
    unittest.main()
