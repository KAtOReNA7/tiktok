"""Regression tests for scene-map CSV bytes, quoting and lossless exports."""
import codecs
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_mapping_csv import COLUMNS, export_mapping_csv, validate_mapping_bytes, validate_mapping_csv


class MappingCsvTests(unittest.TestCase):
    def setUp(self):
        self.content = codecs.BOM_UTF8 + "插图编号,对应口播\r\nS01,这是完整口播。\r\n".encode("utf-8")

    def test_valid_utf8_bom_and_crlf(self):
        self.assertEqual(validate_mapping_bytes(self.content), [COLUMNS, ["S01", "这是完整口播。"]])

    def test_missing_and_duplicate_bom(self):
        for content in (self.content[3:], codecs.BOM_UTF8 + self.content):
            with self.subTest(content=content[:6]), self.assertRaises(ValueError):
                validate_mapping_bytes(content)

    def test_invalid_utf8_is_not_replaced(self):
        with self.assertRaises(UnicodeDecodeError):
            validate_mapping_bytes(self.content.replace(b"S01", b"\xffS01"))

    def test_lf_record_separator_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_mapping_bytes(self.content.replace(b"\r\n", b"\n"))

    def test_duplicate_id_and_empty_narration_are_rejected(self):
        for tail in ("S01,另一句\r\n", "S02,\r\n"):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                validate_mapping_bytes(self.content + tail.encode("utf-8"))

    def test_bad_quotes_are_rejected(self):
        for row in ('S01,"未闭合\r\n', 'S01,未"转义\r\n', 'S01,"闭合后"多字\r\n'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate_mapping_bytes(codecs.BOM_UTF8 + ("插图编号,对应口播\r\n" + row).encode())

    def test_quoted_comma_quotes_multiline_and_idempotent_export(self):
        rows = [["S01", '他说："甲,乙"。\n下一行。'], ["S02", "保留\r\n原始换行与 空格。"]]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "素材映射.csv"
            self.assertTrue(export_mapping_csv(path, rows))
            before = path.read_bytes()
            self.assertEqual(validate_mapping_csv(path), [COLUMNS] + rows)
            self.assertFalse(export_mapping_csv(path, rows))
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(before.count(codecs.BOM_UTF8), 1)
            with self.assertRaises(FileExistsError):
                export_mapping_csv(path, [["S01", "不同的口播"]])
            self.assertEqual(before, path.read_bytes())

    def test_header_only_allowed_only_for_blank_template(self):
        content = codecs.BOM_UTF8 + "插图编号,对应口播\r\n".encode()
        self.assertEqual(validate_mapping_bytes(content, allow_header_only=True), [COLUMNS])
        with self.assertRaises(ValueError):
            validate_mapping_bytes(content)

    def test_cli_requires_actual_files(self):
        script = Path(__file__).with_name("validate_mapping_csv.py")
        for arguments in ([], [str(script.with_name("definitely_missing_scene_map.csv"))]):
            result = subprocess.run([sys.executable, str(script), *arguments], capture_output=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
