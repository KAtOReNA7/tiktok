"""V3 paper/ink/highlight regression checks against the real fixed assets."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from render_cover import ROOT, render_covers
from validate_cover import validate_cover_spec, validate_render_record


class V3PaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / 'spec/cover_delivery.json').read_text(encoding='utf-8'))

    def test_spec_cannot_revert_to_black_or_white_title(self):
        for mutation in ('paper', 'title', 'letterbox'):
            bad = copy.deepcopy(self.spec)
            if mutation == 'paper':
                bad['palette']['paper'] = '#161616'
            elif mutation == 'title':
                bad['variants']['cover_3x4']['layout']['title']['fill'] = '#FFFFFF'
            else:
                bad['composition']['art_letterbox_fill'] = '#161616'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_cover_spec(bad, ROOT)

    def test_approved_title_pixels_are_verified_after_png_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new('RGBA', (1112, 712), (120, 80, 210, 255)).save(root / 'art.png')
            job = {'topic_id': 'V3TEST', 'title': '主角：安排周到', 'art_path': 'art.png',
                   'variants': {'cover_3x4': {'title_lines': ['主角：', '安排周到'], 'highlight_line_indices': [1]},
                                'cover_4x3': {'title_lines': ['主角：', '安排周到'], 'highlight_line_indices': [1]}}}
            job_path = root / 'cover_job.json'
            job_path.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
            record_path, record = render_covers(job_path, root / 'delivery')
            self.assertTrue(validate_render_record(record_path)['actual_cover_pair_checked'])
            entry = record['covers']['cover_3x4']
            x, y, width, height = self.spec['variants']['cover_3x4']['layout']['title']['bounds']
            image_path = Path(entry['path'])
            with Image.open(image_path) as image:
                changed = image.convert('RGBA')
            changed.putpixel((x + 1, y + 1), (22, 22, 22, 255))
            changed.save(image_path)
            entry['sha256'] = hashlib.sha256(image_path.read_bytes()).hexdigest()
            record_path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'title pixels differ'):
                validate_render_record(record_path)


if __name__ == '__main__':
    unittest.main()
