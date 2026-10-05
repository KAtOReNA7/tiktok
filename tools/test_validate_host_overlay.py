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

    def distributed_slots(self):
        return {"doro": {"bounds": [3, 0, 1, 1], "spatial_zone": "upper_right"},
                "gugu": {"bounds": [0, 3, 1, 1], "spatial_zone": "lower_left"},
                "mambo": {"bounds": [2, 5, 1, 1], "spatial_zone": "bottom_center"}}

    def test_actual_alpha_occupies_three_distributed_regions(self):
        alpha = [0] * 24
        for index in (3, 12, 22):
            alpha[index] = 255
        write_png(self.path, alpha, 4)
        result = validate_host_overlay(self.path, [1, 1, 2, 1], (4, 6), self.distributed_slots())
        self.assertTrue(result["distribution_checked"])
        self.assertEqual(result["distribution"]["pixels_outside_regions"], 0)

    def test_same_row_rejected_even_without_story_overlap(self):
        alpha = [0] * 24
        for index in (12, 13, 15):
            alpha[index] = 255
        write_png(self.path, alpha)
        slots = self.distributed_slots()
        for (name, slot), x in zip(slots.items(), (0, 1, 3)):
            slot["bounds"] = [x, 3, 1, 1]
        with self.assertRaisesRegex(ValueError, "different heights"):
            validate_host_overlay(self.path, [1, 1, 2, 1], (4, 6), slots)

    def test_pixels_outside_approved_regions_rejected(self):
        alpha = [0] * 24
        for index in (3, 12, 22, 19):
            alpha[index] = 255
        write_png(self.path, alpha)
        with self.assertRaisesRegex(ValueError, "outside the three approved"):
            validate_host_overlay(self.path, [1, 1, 2, 1], (4, 6), self.distributed_slots())

    def test_missing_actor_region_rejected(self):
        alpha = [0] * 24
        for index in (3, 12):
            alpha[index] = 255
        write_png(self.path, alpha)
        with self.assertRaisesRegex(ValueError, "No visible actor pixels"):
            validate_host_overlay(self.path, [1, 1, 2, 1], (4, 6), self.distributed_slots())

    def test_transparent_frame_may_extend_beyond_canvas(self):
        alpha = [0] * 24
        for index in (3, 12, 22):
            alpha[index] = 255
        write_png(self.path, alpha)
        slots = self.distributed_slots()
        slots["doro"]["bounds"] = [2, -1, 2, 2]
        result = validate_host_overlay(self.path, [1, 1, 2, 1], (4, 6), slots)
        self.assertEqual(result["distribution"]["pixels_outside_regions"], 0)

    def test_protected_text_intersection_rejected(self):
        alpha = [0] * 24
        for index in (3, 12, 22):
            alpha[index] = 255
        write_png(self.path, alpha)
        with self.assertRaisesRegex(ValueError, "protected text region"):
            validate_host_overlay(self.path, [1, 1, 2, 1], (4, 6), self.distributed_slots(),
                                  {"caption": [3, 0, 1, 1]})


if __name__ == "__main__":
    unittest.main()
