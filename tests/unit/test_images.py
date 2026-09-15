"""PNG fixtures exercise decoded content as well as the outer chunk container."""

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from kittyscape.images import ImageError, load_image, validate_png

SIGNATURE = b"\x89PNG\r\n\x1a\n"
HEADER = struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0)


def chunk(kind, body):
    return struct.pack("!I", len(body)) + kind + body + struct.pack("!I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def png(*chunks):
    return SIGNATURE + b"".join(chunks)


def rgb_png(pixel=b"\xff\x00\x00"):
    return png(chunk(b"IHDR", HEADER), chunk(b"IDAT", zlib.compress(b"\0" + pixel)), chunk(b"IEND", b""))


class ImageTests(unittest.TestCase):
    def assert_invalid(self, data):
        with self.assertRaises(ImageError):
            validate_png(data)

    def test_valid_rgb_and_consecutive_idat_chunks(self):
        encoded = zlib.compress(b"\0\xff\0\0")
        data = png(chunk(b"IHDR", HEADER), chunk(b"IDAT", encoded[:5]), chunk(b"IDAT", encoded[5:]), chunk(b"IEND", b""))
        self.assertEqual((validate_png(data).width, validate_png(data).height), (1, 1))
        self.assertEqual(validate_png(rgb_png()).data, rgb_png())

    def test_bad_chunk_checksum_is_rejected(self):
        data = bytearray(rgb_png())
        data[29] ^= 1
        self.assert_invalid(bytes(data))

    def test_invalid_deflate_data_with_valid_chunk_crc_is_rejected(self):
        self.assert_invalid(png(chunk(b"IHDR", HEADER), chunk(b"IDAT", b"not a zlib stream"), chunk(b"IEND", b"")))

    def test_decoded_scanline_length_and_filter_are_validated(self):
        for raw in (b"", b"\0\xff", b"\x05\xff\0\0", b"\0\xff\0\0extra"):
            with self.subTest(raw=raw):
                self.assert_invalid(png(chunk(b"IHDR", HEADER), chunk(b"IDAT", zlib.compress(raw)), chunk(b"IEND", b"")))

    def test_idat_decompression_is_bounded_by_declared_dimensions(self):
        compressed = zlib.compress(b"\0" * 1_000_000)
        self.assert_invalid(png(chunk(b"IHDR", HEADER), chunk(b"IDAT", compressed), chunk(b"IEND", b"")))

    def test_ihdr_encoding_fields_are_validated(self):
        headers = (
            struct.pack("!IIBBBBB", 1, 1, 8, 99, 0, 0, 0),
            struct.pack("!IIBBBBB", 1, 1, 1, 2, 0, 0, 0),
            struct.pack("!IIBBBBB", 1, 1, 8, 2, 1, 0, 0),
            struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 1, 0),
            struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 2),
        )
        for header in headers:
            with self.subTest(header=header):
                self.assert_invalid(png(chunk(b"IHDR", header), chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")), chunk(b"IEND", b"")))

    def test_duplicate_headers_and_terminal_chunks_are_rejected(self):
        parts = (chunk(b"IHDR", HEADER), chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")), chunk(b"IEND", b""))
        self.assert_invalid(png(parts[0], *parts))
        self.assert_invalid(png(*parts, parts[-1]))

    def test_iend_has_no_payload(self):
        self.assert_invalid(png(chunk(b"IHDR", HEADER), chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")), chunk(b"IEND", b"extra")))

    def test_unknown_critical_chunk_is_rejected(self):
        self.assert_invalid(
            png(chunk(b"IHDR", HEADER), chunk(b"ABCD", b""), chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")), chunk(b"IEND", b""))
        )

    def test_idat_chunks_must_be_consecutive(self):
        encoded = zlib.compress(b"\0\xff\0\0")
        self.assert_invalid(png(
            chunk(b"IHDR", HEADER), chunk(b"IDAT", encoded[:5]), chunk(b"tEXt", b"Comment\0fixture"),
            chunk(b"IDAT", encoded[5:]), chunk(b"IEND", b""),
        ))

    def test_animation_is_rejected(self):
        self.assert_invalid(png(
            chunk(b"IHDR", HEADER), chunk(b"acTL", struct.pack("!II", 1, 0)),
            chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")), chunk(b"IEND", b""),
        ))

    def test_local_file_errors_omit_image_path(self):
        with tempfile.TemporaryDirectory(prefix="kittyscape-images-") as directory:
            path = Path(directory) / "private-image.png"
            with self.assertRaises(ImageError) as raised:
                load_image(str(path))
            self.assertNotIn(str(path), str(raised.exception))
            path.write_bytes(rgb_png())
            self.assertEqual(load_image(str(path)).data, rgb_png())


if __name__ == "__main__":
    unittest.main()
