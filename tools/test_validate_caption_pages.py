"""Regression tests for lossless static-caption pagination."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from validate_caption_pages import validate_caption_pages
from validate_mapping_csv import export_mapping_csv


class CaptionPageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.plan = {
            "template_id": "RYP_STORY_MAIN_V3", "caption_mode": "STATIC_CAPTION_PAGES_V1",
            "episodes": [{"episode_id": "TEST_P01", "source_scene_count": 2,
                          "output_page_count": 3, "page_mapping_filename": "mapping.csv",
                          "source_rows": [
                              {"parent_scene_id": "TEST_P01_S01", "source_text": '原文，含"引号"。 保留空格。'},
                              {"parent_scene_id": "TEST_P01_S02", "source_text": "末句！"}],
                          "pages": []}]}
        for parent, index, count, text, lines in [
            ("TEST_P01_S01", 1, 2, '原文，含"引号"。', ['原文，含"引号"。']),
            ("TEST_P01_S01", 2, 2, " 保留空格。", [" 保留", "空格。"]),
            ("TEST_P01_S02", 1, 1, "末句！", ["末句！"]),
        ]:
            page_id = parent + "_%02d" % index
            self.plan["episodes"][0]["pages"].append({
                "parent_scene_id": parent, "page_id": page_id, "caption_text": text,
                "page_index_in_scene": index, "page_count_in_scene": count,
                "display_lines": lines, "output_filename": page_id + "_字幕页_v01.png",
                "render_status": "NOT_RENDERED", "start_s": None, "end_s": None})
        self.write(self.plan)

    def write(self, plan, write_csv=True):
        (self.root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        if write_csv:
            pages = plan["episodes"][0]["pages"]
            export_mapping_csv(self.root / "mapping.csv", [[p["page_id"], p["caption_text"]] for p in pages], overwrite=True)

    def test_valid_unrendered_plan_with_quotes_and_whitespace(self):
        self.assertEqual(validate_caption_pages(self.root / "plan.json"), (1, 3))

    def test_changed_punctuation_is_rejected_even_when_csv_matches(self):
        plan = copy.deepcopy(self.plan)
        page = plan["episodes"][0]["pages"][-1]
        page["caption_text"] = "末句。"
        page["display_lines"] = ["末句。"]
        self.write(plan)
        with self.assertRaisesRegex(ValueError, "change, omit, repeat"):
            validate_caption_pages(self.root / "plan.json")

    def test_parent_reordering_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        pages = plan["episodes"][0]["pages"]
        plan["episodes"][0]["pages"] = pages[2:] + pages[:2]
        self.write(plan)
        with self.assertRaisesRegex(ValueError, "parent scene order"):
            validate_caption_pages(self.root / "plan.json")

    def test_missing_single_page_suffix_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["episodes"][0]["pages"][-1]["page_id"] = "TEST_P01_S02"
        self.write(plan)
        with self.assertRaisesRegex(ValueError, "continuous from _01"):
            validate_caption_pages(self.root / "plan.json")

    def test_actual_csv_disagreement_is_rejected(self):
        export_mapping_csv(self.root / "mapping.csv", [["TEST_P01_S01_01", "不同的正文"]], overwrite=True)
        with self.assertRaisesRegex(ValueError, "Actual delivered CSV differs"):
            validate_caption_pages(self.root / "plan.json")

    def test_missing_actual_csv_is_rejected(self):
        (self.root / "mapping.csv").unlink()
        with self.assertRaisesRegex(ValueError, "does not exist"):
            validate_caption_pages(self.root / "plan.json")


if __name__ == "__main__":
    unittest.main()
