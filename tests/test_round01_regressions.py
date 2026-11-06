"""Synthetic, content-free reproducers for round 01 contract failures."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from qa_core.document_parsing.document_router import DocumentParser
from qa_core.document_parsing.document_router import has_grid


class Round01Regressions(unittest.TestCase):
    def test_R01_002_grid_detection_supports_unicode_path(self):
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / '\u4e2d\u6587'
            folder.mkdir()
            path = folder / 'grid.png'
            image = Image.new('RGB', (600,600), 'white')
            draw = ImageDraw.Draw(image)
            for offset in range(30, 590, 50):
                draw.line((30,offset,580,offset), fill='black', width=2)
                draw.line((offset,30,offset,580), fill='black', width=2)
            image.save(path)
            import cv2
            import numpy as np
            decoded = cv2.imdecode(np.frombuffer(path.read_bytes(),dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
            with patch('cv2.imread',return_value=decoded):
                self.assertTrue(has_grid(path), 'control: grid algorithm must detect fixture')
            self.assertTrue(has_grid(path))

    def test_R01_001_empty_text_must_not_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'empty.txt'
            path.write_text('', encoding='utf-8')
            with DocumentParser() as parser:
                result = parser.parse(path)
            self.assertNotEqual(result.parsing_status, 'success')

    def test_R01_001_whitespace_text_must_not_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'blank.txt'
            path.write_text(' \n\t', encoding='utf-8')
            with DocumentParser() as parser:
                result = parser.parse(path)
            self.assertNotEqual(result.parsing_status, 'success')
