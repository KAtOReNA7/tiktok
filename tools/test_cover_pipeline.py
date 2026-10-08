"""Meaningful regression checks for fixed cover filling and actual-output review.

Run: python -m unittest discover -s tools -p 'test_cover_pipeline.py'
Tests use the real versioned masters/font and a temporary synthetic art image.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from render_cover import ROOT, render_covers
from validate_cover import validate_cover_spec, validate_render_record


class FixedCoverPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "spec/cover_delivery.json").read_text(encoding="utf-8"))
        validate_cover_spec(cls.spec, ROOT)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        Image.new("RGBA", (400, 200), (220, 40, 50, 255)).save(self.root / "art.png")
        self.job = {"topic_id": "TEST", "part_number": 1, "revision": 1,
                    "title": "李逵：救哥哥砍百姓，屠夫也算好汉？", "art_path": "art.png",
                    "variants": {
                        "cover_3x4": {"title_lines": ["李逵：救哥哥", "砍百姓，屠夫", "也算好汉？"],
                                      "highlight_line_indices": [1]},
                        "cover_4x3": {"title_lines": ["李逵：救哥哥砍百姓，", "屠夫也算好汉？"],
                                      "highlight_line_indices": [1]}}}

    def tearDown(self):
        self.directory.cleanup()

    def write_job(self):
        path = self.root / "cover_job.json"
        path.write_text(json.dumps(self.job, ensure_ascii=False), encoding="utf-8")
        return path

    def test_real_masters_render_both_ratios_repeatably_without_art_crop(self):
        path = self.write_job()
        record_path, first = render_covers(path, self.root / "first")
        self.assertTrue(validate_render_record(record_path)["actual_cover_pair_checked"])
        _, repeated = render_covers(path, self.root / "second")
        for name, item in first["covers"].items():
            self.assertEqual(item["sha256"], repeated["covers"][name]["sha256"])
            self.assertEqual(item["art"]["fit"], "contain")
            self.assertEqual(item["art"]["resized_canvas"][0] / item["art"]["resized_canvas"][1], 2)
            self.assertFalse(item["art"]["crop_reviewed"])
            x, y, width, height = self.spec["variants"][name]["layout"]["story_bounds"]
            with Image.open(item["path"]) as image:
                self.assertEqual(image.getpixel((x + width // 2, y + 2)), (22, 22, 22, 255))

    def test_locked_title_overflow_stops_before_either_png(self):
        self.job["title"] = "李" * 100
        for value in self.job["variants"].values():
            value["title_lines"] = [self.job["title"]]
            value["highlight_line_indices"] = [0]
        output = self.root / "overflow"
        with self.assertRaisesRegex(ValueError, "overflows"):
            render_covers(self.write_job(), output)
        self.assertEqual(list(output.glob("*.png")), [])

    def test_art_stretch_and_unreviewed_crop_are_rejected(self):
        for mode, message in (("stretch", "stretching"), ("cover", "requires an internal")):
            with self.subTest(mode=mode):
                self.job["variants"]["cover_3x4"]["art_fit"] = mode
                output = self.root / mode
                with self.assertRaisesRegex(ValueError, message):
                    render_covers(self.write_job(), output)
                self.assertEqual(list(output.glob("*.png")), [])

    def test_different_font_bytes_cannot_pass_as_the_fixed_font(self):
        bad = copy.deepcopy(self.spec)
        item = next(entry for entry in bad["assets"]["asset_inventory"]
                    if entry["file"] == bad["typography"]["font_file"])
        item["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "differs from approved"):
            validate_cover_spec(bad, ROOT)

    def test_host_pixels_cannot_enter_story_or_move_outside_their_slots(self):
        bad = copy.deepcopy(self.spec)
        host_slot = bad["variants"]["cover_3x4"]["layout"]["host_slots"]["doro"]
        host_slot["bounds"] = [180, 464, 168, 168]
        with self.assertRaisesRegex(ValueError, "changed without a new design revision|No visible actor pixels|outside"):
            validate_cover_spec(bad, ROOT)

    def test_actual_chrome_drift_is_rejected_even_with_updated_png_hash(self):
        record_path, record = render_covers(self.write_job(), self.root / "drift")
        entry = record["covers"]["cover_4x3"]
        image_path = Path(entry["path"])
        with Image.open(image_path) as image:
            changed = image.convert("RGBA")
        changed.putpixel((24, 24), (3, 250, 41, 255))
        changed.save(image_path)
        entry["sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "drifted outside"):
            validate_render_record(record_path)

    def test_source_title_or_art_change_requires_real_rerender(self):
        record_path, _ = render_covers(self.write_job(), self.root / "source_changes")
        self.job["title"] = "另一个批准标题"
        self.write_job()
        with self.assertRaisesRegex(ValueError, "local cover job changed"):
            validate_render_record(record_path)
        self.job["title"] = "李逵：救哥哥砍百姓，屠夫也算好汉？"
        self.write_job()
        Image.new("RGBA", (400, 200), (1, 2, 3, 255)).save(self.root / "art.png")
        with self.assertRaisesRegex(ValueError, "local cover art changed"):
            validate_render_record(record_path)

    def test_illegal_or_missing_highlight_selection_stops_before_either_png(self):
        for index, value in enumerate((None, [], [0, 0], [-1], [3], [0, 1, 2], [True], ["0"])):
            with self.subTest(selection=value):
                self.job["variants"]["cover_3x4"]["highlight_line_indices"] = value
                output = self.root / ("invalid_highlight_%d" % index)
                with self.assertRaisesRegex(ValueError, "distinct 0-based"):
                    render_covers(self.write_job(), output)
                self.assertEqual(list(output.glob("*.png")), [])

    def test_explicit_highlights_are_drawn_and_cannot_drift_from_job(self):
        self.job["variants"]["cover_3x4"]["highlight_line_indices"] = [0, 1]
        record_path, record = render_covers(self.write_job(), self.root / "highlight")
        entry = record["covers"]["cover_3x4"]
        title = self.spec["variants"]["cover_3x4"]["layout"]["title"]
        x, y, width, _ = title["bounds"]
        with Image.open(entry["path"]) as actual, Image.open(ROOT / self.spec["variants"]["cover_3x4"]["base_plate"]) as base:
            for index in (0, 1):
                self.assertEqual(actual.getpixel((x + 2, y + (index + 1) * title["line_height_px"] - 1)),
                                 (242, 250, 0, 255))
                self.assertEqual(actual.getpixel((x + width - 2, y + (index + 1) * title["line_height_px"] - 1)),
                                 (242, 250, 0, 255))
                band = actual.crop((x, y + index * title["line_height_px"],
                                    x + width, y + (index + 1) * title["line_height_px"]))
                colors = {color for _, color in band.getcolors(width * title["line_height_px"])}
                self.assertIn((22, 22, 22, 255), colors)
                self.assertNotIn((255, 255, 255, 255), colors)
            point = (x + 2, y + 3 * title["line_height_px"] - 1)
            self.assertEqual(actual.getpixel(point), base.convert("RGBA").getpixel(point))
            band = actual.crop((x, y + 2 * title["line_height_px"], x + width, y + 3 * title["line_height_px"]))
            self.assertIn((255, 255, 255, 255),
                          {color for _, color in band.getcolors(width * title["line_height_px"])})
        entry["highlight_line_indices"] = [2]
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "highlight lines differ"):
            validate_render_record(record_path)

    def test_per_ratio_art_override_is_recorded_and_cross_ratio_source_tampering_fails(self):
        alternate = self.root / "art_wide.png"
        Image.new("RGBA", (800, 400), (20, 80, 230, 255)).save(alternate)
        self.job["variants"]["cover_4x3"]["art_path"] = "art_wide.png"
        record_path, record = render_covers(self.write_job(), self.root / "different_sources")
        first = record["covers"]["cover_3x4"]["art"]
        wide = record["covers"]["cover_4x3"]["art"]
        self.assertEqual(Path(first["source_path"]), self.root / "art.png")
        self.assertEqual(Path(wide["source_path"]), alternate)
        self.assertNotEqual(first["source_sha256"], wide["source_sha256"])
        self.assertTrue(validate_render_record(record_path)["actual_cover_pair_checked"])
        first["source_path"], first["source_sha256"] = wide["source_path"], wide["source_sha256"]
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "per-ratio art source differs"):
            validate_render_record(record_path)

    def test_short_title_uses_centered_stack_and_record_cannot_claim_another_baseline(self):
        self.job["title"] = "李逵？"
        for value in self.job["variants"].values():
            value["title_lines"] = [self.job["title"]]
            value["highlight_line_indices"] = [0]
        record_path, record = render_covers(self.write_job(), self.root / "centered_title")
        for name, entry in record["covers"].items():
            title = self.spec["variants"][name]["layout"]["title"]
            x, y, width, height = title["bounds"]
            line_top = y + (height - title["line_height_px"]) // 2
            self.assertEqual(entry["title_lines"][0]["line_bounds"],
                             [x, line_top, width, title["line_height_px"]])
        record["covers"]["cover_4x3"]["title_lines"][0]["baseline_y"] += 1
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "vertically centered"):
            validate_render_record(record_path)


if __name__ == "__main__":
    unittest.main()
