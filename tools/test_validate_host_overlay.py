"""Regression checks for real PNG alpha, including antialiased edge pixels."""
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from validate_host_overlay import read_rgba_alpha, validate_host_overlay


def write_png(path, alpha, row_filter=0):
    width, height = 4, len(alpha) // 4
    rows, previous = bytearray(), bytes(width * 4)
    for y in range(height):
        row = bytes(value for a in alpha[y * width:(y + 1) * width] for value in (47, 128, 230, a))
        filtered = bytearray()
        for x, value in enumerate(row):
            a, b, c = row[x - 4] if x >= 4 else 0, previous[x], previous[x - 4] if x >= 4 else 0
            if row_filter == 0:
                predict = 0
            elif row_filter == 1:
                predict = a
            elif row_filter == 2:
                predict = b
            elif row_filter == 3:
                predict = (a + b) // 2
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predict = a if pa <= pb and pa <= pc else b if pb <= pc else c
            filtered.append((value - predict) & 255)
        rows.append(row_filter)
        rows.extend(filtered)
        previous = row
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content) & 0xffffffff)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class HostOverlayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "overlay.png"

    def test_each_png_filter_recovers_actual_alpha(self):
        expected = [0, 1, 128, 255, 19, 200, 0, 255, 2, 1, 254, 0]
        for filtering in range(5):
            with self.subTest(filter=filtering):
                write_png(self.path, expected, filtering)
                self.assertEqual(read_rgba_alpha(self.path, (4, 3)), (4, 3, bytes(expected)))

    def test_clear_story_accepts_actor_pixels_outside_it(self):
        write_png(self.path, [255, 0, 0, 0, 0, 0, 0, 0])
        result = validate_host_overlay(self.path, [1, 0, 3, 2], (4, 2))
        self.assertEqual(result["story_intersection_pixels"], 0)
        self.assertEqual(result["visible_actor_pixels"], 1)

    def test_one_alpha_edge_pixel_inside_story_fails(self):
        write_png(self.path, [255, 1, 0, 0, 0, 0, 0, 0], 4)
        with self.assertRaisesRegex(ValueError, "1 pixels have alpha > 0"):
            validate_host_overlay(self.path, [1, 0, 3, 2], (4, 2))

    def test_empty_actor_layer_does_not_count_as_pass(self):
        write_png(self.path, [0] * 8)
        with self.assertRaisesRegex(ValueError, "fully transparent"):
            validate_host_overlay(self.path, [1, 0, 3, 2], (4, 2))

    def test_invalid_story_bounds_fail(self):
        write_png(self.path, [255] + [0] * 7)
        with self.assertRaisesRegex(ValueError, "inside the PNG"):
            validate_host_overlay(self.path, [1, 0, 4, 2], (4, 2))


if __name__ == "__main__":
    unittest.main()
