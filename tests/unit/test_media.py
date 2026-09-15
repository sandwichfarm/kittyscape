"""Media normalization preserves PNG uploads while accepting JPEG and GIF sources."""

from __future__ import annotations

import shutil
import struct
import sys
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from kittyscape.images import ImageError
from kittyscape.media import load_media, source_format


MAGICK = shutil.which("magick")


def rgb_png():
    header = struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    def chunk(kind, body):
        return struct.pack("!I", len(body)) + kind + body + struct.pack("!I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")) + chunk(b"IEND", b"")


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kittyscape-media-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def create(self, name, *arguments):
        path = self.root / name
        subprocess.run([MAGICK, *arguments, str(path)], check=True, capture_output=True)
        return path

    def test_magic_bytes_determine_supported_source_format(self):
        self.assertEqual(source_format(rgb_png()), "png")
        self.assertEqual(source_format(b"\xff\xd8\xff\xe0"), "jpeg")
        self.assertEqual(source_format(b"GIF89a"), "gif")
        with self.assertRaisesRegex(ImageError, "unsupported-image-format"):
            source_format(b"not an image")

    def test_validate_false_bypasses_the_semantic_png_validator(self):
        path = self.root / "bad-crc.png"
        data = bytearray(rgb_png())
        data[29] ^= 1
        path.write_bytes(data)
        with patch("kittyscape.media.validate_png") as semantic:
            media = load_media(str(path), validate_bytes=False)
        semantic.assert_not_called()
        self.assertEqual(media.frames[0].image.width, 1)
        with self.assertRaises(ImageError):
            load_media(str(path), validate_bytes=True)

    def test_linux_worker_sets_limits_before_exec(self):
        worker = Path(__file__).parents[2] / "kittyscape/media_worker.py"
        program = (
            "import json, resource; print(json.dumps([resource.getrlimit(resource.RLIMIT_AS), "
            "resource.getrlimit(resource.RLIMIT_CPU), resource.getrlimit(resource.RLIMIT_FSIZE)]))"
        )
        result = subprocess.run([sys.executable, str(worker), sys.executable, "-c", program], check=True,
                                capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "[[536870912, 536870912], [5, 5], [67108864, 67108864]]")

    @unittest.skipUnless(MAGICK, "ImageMagick is unavailable")
    def test_jpeg_and_static_gif_normalize_to_png_upload_frames(self):
        jpeg = self.create("input.jpg", "-size", "3x2", "xc:red")
        gif = self.create("input.gif", "-size", "3x2", "xc:blue")
        for source, kind in ((jpeg, "jpeg"), (gif, "gif")):
            with self.subTest(source=kind):
                media = load_media(str(source))
                self.assertEqual(media.source_format, kind)
                self.assertEqual(len(media.frames), 1)
                self.assertTrue(media.frames[0].image.data.startswith(b"\x89PNG\r\n\x1a\n"))

    @unittest.skipUnless(MAGICK, "ImageMagick is unavailable")
    def test_animated_gif_retains_multiple_normalized_frames(self):
        path = self.root / "animated.gif"
        subprocess.run([MAGICK, "-size", "2x2", "xc:red", "-delay", "7", "-size", "2x2", "xc:green",
                        "-delay", "13", "-loop", "0", str(path)], check=True, capture_output=True)
        media = load_media(str(path))
        self.assertEqual(media.source_format, "gif")
        self.assertGreaterEqual(len(media.frames), 2)
        self.assertIsNone(media.loop)
        self.assertEqual([frame.duration_ms for frame in media.frames[:2]], [10, 70])
