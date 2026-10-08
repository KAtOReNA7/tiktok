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
                        "cover_3x4": {"title_lines": ["李逵：救哥哥", "砍百姓，屠夫", "也算好汉？"]},
                        "cover_4x3": {"title_lines": ["李逵：", "救哥哥砍百姓，", "屠夫也算好汉？"]}}}

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


if __name__ == "__main__":
    unittest.main()
